"""Type stub for qbox package - makes QBox transparent to static type checkers."""

from collections.abc import Awaitable, Generator
from contextlib import contextmanager
from typing import Any, Generic, Literal, TypeGuard, TypeVar

T = TypeVar("T")

ScopeType = Literal["locals", "stack", "globals"]
StartMode = Literal["soon", "observed"]

class QBox(Generic[T]):
    """QBox is transparent to type checkers - returns T, not QBox[T]."""

    def __new__(
        cls,
        awaitable: Awaitable[T],
        mimic_type: type[T] | None = ...,
        scope: ScopeType = ...,
        start: StartMode = ...,
        repr_observes: bool = ...,
        cancel_on_delete: bool = ...,
    ) -> T: ...  # Returns T, not QBox[T]
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
    def _qbox_is_qbox(obj: object) -> TypeGuard[QBox[Any]]: ...

def observe(obj: T, scope: ScopeType | None = None) -> T:
    """Observe an object, collapsing it if it's a QBox.

    Since QBox is transparent to type checkers, observe() is typed as
    identity: T -> T. At runtime it forces QBox evaluation.
    """
    ...

def enable_qbox_isinstance() -> None:
    """Enable patched isinstance() that recognizes QBox type mimicry."""
    ...

def disable_qbox_isinstance() -> None:
    """Disable patched isinstance()."""
    ...

def is_qbox_isinstance_enabled() -> bool:
    """Check if patched isinstance() is currently enabled."""
    ...

@contextmanager
def qbox_isinstance() -> Generator[None, None, None]:
    """Context manager to temporarily enable patched isinstance()."""
    ...

__all__: list[str]
