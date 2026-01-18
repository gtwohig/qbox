Observation: Collapsing the Quantum Box
========================================

QBox uses a quantum mechanics metaphor: values exist in superposition until observed.
When you "observe" a QBox, the wave function collapses and the box disappears,
leaving only the concrete value.

What is Observation?
--------------------

Observation occurs when you need the actual value. This happens automatically with:

- Comparisons: ``data > 5``
- Boolean checks: ``if data:``
- String conversion: ``str(data)``
- Iteration: ``for item in data:``
- Numeric conversions: ``int(data)``

Or explicitly with::

    from qbox import observe
    value = observe(data)

When Does Code Execute?
-----------------------

With the default ``start='soon'``, execution begins immediately on creation.
With ``start='observed'``, it waits until observation.

Default behavior (start='soon')::

    from qbox import QBox

    async def log_and_fetch():
        print("EXECUTING")
        return await fetch_data()

    data = QBox(log_and_fetch())  # Coroutine submitted NOW, starts running
    print("Continuing...")        # "EXECUTING" may print during this line
    if data:                      # Blocks until result ready (may already be done)
        print(data)

Deferred behavior (start='observed')::

    data = QBox(log_and_fetch(), start='observed')
    # "EXECUTING" has NOT printed - coroutine not submitted yet

    print("Doing other work...")  # Nothing happening in background
    if data:                      # NOW coroutine submitted, blocks for result
        print(data)
    # Output:
    # Doing other work...
    # EXECUTING
    # <the data>

When to use each:

.. list-table::
   :header-rows: 1

   * - ``start=``
     - Use When
   * - ``'soon'`` (default)
     - You'll likely need the value; want parallelism with other sync work
   * - ``'observed'``
     - Might not need the value; building lazy chains; deferring expensive work

Force-evaluation triggers (cause observation and reference replacement):

- Comparisons: ``<``, ``>``, ``==``, ``!=``, ``<=``, ``>=``
- Boolean: ``if data:``, ``bool(data)``
- Conversion: ``str()``, ``int()``, ``float()``, ``complex()``, ``len()``
- Hashing: ``hash(data)``
- Indexing: ``__index__`` (for use in slices)
- Rounding: ``round()``, ``math.floor()``, ``math.ceil()``, ``math.trunc()``
- Iteration: ``for item in data:``
- Containment: ``x in data``
- Explicit: ``observe(data)``
- ``repr()`` only if ``repr_observes=True``

Lazy operations (NO observation, return new QBox):

- Arithmetic: ``+``, ``-``, ``*``, ``/``, ``//``, ``%``, ``**``, etc.
- Unary: ``-data``, ``+data``, ``abs(data)``, ``~data``
- Bitwise: ``&``, ``|``, ``^``, ``<<``, ``>>``
- Item access: ``data[key]``, ``data[0:10]``
- Attribute access: ``data.attribute``
- Method calls: ``data.method()``
- ``repr()`` with default ``repr_observes=False``

Side Effects and Exceptions
---------------------------

Since execution can be deferred with ``start='observed'``, side effects and
exceptions occur during observation, not during QBox creation.

Side Effects::

    async def write_to_database(record):
        await db.insert(record)  # Side effect!
        return record.id

    record_id = QBox(write_to_database(user_record), start='observed')
    # Database write has NOT happened yet!

    # To ensure side effects have occurred:
    observe(record_id)  # Write happens HERE

Exceptions::

    async def might_fail():
        raise ValueError("Something went wrong")

    result = QBox(might_fail(), start='observed')
    # No exception yet!

    try:
        if result:  # Exception raised HERE on observation
            print(result)
    except ValueError:
        print("Caught during observation")

    # Exceptions are cached - subsequent access re-raises the same exception

Auto-Replacement
----------------

When observed, QBox replaces references to itself with the unwrapped value in
the call stack::

    from qbox import QBox

    async def fetch_user():
        return User(name="Alice")

    user = QBox(fetch_user())
    print(user.name)          # Triggers cascading observation
    # After this line, `user` IS the User, not a QBox

How this works:

1. ``user.name`` returns a *new* QBox (attribute access is lazy)
2. ``print()`` calls ``str()`` on that QBox, forcing observation
3. The ``.name`` QBox observes its parent (``user``), cascading up the chain
4. Both QBoxes are replaced with their actual values

Scope Control
-------------

Control how aggressively references are replaced with the ``scope`` parameter:

