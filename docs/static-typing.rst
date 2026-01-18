Static Type Checking
====================

QBox uses a unique approach to static typing: **transparent typing**. To type
checkers, QBox is invisible—``QBox(awaitable)`` appears to return the awaitable's
result type directly, not a ``QBox[T]`` wrapper.

This enables natural usage without type errors::

    from qbox import QBox

    async def fetch_dict() -> dict[str, int]:
        return {"a": 1, "b": 2}

    data = QBox(fetch_dict())
    reveal_type(data)     # dict[str, int]! Not QBox[dict[str, int]]
    data["key"]           # Works! dict.__getitem__
    data.get("x", 0)      # Works! dict.get
    len(data)             # Works! len(dict)

How It Works
------------

QBox includes stub files (``.pyi``) that declare ``__new__`` returns ``T``
instead of ``QBox[T]``::

    # In qbox.pyi (simplified)
    class QBox(Generic[T]):
        def __new__(cls, awaitable: Awaitable[T], ...) -> T: ...

Type checkers read the stub and think you're getting the actual value. At
runtime, you get a QBox that behaves lazily.

Benefits
--------

**Natural operations**: All operations use the underlying type's semantics::

    # Type checkers see these as dict operations
    data = QBox(fetch_dict())
    value: int = data["key"]       # dict.__getitem__ -> value type
    keys = data.keys()             # dict.keys() -> KeysView
    items = list(data.items())     # dict.items() -> ItemsView

**IDE autocomplete**: Your IDE shows methods of the wrapped type, not QBox::

    data = QBox(fetch_user())
    data.  # IDE shows: name, email, save(), etc. (User's attributes)

**No type casts needed**: Operations return the expected types::

    numbers = QBox(fetch_list())
    first: int = numbers[0]        # list[int].__getitem__(0) -> int
    total: int = sum(numbers)      # sum(list[int]) -> int

The observe() Function
----------------------

Since QBox is transparent, ``observe()`` is typed as identity (``T -> T``)::

    from qbox import QBox, observe

    data = QBox(fetch_dict())
    result = observe(data)
    reveal_type(result)  # dict[str, int]

At runtime, ``observe()`` forces evaluation and replaces references. To type
checkers, it's a pass-through.

Runtime Type Checking
---------------------

Since QBox is invisible to type checkers, ``isinstance(x, QBox)`` won't work
for type narrowing. Use ``QBox._qbox_is_qbox()`` instead::

    from qbox import QBox

    data = QBox(fetch_data())

    # Don't do this - type checker thinks data is dict, not QBox
    if isinstance(data, QBox):  # Always False to type checker
        pass

    # Do this instead
    if QBox._qbox_is_qbox(data):  # Runtime check that works
        print("It's a QBox!")

Async Context
-------------

QBox supports ``await`` and preserves types::

    async def process() -> int:
        box = QBox(fetch_number())  # Type: int (transparent)
        value: int = await box      # Type: int
        return value

The ``__await__`` method is typed to return ``T``, maintaining transparency.

PEP 561 Compatibility
---------------------

QBox includes a ``py.typed`` marker file, making it a PEP 561 compliant typed
package. Type checkers automatically use QBox's stub files.

Implications
------------

**What works well:**

- ``QBox(fetch_int()) + 5`` → ``int``
- ``QBox(fetch_dict())["key"]`` → uses ``dict.__getitem__``
- ``QBox(fetch_list()).append(x)`` → uses ``list.append``
- IDE autocomplete shows methods of the wrapped type

**What to be aware of:**

- Can't annotate variables as ``QBox[T]`` (would be incorrect with stubs)
- ``isinstance(x, QBox)`` type narrowing doesn't work (use ``_qbox_is_qbox()``)
- Type checkers may complain about calling methods on "wrong" types if you
  use explicit ``QBox[T]`` annotations

**Runtime is unchanged:**

- QBox is still a real class at runtime
- All lazy evaluation still works exactly as before
- Only the static type checker sees it differently

Best Practices
--------------

**1. Don't annotate with QBox[T]**

The stubs make this incorrect for type checkers::

    # Avoid
    data: QBox[dict[str, int]] = QBox(fetch_dict())

    # Better - let the transparent type flow through
    data = QBox(fetch_dict())  # Type: dict[str, int]

**2. Use _qbox_is_qbox() for runtime checks**::

    # For runtime type checking
    if QBox._qbox_is_qbox(obj):
        # Handle QBox case
        pass

**3. Trust the transparent typing**

Operations just work because type checkers see the underlying type::

    data = QBox(fetch_dict())
    # All dict operations type-check correctly
    data["key"]
    data.get("key", default)
    data.keys()
    data | other_dict

**4. Use observe() at API boundaries**

When calling functions that expect concrete types::

    def process_data(data: dict[str, int]) -> None:
        ...

    box = QBox(fetch_dict())
    process_data(observe(box))  # Forces evaluation, passes dict
