"""The Quantum Box container - a lazily awaited async container."""

from __future__ import annotations

import asyncio
import contextlib
import ctypes
import math
import operator
import platform
import sys
import threading
from collections.abc import MutableMapping, MutableSequence, MutableSet, Set
from numbers import Complex, Integral, Real
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Literal,
    TypeVar,
    cast,
    overload,
)

from qbox._loop import submit_to_loop

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine, Generator, Iterator
    from concurrent.futures import Future
    from types import FrameType

T = TypeVar("T")
U = TypeVar("U")

# Start mode type alias
StartMode = Literal["soon", "observed"]

# Map builtin types to their ABCs for isinstance compatibility
_TYPE_TO_ABC: dict[type[Any], type[Any]] = {
    dict: MutableMapping,
    list: MutableSequence,
    set: MutableSet,
    frozenset: Set,
    int: Integral,
    float: Real,
    complex: Complex,
}

# Cache for typed QBox classes (with lock for thread safety)
_typed_qbox_cache: dict[type[Any], type[Any]] = {}
_typed_qbox_cache_lock = threading.Lock()

# Scope type alias
ScopeType = Literal["locals", "stack", "globals"]

# Frame locals sync implementation selection (curried at module load)
#
# Cross-platform helper that handles the differences between Python implementations:
# - Python 3.13+: Uses FrameLocalsProxy (PEP 667) - writes persist automatically
# - PyPy: Uses __pypy__.locals_to_fast(frame)
# - CPython < 3.13: Uses ctypes.pythonapi.PyFrame_LocalsToFast
# - Other: No-op (best effort, modifications may not persist)


def _sync_frame_locals_noop(frame: FrameType) -> None:
    """No-op sync for Python 3.13+ or unsupported implementations."""


def _sync_frame_locals_cpython(frame: FrameType) -> None:  # pragma: no cover
    """CPython < 3.13 sync using PyFrame_LocalsToFast."""
    with contextlib.suppress(AttributeError, OSError):
        ctypes.pythonapi.PyFrame_LocalsToFast(
            ctypes.py_object(frame),
            ctypes.c_int(0),
        )


# Select the appropriate sync implementation at import time
if sys.version_info >= (3, 13):
    # Python 3.13+ uses FrameLocalsProxy - writes persist automatically
    _sync_frame_locals = _sync_frame_locals_noop
elif platform.python_implementation() == "PyPy":  # pragma: no cover
    # PyPy has its own locals_to_fast in the __pypy__ module
    try:
        import __pypy__  # type: ignore[import-not-found]

        def _sync_frame_locals_pypy(frame: FrameType) -> None:
            """PyPy sync using __pypy__.locals_to_fast."""
            __pypy__.locals_to_fast(frame)

        _sync_frame_locals = _sync_frame_locals_pypy
    except (ImportError, AttributeError):
        _sync_frame_locals = _sync_frame_locals_noop
elif platform.python_implementation() == "CPython":  # pragma: no cover
    _sync_frame_locals = _sync_frame_locals_cpython
else:  # pragma: no cover
    # Other implementations: best effort, modifications may not persist
    _sync_frame_locals = _sync_frame_locals_noop


def _get_typed_qbox_class(mimic_type: type[Any]) -> type[Any]:
    """Get or create a QBox subclass registered with the mimic type's ABC.

    This allows isinstance(box, SomeABC) to return True without forcing
    evaluation when the QBox was created with mimic_type.

    This function is thread-safe via double-checked locking.

    Args:
        mimic_type: The type that the QBox mimics for isinstance checks.

    Returns:
        A QBox subclass registered as a virtual subclass of the appropriate ABC.
    """
    # Fast path: check without lock (safe because dict reads are atomic in CPython)
    if mimic_type in _typed_qbox_cache:
        return _typed_qbox_cache[mimic_type]

    # Slow path: acquire lock and double-check
    with _typed_qbox_cache_lock:
        # Re-check after acquiring lock (another thread may have created it)
        if mimic_type in _typed_qbox_cache:  # pragma: no cover (race condition)
            return _typed_qbox_cache[mimic_type]

        # Find ABC for this type (builtins map to ABCs, others use the type itself)
        abc_type = _TYPE_TO_ABC.get(mimic_type, mimic_type)

        # Create a subclass with the declared type
        class TypedQBox(QBox):
            """QBox subclass registered with a specific ABC for isinstance support."""

            _declared_mimic_type: type[Any] = mimic_type

        TypedQBox.__name__ = f"QBox[{mimic_type.__name__}]"
        TypedQBox.__qualname__ = f"QBox[{mimic_type.__name__}]"

        # Register as virtual subclass if ABC supports it
        if hasattr(abc_type, "register"):
            with contextlib.suppress(TypeError):
                # Not all types support registration (e.g., concrete classes)
                abc_type.register(TypedQBox)

        _typed_qbox_cache[mimic_type] = TypedQBox
        return TypedQBox


