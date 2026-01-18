"""Type checking tests - verified by pyright/mypy, not pytest.

These tests verify that QBox's transparent typing works correctly with
static type checkers. Run with:
    uv run pyright tests/test_typing.py

The tests use reveal_type() which is a type checker directive, not a runtime
function. Type checkers will report the inferred types.
"""

from typing import TYPE_CHECKING

from qbox import QBox, observe

# Helper async functions for testing


async def fetch_int() -> int:
    """Return an integer."""
    return 42


async def fetch_str() -> str:
    """Return a string."""
    return "hello"


async def fetch_dict() -> dict[str, int]:
    """Return a dict."""
    return {"a": 1, "b": 2}


async def fetch_list() -> list[str]:
    """Return a list."""
    return ["a", "b", "c"]


class User:
    """Sample user class for testing."""

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    def greet(self) -> str:
        """Return a greeting."""
        return f"Hello, {self.name}!"


async def fetch_user() -> User:
    """Return a user."""
    return User("Alice", 30)


# =============================================================================
# Type Transparency Tests
# =============================================================================


def test_int_transparent() -> None:
    """QBox(awaitable) returns the underlying type, not QBox[T]."""
    box = QBox(fetch_int())
    # Type checker sees: int
    result: int = box  # OK - box is typed as int
    added: int = box + 5  # OK - int + int = int
    _ = result, added  # Silence unused warnings


def test_str_transparent() -> None:
    """String operations work transparently."""
    box = QBox(fetch_str())
    # Type checker sees: str
    upper: str = box.upper()  # OK - str.upper() -> str
    length: int = len(box)  # OK - len(str) -> int
    _ = upper, length


def test_dict_transparent() -> None:
    """Dict operations work transparently."""
    data = QBox(fetch_dict())
    # Type checker sees: dict[str, int]
    value: int | None = data.get("a")  # OK - dict.get() -> int | None
    keys = data.keys()  # OK - dict.keys() -> KeysView[str]
    items = list(data.items())  # OK - dict.items() -> ItemsView[str, int]
    _ = value, keys, items


def test_list_transparent() -> None:
    """List operations work transparently."""
    items = QBox(fetch_list())
    # Type checker sees: list[str]
    first: str = items[0]  # OK - list[str].__getitem__(int) -> str
    joined: str = ",".join(items)  # OK - str.join(Iterable[str]) -> str
    _ = first, joined


def test_class_transparent() -> None:
    """Class attribute/method access works transparently."""
    user = QBox(fetch_user())
    # Type checker sees: User
    name: str = user.name  # OK - User.name -> str
    age: int = user.age  # OK - User.age -> int
    greeting: str = user.greet()  # OK - User.greet() -> str
    _ = name, age, greeting


# =============================================================================
# observe() Tests
# =============================================================================


def test_observe_identity() -> None:
    """observe() is typed as identity: T -> T."""
    box = QBox(fetch_int())
    result: int = observe(box)  # OK - int -> int
    _ = result


def test_observe_dict() -> None:
    """observe() preserves dict type."""
    box = QBox(fetch_dict())
    result: dict[str, int] = observe(box)  # OK
    _ = result


def test_observe_plain_value() -> None:
    """observe() on non-QBox returns same type."""
    plain: str = observe("hello")  # OK - str -> str
    number: int = observe(42)  # OK - int -> int
    _ = plain, number


# =============================================================================
# Arithmetic Operations Tests
# =============================================================================


def test_arithmetic() -> None:
    """Arithmetic operations return the underlying type."""
    box = QBox(fetch_int())
    # All these should type as int due to transparent typing
    added: int = box + 5
    subbed: int = box - 3
    multed: int = box * 2
    _ = added, subbed, multed


# =============================================================================
# Runtime Type Check Tests
# =============================================================================


def test_qbox_is_qbox() -> None:
    """_qbox_is_qbox() is available for runtime type checks."""
    box = QBox(fetch_int())
    # This is how to check for QBox at runtime
    is_box: bool = QBox._qbox_is_qbox(box)
    _ = is_box


# =============================================================================
# Await Tests (for async contexts)
# =============================================================================


async def test_await_transparent() -> int:
    """await on QBox returns the underlying type."""
    box = QBox(fetch_int())
    # Type checker sees box as int, await int works
    value: int = await box  # type: ignore[misc]  # await on non-awaitable warning
    return value


# =============================================================================
# TYPE_CHECKING guard tests
# =============================================================================

if TYPE_CHECKING:
    # These only run during type checking, not at runtime

    def _static_only_int_test() -> None:
        """Verify int transparency in static context."""
        box = QBox(fetch_int())
        _: int = box

    def _static_only_dict_test() -> None:
        """Verify dict transparency in static context."""
        box = QBox(fetch_dict())
        _: dict[str, int] = box

    def _static_only_observe_test() -> None:
        """Verify observe preserves types."""
        box = QBox(fetch_list())
        result: list[str] = observe(box)
        _ = result
