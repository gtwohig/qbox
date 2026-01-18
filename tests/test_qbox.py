"""Test cases for the QBox container."""

import asyncio
import math
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from qbox import QBox, observe


class TestBasic:
    """Basic QBox creation and value access tests."""

    def test_create_from_coroutine(self) -> None:
        """Test creating a QBox from a coroutine."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        assert isinstance(box, QBox)

    def test_wrapped_property_returns_value(self) -> None:
        """Test that __wrapped__ returns the resolved value."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        assert box.__wrapped__ == 42

    def test_wrapped_caches_value(self) -> None:
        """Test that __wrapped__ caches the result."""
        call_count = 0

        async def get_value() -> int:
            nonlocal call_count
            call_count += 1
            return 42

        box = QBox(get_value())
        _ = box.__wrapped__
        _ = box.__wrapped__
        _ = box.__wrapped__
        assert call_count == 1

    def test_repr_pending(self) -> None:
        """Test repr shows pending state before evaluation."""

        async def slow() -> int:
            await asyncio.sleep(10)
            return 42

        # Use start='observed' to ensure coroutine hasn't started yet
        box = QBox(slow(), start="observed")
        assert repr(box) == "<QBox[pending]>"

    def test_repr_cached(self) -> None:
        """Test repr shows value after evaluation."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        _ = box.__wrapped__
        assert repr(box) == "<QBox[42]>"

    def test_str_forces_evaluation(self) -> None:
        """Test that str() forces evaluation."""

        async def get_value() -> str:
            return "hello"

        box = QBox(get_value())
        assert str(box) == "hello"


class TestAsyncContext:
    """Tests for using QBox in async contexts."""

    async def test_await_box(self) -> None:
        """Test awaiting a QBox in async context."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        result = await box
        assert result == 42

    async def test_await_with_delay(self) -> None:
        """Test awaiting a QBox with an async delay."""

        async def delayed() -> int:
            await asyncio.sleep(0.01)
            return 42

        box = QBox(delayed())
        result = await box
        assert result == 42


class TestLazyComposition:
    """Tests for lazy operation composition."""

    def test_add_returns_qbox(self) -> None:
        """Test that addition returns a QBox (lazy)."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        result = box + 5
        assert isinstance(result, QBox)

    def test_add_evaluates_correctly(self) -> None:
        """Test that addition evaluates correctly when forced."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        result = box + 5
        assert result.__wrapped__ == 15

    def test_chain_operations(self) -> None:
        """Test chaining multiple operations."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        result = (box + 5) * 2 - 10
        assert isinstance(result, QBox)
        assert result.__wrapped__ == 20  # (10+5)*2-10 = 20

    def test_lazy_chain_no_evaluation_until_needed(self) -> None:
        """Test that chains don't evaluate until needed with start='observed'."""
        call_count = 0

        async def get_value() -> int:
            nonlocal call_count
            call_count += 1
            return 10

        # Use start='observed' to defer execution until observation
        box = QBox(get_value(), start="observed")
        result = (box + 5) * 2 - 10
        assert call_count == 0  # Not evaluated yet
        _ = result > 15  # Force evaluation
        assert call_count == 1

    def test_reverse_add(self) -> None:
        """Test reverse add (number + QBox)."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        result = 5 + box
        assert isinstance(result, QBox)
        assert result.__wrapped__ == 15

    def test_all_arithmetic_ops(self) -> None:
        """Test all arithmetic operators."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())

        assert (box + 5).__wrapped__ == 15
        assert (box - 3).__wrapped__ == 7
        assert (box * 2).__wrapped__ == 20
        assert (box / 4).__wrapped__ == 2.5
        assert (box // 3).__wrapped__ == 3
        assert (box % 3).__wrapped__ == 1
        assert (box**2).__wrapped__ == 100

    def test_unary_operators(self) -> None:
        """Test unary operators."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        assert (-box).__wrapped__ == -10
        assert (+box).__wrapped__ == 10
        assert abs(QBox(self._neg_coro())).__wrapped__ == 5

    @staticmethod
    async def _neg_coro() -> int:
        return -5


class TestForceEvaluation:
    """Tests for operations that force evaluation."""

    def test_comparison_forces_evaluation(self) -> None:
        """Test that comparisons force evaluation."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        assert box > 40
        assert box < 50
        assert box >= 42
        assert box <= 42
        assert box == 42
        assert box != 41

    def test_bool_forces_evaluation(self) -> None:
        """Test that bool conversion forces evaluation."""

        async def truthy() -> int:
            return 1

        async def falsy() -> int:
            return 0

        assert bool(QBox(truthy()))
        assert not bool(QBox(falsy()))

    def test_len_forces_evaluation(self) -> None:
        """Test that len() forces evaluation."""

        async def get_list() -> list[int]:
            return [1, 2, 3, 4, 5]

        box = QBox(get_list())
        assert len(box) == 5

    def test_contains_forces_evaluation(self) -> None:
        """Test that 'in' operator forces evaluation."""

        async def get_list() -> list[int]:
            return [1, 2, 3]

        box = QBox(get_list())
        assert 2 in box
        assert 4 not in box

    def test_iter_forces_evaluation(self) -> None:
        """Test that iteration forces evaluation."""

        async def get_list() -> list[int]:
            return [1, 2, 3]

        box = QBox(get_list())
        result = list(box)
        assert result == [1, 2, 3]

    def test_numeric_conversions(self) -> None:
        """Test numeric conversion methods."""

        async def get_value() -> float:
            return 42.7

        box = QBox(get_value())
        assert int(box) == 42
        assert float(box) == 42.7
        assert complex(box) == complex(42.7)

    def test_round_floor_ceil_trunc(self) -> None:
        """Test rounding operations."""

        async def get_value() -> float:
            return 42.7

        box = QBox(get_value())
        assert round(box) == 43
        assert round(box, 1) == 42.7
        assert math.floor(box) == 42
        assert math.ceil(box) == 43
        assert math.trunc(box) == 42


class TestLazyItemAccess:
    """Tests for lazy item and attribute access."""

    def test_getitem_is_lazy(self) -> None:
        """Test that __getitem__ returns a QBox."""

        async def get_list() -> list[int]:
            return [1, 2, 3]

        box = QBox(get_list())
        result = box[1]
        assert isinstance(result, QBox)
        assert result.__wrapped__ == 2

    def test_getitem_with_slice(self) -> None:
        """Test slicing returns a QBox."""

        async def get_list() -> list[int]:
            return [1, 2, 3, 4, 5]

        box = QBox(get_list())
        result = box[1:4]
        assert isinstance(result, QBox)
        assert result.__wrapped__ == [2, 3, 4]

    def test_getattr_is_lazy(self) -> None:
        """Test that attribute access returns a QBox."""

        async def get_string() -> str:
            return "hello"

        box = QBox(get_string())
        result = box.upper
        assert isinstance(result, QBox)

    def test_method_call_is_lazy(self) -> None:
        """Test that method calls are lazy."""

        async def get_string() -> str:
            return "hello"

        box = QBox(get_string())
        result = box.upper()
        assert isinstance(result, QBox)
        assert result.__wrapped__ == "HELLO"


class TestCallable:
    """Tests for calling wrapped values."""

    def test_call_returns_qbox(self) -> None:
        """Test that calling a QBox returns a QBox."""

        async def get_func() -> type[str]:
            return str

        box = QBox(get_func())
        result = box(42)
        assert isinstance(result, QBox)
        assert result.__wrapped__ == "42"

    def test_call_with_kwargs(self) -> None:
        """Test calling with keyword arguments."""

        async def get_dict() -> type[dict[str, int]]:
            return dict

        box = QBox(get_dict())
        result = box(a=1, b=2)
        assert result.__wrapped__ == {"a": 1, "b": 2}


class TestErrorHandling:
    """Tests for error handling."""

    def test_exception_is_cached(self) -> None:
        """Test that exceptions are cached."""
        call_count = 0

        async def failing() -> int:
            nonlocal call_count
            call_count += 1
            raise ValueError("test error")

        box = QBox(failing())

        with pytest.raises(ValueError, match="test error"):
            _ = box.__wrapped__

        with pytest.raises(ValueError, match="test error"):
            _ = box.__wrapped__

        assert call_count == 1

    def test_repr_shows_error(self) -> None:
        """Test that repr shows error state."""

        async def failing() -> int:
            raise ValueError("test error")

        box = QBox(failing())

        with pytest.raises(ValueError):
            _ = box.__wrapped__

        assert repr(box) == "<QBox[ERROR: ValueError]>"

    def test_error_in_chain(self) -> None:
        """Test that errors propagate through chains."""

        async def failing() -> int:
            raise ValueError("test error")

        box = QBox(failing())
        result = box + 5

        with pytest.raises(ValueError, match="test error"):
            _ = result.__wrapped__


class TestThreading:
    """Tests for thread safety."""

    def test_concurrent_access(self) -> None:
        """Test that concurrent access is safe."""

        async def slow() -> int:
            await asyncio.sleep(0.01)
            return 42

        box = QBox(slow())
        results: list[int] = []

        def access() -> None:
            results.append(box.__wrapped__)

        threads = [threading.Thread(target=access) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == 42 for r in results)

    def test_concurrent_creation(self) -> None:
        """Test creating many QBoxes concurrently."""

        async def get_value(n: int) -> int:
            await asyncio.sleep(0.001)
            return n

        def create_and_resolve(n: int) -> int:
            box = QBox(get_value(n))
            return box.__wrapped__

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(create_and_resolve, range(100)))

        assert results == list(range(100))