class QBox(Generic[T]):
    """A lazily awaited container for async operations.

    QBox wraps a coroutine or awaitable and defers its evaluation until
    the value is actually needed. Operations on a QBox return new QBox
    instances, allowing lazy composition of async operations.

    The value is computed on a background thread running an asyncio event
    loop. When the value is needed (e.g., for comparison, str conversion,
    or explicit access via __wrapped__), the QBox blocks until the result
    is available.

    Args:
        awaitable: A coroutine or awaitable to wrap.

    Example::

        async def fetch_value() -> int:
            return 42

        box = QBox(fetch_value())
        result = box + 8  # Returns QBox, no blocking
        if result > 40:   # Blocks here, evaluates to 50
            print("Large!")
    """

    __slots__ = (
        "__weakref__",  # Allow weak references to QBox instances
        "_qbox_cached_value",
        "_qbox_cancel_on_delete",
        "_qbox_exception",
        "_qbox_factory",
        "_qbox_future",
        "_qbox_is_cached",
        "_qbox_lock",
        "_qbox_mimic_type",
        "_qbox_parent_boxes",
        "_qbox_repr_observes",
        "_qbox_scope",
        "_qbox_start_mode",
    )

    def __new__(
        cls,
        awaitable: Awaitable[T],
        mimic_type: type[T] | None = None,
        scope: ScopeType = "stack",
        start: StartMode = "soon",
        repr_observes: bool = False,
        cancel_on_delete: bool = True,
    ) -> QBox[T]:
        """Create a new QBox instance.

        If mimic_type is provided, returns an instance of a typed QBox
        subclass that is registered with the appropriate ABC for isinstance
        support.

        Args:
            awaitable: The coroutine or awaitable to wrap (used by __init__).
            mimic_type: Optional type hint for ABC registration.
            scope: Scope for reference replacement (used by __init__).
            start: When to start execution ('soon' or 'observed').
            repr_observes: Whether repr() triggers observation.
            cancel_on_delete: Whether to cancel pending work on deletion.

        Returns:
            A QBox instance (possibly of a typed subclass).
        """
        # Silence unused warnings - used by __init__
        del awaitable, scope, start, repr_observes, cancel_on_delete
        if mimic_type is not None and cls is QBox:
            typed_cls = _get_typed_qbox_class(mimic_type)
            instance = object.__new__(typed_cls)
        else:
            instance = object.__new__(cls)
        return cast("QBox[T]", instance)

    def __init__(
        self,
        awaitable: Awaitable[T],
        mimic_type: type[T] | None = None,
        scope: ScopeType = "stack",
        start: StartMode = "soon",
        repr_observes: bool = False,
        cancel_on_delete: bool = True,
    ) -> None:
        """Initialize a QBox with an awaitable.

        Args:
            awaitable: The coroutine or awaitable to wrap.
            mimic_type: Optional type hint for the wrapped value. If provided
                and the type is an ABC or has a register method, the QBox will
                be registered as a virtual subclass for isinstance checks.
            scope: How aggressively to replace references when observed.
                - 'locals': Replace only in immediate caller's locals
                - 'stack': Replace in all frames on the call stack (default)
                - 'globals': Stack + module globals of calling module
            start: When to start execution.
                - 'soon' (default): Submit coroutine immediately on creation
                - 'observed': Wait until observation to submit
            repr_observes: Whether repr() triggers observation.
                - False (default): repr() returns '<QBox[pending]>' without observing
                - True: repr() triggers observation and shows actual value
            cancel_on_delete: Whether to cancel pending work when QBox is deleted.
                - True (default): Cancel the future if not yet complete
                - False: Let the coroutine run to completion even if QBox is deleted
        """
        self._init_slots(
            factory=awaitable,
            mimic_type=mimic_type,
            scope=scope,
            parent_boxes=[],
            start=start,
            repr_observes=repr_observes,
            cancel_on_delete=cancel_on_delete,
        )

    def _init_slots(
        self,
        factory: Awaitable[Any] | Callable[[], Awaitable[Any]],
        scope: ScopeType,
        parent_boxes: list[QBox[Any]],
        start: StartMode,
        repr_observes: bool,
        cancel_on_delete: bool,
        mimic_type: type[Any] | None = None,
    ) -> None:
        """Initialize all QBox slots with the given values.

        Args:
            factory: The awaitable or factory function.
            scope: Scope for reference replacement.
            parent_boxes: QBox instances this operation depends on.
            start: When to start execution ('soon' or 'observed').
            repr_observes: Whether repr() triggers observation.
            cancel_on_delete: Whether to cancel pending work on deletion.
            mimic_type: Optional type hint for ABC registration.
        """
        self._qbox_factory: Awaitable[Any] | Callable[[], Awaitable[Any]] | None = (
            factory
        )
        self._qbox_future: Future[Any] | None = None
        self._qbox_cached_value: Any | None = None
        self._qbox_is_cached: bool = False
        self._qbox_lock: threading.RLock = threading.RLock()
        self._qbox_exception: BaseException | None = None
        self._qbox_mimic_type: type[Any] | None = mimic_type
        self._qbox_scope: ScopeType = scope
        self._qbox_parent_boxes: list[QBox[Any]] = parent_boxes
        self._qbox_start_mode: StartMode = start
        self._qbox_repr_observes: bool = repr_observes
        self._qbox_cancel_on_delete: bool = cancel_on_delete

        # If start='soon', submit immediately
        if start == "soon":
            self._ensure_future()

    @classmethod
    def _from_factory(
        cls,
        factory: Callable[[], Awaitable[U]],
        parent_boxes: list[QBox[Any]] | None = None,
        scope: ScopeType = "stack",
        start: StartMode = "observed",
        repr_observes: bool = False,
        cancel_on_delete: bool = True,
    ) -> QBox[U]:
        """Create a QBox from a factory function (for lazy composition).

        Note: Composed QBoxes default to start='observed' since they depend
        on parent values that may not be available yet.

        Args:
            factory: A callable that returns an awaitable.
            parent_boxes: QBox instances this operation depends on.
            scope: Scope for reference replacement.
            start: When to start execution ('soon' or 'observed').
            repr_observes: Whether repr() triggers observation.
            cancel_on_delete: Whether to cancel pending work on deletion.

        Returns:
            A new QBox wrapping the factory.
        """
        instance: QBox[Any] = object.__new__(cls)
        instance._init_slots(
            factory=factory,
            scope=scope,
            parent_boxes=parent_boxes or [],
            start=start,
            repr_observes=repr_observes,
            cancel_on_delete=cancel_on_delete,
        )
        return cast("QBox[U]", instance)

    def _ensure_future(self) -> Future[T]:
        """Ensure the future is created and submitted."""
        if self._qbox_future is None:
            with self._qbox_lock:
                if self._qbox_future is None:  # pragma: no cover (race condition)
                    factory = self._qbox_factory
                    if callable(factory) and not hasattr(factory, "__await__"):
                        awaitable: Awaitable[T] = factory()
                    else:
                        awaitable = cast("Awaitable[T]", factory)

                    # Ensure we have a coroutine for run_coroutine_threadsafe
                    # Non-coroutine awaitables need to be wrapped
                    if asyncio.iscoroutine(awaitable):
                        coro = awaitable
                    else:
                        # Wrap non-coroutine awaitable in a coroutine
                        async def _wrap_awaitable(aw: Awaitable[T]) -> T:
                            return await aw

                        coro = _wrap_awaitable(awaitable)

                    self._qbox_future = submit_to_loop(
                        cast("Coroutine[Any, Any, T]", coro),
                    )
        # Future is guaranteed to be set by this point (all branches set it)
        return self._qbox_future  # type: ignore[return-value]

    def __del__(self) -> None:
        """Clean up resources when the QBox is garbage collected.

        - If the coroutine was never submitted (start='observed'), close it
          to suppress 'coroutine was never awaited' warnings.
        - If cancel_on_delete is True and a future exists, cancel it.

        Note: Uses getattr with defaults to handle partially initialized
        instances (e.g., if __init__ raised an exception).
        """
        # Handle unsubmitted coroutines (start='observed' case)
        # Use getattr to safely handle partially initialized instances
        future = getattr(self, "_qbox_future", None)
        factory = getattr(self, "_qbox_factory", None)

        if future is None and factory is not None:
            # Close the coroutine to suppress "never awaited" warning
            close_method = getattr(factory, "close", None)
            if close_method is not None:
                with contextlib.suppress(Exception):
                    close_method()

        # Handle submitted but incomplete futures
        cancel_on_delete = getattr(self, "_qbox_cancel_on_delete", False)
        if cancel_on_delete and future is not None and not future.done():
            with contextlib.suppress(Exception):
                future.cancel()

    @property
    def __wrapped__(self) -> T:
        """Get the wrapped value, blocking if necessary.

        This property triggers evaluation of the async operation if it
        hasn't been evaluated yet. If the operation raised an exception,
        that exception is re-raised here.

        Returns:
            The result of the async operation.

        Raises:
            Exception: Any exception raised by the wrapped coroutine.
        """
        if self._qbox_is_cached:
            if self._qbox_exception is not None:
                raise self._qbox_exception
            return cast("T", self._qbox_cached_value)

        with self._qbox_lock:
            if self._qbox_is_cached:  # pragma: no cover (race condition)
                if self._qbox_exception is not None:
                    raise self._qbox_exception
                return cast("T", self._qbox_cached_value)

            future = self._ensure_future()
            try:
                self._qbox_cached_value = future.result()
            except BaseException as e:
                self._qbox_exception = e
                self._qbox_is_cached = True
                # Clear refs to allow GC (even on error)
                self._qbox_parent_boxes = []
                self._qbox_factory = None
                raise
            self._qbox_is_cached = True
            # Clear refs to allow garbage collection
            # Factory and parents are no longer needed after value is cached
            self._qbox_parent_boxes = []
            self._qbox_factory = None
            # _cached_value was just set from future.result() which returns T
            return self._qbox_cached_value  # pyright: ignore[reportReturnType]

    def __await__(self) -> Generator[Any, None, T]:
        """Support awaiting the QBox in async contexts.

        Yields:
            The result of the async operation.
        """
        return self._await_impl().__await__()

    async def _await_impl(self) -> T:
        """Implementation of await behavior."""
        if self._qbox_is_cached:
            if self._qbox_exception is not None:
                raise self._qbox_exception
            return cast("T", self._qbox_cached_value)

        future = self._ensure_future()
        # Get the CURRENT running loop (the one we're awaiting from)
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, future.result)
        except BaseException as e:
            with self._qbox_lock:
                self._qbox_exception = e
                self._qbox_is_cached = True
                self._qbox_parent_boxes = []
                self._qbox_factory = None
            raise
        with self._qbox_lock:
            if not self._qbox_is_cached:  # pragma: no cover (race)
                self._qbox_cached_value = result
                self._qbox_is_cached = True
                self._qbox_parent_boxes = []
                self._qbox_factory = None
        return result

    async def _get_value_async(self) -> T:
        """Get the value asynchronously (for use within composed operations).

        This method is used internally by _compose to avoid blocking the
        background event loop when getting the value of a parent QBox.
        """
        if self._qbox_is_cached:
            if self._qbox_exception is not None:
                raise self._qbox_exception
            return cast("T", self._qbox_cached_value)

        future = self._ensure_future()
        # Wrap the concurrent.futures.Future in an asyncio.Future
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wrap_future(future, loop=loop)
        except BaseException as e:
            with self._qbox_lock:
                self._qbox_exception = e
                self._qbox_is_cached = True
                self._qbox_parent_boxes = []
                self._qbox_factory = None
            raise
        with self._qbox_lock:
            if not self._qbox_is_cached:  # pragma: no cover (race)
                self._qbox_cached_value = result
                self._qbox_is_cached = True
                self._qbox_parent_boxes = []
                self._qbox_factory = None
        return result

    def _inherit_start_mode(self, other: Any = None) -> StartMode:
        """Determine start mode for composed operations.

        Returns 'soon' if self or other (if QBox) has start_mode='soon',
        otherwise returns 'observed'.

        Args:
            other: Optional other operand that may be a QBox.

        Returns:
            The inherited start mode.
        """
        if self._qbox_start_mode == "soon":
            return "soon"
        if isinstance(other, QBox) and other._qbox_start_mode == "soon":
            return "soon"
        return "observed"

    def _compose(
        self,
        op: Callable[..., Any],
        other: Any = None,
        *,
        has_other: bool = False,
    ) -> QBox[Any]:
        """Create a new QBox with a composed operation.

        Args:
            op: The operation to apply.
            other: Optional second operand.
            has_other: Whether other is used.

        Returns:
            A new QBox with the composed operation.
        """
        # Track parent boxes for cascading observation
        parents: list[QBox[Any]] = [self]
        if has_other and isinstance(other, QBox):
            parents.append(other)

        start = self._inherit_start_mode(other if has_other else None)

        async def composed() -> Any:
            value = await self._get_value_async()
            if has_other:
                if isinstance(other, QBox):
                    other_val = await other._get_value_async()
                else:
                    other_val = other
                return op(value, other_val)
            return op(value)

        return QBox._from_factory(
            composed,
            parent_boxes=parents,
            scope=self._qbox_scope,
            start=start,
            repr_observes=self._qbox_repr_observes,
            cancel_on_delete=self._qbox_cancel_on_delete,
        )

    def _compose_reverse(
        self,
        op: Callable[[Any, Any], Any],
        other: Any,
    ) -> QBox[Any]:
        """Create a new QBox with a reversed composed operation.

        Args:
            op: The operation to apply.
            other: The left operand.

        Returns:
            A new QBox with the composed operation.
        """
        # Track parent boxes for cascading observation
        parents: list[QBox[Any]] = [self]
        if isinstance(other, QBox):  # pragma: no cover
            parents.append(other)

        start = self._inherit_start_mode(other)

        async def composed() -> Any:
            value = await self._get_value_async()
            if isinstance(other, QBox):  # pragma: no cover (see note)
                # Note: This branch is unreachable in normal usage because when
                # both operands are QBox, Python calls left.__op__ not right.__rop__
                other_val = await other._get_value_async()
            else:
                other_val = other
            return op(other_val, value)

        return QBox._from_factory(
            composed,
            parent_boxes=parents,
            scope=self._qbox_scope,
            start=start,
            repr_observes=self._qbox_repr_observes,
            cancel_on_delete=self._qbox_cancel_on_delete,
        )

    # =========================================================================
    # Observation and Reference Replacement
    # =========================================================================

    @staticmethod
    def _qbox_is_qbox(obj: Any) -> bool:
        """Check if an object is a QBox without triggering patched isinstance.

        This method uses direct type checking to avoid recursion when isinstance
        has been patched.

        Args:
            obj: The object to check.

        Returns:
            True if obj is a QBox or typed QBox subclass, False otherwise.
        """
        obj_type = type(obj)
        # Check for typed QBox subclass (has _declared_mimic_type attribute)
        if hasattr(obj_type, "_declared_mimic_type"):
            return True
        # Check if QBox is in the MRO (handles QBox and its subclasses)
        return QBox in obj_type.__mro__

    def _force_and_replace(self, scope: ScopeType) -> T:
        """Force evaluation and replace references in the specified scope.

        Args:
            scope: The scope for reference replacement.

        Returns:
            The unwrapped value.
        """
        # Snapshot parent boxes BEFORE __wrapped__ clears them
        # This is necessary because __wrapped__ clears _qbox_parent_boxes
        # after caching the value, which would make parent cascading dead code
        with self._qbox_lock:
            parents_snapshot = list(self._qbox_parent_boxes)

        # Force evaluation (this clears _qbox_parent_boxes)
        value = self.__wrapped__

        # Replace references (cascades to parent boxes using snapshot)
        self._replace_references(value, scope, parents_snapshot)

        return value

    @staticmethod
    def _find_user_frame() -> FrameType | None:
        """Find the first frame outside the qbox package.

        Walks up the call stack to find where user code begins,
        skipping all frames within the qbox package.

        Returns:
            The first frame outside qbox, or None if not found.
        """
        # Get the directory containing this module to identify qbox frames
        qbox_dir = str(Path(__file__).parent)

        try:
            frame: FrameType | None = sys._getframe(1)
        except ValueError:  # pragma: no cover
            return None

        while frame is not None:
            # Check if this frame is outside the qbox package
            frame_file = frame.f_code.co_filename
            if not frame_file.startswith(qbox_dir):
                return frame
            frame = frame.f_back

        return None  # pragma: no cover

    def _replace_references(  # noqa: PLR0912
        self,
        value: T,
        scope: ScopeType,
        parents_snapshot: list[QBox[Any]] | None = None,
    ) -> None:
        """Replace references to self with value in the specified scope.

        Also recursively observes parent QBox instances to cascade observation.
        Automatically finds the first frame outside the qbox package.

        Args:
            value: The value to replace self with.
            scope: The replacement scope.
            parents_snapshot: Optional pre-captured list of parent boxes.
                If provided, uses this instead of reading from self._qbox_parent_boxes.
                This is needed when called from _force_and_replace, since __wrapped__
                clears _qbox_parent_boxes before this method is called.
        """
        # First, cascade to parent boxes
        # Use provided snapshot if available, otherwise snapshot under lock
        if parents_snapshot is None:  # pragma: no cover (recursive call path)
            with self._qbox_lock:
                parents_snapshot = list(self._qbox_parent_boxes)
                # Clear parent references to allow garbage collection
                # Parents are no longer needed after observation completes
                self._qbox_parent_boxes = []

        for parent in parents_snapshot:
            if not parent._qbox_is_cached:  # pragma: no cover (race condition)
                # Force evaluation of parent
                try:
                    parent_value = parent.__wrapped__
                except BaseException:  # pragma: no cover  # noqa: S112
                    # Parent failed - intentionally continue to process other parents
                    continue
                # Replace parent references too
                parent._replace_references(parent_value, scope)

        # Find the first frame outside qbox package
        frame = self._find_user_frame()
        if frame is None:  # pragma: no cover (defensive)
            return

        replaced_frames: set[int] = set()
        current_frame: FrameType | None = frame

        while current_frame is not None:
            # Replace in locals
            try:
                frame_locals = current_frame.f_locals
                for name in list(frame_locals.keys()):
                    if frame_locals.get(name) is self:
                        frame_locals[name] = value
                        replaced_frames.add(id(current_frame))
            except (RuntimeError, KeyError):  # pragma: no cover (defensive)
                # Frame locals may not be accessible in all contexts
                pass

            # Sync frame locals back to fast locals (cross-platform)
            if id(current_frame) in replaced_frames:
                _sync_frame_locals(current_frame)

            if scope == "locals":
                break

            current_frame = current_frame.f_back

        # Replace in globals if requested
        if scope == "globals" and frame is not None:
            try:
                caller_globals = frame.f_globals
                for name in list(caller_globals.keys()):
                    if caller_globals.get(name) is self:
                        caller_globals[name] = value
            except (RuntimeError, KeyError):  # pragma: no cover
                pass

    # =========================================================================
    # Magic methods that FORCE evaluation (return concrete values)
    # =========================================================================

    def __repr__(self) -> str:
        """Return a string representation.

        If repr_observes is True, this triggers observation.
        Otherwise, returns '<QBox[pending]>' for unevaluated boxes.
        """
        if self._qbox_is_cached:
            if self._qbox_exception is not None:
                return f"<QBox[ERROR: {type(self._qbox_exception).__name__}]>"
            return f"<QBox[{self._qbox_cached_value!r}]>"
        if self._qbox_repr_observes:
            # Force observation and return the repr of the actual value
            try:
                value = self.__wrapped__
                return repr(value)
            except Exception as e:
                return f"<QBox[ERROR: {type(e).__name__}]>"
        return "<QBox[pending]>"

    def __str__(self) -> str:
        """Return the string representation of the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached and references
        are replaced in the call stack.

        Returns:
            The string representation of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
        """
        return str(self._force_and_replace(self._qbox_scope))

    def __bool__(self) -> bool:
        """Return the truthiness of the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached and references
        are replaced in the call stack.

        Returns:
            The boolean value of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
        """
        return bool(self._force_and_replace(self._qbox_scope))

    def __hash__(self) -> int:
        """Return the hash of the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached and references
        are replaced in the call stack.

        Returns:
            The hash of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value is not hashable.
        """
        return hash(self._force_and_replace(self._qbox_scope))

    def __len__(self) -> int:
        """Return the length of the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached and references
        are replaced in the call stack.

        Returns:
            The length of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value has no len().
        """
        return len(cast("Any", self._force_and_replace(self._qbox_scope)))

    def __contains__(self, item: Any) -> bool:
        """Check if item is in the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached and references
        are replaced in the call stack.

        Args:
            item: The item to check for membership.

        Returns:
            True if item is in the wrapped result, False otherwise.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value doesn't support 'in'.
        """
        return item in cast("Any", self._force_and_replace(self._qbox_scope))

    def __iter__(self) -> Iterator[Any]:
        """Iterate over the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached and references
        are replaced in the call stack.

        Returns:
            An iterator over the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value is not iterable.
        """
        return iter(cast("Any", self._force_and_replace(self._qbox_scope)))

    # Comparison operators (force evaluation, return bool)
    @staticmethod
    def _unwrap_if_qbox(value: Any) -> Any:
        """Unwrap a value if it's a QBox (with reference replacement), otherwise as-is.

        Args:
            value: The value to unwrap.
        """
        if isinstance(value, QBox):
            return value._force_and_replace(value._qbox_scope)
        return value

    def __lt__(self, other: Any) -> bool:
        """Less than comparison.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Args:
            other: Value to compare against. Can be a QBox or any value.

        Returns:
            True if wrapped value is less than other.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If comparison is not supported.
        """
        value = self._force_and_replace(self._qbox_scope)
        return bool(cast("Any", value) < self._unwrap_if_qbox(other))

    def __le__(self, other: Any) -> bool:
        """Less than or equal comparison.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Args:
            other: Value to compare against. Can be a QBox or any value.

        Returns:
            True if wrapped value is less than or equal to other.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If comparison is not supported.
        """
        value = self._force_and_replace(self._qbox_scope)
        return bool(cast("Any", value) <= self._unwrap_if_qbox(other))

    def __eq__(self, other: object) -> bool:
        """Equality comparison.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Args:
            other: Value to compare against. Can be a QBox or any value.

        Returns:
            True if wrapped value equals other.

        Raises:
            Exception: Any exception from the wrapped coroutine.
        """
        value = self._force_and_replace(self._qbox_scope)
        return bool(value == self._unwrap_if_qbox(other))

    def __ne__(self, other: object) -> bool:
        """Inequality comparison.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Args:
            other: Value to compare against. Can be a QBox or any value.

        Returns:
            True if wrapped value does not equal other.

        Raises:
            Exception: Any exception from the wrapped coroutine.
        """
        value = self._force_and_replace(self._qbox_scope)
        return bool(value != self._unwrap_if_qbox(other))

    def __gt__(self, other: Any) -> bool:
        """Greater than comparison.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Args:
            other: Value to compare against. Can be a QBox or any value.

        Returns:
            True if wrapped value is greater than other.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If comparison is not supported.
        """
        value = self._force_and_replace(self._qbox_scope)
        return bool(cast("Any", value) > self._unwrap_if_qbox(other))

    def __ge__(self, other: Any) -> bool:
        """Greater than or equal comparison.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Args:
            other: Value to compare against. Can be a QBox or any value.

        Returns:
            True if wrapped value is greater than or equal to other.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If comparison is not supported.
        """
        value = self._force_and_replace(self._qbox_scope)
        return bool(cast("Any", value) >= self._unwrap_if_qbox(other))

    # =========================================================================
    # Magic methods that STAY LAZY (return new QBox)
    # =========================================================================

    # Arithmetic operators
    def __add__(self, other: Any) -> QBox[Any]:
        """Add operation (lazy).

        Returns a new QBox that will compute ``self + other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Value to add. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred addition.
        """
        return self._compose(operator.add, other, has_other=True)

    def __radd__(self, other: Any) -> QBox[Any]:
        """Reverse add operation (lazy).

        Returns a new QBox that will compute ``other + self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Left operand for addition.

        Returns:
            A new QBox containing the deferred addition.
        """
        return self._compose_reverse(operator.add, other)

    def __sub__(self, other: Any) -> QBox[Any]:
        """Subtract operation (lazy).

        Returns a new QBox that will compute ``self - other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Value to subtract. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred subtraction.
        """
        return self._compose(operator.sub, other, has_other=True)

    def __rsub__(self, other: Any) -> QBox[Any]:
        """Reverse subtract operation (lazy).

        Returns a new QBox that will compute ``other - self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Left operand for subtraction.

        Returns:
            A new QBox containing the deferred subtraction.
        """
        return self._compose_reverse(operator.sub, other)

    def __mul__(self, other: Any) -> QBox[Any]:
        """Multiply operation (lazy).

        Returns a new QBox that will compute ``self * other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Value to multiply by. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred multiplication.
        """
        return self._compose(operator.mul, other, has_other=True)

    def __rmul__(self, other: Any) -> QBox[Any]:
        """Reverse multiply operation (lazy).

        Returns a new QBox that will compute ``other * self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Left operand for multiplication.

        Returns:
            A new QBox containing the deferred multiplication.
        """
        return self._compose_reverse(operator.mul, other)

    def __truediv__(self, other: Any) -> QBox[Any]:
        """True divide operation (lazy).

        Returns a new QBox that will compute ``self / other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Divisor. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred division.
        """
        return self._compose(operator.truediv, other, has_other=True)

    def __rtruediv__(self, other: Any) -> QBox[Any]:
        """Reverse true divide operation (lazy).

        Returns a new QBox that will compute ``other / self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Dividend (left operand).

        Returns:
            A new QBox containing the deferred division.
        """
        return self._compose_reverse(operator.truediv, other)

    def __floordiv__(self, other: Any) -> QBox[Any]:
        """Floor divide operation (lazy).

        Returns a new QBox that will compute ``self // other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Divisor. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred floor division.
        """
        return self._compose(operator.floordiv, other, has_other=True)

    def __rfloordiv__(self, other: Any) -> QBox[Any]:
        """Reverse floor divide operation (lazy).

        Returns a new QBox that will compute ``other // self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Dividend (left operand).

        Returns:
            A new QBox containing the deferred floor division.
        """
        return self._compose_reverse(operator.floordiv, other)

    def __mod__(self, other: Any) -> QBox[Any]:
        """Modulo operation (lazy).

        Returns a new QBox that will compute ``self % other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Divisor for modulo. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred modulo operation.
        """
        return self._compose(operator.mod, other, has_other=True)

    def __rmod__(self, other: Any) -> QBox[Any]:
        """Reverse modulo operation (lazy).

        Returns a new QBox that will compute ``other % self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Dividend (left operand).

        Returns:
            A new QBox containing the deferred modulo operation.
        """
        return self._compose_reverse(operator.mod, other)

    def __pow__(self, other: Any) -> QBox[Any]:
        """Power operation (lazy).

        Returns a new QBox that will compute ``self ** other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Exponent. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred power operation.
        """
        return self._compose(operator.pow, other, has_other=True)

    def __rpow__(self, other: Any) -> QBox[Any]:
        """Reverse power operation (lazy).

        Returns a new QBox that will compute ``other ** self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Base (left operand).

        Returns:
            A new QBox containing the deferred power operation.
        """
        return self._compose_reverse(operator.pow, other)

    # Unary operators
    def __neg__(self) -> QBox[Any]:
        """Negation (lazy).

        Returns a new QBox that will compute ``-self`` when observed.
        Does not block or evaluate immediately.

        Returns:
            A new QBox containing the deferred negation.
        """
        return self._compose(operator.neg)

    def __pos__(self) -> QBox[Any]:
        """Positive (lazy).

        Returns a new QBox that will compute ``+self`` when observed.
        Does not block or evaluate immediately.

        Returns:
            A new QBox containing the deferred positive operation.
        """
        return self._compose(operator.pos)

    def __abs__(self) -> QBox[Any]:
        """Absolute value (lazy).

        Returns a new QBox that will compute ``abs(self)`` when observed.
        Does not block or evaluate immediately.

        Returns:
            A new QBox containing the deferred absolute value.
        """
        return self._compose(operator.abs)

    def __invert__(self) -> QBox[Any]:
        """Bitwise invert (lazy).

        Returns a new QBox that will compute ``~self`` when observed.
        Does not block or evaluate immediately.

        Returns:
            A new QBox containing the deferred bitwise inversion.
        """
        return self._compose(operator.invert)

    # Bitwise operators
    def __and__(self, other: Any) -> QBox[Any]:
        """Bitwise and (lazy).

        Returns a new QBox that will compute ``self & other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Value for bitwise AND. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred bitwise AND.
        """
        return self._compose(operator.and_, other, has_other=True)

    def __rand__(self, other: Any) -> QBox[Any]:
        """Reverse bitwise and (lazy).

        Returns a new QBox that will compute ``other & self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Left operand for bitwise AND.

        Returns:
            A new QBox containing the deferred bitwise AND.
        """
        return self._compose_reverse(operator.and_, other)

    def __or__(self, other: Any) -> QBox[Any]:
        """Bitwise or (lazy).

        Returns a new QBox that will compute ``self | other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Value for bitwise OR. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred bitwise OR.
        """
        return self._compose(operator.or_, other, has_other=True)

    def __ror__(self, other: Any) -> QBox[Any]:
        """Reverse bitwise or (lazy).

        Returns a new QBox that will compute ``other | self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Left operand for bitwise OR.

        Returns:
            A new QBox containing the deferred bitwise OR.
        """
        return self._compose_reverse(operator.or_, other)

    def __xor__(self, other: Any) -> QBox[Any]:
        """Bitwise xor (lazy).

        Returns a new QBox that will compute ``self ^ other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Value for bitwise XOR. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred bitwise XOR.
        """
        return self._compose(operator.xor, other, has_other=True)

    def __rxor__(self, other: Any) -> QBox[Any]:
        """Reverse bitwise xor (lazy).

        Returns a new QBox that will compute ``other ^ self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Left operand for bitwise XOR.

        Returns:
            A new QBox containing the deferred bitwise XOR.
        """
        return self._compose_reverse(operator.xor, other)

    def __lshift__(self, other: Any) -> QBox[Any]:
        """Left shift (lazy).

        Returns a new QBox that will compute ``self << other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Number of bits to shift. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred left shift.
        """
        return self._compose(operator.lshift, other, has_other=True)

    def __rlshift__(self, other: Any) -> QBox[Any]:
        """Reverse left shift (lazy).

        Returns a new QBox that will compute ``other << self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Value to shift (left operand).

        Returns:
            A new QBox containing the deferred left shift.
        """
        return self._compose_reverse(operator.lshift, other)

    def __rshift__(self, other: Any) -> QBox[Any]:
        """Right shift (lazy).

        Returns a new QBox that will compute ``self >> other`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Number of bits to shift. Can be another QBox or any compatible value.

        Returns:
            A new QBox containing the deferred right shift.
        """
        return self._compose(operator.rshift, other, has_other=True)

    def __rrshift__(self, other: Any) -> QBox[Any]:
        """Reverse right shift (lazy).

        Returns a new QBox that will compute ``other >> self`` when observed.
        Does not block or evaluate immediately.

        Args:
            other: Value to shift (left operand).

        Returns:
            A new QBox containing the deferred right shift.
        """
        return self._compose_reverse(operator.rshift, other)

    # Item access (lazy)
    @overload
    def __getitem__(self, key: int) -> QBox[Any]: ...

    @overload
    def __getitem__(self, key: slice) -> QBox[Any]: ...

    @overload
    def __getitem__(self, key: str) -> QBox[Any]: ...

    def __getitem__(self, key: int | slice | str) -> QBox[Any]:
        """Get item (lazy).

        Returns a new QBox that will compute ``self[key]`` when observed.
        Does not block or evaluate immediately.

        Args:
            key: The index, slice, or key to access.

        Returns:
            A new QBox containing the deferred item access.
        """
        return self._compose(lambda x: x[key])

    # Attribute access (lazy)
    def __getattr__(self, name: str) -> QBox[Any]:
        """Get attribute (lazy).

        Returns a new QBox that will compute ``self.name`` when observed.
        Does not block or evaluate immediately.

        Note: This only handles attributes not defined on QBox itself.
        Accessing private attributes (starting with ``_``) raises AttributeError.

        Args:
            name: The attribute name to access.

        Returns:
            A new QBox containing the deferred attribute access.

        Raises:
            AttributeError: If name starts with ``_`` (reserved for QBox internals).
        """
        # Avoid recursion on special attributes
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
        return self._compose(lambda x: getattr(x, name))

    def __call__(self, *args: Any, **kwargs: Any) -> QBox[Any]:
        """Call the wrapped value (lazy).

        Returns a new QBox that will compute ``self(*args, **kwargs)`` when
        observed. Does not block or evaluate immediately.

        Args and kwargs that are QBox instances will also be resolved lazily.

        Args:
            *args: Positional arguments for the call.
            **kwargs: Keyword arguments for the call.

        Returns:
            A new QBox containing the deferred call result.
        """
        # Track parent boxes
        parents: list[QBox[Any]] = [self]
        parents.extend(arg for arg in args if isinstance(arg, QBox))
        parents.extend(v for v in kwargs.values() if isinstance(v, QBox))

        # Inherit start mode: 'soon' wins if any parent is 'soon'
        start: StartMode = self._qbox_start_mode
        if start != "soon":
            for parent in parents[1:]:  # Skip self, already checked
                if parent._qbox_start_mode == "soon":
                    start = "soon"
                    break

        async def composed() -> Any:
            """Resolve self and args, then call the wrapped callable."""
            value = await self._get_value_async()
            # Resolve any QBox arguments
            resolved_args = []
            for arg in args:
                if isinstance(arg, QBox):
                    resolved_args.append(await arg._get_value_async())
                else:
                    resolved_args.append(arg)
            resolved_kwargs = {}
            for k, v in kwargs.items():
                if isinstance(v, QBox):
                    resolved_kwargs[k] = await v._get_value_async()
                else:
                    resolved_kwargs[k] = v
            return cast("Any", value)(*resolved_args, **resolved_kwargs)

        return QBox._from_factory(
            composed,
            parent_boxes=parents,
            scope=self._qbox_scope,
            start=start,
            repr_observes=self._qbox_repr_observes,
            cancel_on_delete=self._qbox_cancel_on_delete,
        )

    # Numeric conversions (force evaluation)
    def __int__(self) -> int:
        """Convert to int.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Returns:
            Integer conversion of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value cannot be converted to int.
        """
        return int(cast("Any", self._force_and_replace(self._qbox_scope)))

    def __float__(self) -> float:
        """Convert to float.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Returns:
            Float conversion of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value cannot be converted to float.
        """
        return float(cast("Any", self._force_and_replace(self._qbox_scope)))

    def __complex__(self) -> complex:
        """Convert to complex.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Returns:
            Complex conversion of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value cannot be converted to complex.
        """
        return complex(cast("Any", self._force_and_replace(self._qbox_scope)))

    def __index__(self) -> int:
        """Return an integer for use in slicing.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Returns:
            Integer index of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value doesn't support __index__.
        """
        value = self._force_and_replace(self._qbox_scope)
        if hasattr(value, "__index__"):
            return int(cast("Any", value).__index__())
        raise TypeError(
            f"'{type(value).__name__}' object cannot be interpreted as an integer"
        )

    def __round__(self, ndigits: int | None = None) -> Any:
        """Round the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Args:
            ndigits: Number of decimal places to round to. If None, rounds to
                nearest integer.

        Returns:
            Rounded value of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value doesn't support rounding.
        """
        if ndigits is None:
            return round(cast("Any", self.__wrapped__))
        return round(cast("Any", self.__wrapped__), ndigits)

    def __floor__(self) -> int:
        """Floor the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Returns:
            Floor of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value doesn't support floor.
        """
        result = math.floor(cast("Any", self.__wrapped__))
        return int(result)

    def __ceil__(self) -> int:
        """Ceil the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Returns:
            Ceiling of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value doesn't support ceil.
        """
        result = math.ceil(cast("Any", self.__wrapped__))
        return int(result)

    def __trunc__(self) -> int:
        """Truncate the wrapped value.

        This method forces evaluation, blocking until the async operation
        completes. After evaluation, the result is cached.

        Returns:
            Truncated value of the wrapped result.

        Raises:
            Exception: Any exception from the wrapped coroutine.
            TypeError: If the wrapped value doesn't support trunc.
        """
        result = math.trunc(cast("Any", self.__wrapped__))
        return int(result)
