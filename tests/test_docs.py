"""Tests to ensure documentation stays in sync with code."""

import inspect
from typing import get_origin

import qbox
from qbox import QBox, __all__, observe

# Type aliases that cannot have docstrings (Literal, TypeVar, etc.)
TYPE_ALIAS_EXCEPTIONS = {"ScopeType", "StartMode"}


def test_public_api_has_docstrings():
    """All public API members must have docstrings (except type aliases)."""
    for name in __all__:
        if name in TYPE_ALIAS_EXCEPTIONS:
            continue  # Type aliases cannot have docstrings
        obj = getattr(qbox, name)
        # Skip type aliases that use Literal
        if get_origin(obj) is not None:
            continue
        assert obj.__doc__, f"{name} missing docstring"


def test_qbox_init_params_documented():
    """QBox.__init__ docstring must document all parameters."""
    sig = inspect.signature(QBox.__init__)
    params = {p for p in sig.parameters if p != "self"}
    docstring = QBox.__init__.__doc__ or ""
    for param in params:
        assert param in docstring, f"Parameter '{param}' not in QBox.__init__ docstring"


def test_observe_params_documented():
    """observe() docstring must document all parameters."""
    sig = inspect.signature(observe)
    params = set(sig.parameters.keys())
    docstring = observe.__doc__ or ""
    for param in params:
        assert param in docstring, f"Parameter '{param}' not in observe() docstring"


def test_qbox_class_docstring_has_example():
    """QBox class docstring should have an example section."""
    docstring = QBox.__doc__ or ""
    assert "Example:" in docstring or "Examples:" in docstring, (
        "QBox class docstring missing Example section"
    )


def test_force_evaluation_methods_have_docstrings():
    """Force-evaluation methods must have docstrings explaining blocking."""
    force_methods = [
        "__bool__",
        "__str__",
        "__len__",
        "__iter__",
        "__contains__",
        "__lt__",
        "__le__",
        "__eq__",
        "__ne__",
        "__gt__",
        "__ge__",
        "__int__",
        "__float__",
        "__hash__",
    ]
    for method_name in force_methods:
        method = getattr(QBox, method_name, None)
        if method is not None:
            assert method.__doc__, f"QBox.{method_name} missing docstring"


def test_lazy_methods_have_docstrings():
    """Lazy composition methods must have docstrings."""
    lazy_methods = [
        "__add__",
        "__sub__",
        "__mul__",
        "__truediv__",
        "__floordiv__",
        "__mod__",
        "__pow__",
        "__neg__",
        "__pos__",
        "__abs__",
        "__and__",
        "__or__",
        "__xor__",
        "__lshift__",
        "__rshift__",
        "__getitem__",
        "__getattr__",
        "__call__",
    ]
    for method_name in lazy_methods:
        method = getattr(QBox, method_name, None)
        if method is not None:
            assert method.__doc__, f"QBox.{method_name} missing docstring"


def test_wrapped_property_documented():
    """__wrapped__ property must have a complete docstring."""
    docstring = QBox.__wrapped__.__doc__ or ""
    assert "Returns:" in docstring, "__wrapped__ docstring missing Returns section"
    assert "Raises:" in docstring, "__wrapped__ docstring missing Raises section"