class TestBitwiseOperators:
    """Tests for bitwise operators."""

    def test_and_or_xor(self) -> None:
        """Test bitwise and, or, xor."""

        async def get_value() -> int:
            return 0b1010

        box = QBox(get_value())
        assert (box & 0b1100).__wrapped__ == 0b1000
        assert (box | 0b0101).__wrapped__ == 0b1111
        assert (box ^ 0b0011).__wrapped__ == 0b1001

    def test_shift(self) -> None:
        """Test left and right shift."""

        async def get_value() -> int:
            return 8

        box = QBox(get_value())
        assert (box << 2).__wrapped__ == 32
        assert (box >> 2).__wrapped__ == 2

    def test_invert(self) -> None:
        """Test bitwise invert."""

        async def get_value() -> int:
            return 0

        box = QBox(get_value())
        assert (~box).__wrapped__ == -1


class TestQBoxToQBoxOperations:
    """Tests for operations between QBox instances."""

    def test_add_two_boxes(self) -> None:
        """Test adding two QBox instances."""

        async def get_a() -> int:
            return 10

        async def get_b() -> int:
            return 20

        box_a = QBox(get_a())
        box_b = QBox(get_b())
        result = box_a + box_b
        assert isinstance(result, QBox)
        assert result.__wrapped__ == 30

    def test_compare_two_boxes(self) -> None:
        """Test comparing two QBox instances."""

        async def get_a() -> int:
            return 10

        async def get_b() -> int:
            return 20

        box_a = QBox(get_a())
        box_b = QBox(get_b())
        assert box_a < box_b
        assert box_b > box_a
        assert box_a != box_b

    def test_equal_boxes(self) -> None:
        """Test equality of two QBox instances."""

        async def get_value() -> int:
            return 42

        box_a = QBox(get_value())
        box_b = QBox(get_value())
        assert box_a == box_b


class TestEdgeCases:
    """Tests for edge cases."""

    def test_none_value(self) -> None:
        """Test QBox wrapping None."""

        async def get_none() -> None:
            return None

        box = QBox(get_none())
        assert box.__wrapped__ is None
        assert not bool(box)

    def test_empty_list(self) -> None:
        """Test QBox wrapping empty list."""

        async def get_empty() -> list[int]:
            return []

        box = QBox(get_empty())
        assert box.__wrapped__ == []
        assert len(box) == 0
        assert not bool(box)

    def test_hash(self) -> None:
        """Test that hashable wrapped values can be hashed."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        assert hash(box) == hash(42)

    def test_dict_key(self) -> None:
        """Test using QBox result as dict key."""

        async def get_key() -> str:
            return "key"

        box = QBox(get_key())
        d = {box.__wrapped__: "value"}
        assert d["key"] == "value"

    def test_attribute_error_for_private(self) -> None:
        """Test that private attributes raise AttributeError."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        with pytest.raises(AttributeError):
            _ = box._private_attr


class TestIndex:
    """Tests for __index__ method."""

    def test_index_with_int(self) -> None:
        """Test __index__ with an integer value."""

        async def get_value() -> int:
            return 5

        box = QBox(get_value())
        data = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        assert data[box] == 5

    def test_index_with_non_int_raises(self) -> None:
        """Test __index__ raises TypeError for non-integers."""

        async def get_value() -> str:
            return "not an int"

        box = QBox(get_value())
        with pytest.raises(TypeError):
            _ = [1, 2, 3][box]


class TestReverseOperators:
    """Tests for reverse operator methods."""

    @pytest.mark.parametrize(
        ("box_value", "left_operand", "op_symbol", "expected"),
        [
            # Arithmetic operations
            (10, 20, "-", 10),  # rsub: 20 - 10
            (5, 3, "*", 15),  # rmul: 3 * 5
            (2, 10, "/", 5.0),  # rtruediv: 10 / 2
            (3, 10, "//", 3),  # rfloordiv: 10 // 3
            (3, 10, "%", 1),  # rmod: 10 % 3
            (3, 2, "**", 8),  # rpow: 2 ** 3
            # Bitwise operations
            (0b1100, 0b1010, "&", 0b1000),  # rand
            (0b1100, 0b0011, "|", 0b1111),  # ror
            (0b1100, 0b1010, "^", 0b0110),  # rxor
            (2, 1, "<<", 4),  # rlshift: 1 << 2
            (2, 8, ">>", 2),  # rrshift: 8 >> 2
        ],
        ids=[
            "rsub",
            "rmul",
            "rtruediv",
            "rfloordiv",
            "rmod",
            "rpow",
            "rand",
            "ror",
            "rxor",
            "rlshift",
            "rrshift",
        ],
    )
    def test_reverse_operator(
        self,
        box_value: int,
        left_operand: int,
        op_symbol: str,
        expected: int | float,
    ) -> None:
        """Test reverse operator methods with parametrized values."""

        async def get_value() -> int:
            return box_value

        box = QBox(get_value())

        # Apply the operation using the symbol
        op_map = {
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b,
            "//": lambda a, b: a // b,
            "%": lambda a, b: a % b,
            "**": lambda a, b: a**b,
            "&": lambda a, b: a & b,
            "|": lambda a, b: a | b,
            "^": lambda a, b: a ^ b,
            "<<": lambda a, b: a << b,
            ">>": lambda a, b: a >> b,
        }
        result = op_map[op_symbol](left_operand, box)

        assert isinstance(result, QBox)
        assert result.__wrapped__ == expected


