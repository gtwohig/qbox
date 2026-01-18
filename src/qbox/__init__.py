"""Quantum Box - A lazily awaited container for async operations.

QBox wraps a coroutine or awaitable and defers its evaluation until
the value is actually needed. Like Schrödinger's cat, the value exists
in a state of superposition until observed.

Basic usage::

    from qbox import QBox, observe

    async def fetch_value():
        return 42

    value = QBox(fetch_value())
    result = value + 8  # Still lazy, returns QBox
    if result > 40:     # Observation happens here
        print("Large!")

Type mimicry::

    from collections.abc import Mapping
    data = QBox(fetch_dict(), mimic_type=Mapping)
    isinstance(data, Mapping)  # True, without forcing evaluation!

Explicit observation::

    from qbox import observe
    result = observe(data)  # Forces evaluation, replaces references

Eager vs lazy execution::

    # Default: eager execution (start='soon')
    data = QBox(fetch_data())  # Starts immediately

    # Lazy execution (start='observed')
    data = QBox(fetch_data(), start='observed')  # Waits until observed
"""

from typing import TypeVar, cast

from ._isinstance import (
    disable_qbox_isinstance,
    enable_qbox_isinstance,
    is_qbox_isinstance_enabled,
    qbox_isinstance,
)
from .qbox import QBox, ScopeType, StartMode

T = TypeVar("T")


def observe(obj: "T | QBox[T]", scope: ScopeType | None = None) -> T:
    """Observe an object, collapsing it if it's a QBox.

    If obj is a QBox: forces evaluation, replaces references, returns value.
    If obj is not a QBox: returns obj unchanged (idempotent).

    Observing a composed QBox observes its entire dependency tree.

    Args:
        obj: The object to observe (may or may not be a QBox).
        scope: Override the default scope for replacement. If None, uses
            the QBox's default scope.

    Returns:
        The unwrapped value if obj is a QBox, otherwise obj unchanged.

    Example::

        from qbox import QBox, observe
        data = QBox(fetch_data())
        value = observe(data)  # Forces evaluation
        value = observe("hello")  # Returns "hello" unchanged
    """
    # Use _qbox_is_qbox to avoid triggering patched isinstance
    if not QBox._qbox_is_qbox(obj):
        # obj is definitely not a QBox, so it's just T
        return cast("T", obj)

    # We know obj is a QBox here
    qbox_obj = cast("QBox[T]", obj)
    effective_scope = scope or qbox_obj._qbox_scope
    return qbox_obj._force_and_replace(effective_scope)


__all__ = [
    "QBox",
    "ScopeType",
    "StartMode",
    "disable_qbox_isinstance",
    "enable_qbox_isinstance",
    "is_qbox_isinstance_enabled",
    "observe",
    "qbox_isinstance",
]
