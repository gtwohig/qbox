"""Opt-in transparent isinstance support for QBox.

This module provides functions to patch builtins.isinstance to work
transparently with QBox instances. When enabled, isinstance(box, SomeType)
will force observation of the QBox and return the correct result.

Example usage::

    from qbox import enable_qbox_isinstance, disable_qbox_isinstance

    # Enable at startup
    enable_qbox_isinstance()

    # Now isinstance works transparently
    data = QBox(fetch_dict())
    isinstance(data, dict)  # True! Forces observation automatically

    # Optionally disable later
    disable_qbox_isinstance()

Or use the context manager for scoped patching::

    with qbox_isinstance():
        isinstance(data, dict)  # True in this block
    # Original isinstance restored after block
"""

from __future__ import annotations

import builtins
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

# Thread-safe patching state
_isinstance_lock = threading.Lock()
_isinstance_patched: bool = False
_isinstance_refcount: int = 0  # Reference count for nested context managers
_original_isinstance: Any = None


def enable_qbox_isinstance() -> None:
    """Patch builtins.isinstance to work transparently with QBox.

    After calling this, isinstance(qbox, SomeType) will:
    1. Force observation of the QBox
    2. Replace references to the QBox with the unwrapped value
    3. Return the correct isinstance result

    This is a global change affecting all code. Call once at startup.

    Note:
        - This function is idempotent (safe to call multiple times)
        - Use disable_qbox_isinstance() to restore original behavior
        - Consider using ABCs with mimic_type instead for library code
        - This function is thread-safe
    """
    global _isinstance_patched, _original_isinstance

    with _isinstance_lock:
        if _isinstance_patched:
            return

        _original_isinstance = builtins.isinstance

        def _transparent_isinstance(
            obj: Any, classinfo: type[Any] | tuple[type[Any], ...]
        ) -> bool:
            """Transparent isinstance that observes QBox instances."""
            # Import qbox.qbox directly to avoid circular imports
            from qbox.qbox import QBox

            # Use QBox._qbox_is_qbox to check without triggering recursion
            if QBox._qbox_is_qbox(obj):
                # Store scope before calling _force_and_replace to avoid race
                # where another thread could replace the reference
                scope = obj._qbox_scope
                # Observe the QBox (forces evaluation and replaces references)
                # Inline the observe logic here to avoid circular imports
                obj = obj._force_and_replace(scope)

            result: bool = _original_isinstance(obj, classinfo)
            return result

        builtins.isinstance = _transparent_isinstance  # type: ignore[assignment]
        _isinstance_patched = True


def disable_qbox_isinstance() -> None:
    """Restore the original isinstance behavior.

    After calling this, isinstance will return False for QBox instances
    when checking against the wrapped type (normal Python behavior).

    Note:
        - This function is idempotent (safe to call multiple times)
        - This function is thread-safe
    """
    global _isinstance_patched, _original_isinstance

    with _isinstance_lock:
        if not _isinstance_patched:
            return

        builtins.isinstance = _original_isinstance
        _isinstance_patched = False


def is_qbox_isinstance_enabled() -> bool:
    """Check if isinstance has been patched for QBox transparency.

    Returns:
        True if enable_qbox_isinstance() has been called and
        disable_qbox_isinstance() has not been called since.
    """
    return _isinstance_patched


@contextmanager
def qbox_isinstance() -> Generator[None, None, None]:
    """Context manager for scoped QBox isinstance behavior.

    Within this context, isinstance() will work transparently with QBox
    instances, forcing observation and returning the correct result.

    This context manager supports nesting - the patching will remain active
    until the outermost context exits.

    Example:
        >>> from qbox import QBox, qbox_isinstance
        >>> async def fetch_dict():
        ...     return {"key": "value"}
        >>> data = QBox(fetch_dict())
        >>> with qbox_isinstance():
        ...     assert isinstance(data, dict)  # True, forces observation
        >>> # Original isinstance restored after block

        >>> # Nested contexts work correctly:
        >>> with qbox_isinstance():
        ...     with qbox_isinstance():
        ...         pass  # Still enabled
        ...     # Still enabled after inner context exits
        >>> # Disabled after outermost context exits

    Note:
        - This function is thread-safe
        - Nested contexts increment a reference count; patching is only
          disabled when the outermost context exits
    """
    global _isinstance_refcount

    with _isinstance_lock:
        _isinstance_refcount += 1
        should_enable = _isinstance_refcount == 1

    # Enable outside the lock (enable_qbox_isinstance has its own lock)
    # Use try-finally to ensure refcount is decremented even if enable fails
    try:
        if should_enable:
            enable_qbox_isinstance()
        yield
    finally:
        with _isinstance_lock:
            _isinstance_refcount -= 1
            should_disable = _isinstance_refcount == 0

        if should_disable:
            disable_qbox_isinstance()