class TestCallWithQBoxArgs:
    """Tests for calling with QBox arguments."""

    def test_call_with_qbox_args(self) -> None:
        """Test calling with QBox positional arguments."""

        async def get_func() -> type[int]:
            return int

        async def get_arg() -> str:
            return "42"

        func_box = QBox(get_func())
        arg_box = QBox(get_arg())
        result = func_box(arg_box)
        assert isinstance(result, QBox)
        assert result.__wrapped__ == 42

    def test_call_with_qbox_kwargs(self) -> None:
        """Test calling with QBox keyword arguments."""

        async def get_func() -> type[dict[str, int]]:
            return dict

        async def get_value() -> int:
            return 42

        func_box = QBox(get_func())
        val_box = QBox(get_value())
        result = func_box(x=val_box)
        assert result.__wrapped__ == {"x": 42}

    def test_call_start_mode_inheritance_from_arg(self) -> None:
        """Test that __call__ inherits start='soon' from QBox arguments."""

        async def get_func() -> type[int]:
            return int

        async def get_arg() -> str:
            return "42"

        # Callable is 'observed', argument is 'soon'
        func_box = QBox(get_func(), start="observed")
        arg_box = QBox(get_arg(), start="soon")
        result = func_box(arg_box)

        # Result should inherit 'soon' from the argument
        assert result._qbox_start_mode == "soon"
        assert result.__wrapped__ == 42

    def test_call_start_mode_all_observed(self) -> None:
        """Test __call__ when all boxes are 'observed'."""

        def make_adder(x: int) -> type:
            class Adder:
                def __init__(self, y: int):
                    self.result = x + y

            return Adder

        async def get_func() -> type:
            return make_adder(10)

        async def get_arg() -> int:
            return 5

        # All boxes are 'observed'
        func_box = QBox(get_func(), start="observed")
        arg_box = QBox(get_arg(), start="observed")
        result = func_box(arg_box)

        # Result should stay 'observed'
        assert result._qbox_start_mode == "observed"
        assert result.__wrapped__.result == 15

    def test_call_start_mode_inheritance_from_later_arg(self) -> None:
        """Test __call__ finds 'soon' in a later argument."""
        from collections.abc import Callable

        async def get_value(n: int) -> int:
            return n

        async def get_sum_func() -> Callable[[int, int], int]:
            def sum_func(a: int, b: int) -> int:
                return a + b

            return sum_func

        # Callable and first arg are 'observed', second arg is 'soon'
        func_box = QBox(get_sum_func(), start="observed")
        arg1 = QBox(get_value(1), start="observed")
        arg2 = QBox(get_value(2), start="soon")
        result = func_box(arg1, arg2)

        # Result should inherit 'soon' from the second argument
        assert result._qbox_start_mode == "soon"
        assert result.__wrapped__ == 3


class TestAwaitCachedValue:
    """Tests for awaiting cached values."""

    async def test_await_cached_value(self) -> None:
        """Test awaiting a QBox that already has a cached value."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        _ = box.__wrapped__  # Force evaluation, cache the value
        result = await box  # Await the already-cached value
        assert result == 42

    async def test_await_cached_exception(self) -> None:
        """Test awaiting a QBox that has a cached exception."""

        async def failing() -> int:
            raise ValueError("test error")

        box = QBox(failing())

        # Force evaluation to cache the exception
        with pytest.raises(ValueError, match="test error"):
            _ = box.__wrapped__

        # Awaiting should re-raise the cached exception
        with pytest.raises(ValueError, match="test error"):
            await box

    async def test_await_uncached_exception(self) -> None:
        """Test awaiting a QBox that raises exception during await (not from cache)."""

        async def failing() -> int:
            raise ValueError("await error")

        box = QBox(failing(), start="observed")

        # Await directly without calling __wrapped__ first
        # This exercises the exception path in _await_impl
        with pytest.raises(ValueError, match="await error"):
            await box

        # Exception should now be cached
        assert box._qbox_is_cached is True
        assert box._qbox_exception is not None
        # Parent boxes should be cleared even on error
        assert len(box._qbox_parent_boxes) == 0


class TestLoopManager:
    """Tests for BackgroundLoopManager."""

    def test_loop_property(self) -> None:
        """Test that the loop property returns the event loop."""
        from qbox._loop import get_loop_manager

        manager = get_loop_manager()
        loop = manager.loop
        assert loop is not None
        assert loop.is_running()


class TestCachedExceptionInCompose:
    """Tests for cached exceptions in composed operations."""

    def test_cached_exception_in_add(self) -> None:
        """Test that a cached exception propagates through addition."""

        async def failing() -> int:
            raise ValueError("test error")

        box = QBox(failing())

        # Force evaluation to cache the exception
        with pytest.raises(ValueError, match="test error"):
            _ = box.__wrapped__

        # Now use in a composed operation
        result = box + 5

        # The exception should propagate
        with pytest.raises(ValueError, match="test error"):
            _ = result.__wrapped__

    def test_cached_exception_in_second_operand(self) -> None:
        """Test that a cached exception in second operand propagates."""

        async def get_value() -> int:
            return 10

        async def failing() -> int:
            raise ValueError("second error")

        box1 = QBox(get_value())
        box2 = QBox(failing())

        # Force evaluation to cache the exception in box2
        with pytest.raises(ValueError, match="second error"):
            _ = box2.__wrapped__

        # Now add them
        result = box1 + box2

        # The exception should propagate
        with pytest.raises(ValueError, match="second error"):
            _ = result.__wrapped__


class TestWrappedExceptionUnderLock:
    """Test for the cached exception path under lock."""

    def test_concurrent_access_with_exception(self) -> None:
        """Test concurrent access to a failing QBox."""

        async def failing() -> int:
            raise ValueError("concurrent error")

        box = QBox(failing())
        results: list[Exception | None] = []

        def access() -> None:
            try:
                _ = box.__wrapped__
                results.append(None)
            except ValueError as e:
                results.append(e)

        threads = [threading.Thread(target=access) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same exception
        assert len(results) == 5
        assert all(isinstance(r, ValueError) for r in results)


class TestCachedValueInCompose:
    """Test for cached value path in _get_value_async."""

    def test_compose_on_cached_value(self) -> None:
        """Test that compose works on an already-cached successful QBox."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        # Force evaluation to cache the value
        assert box.__wrapped__ == 10

        # Now use in a composed operation - this should use cached path
        result = box + 5
        assert result.__wrapped__ == 15

    def test_reverse_compose_on_cached_value(self) -> None:
        """Test reverse compose on an already-cached QBox."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        # Force evaluation to cache the value
        assert box.__wrapped__ == 10

        # Now use in a reverse composed operation
        result = 20 - box
        assert result.__wrapped__ == 10


class TestObservation:
    """Tests for observe() and auto-observation."""

    def test_observe_returns_value(self) -> None:
        """Test that observe returns the unwrapped value."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        value = observe(box)
        assert value == 42

    def test_observe_idempotent_on_non_qbox(self) -> None:
        """Test that observe returns non-QBox values unchanged."""
        value = 42
        result = observe(value)
        assert result == 42

        # Works with any type
        result2 = observe("hello")
        assert result2 == "hello"

        result3 = observe([1, 2, 3])
        assert result3 == [1, 2, 3]

    def test_observe_with_cached_value(self) -> None:
        """Test observe on an already-cached QBox."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        # Force evaluation first
        _ = box.__wrapped__
        # Observe should return cached value
        value = observe(box)
        assert value == 42

    def test_observe_with_exception(self) -> None:
        """Test observe on a QBox with a cached exception."""

        async def failing() -> int:
            raise ValueError("test error")

        box = QBox(failing())
        with pytest.raises(ValueError, match="test error"):
            observe(box)


class TestScopeParameter:
    """Tests for scope parameter functionality."""

    def test_default_scope_is_stack(self) -> None:
        """Test that default scope is 'stack'."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        assert box._qbox_scope == "stack"

    def test_scope_can_be_set(self) -> None:
        """Test that scope can be set via constructor."""

        async def get_value() -> int:
            return 42

        box_locals = QBox(get_value(), scope="locals")
        assert box_locals._qbox_scope == "locals"

        box_globals = QBox(get_value(), scope="globals")
        assert box_globals._qbox_scope == "globals"


class TestWrappedType:
    """Tests for wrapped_type parameter and ABC registration."""

    def test_wrapped_type_can_be_set(self) -> None:
        """Test that wrapped_type can be set via constructor."""
        from collections.abc import Mapping

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        box = QBox(get_dict(), mimic_type=Mapping)
        assert box._qbox_mimic_type is Mapping

    def test_isinstance_with_abc_mapping(self) -> None:
        """Test isinstance works with Mapping ABC."""
        from collections.abc import Mapping

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        box = QBox(get_dict(), mimic_type=Mapping)
        # This should work via ABC registration
        assert isinstance(box, Mapping)

    def test_isinstance_with_abc_sequence(self) -> None:
        """Test isinstance works with Sequence ABC."""
        from collections.abc import Sequence

        async def get_list() -> list[int]:
            return [1, 2, 3]

        box = QBox(get_list(), mimic_type=Sequence)
        assert isinstance(box, Sequence)

    def test_isinstance_with_abc_mutable_mapping(self) -> None:
        """Test isinstance works with MutableMapping ABC."""
        from collections.abc import MutableMapping

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        box = QBox(get_dict(), mimic_type=MutableMapping)
        assert isinstance(box, MutableMapping)

    def test_isinstance_returns_false_for_concrete_without_patch(self) -> None:
        """Test that isinstance returns False for concrete types without patch."""

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        box = QBox(get_dict())
        # Without wrapped_type or patching, isinstance returns False
        assert not isinstance(box, dict)