``locals`` (minimal)
    Replace only in the immediate caller's local variables::

        data = QBox(fetch_data(), scope='locals')

    Use when:

    - You want explicit control over variable replacement
    - Performance-sensitive tight loops
    - QBox is only used in one function

    Note: The object is still the same object globally - only the
    local variable binding is replaced.

``stack`` (default)
    Replace in all frames on the call stack::

        data = QBox(fetch_data(), scope='stack')

    Use when:

    - General-purpose usage
    - QBox passed to helper functions
    - You want natural "it just works" behavior

``globals`` (maximum)
    Replace in stack + module globals of the calling module::

        data = QBox(fetch_data(), scope='globals')

    Use when:

    - Working with module-level variables
    - Building REPL/interactive tools
    - Fully transparent operation required

    Caution: Can have surprising effects if the same QBox is
    referenced from multiple modules.

You can override the scope per-observation::

    observe(data, scope='globals')

Cascading Observation
---------------------

Observing a composed QBox observes its entire dependency tree::

    number = QBox(fetch_number())
    result = number + 5
    observe(result)  # Both `result` AND `number` are replaced with their values

Explicit Observation
--------------------

The ``observe()`` function provides explicit control over observation::

    from qbox import QBox, observe

    # Observe a QBox
    value = observe(data)

    # Safe for non-QBox values (idempotent)
    value = observe(maybe_a_qbox)  # Returns unchanged if not a QBox

This is useful when:

- You want to control when observation happens
- You need to handle values that might or might not be QBox instances
- You want to specify a different scope than the default

.. _debugging-gotchas:

Debugging and IDE Gotchas
-------------------------

.. warning::

   **IDEs and debuggers can accidentally trigger observation!**

   When debugging code that uses QBox, be aware that simply viewing a variable
   in your IDE's debugger or watch window can collapse the superposition earlier
   than your application would normally.

How it happens:

1. **Variable inspection**: IDEs call ``repr()`` or ``str()`` to display variables.
   With ``repr_observes=True``, this triggers observation.

2. **Watch expressions**: Adding ``data`` to a watch window may evaluate it.

3. **Hover tooltips**: Hovering over a variable often calls ``repr()``.

4. **Debug console**: Typing ``data`` in a REPL/console triggers ``__repr__``.

Consequences:

- Your QBox may be observed (and replaced) before the line you're debugging
- Side effects happen during debugging, not where you expect
- Exceptions might be raised in the debugger rather than your code
- Timing-sensitive bugs may not reproduce under debugging

Recommendations:

1. **Use** ``repr_observes=False`` **(default)** during development::

       # Safe for debugging - repr() shows <QBox[pending]>
       data = QBox(fetch_data())  # repr_observes=False by default

2. **Check observation state** without triggering it::

       # Safe checks that don't observe:
       data._qbox_is_cached      # True if already observed
       data._qbox_future         # The Future object, or None if not yet submitted
                                 # (i.e., when using start='observed' before observation).
                                 # After submission, you can check .done() on the Future.

3. **Use conditional breakpoints** on cached state::

       # Break only after observation has occurred
       if data._qbox_is_cached:
           breakpoint()

4. **Be aware of IDE settings** that auto-evaluate expressions

5. **Test without debugger** when investigating timing issues

.. _implementation-notes:

Implementation Notes
--------------------

QBox's reference replacement feature relies on modifying frame locals, which
requires implementation-specific handling:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Implementation
     - Behavior
   * - **CPython 3.13+**
     - Uses ``FrameLocalsProxy`` (PEP 667). Writes to ``frame.f_locals`` persist
       automatically - no additional sync needed.
   * - **CPython < 3.13**
     - Uses ``ctypes.pythonapi.PyFrame_LocalsToFast`` to sync modifications back
       to the frame's fast locals.
   * - **PyPy**
     - Uses ``__pypy__.locals_to_fast(frame)`` for the same effect.
   * - **Other implementations**
     - Best effort - reference replacement may not work. The value is still
       computed correctly, but local variable bindings may not be updated.

This means:

- **Full support**: CPython (all versions), PyPy
- **Value computation works everywhere**: Even on unsupported implementations,
  ``observe(box)`` returns the correct value
- **Reference replacement is implementation-specific**: The "variable disappears
  and becomes the value" behavior depends on frame manipulation support

If you need portable code that doesn't rely on reference replacement::

    from qbox import QBox, observe

    data = QBox(fetch_data())
    # Instead of relying on auto-replacement:
    value = observe(data)  # Explicitly capture the value
    # Use 'value' from here on
