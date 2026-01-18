"""Type stub for QBox - makes QBox transparent to static type checkers.

This stub declares that QBox.__new__ returns T instead of QBox[T], making
QBox invisible to type checkers while preserving runtime behavior.
"""

from collections.abc import Awaitable, Generator
from typing import Any, Generic, Literal, TypeGuard, TypeVar

T = TypeVar("T")

ScopeType = Literal["locals", "stack", "globals"]
StartMode = Literal["soon", "observed"]

class QBox(Generic[T]):
    """QBox is transparent to type checkers - returns T, not QBox[T].

    At runtime, QBox wraps an awaitable and defers evaluation. But for static
    type checking, QBox(awaitable) appears to return the awaitable's result
    type directly. This enables natural usage like:

        data = QBox(fetch_dict())
        data["key"]      # Works! dict.__getitem__
        data.get("x", 0) # Works! dict.get
        len(data)        # Works! len(dict)

    Use QBox._qbox_is_qbox(obj) for runtime type checks instead of isinstance.
    """

    def __new__(
        cls,
        awaitable: Awaitable[T],
        mimic_type: type[T] | None = ...,
        scope: ScopeType = ...,
        start: StartMode = ...,
        repr_observes: bool = ...,
        cancel_on_delete: bool = ...,
    ) -> T: ...  # Returns T, not QBox[T] - makes QBox transparent
    def __init__(
        self,
        awaitable: Awaitable[T],
        mimic_type: type[T] | None = ...,
        scope: ScopeType = ...,
        start: StartMode = ...,
        repr_observes: bool = ...,
        cancel_on_delete: bool = ...,
    ) -> None: ...

    # Internal attributes (for library internals only - not part of public API)
    _qbox_scope: ScopeType
    _qbox_is_cached: bool

    @property
    def __wrapped__(self) -> T: ...
    def __await__(self) -> Generator[Any, None, T]: ...
    def _force_and_replace(self, scope: ScopeType) -> T:
        """Force evaluation and replace references. Internal use only."""
        ...

    @staticmethod
    def _qbox_is_qbox(obj: object) -> TypeGuard[QBox[Any]]:
        """Check if an object is a QBox at runtime.

        Since QBox is transparent to type checkers, isinstance(x, QBox) won't
        work for type narrowing. Use this method for runtime type checks.

        Args:
            obj: The object to check.

        Returns:
            True if obj is a QBox instance, False otherwise.
        """
        ...