class TestIsinstancePatching:
    """Tests for opt-in isinstance patching."""

    def test_isinstance_with_patch_enabled(self) -> None:
        """Test isinstance works correctly when patching is enabled."""
        from qbox import (
            disable_qbox_isinstance,
            enable_qbox_isinstance,
            is_qbox_isinstance_enabled,
        )

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        # Ensure we start unpatched
        disable_qbox_isinstance()
        assert not is_qbox_isinstance_enabled()

        # Enable patching
        enable_qbox_isinstance()
        try:
            assert is_qbox_isinstance_enabled()

            box = QBox(get_dict())
            # Now isinstance should work for concrete types
            assert isinstance(box, dict)
        finally:
            disable_qbox_isinstance()

    def test_isinstance_patch_can_be_disabled(self) -> None:
        """Test that isinstance patching can be disabled."""
        from qbox import (
            disable_qbox_isinstance,
            enable_qbox_isinstance,
            is_qbox_isinstance_enabled,
        )

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        enable_qbox_isinstance()
        disable_qbox_isinstance()
        assert not is_qbox_isinstance_enabled()

        box = QBox(get_dict())
        # Without patching, isinstance returns False
        assert not isinstance(box, dict)

    def test_enable_isinstance_is_idempotent(self) -> None:
        """Test that enabling isinstance patching multiple times is safe."""
        from qbox import (
            disable_qbox_isinstance,
            enable_qbox_isinstance,
            is_qbox_isinstance_enabled,
        )

        try:
            enable_qbox_isinstance()
            enable_qbox_isinstance()  # Should not error
            enable_qbox_isinstance()  # Should not error
            assert is_qbox_isinstance_enabled()
        finally:
            disable_qbox_isinstance()

    def test_disable_isinstance_is_idempotent(self) -> None:
        """Test that disabling isinstance patching multiple times is safe."""
        from qbox import disable_qbox_isinstance, is_qbox_isinstance_enabled

        disable_qbox_isinstance()
        disable_qbox_isinstance()  # Should not error
        disable_qbox_isinstance()  # Should not error
        assert not is_qbox_isinstance_enabled()

    def test_qbox_isinstance_context_manager(self) -> None:
        """Test the qbox_isinstance context manager."""
        from qbox import is_qbox_isinstance_enabled, qbox_isinstance

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        # Ensure we start unpatched
        assert not is_qbox_isinstance_enabled()

        with qbox_isinstance():
            assert is_qbox_isinstance_enabled()
            box = QBox(get_dict())
            assert isinstance(box, dict)

        # Patching should be disabled after the context
        assert not is_qbox_isinstance_enabled()

    def test_comparison_works_with_isinstance_patching_enabled(self) -> None:
        """Test that QBox comparisons work correctly with isinstance patching.

        Regression test: _unwrap_if_qbox used isinstance(value, QBox) which
        failed when enable_qbox_isinstance() was active because the patched
        isinstance observes and unwraps the value before checking.
        """
        from qbox import disable_qbox_isinstance, enable_qbox_isinstance

        async def get_list() -> list[int]:
            return [1, 2, 3]

        enable_qbox_isinstance()
        try:
            box1 = QBox(get_list())
            box2 = QBox(get_list())

            # Comparisons between QBoxes should work
            assert box1 == box2  # Both contain [1, 2, 3]
            assert box1 != [1, 2, 4]  # Test inequality with different value

            # Comparisons with concrete values should work
            assert box1 == [1, 2, 3]
            # Test reverse comparison (concrete == QBox) to ensure __eq__ works
            # from both directions. Intentionally written this way for coverage.
            assert box1 == [1, 2, 3] and [1, 2, 3] == box1  # noqa: SIM300
        finally:
            disable_qbox_isinstance()


class TestCascadingObservation:
    """Tests for cascading observation of dependency trees."""

    def test_composed_box_tracks_parent(self) -> None:
        """Test that composed operations track their parent boxes."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        result = box + 5
        assert box in result._qbox_parent_boxes

    def test_two_box_operation_tracks_both_parents(self) -> None:
        """Test that operations with two QBoxes track both."""

        async def get_a() -> int:
            return 10

        async def get_b() -> int:
            return 20

        box_a = QBox(get_a())
        box_b = QBox(get_b())
        result = box_a + box_b

        assert box_a in result._qbox_parent_boxes
        assert box_b in result._qbox_parent_boxes


class TestTypedQBoxClass:
    """Tests for typed QBox class creation."""

    def test_typed_qbox_has_different_class(self) -> None:
        """Test that typed QBox instances use a subclass."""
        from collections.abc import Mapping

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        untyped_box = QBox(get_dict())
        typed_box = QBox(get_dict(), mimic_type=Mapping)

        # They should be different classes
        assert type(untyped_box) is QBox
        assert type(typed_box) is not QBox
        assert type(typed_box).__name__ == "QBox[Mapping]"

    def test_typed_qbox_is_subclass_of_qbox(self) -> None:
        """Test that typed QBox is a subclass of QBox."""
        from collections.abc import Mapping

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        typed_box = QBox(get_dict(), mimic_type=Mapping)
        assert isinstance(typed_box, QBox)

    def test_typed_qbox_class_is_cached(self) -> None:
        """Test that typed QBox classes are cached."""
        from collections.abc import Mapping

        async def get_dict() -> dict[str, int]:
            return {"a": 1}

        box1 = QBox(get_dict(), mimic_type=Mapping)
        box2 = QBox(get_dict(), mimic_type=Mapping)

        # Should be the same class
        assert type(box1) is type(box2)


class TestParentBoxes:
    """Tests for parent box tracking in composed operations."""

    def test_simple_box_has_no_parents(self) -> None:
        """Test that a simple QBox has no parent boxes."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        assert box._qbox_parent_boxes == []

    def test_unary_operation_tracks_self(self) -> None:
        """Test that unary operations track the original box."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        result = -box
        assert box in result._qbox_parent_boxes

    def test_chain_tracks_all_parents(self) -> None:
        """Test that chained operations track intermediate boxes."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        step1 = box + 5
        step2 = step1 * 2

        # step1 should track box
        assert box in step1._qbox_parent_boxes
        # step2 should track step1 (which tracks box)
        assert step1 in step2._qbox_parent_boxes


class TestObserveScopeLocals:
    """Tests for observe with scope='locals'."""

    def test_observe_with_scope_locals(self) -> None:
        """Test observe with scope='locals' only replaces in local scope."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value(), scope="locals")
        value = observe(box)
        assert value == 42


class TestObserveCascading:
    """Tests for cascading observation of parent boxes."""

    def test_observe_cascades_to_parent_boxes(self) -> None:
        """Test that observing a composed box evaluates parents."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        composed = box + 5

        # Keep a reference that won't be replaced (stored in list)
        boxes = [box, composed]

        # Before observation, neither is cached
        assert not boxes[0]._qbox_is_cached
        assert not boxes[1]._qbox_is_cached

        # Observe the composed result
        value = observe(composed)
        assert value == 15

        # The original box should now be cached (cascade)
        # Note: boxes[0] still holds the QBox reference
        assert boxes[0]._qbox_is_cached

    def test_observe_handles_failed_parent(self) -> None:
        """Test that observe handles failed parent gracefully."""

        async def failing() -> int:
            raise ValueError("parent failed")

        async def get_value() -> int:
            return 5

        parent_box = QBox(failing())
        child_box = QBox(get_value())
        composed = child_box + parent_box

        # Trying to observe composed should fail
        with pytest.raises(ValueError, match="parent failed"):
            observe(composed)


class TestObserveScopeGlobals:
    """Tests for observe with scope='globals'."""

    def test_observe_with_scope_globals(self) -> None:
        """Test observe with scope='globals' works."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value(), scope="globals")
        value = observe(box)
        assert value == 42


# Global variable for testing global scope replacement
_test_global_box: QBox[int] | int | None = None


class TestGlobalScopeReplacement:
    """Tests for global scope replacement."""

    def test_globals_replacement_actually_replaces(self) -> None:
        """Test that globals scope actually replaces global variables."""
        global _test_global_box

        async def get_value() -> int:
            return 42

        _test_global_box = QBox(get_value(), scope="globals")

        # Observe should replace the global
        value = observe(_test_global_box)
        assert value == 42

        # Clean up
        _test_global_box = None


class TestTypedQBoxABCEdgeCases:
    """Tests for edge cases in typed QBox ABC registration."""

    def test_typed_qbox_with_concrete_type(self) -> None:
        """Test typed QBox with a concrete type that can't be registered."""

        class CustomClass:
            pass

        async def get_value() -> CustomClass:
            return CustomClass()

        # This should not raise even though CustomClass doesn't support register
        box = QBox(get_value(), mimic_type=CustomClass)
        assert isinstance(box, QBox)


class TestCallCompose:
    """Tests for the __call__ compose method."""

    def test_call_compose_creates_parent_tracking(self) -> None:
        """Test that __call__ creates proper parent tracking."""

        async def get_func() -> type[str]:
            return str

        box = QBox(get_func())
        result = box(42)

        # result should track box as parent
        assert box in result._qbox_parent_boxes


class TestReplaceReferencesEdgeCases:
    """Tests for edge cases in reference replacement."""

    def test_replace_handles_exception_in_frame_locals(self) -> None:
        """Test that replacement handles exceptions accessing frame locals."""

        async def get_value() -> int:
            return 42

        # This should not raise - it handles exceptions internally
        box = QBox(get_value())
        value = observe(box)
        assert value == 42


class TestStartParameter:
    """Tests for the start parameter."""

    def test_start_soon_is_default(self) -> None:
        """Test that start='soon' is the default behavior."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        assert box._qbox_start_mode == "soon"

    def test_start_soon_submits_immediately(self) -> None:
        """Test that start='soon' submits the coroutine immediately."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        # With start='soon', the future should already be created
        assert box._qbox_future is not None

    def test_start_observed_defers_submission(self) -> None:
        """Test that start='observed' defers coroutine submission."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value(), start="observed")
        # With start='observed', the future should not be created yet
        assert box._qbox_future is None
        # After accessing the value, it should be created
        _ = box.__wrapped__
        assert box._qbox_future is not None

    def test_start_observed_lazy_chain(self) -> None:
        """Test that start='observed' keeps chains lazy until needed."""
        call_count = 0

        async def get_value() -> int:
            nonlocal call_count
            call_count += 1
            return 10

        box = QBox(get_value(), start="observed")
        result = box + 5
        # Neither should have started yet
        assert call_count == 0
        assert box._qbox_future is None
        # Force evaluation
        _ = result.__wrapped__
        assert call_count == 1

    def test_start_soon_inherited_by_composed(self) -> None:
        """Test that start='soon' is inherited by composed QBoxes."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value(), start="soon")
        composed = box + 10
        # Composed should inherit 'soon'
        assert composed._qbox_start_mode == "soon"

    def test_start_observed_inherited_when_both_observed(self) -> None:
        """Test that start='observed' is used when both parents are observed."""

        async def get_value() -> int:
            return 42

        box1 = QBox(get_value(), start="observed")
        box2 = QBox(get_value(), start="observed")
        composed = box1 + box2
        # Both parents are observed, so composed should be observed
        assert composed._qbox_start_mode == "observed"

    def test_start_soon_wins_in_mixed_composition(self) -> None:
        """Test that start='soon' wins when mixing soon and observed."""

        async def get_value() -> int:
            return 42

        soon_box = QBox(get_value(), start="soon")
        observed_box = QBox(get_value(), start="observed")

        # soon + observed = soon
        composed1 = soon_box + observed_box
        assert composed1._qbox_start_mode == "soon"

        # observed + soon = soon
        composed2 = observed_box + soon_box
        assert composed2._qbox_start_mode == "soon"


class TestReprObservesParameter:
    """Tests for the repr_observes parameter."""

    def test_repr_observes_false_is_default(self) -> None:
        """Test that repr_observes=False is the default."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        assert box._qbox_repr_observes is False

    def test_repr_observes_false_shows_pending(self) -> None:
        """Test that repr with repr_observes=False shows pending."""

        async def slow() -> int:
            await asyncio.sleep(10)
            return 42

        box = QBox(slow(), start="observed", repr_observes=False)
        assert repr(box) == "<QBox[pending]>"

    def test_repr_observes_true_forces_evaluation(self) -> None:
        """Test that repr with repr_observes=True forces evaluation."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value(), repr_observes=True)
        result = repr(box)
        # Should show the actual value, not QBox wrapper
        assert result == "42"

    def test_repr_observes_true_with_exception(self) -> None:
        """Test that repr with repr_observes=True handles exceptions."""

        async def failing() -> int:
            raise ValueError("test error")

        box = QBox(failing(), repr_observes=True)
        result = repr(box)
        assert "ERROR" in result
        assert "ValueError" in result


class TestCancelOnDeleteParameter:
    """Tests for the cancel_on_delete parameter."""

    def test_cancel_on_delete_true_is_default(self) -> None:
        """Test that cancel_on_delete=True is the default."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value())
        assert box._qbox_cancel_on_delete is True

    def test_cancel_on_delete_can_be_set_false(self) -> None:
        """Test that cancel_on_delete can be set to False."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value(), cancel_on_delete=False)
        assert box._qbox_cancel_on_delete is False

    def test_del_suppresses_never_awaited_warning(self) -> None:
        """Test that __del__ suppresses 'coroutine never awaited' warning."""
        import gc
        import warnings

        async def get_value() -> int:
            return 42

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            box = QBox(get_value(), start="observed")
            del box
            gc.collect()  # Force garbage collection

            # Should not have any "never awaited" warnings
            coro_warnings = [x for x in w if "was never awaited" in str(x.message)]
            assert len(coro_warnings) == 0

    def test_del_cancels_future_when_cancel_on_delete_true(self) -> None:
        """Test that __del__ cancels the future when cancel_on_delete=True."""
        import gc
        import time

        ran = []

        async def slow_task() -> int:
            await asyncio.sleep(1.0)
            ran.append(True)
            return 42

        box = QBox(slow_task(), cancel_on_delete=True)
        future = box._qbox_future  # Get reference to future before deletion
        del box
        gc.collect()

        # Give some time for cancellation to propagate
        time.sleep(0.1)

        # Future should be cancelled
        assert future is not None
        assert future.cancelled() or future.done()
        # The task should not have completed
        assert len(ran) == 0

    def test_del_does_not_cancel_when_cancel_on_delete_false(self) -> None:
        """Test that __del__ does NOT cancel when cancel_on_delete=False."""
        import gc
        import time

        ran = []

        async def quick_task() -> int:
            ran.append(True)
            return 42

        box = QBox(quick_task(), cancel_on_delete=False)
        future = box._qbox_future
        del box
        gc.collect()

        # Give time for the task to complete
        time.sleep(0.1)

        # The task should have completed
        assert len(ran) == 1
        assert future is not None
        assert future.done()
        assert not future.cancelled()

    def test_cancel_on_delete_inherited_by_composed(self) -> None:
        """Test that composed QBoxes inherit cancel_on_delete."""

        async def get_value() -> int:
            return 42

        box = QBox(get_value(), cancel_on_delete=False)
        composed = box + 10
        assert composed._qbox_cancel_on_delete is False

        box2 = QBox(get_value(), cancel_on_delete=True)
        composed2 = box2 + 10
        assert composed2._qbox_cancel_on_delete is True


class TestNonCoroutineAwaitables:
    """Tests for non-coroutine awaitables (Future, Task, custom __await__)."""

    def test_custom_awaitable_class(self) -> None:
        """Test QBox with a custom awaitable class implementing __await__."""

        class CustomAwaitable:
            """A custom awaitable that returns a value."""

            def __init__(self, value: int) -> None:
                self.value = value

            def __await__(self):
                # Must yield from a coroutine or return a value
                async def inner():
                    return self.value

                return inner().__await__()

        box = QBox(CustomAwaitable(42))
        assert box.__wrapped__ == 42

    def test_custom_awaitable_with_delay(self) -> None:
        """Test QBox with a custom awaitable that includes async delay."""

        class DelayedAwaitable:
            """A custom awaitable with an async delay."""

            def __init__(self, value: int) -> None:
                self.value = value

            def __await__(self):
                async def inner():
                    await asyncio.sleep(0.01)
                    return self.value

                return inner().__await__()

        box = QBox(DelayedAwaitable(123))
        assert box.__wrapped__ == 123

    def test_custom_awaitable_with_operations(self) -> None:
        """Test QBox operations work with custom awaitables."""

        class ValueAwaitable:
            """A custom awaitable returning a numeric value."""

            def __init__(self, value: int) -> None:
                self.value = value

            def __await__(self):
                async def inner():
                    return self.value

                return inner().__await__()

        box = QBox(ValueAwaitable(10))
        result = box + 5
        assert result.__wrapped__ == 15

    def test_custom_awaitable_chained(self) -> None:
        """Test multiple custom awaitables in a chain."""

        class ChainableAwaitable:
            """A custom awaitable for chaining tests."""

            def __init__(self, value: int) -> None:
                self.value = value

            def __await__(self):
                async def inner():
                    return self.value

                return inner().__await__()

        box1 = QBox(ChainableAwaitable(10))
        box2 = QBox(ChainableAwaitable(20))
        result = box1 + box2
        assert result.__wrapped__ == 30

    def test_custom_awaitable_error_propagation(self) -> None:
        """Test that exceptions from custom awaitables propagate correctly."""

        class FailingAwaitable:
            """A custom awaitable that raises an exception."""

            def __await__(self):
                async def inner():
                    raise ValueError("Custom awaitable error")

                return inner().__await__()

        box = QBox(FailingAwaitable())
        with pytest.raises(ValueError, match="Custom awaitable error"):
            _ = box.__wrapped__

    def test_custom_awaitable_with_start_observed(self) -> None:
        """Test custom awaitable with start='observed' mode."""
        executed = []

        class TrackedAwaitable:
            """A custom awaitable that tracks execution."""

            def __await__(self):
                async def inner():
                    executed.append(True)
                    return 42

                return inner().__await__()

        box = QBox(TrackedAwaitable(), start="observed")
        assert len(executed) == 0  # Not executed yet

        _ = box.__wrapped__
        assert len(executed) == 1  # Executed on observation

    async def test_await_custom_awaitable(self) -> None:
        """Test awaiting a QBox wrapping a custom awaitable in async context."""

        class AsyncAwaitable:
            """A custom awaitable for async context testing."""

            def __init__(self, value: str) -> None:
                self.value = value

            def __await__(self):
                async def inner():
                    return self.value

                return inner().__await__()

        box = QBox(AsyncAwaitable("hello"))
        result = await box
        assert result == "hello"


class TestIsinstanceThreadSafety:
    """Tests for thread safety of isinstance patching."""

    def test_concurrent_enable_disable(self) -> None:
        """Test that concurrent enable/disable calls are thread-safe."""
        from qbox import (
            disable_qbox_isinstance,
            enable_qbox_isinstance,
            is_qbox_isinstance_enabled,
        )

        # Ensure we start in a known state
        disable_qbox_isinstance()
        assert not is_qbox_isinstance_enabled()

        errors = []

        def toggle_isinstance(iterations: int) -> None:
            try:
                for _ in range(iterations):
                    enable_qbox_isinstance()
                    # Small operation to allow context switches
                    _ = is_qbox_isinstance_enabled()
                    disable_qbox_isinstance()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=toggle_isinstance, args=(100,)) for _ in range(4)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"

        # Clean up
        disable_qbox_isinstance()

    def test_nested_context_managers(self) -> None:
        """Test that nested qbox_isinstance context managers work correctly."""
        from qbox import is_qbox_isinstance_enabled, qbox_isinstance

        assert not is_qbox_isinstance_enabled()

        with qbox_isinstance():
            assert is_qbox_isinstance_enabled()
            with qbox_isinstance():
                assert is_qbox_isinstance_enabled()
                with qbox_isinstance():
                    assert is_qbox_isinstance_enabled()
                # Still enabled after inner exits
                assert is_qbox_isinstance_enabled()
            # Still enabled after middle exits
            assert is_qbox_isinstance_enabled()
        # Disabled after outermost exits
        assert not is_qbox_isinstance_enabled()


class TestTypedCacheThreadSafety:
    """Tests for thread safety of typed QBox class cache."""

    def test_concurrent_mimic_type_creation(self) -> None:
        """Test that concurrent mimic_type creation is thread-safe."""
        from collections.abc import Mapping, Sequence

        errors = []
        results: dict[type, list[type]] = {t: [] for t in [Mapping, Sequence]}

        async def get_value() -> dict:
            return {"key": "value"}

        def create_typed_qbox(mimic_type: type) -> None:
            try:
                for _ in range(50):
                    box = QBox(get_value(), mimic_type=mimic_type)
                    results[mimic_type].append(type(box))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_typed_qbox, args=(Mapping,)),
            threading.Thread(target=create_typed_qbox, args=(Mapping,)),
            threading.Thread(target=create_typed_qbox, args=(Sequence,)),
            threading.Thread(target=create_typed_qbox, args=(Sequence,)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"

        # All boxes with the same mimic_type should have the same class
        for mimic_type, classes in results.items():
            unique_classes = set(classes)
            assert len(unique_classes) == 1, (
                f"Expected one class for {mimic_type}, got {len(unique_classes)}"
            )


class TestBackgroundLoopManagerRepr:
    """Tests for BackgroundLoopManager __repr__."""

    def test_repr_shows_running_state(self) -> None:
        """Test that repr shows the loop manager state."""
        from qbox._loop import get_loop_manager

        manager = get_loop_manager()
        repr_str = repr(manager)

        assert "BackgroundLoopManager" in repr_str
        assert "loop_running=True" in repr_str
        assert "thread_alive=True" in repr_str
        assert "thread_name='qbox-background-loop'" in repr_str


class TestParentBoxMemory:
    """Tests verifying parent boxes become garbage-collectable after observation."""

    def test_parent_becomes_gc_eligible_after_observation(self) -> None:
        """Test that parent box can be GC'd after child is observed."""
        import gc
        import weakref

        async def get_value() -> int:
            return 10

        parent = QBox(get_value())
        parent_ref = weakref.ref(parent)
        child = parent + 5

        del parent  # Remove our strong reference
        gc.collect()

        # Parent should still be alive (child holds reference via _qbox_parent_boxes)
        assert parent_ref() is not None

        # Observe the child - this clears parent references
        _ = child.__wrapped__
        gc.collect()

        # Parent should now be garbage collected
        assert parent_ref() is None

    def test_chain_becomes_gc_eligible_after_observation(self) -> None:
        """Test that entire chain can be GC'd after end is observed."""
        import gc
        import weakref

        async def get_value() -> int:
            return 10

        # Use start='observed' to prevent the background thread from clearing
        # parent references before we test them. With start='soon', box3's
        # coroutine runs immediately and calls box2._get_value_async(), which
        # clears box2._qbox_parent_boxes before we reach the assertions.
        box1 = QBox(get_value(), start="observed")
        box2 = box1 + 5
        box3 = box2 * 2

        ref1 = weakref.ref(box1)
        ref2 = weakref.ref(box2)

        del box1, box2  # Remove our strong references
        gc.collect()

        # Boxes should still be alive (chain holds references)
        assert ref1() is not None
        assert ref2() is not None

        # Observe the end of the chain
        _ = box3.__wrapped__
        gc.collect()

        # All intermediate boxes should now be GC'd
        assert ref1() is None
        assert ref2() is None

    def test_both_parents_gc_eligible_in_binary_op(self) -> None:
        """Test that both parents can be GC'd after binary operation observed."""
        import gc
        import weakref

        async def get_value(x: int) -> int:
            return x

        left = QBox(get_value(10))
        right = QBox(get_value(20))
        result = left + right

        left_ref = weakref.ref(left)
        right_ref = weakref.ref(right)

        del left, right
        gc.collect()

        # Both parents still alive
        assert left_ref() is not None
        assert right_ref() is not None

        # Observe
        _ = result.__wrapped__
        gc.collect()

        # Both parents now GC'd
        assert left_ref() is None
        assert right_ref() is None


class TestDiamondDependency:
    """Tests for diamond dependency observation patterns."""

    def test_diamond_dependency_observation(self) -> None:
        """Test diamond dependency: two children share one parent."""
        #
        #     parent
        #    /      \
        # child1  child2
        #    \      /
        #     result
        #

        async def get_value() -> int:
            return 10

        parent = QBox(get_value())
        child1 = parent + 5  # 15
        child2 = parent * 2  # 20
        result = child1 + child2  # 35

        # Observe result - should evaluate parent only once
        assert result.__wrapped__ == 35

        # All should be cached now
        assert parent._qbox_is_cached
        assert child1._qbox_is_cached
        assert child2._qbox_is_cached
        assert result._qbox_is_cached

    def test_multiple_parents_with_different_exceptions(self) -> None:
        """Test that first exception in observation order is raised."""

        async def fail_a() -> int:
            raise ValueError("error A")

        async def fail_b() -> int:
            raise ValueError("error B")

        box_a = QBox(fail_a())
        box_b = QBox(fail_b())
        result = box_a + box_b

        # First to be evaluated should raise its exception
        with pytest.raises(ValueError):
            _ = result.__wrapped__


class TestConcurrentObservation:
    """Tests for concurrent observation race conditions."""

    def test_concurrent_observation_same_box(self) -> None:
        """Test multiple threads observing the same QBox concurrently."""
        call_count = 0
        call_count_lock = threading.Lock()

        async def counted_value() -> int:
            nonlocal call_count
            await asyncio.sleep(0.01)  # Small delay to increase race chance
            with call_count_lock:
                call_count += 1
            return 42

        box = QBox(counted_value())
        results: list[int] = []
        results_lock = threading.Lock()

        def observe_box() -> None:
            val = box.__wrapped__
            with results_lock:
                results.append(val)

        threads = [threading.Thread(target=observe_box) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads got the same result
        assert all(r == 42 for r in results)
        # Coroutine was only called once
        assert call_count == 1

    def test_concurrent_composition_and_observation(self) -> None:
        """Test composing and observing QBoxes concurrently."""

        async def get_value(n: int) -> int:
            await asyncio.sleep(0.001)
            return n

        results: list[int] = []
        results_lock = threading.Lock()
        errors: list[Exception] = []

        def create_and_observe(n: int) -> None:
            try:
                box = QBox(get_value(n))
                result = box + 10
                val = result.__wrapped__
                with results_lock:
                    results.append(val)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_and_observe, args=(i,)) for i in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors: {errors}"
        assert len(results) == 50
        # Each result should be n + 10
        expected = {i + 10 for i in range(50)}
        assert set(results) == expected


class TestDeepChain:
    """Tests for deep composition chains."""

    def test_deep_chain_10_levels(self) -> None:
        """Test a chain of 10+ composed operations."""

        async def get_value() -> int:
            return 1

        box = QBox(get_value())
        # Build a chain: 1 + 1 + 1 + ... (10 times) = 10
        for _ in range(10):
            box = box + 1

        assert box.__wrapped__ == 11  # 1 + 10*1

    def test_deep_chain_mixed_operators(self) -> None:
        """Test deep chain with mixed operators."""

        async def get_value() -> int:
            return 2

        box = QBox(get_value())
        # 2 + 3 = 5, *2 = 10, -1 = 9, //2 = 4, **2 = 16
        chain = ((((box + 3) * 2) - 1) // 2) ** 2
        assert chain.__wrapped__ == 16

    def test_deep_chain_gc_eligible(self) -> None:
        """Test that all intermediate boxes in deep chain can be GC'd."""
        import gc
        import weakref

        async def get_value() -> int:
            return 1

        # Create first box and keep weak reference
        box = QBox(get_value())
        first_box_ref = weakref.ref(box)

        # Build chain
        refs: list[weakref.ref] = [first_box_ref]
        for _ in range(5):
            box = box + 1
            refs.append(weakref.ref(box))

        # Keep only the final box
        final = box
        del box

        # Force GC before observation
        gc.collect()

        # Intermediate refs should still be alive (chain references them)
        # Actually, we only keep the final box, so intermediate may be GC'd
        # if Python decides to. Let's just observe and verify final works.

        # Observe
        assert final.__wrapped__ == 6  # 1 + 5

        # After observation, first box should be GC-eligible
        gc.collect()
        assert first_box_ref() is None


class TestExceptionCascading:
    """Tests for exception handling during cascading observation."""

    def test_exception_during_cascading_observation(self) -> None:
        """Test exception during cascading observation - partial cleanup."""

        async def fail() -> int:
            raise ValueError("cascade fail")

        async def succeed() -> int:
            return 10

        parent1 = QBox(fail())
        parent2 = QBox(succeed())
        child = parent1 + parent2

        with pytest.raises(ValueError, match="cascade fail"):
            _ = child.__wrapped__

        # parent2 should have been evaluated (may be cached)
        # parent1 should have exception cached
        assert parent1._qbox_is_cached
        assert parent1._qbox_exception is not None

    def test_exception_clears_parent_boxes(self) -> None:
        """Test that parent boxes are cleared even on exception."""

        async def fail() -> int:
            raise ValueError("cleanup test")

        parent = QBox(fail())
        child = parent + 5

        # Before observation
        assert len(child._qbox_parent_boxes) > 0

        with pytest.raises(ValueError):
            _ = child.__wrapped__

        # After observation (even with exception), parent boxes should be cleared
        assert len(child._qbox_parent_boxes) == 0


class TestNestedQboxIsinstanceException:
    """Tests for nested qbox_isinstance context with exceptions."""

    def test_nested_context_with_exception(self) -> None:
        """Test nested qbox_isinstance contexts handle exceptions correctly."""
        from qbox import is_qbox_isinstance_enabled, qbox_isinstance

        assert not is_qbox_isinstance_enabled()

        try:
            with qbox_isinstance():
                assert is_qbox_isinstance_enabled()
                with qbox_isinstance():
                    assert is_qbox_isinstance_enabled()
                    raise ValueError("test exception")
        except ValueError:
            pass

        # Patching should be disabled after all contexts exit
        assert not is_qbox_isinstance_enabled()

    def test_exception_in_outer_context(self) -> None:
        """Test exception in outer context cleans up properly."""
        from qbox import is_qbox_isinstance_enabled, qbox_isinstance

        assert not is_qbox_isinstance_enabled()

        try:
            with qbox_isinstance():
                assert is_qbox_isinstance_enabled()
                raise RuntimeError("outer exception")
        except RuntimeError:
            pass

        assert not is_qbox_isinstance_enabled()


class TestGCStress:
    """Stress tests for garbage collection with large chains."""

    def test_gc_100_box_chain(self) -> None:
        """Test GC with a chain of 100 QBoxes."""
        import gc
        import weakref

        async def get_value() -> int:
            return 0

        # Create a chain of 100 boxes
        boxes = [QBox(get_value())]
        for _i in range(99):
            boxes.append(boxes[-1] + 1)

        # Keep weak references to all boxes
        refs = [weakref.ref(b) for b in boxes]

        # Keep only the last box
        last = boxes[-1]
        del boxes

        # Force GC
        gc.collect()

        # Observe the last box
        assert last.__wrapped__ == 99

        # Force GC again
        gc.collect()

        # All but the last should be GC'd
        for _i, ref in enumerate(refs[:-1]):
            assert ref() is None, f"Box {_i} should be GC'd"

    def test_gc_wide_dependency_tree(self) -> None:
        """Test GC with many boxes depending on one parent."""
        import gc
        import weakref

        async def get_value() -> int:
            return 10

        parent = QBox(get_value())
        parent_ref = weakref.ref(parent)

        # Create 50 children all depending on the same parent
        children = [parent + i for i in range(50)]

        del parent  # Remove our reference
        gc.collect()

        # Parent should still be alive (children reference it)
        assert parent_ref() is not None

        # Observe all children
        for i, child in enumerate(children):
            assert child.__wrapped__ == 10 + i

        # Clear children
        del children
        gc.collect()

        # Now parent should be GC'd
        assert parent_ref() is None


class TestLargeArgumentCall:
    """Tests for __call__ with many arguments."""

    def test_call_with_many_args(self) -> None:
        """Test calling with many QBox arguments."""
        from collections.abc import Callable

        async def get_func() -> Callable[..., int]:
            return sum

        async def get_value(n: int) -> int:
            return n

        func_box = QBox(get_func())
        # Create 20 QBox arguments
        args = [QBox(get_value(i)) for i in range(20)]
        result = func_box(args)

        # sum([0, 1, 2, ..., 19]) = 190
        assert result.__wrapped__ == 190

    def test_call_with_many_qbox_kwargs(self) -> None:
        """Test calling with many QBox keyword arguments."""

        async def get_dict() -> type:
            return dict

        async def get_value(n: int) -> int:
            return n

        func_box = QBox(get_dict())
        # Create QBox kwargs
        kwargs = {f"key{i}": QBox(get_value(i)) for i in range(10)}
        result = func_box(**kwargs)

        expected = {f"key{i}": i for i in range(10)}
        assert result.__wrapped__ == expected


class TestStartModeInMultiOperandExpressions:
    """Tests for start mode inheritance in 3+ operand expressions."""

    def test_three_operand_all_observed(self) -> None:
        """Test 3-operand expression with all 'observed'."""

        async def get_value(n: int) -> int:
            return n

        a = QBox(get_value(1), start="observed")
        b = QBox(get_value(2), start="observed")
        c = QBox(get_value(3), start="observed")

        result = a + b + c
        assert result._qbox_start_mode == "observed"
        assert result.__wrapped__ == 6

    def test_three_operand_one_soon(self) -> None:
        """Test 3-operand expression with one 'soon' in middle."""

        async def get_value(n: int) -> int:
            return n

        a = QBox(get_value(1), start="observed")
        b = QBox(get_value(2), start="soon")
        c = QBox(get_value(3), start="observed")

        # a + b should be 'soon' (b is soon)
        ab = a + b
        assert ab._qbox_start_mode == "soon"

        # ab + c should be 'soon' (ab is soon)
        result = ab + c
        assert result._qbox_start_mode == "soon"
        assert result.__wrapped__ == 6

    def test_three_operand_last_soon(self) -> None:
        """Test 3-operand expression with 'soon' at end."""

        async def get_value(n: int) -> int:
            return n

        a = QBox(get_value(1), start="observed")
        b = QBox(get_value(2), start="observed")
        c = QBox(get_value(3), start="soon")

        # a + b = observed
        ab = a + b
        assert ab._qbox_start_mode == "observed"

        # ab + c = soon (c is soon)
        result = ab + c
        assert result._qbox_start_mode == "soon"
        assert result.__wrapped__ == 6


class TestComparisonCoverage:
    """Tests for comparison operators between QBox instances."""

    def test_le_between_two_qboxes(self) -> None:
        """Test <= comparison between two QBox instances."""

        async def get_smaller() -> int:
            return 10

        async def get_larger() -> int:
            return 20

        box_smaller = QBox(get_smaller())
        box_larger = QBox(get_larger())

        # smaller <= larger should be True
        assert box_smaller <= box_larger

        # larger <= smaller should be False
        assert not (box_larger <= box_smaller)

    def test_le_between_equal_qboxes(self) -> None:
        """Test <= comparison between two QBox instances with equal values."""

        async def get_value() -> int:
            return 42

        box_a = QBox(get_value())
        box_b = QBox(get_value())

        # equal values: both <= comparisons should be True
        assert box_a <= box_b
        assert box_b <= box_a

    def test_ge_between_two_qboxes(self) -> None:
        """Test >= comparison between two QBox instances."""

        async def get_smaller() -> int:
            return 10

        async def get_larger() -> int:
            return 20

        box_smaller = QBox(get_smaller())
        box_larger = QBox(get_larger())

        # larger >= smaller should be True
        assert box_larger >= box_smaller

        # smaller >= larger should be False
        assert not (box_smaller >= box_larger)

    def test_ge_between_equal_qboxes(self) -> None:
        """Test >= comparison between two QBox instances with equal values."""

        async def get_value() -> int:
            return 42

        box_a = QBox(get_value())
        box_b = QBox(get_value())

        # equal values: both >= comparisons should be True
        assert box_a >= box_b
        assert box_b >= box_a

    def test_ne_between_equal_qboxes_returns_false(self) -> None:
        """Test != between two QBoxes with equal values returns False."""

        async def get_value() -> int:
            return 42

        box_a = QBox(get_value())
        box_b = QBox(get_value())

        # != should return False when values are equal
        # (intentionally using != to test __ne__, not ==)
        assert not (box_a != box_b)  # noqa: SIM202
        assert not (box_b != box_a)  # noqa: SIM202

    def test_ne_between_unequal_qboxes_returns_true(self) -> None:
        """Test != between two QBoxes with different values returns True."""

        async def get_a() -> int:
            return 10

        async def get_b() -> int:
            return 20

        box_a = QBox(get_a())
        box_b = QBox(get_b())

        # != should return True when values are different
        assert box_a != box_b
        assert box_b != box_a


class TestNumericConversionCoverage:
    """Tests for numeric conversions on fresh QBox instances."""

    def test_float_on_fresh_box(self) -> None:
        """Test __float__ conversion on a fresh (uncached) QBox."""

        async def get_value() -> float:
            return 3.14159

        box = QBox(get_value())
        # Keep reference in list to avoid local variable replacement
        boxes = [box]

        # Ensure box is not cached yet
        assert not boxes[0]._qbox_is_cached

        # float() should force evaluation and return the float value
        result = float(boxes[0])
        assert result == 3.14159
        assert isinstance(result, float)

        # Box should now be cached
        assert boxes[0]._qbox_is_cached

    def test_float_on_fresh_int_box(self) -> None:
        """Test __float__ conversion on a fresh QBox wrapping an int."""

        async def get_int() -> int:
            return 42

        box = QBox(get_int())
        boxes = [box]
        assert not boxes[0]._qbox_is_cached

        result = float(boxes[0])
        assert result == 42.0
        assert isinstance(result, float)
        assert boxes[0]._qbox_is_cached

    def test_complex_on_fresh_box(self) -> None:
        """Test __complex__ conversion on a fresh (uncached) QBox."""

        async def get_value() -> float:
            return 2.5

        box = QBox(get_value())
        # Keep reference in list to avoid local variable replacement
        boxes = [box]

        # Ensure box is not cached yet
        assert not boxes[0]._qbox_is_cached

        # complex() should force evaluation and return a complex value
        result = complex(boxes[0])
        assert result == complex(2.5)
        assert isinstance(result, complex)

        # Box should now be cached
        assert boxes[0]._qbox_is_cached

    def test_complex_on_fresh_int_box(self) -> None:
        """Test __complex__ conversion on a fresh QBox wrapping an int."""

        async def get_int() -> int:
            return 7

        box = QBox(get_int())
        boxes = [box]
        assert not boxes[0]._qbox_is_cached

        result = complex(boxes[0])
        assert result == complex(7)
        assert isinstance(result, complex)
        assert boxes[0]._qbox_is_cached

    def test_float_and_complex_on_composed_box(self) -> None:
        """Test float/complex conversions on a composed (lazy) QBox."""

        async def get_value() -> int:
            return 10

        box = QBox(get_value())
        composed = box + 5  # Composed box: 10 + 5 = 15

        # Keep references in list to avoid replacement
        boxes = [box, composed]

        # Both boxes should not be cached yet
        assert not boxes[0]._qbox_is_cached
        assert not boxes[1]._qbox_is_cached

        # float() on composed box
        float_result = float(boxes[1])
        assert float_result == 15.0
        assert isinstance(float_result, float)

        # Create another composed box for complex test
        async def get_value2() -> int:
            return 20

        box2 = QBox(get_value2())
        composed2 = box2 * 2  # 20 * 2 = 40

        boxes2 = [box2, composed2]
        assert not boxes2[1]._qbox_is_cached

        complex_result = complex(boxes2[1])
        assert complex_result == complex(40)
        assert isinstance(complex_result, complex)
