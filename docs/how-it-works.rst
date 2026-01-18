How QBox Works
==============

QBox provides a transparent proxy that wraps async operations and allows them
to be used in synchronous code. This page explains the internal architecture
and design decisions.

Architecture Overview
---------------------

QBox consists of three main components:

1. **BackgroundLoopManager** - A singleton that manages a background asyncio event loop
2. **QBox** - The transparent proxy class that wraps awaitables
3. **Reference Replacement** - The mechanism that "collapses" QBoxes after observation

.. code::

    ┌─────────────────────────────────────────────────────────────┐
    │                      Main Thread                            │
    │                                                             │
    │   user = QBox(fetch_user())                                 │
    │         │                                                   │
    │         │ submit coroutine                                  │
    │         ▼                                                   │
    │   ┌─────────────────────────────────────────────────────┐   │
    │   │              concurrent.futures.Future               │   │
    │   └─────────────────────────────────────────────────────┘   │
    │         │                                                   │
    │         │ (later) if user.is_admin:                         │
    │         │         blocks on future.result()                 │
    │         ▼                                                   │
    │   value returned, references replaced                       │
    └─────────────────────────────────────────────────────────────┘
                              │
                              │ run_coroutine_threadsafe()
                              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                  Background Daemon Thread                   │
    │                                                             │
    │   ┌─────────────────────────────────────────────────────┐   │
    │   │              asyncio Event Loop                      │   │
    │   │                                                      │   │
    │   │   async def fetch_user():                            │   │
    │   │       await some_io()                                │   │
    │   │       return User(...)                               │   │
    │   │                                                      │   │
    │   └─────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────┘


The Background Loop
-------------------

QBox uses a singleton background event loop running on a daemon thread. This
design has several advantages:

**Thread Safety**
    The background loop runs on its own thread, so blocking on ``future.result()``
    never deadlocks—the loop can always make progress while the main thread waits.

**Simplicity**
    Users don't need to manage event loops. QBox "just works" in both sync and
    async contexts.

**Resource Efficiency**
    All QBoxes share a single background loop, avoiding thread proliferation.

The loop is created lazily on first use and runs until the Python interpreter
shuts down.

.. note::

   The ``qbox._loop`` module is an internal implementation detail. Users should
   interact with QBox through the public API (``QBox``, ``observe``). The internal
   API (``get_loop_manager()``, ``submit_to_loop()``, etc.) may change between
   versions without notice.


Lazy vs Eager Execution
-----------------------

QBox supports two execution modes controlled by the ``start`` parameter. To
illustrate when code executes, consider this coroutine with prints before
and after the async work:

.. code:: python

    async def log_and_fetch():
        print("STARTING")       # Prints when coroutine begins
        await asyncio.sleep(0.1)
        print("FINISHED")       # Prints when coroutine completes
        return {"data": 42}

**``start='soon'`` (default)**
    The coroutine is submitted to the background loop immediately when the
    QBox is created. This provides parallelism—the async work begins while
    your sync code continues.

    .. code:: python

        data = QBox(log_and_fetch())  # Coroutine submitted NOW
        # "STARTING" prints almost immediately (on background thread)
        print("Continuing...")        # Main thread continues in parallel
        # "FINISHED" may print during this time
        time.sleep(0.2)               # Give coroutine time to complete
        if data:                      # Blocks until result ready (likely already done)
            print(data["data"])

        # Output (order may vary due to parallelism):
        # STARTING
        # Continuing...
        # FINISHED
        # 42

**``start='observed'``**
    The coroutine is not submitted until the value is first accessed. This
    defers work that might not be needed.

    .. code:: python

        data = QBox(log_and_fetch(), start='observed')
        # Nothing printed yet - coroutine hasn't started
        print("Doing other work...")
        time.sleep(0.1)
        # Still nothing from the coroutine
        if data:                      # NOW coroutine starts and blocks
            # "STARTING" prints, then wait, then "FINISHED" prints
            print(data["data"])

        # Output (deterministic order):
        # Doing other work...
        # STARTING
        # FINISHED
        # 42


Lazy Composition
----------------

Operations on a QBox return new QBox instances, creating a lazy computation
graph::

    number = QBox(fetch_number())    # QBox[int]
    result = (number + 10) * 2       # QBox[int], no evaluation yet
    doubled = result + result        # Still lazy

    if doubled > 100:                # NOW evaluates entire chain
        print("Large!")

Under the hood, each operation creates a factory function that awaits the
parent(s) and applies the operation::

    # result = number + 10 creates something like:
    async def composed():
        value = await number._get_value_async()
        return value + 10

When composed QBoxes are created:

- If any parent has ``start='soon'``, the composed QBox also uses ``start='soon'``
- Parent references are tracked for cascading observation


The Observation Model
---------------------

"Observation" is when a QBox's value is actually needed. This triggers:

1. **Evaluation** - The coroutine runs (or its cached result is retrieved)
2. **Reference Replacement** - Variables pointing to the QBox are updated
3. **Cascading** - Parent QBoxes in the composition chain are also observed

**What triggers observation:**

- Comparisons: ``<``, ``>``, ``==``, etc.
- Boolean context: ``if data:``, ``bool(data)``
- Type conversions: ``str()``, ``int()``, ``len()``
- Iteration: ``for item in data:``
- Explicit: ``observe(data)``

**What stays lazy (returns new QBox):**

- Arithmetic: ``+``, ``-``, ``*``, ``/``
- Item access: ``data[key]``
- Attribute access: ``data.attr``
- Method calls: ``data.method()``


Reference Replacement
---------------------

When a QBox is observed, it doesn't just return the value—it replaces references
to itself with the actual value throughout the call stack::

    def process():
        user = QBox(fetch_user())  # user is a QBox
        if user.is_admin:          # Observation happens
            # After this line, 'user' IS the User object, not a QBox!
            print(user.name)       # Direct attribute access, no proxy

This "collapse" behavior is controlled by the ``scope`` parameter:

- ``'locals'``: Replace only in the immediate caller's local variables
- ``'stack'``: Replace throughout the call stack (default)
- ``'globals'``: Replace in stack + module globals

The replacement uses implementation-specific mechanisms to update frame locals:

- **Python 3.13+**: PEP 667 ``FrameLocalsProxy`` (writes persist automatically)
- **PyPy**: ``__pypy__.locals_to_fast(frame)``
- **CPython < 3.13**: ``ctypes.pythonapi.PyFrame_LocalsToFast``

This makes the QBox truly "disappear" after observation.
See :ref:`implementation-notes` in the Observation docs for details.


Type Mimicry
------------

QBox can register itself as a virtual subclass of ABCs, allowing
``isinstance()`` checks to work without forcing evaluation::

    from collections.abc import Mapping

    data = QBox(fetch_dict(), mimic_type=Mapping)
    isinstance(data, Mapping)  # True! No evaluation needed

This works by creating typed QBox subclasses at runtime and registering them
with the appropriate ABC::

    # Internally creates:
    class TypedQBox(QBox):
        _declared_mimic_type = Mapping

    Mapping.register(TypedQBox)  # Now isinstance works

For concrete type checking (``isinstance(data, dict)``), QBox offers optional
``isinstance`` patching that forces observation during the check.


Error Handling
--------------

Exceptions from the wrapped coroutine are:

1. **Caught** when the coroutine completes
2. **Cached** in the QBox
3. **Re-raised** on every subsequent access

.. code:: python

    async def failing():
        raise ValueError("oops")

    result = QBox(failing())
    # Exception hasn't been raised yet...

    try:
        observe(result)  # Raises ValueError
    except ValueError:
        pass

    observe(result)  # Raises same ValueError again (cached)


Cleanup on Deletion
-------------------

When a QBox is garbage collected without being observed:

- **Unsubmitted coroutines** (``start='observed'``) are closed to suppress
  "coroutine was never awaited" warnings
- **Pending futures** are optionally cancelled (controlled by ``cancel_on_delete``)

.. code:: python

    # cancel_on_delete=True (default): work is cancelled
    box = QBox(expensive_operation())
    del box  # Future is cancelled

    # cancel_on_delete=False: work runs to completion
    box = QBox(fire_and_forget(), cancel_on_delete=False)
    del box  # Operation continues in background


Thread Safety
-------------

QBox is designed for safe concurrent access:

- The background loop runs on its own thread
- Value caching uses ``threading.RLock``
- Multiple threads can safely access the same QBox
- The first thread to force evaluation caches the result for others

**Concurrent Observation Behavior**

When multiple threads observe the same QBox simultaneously:

1. **Exactly-once evaluation**: The wrapped coroutine executes only once.
   The first thread to acquire the lock submits the coroutine (if not
   already submitted) and blocks on the result.

2. **Blocking until ready**: Other threads attempting to access the value
   either:
   - Wait on the lock if evaluation is in progress
   - Get the cached value immediately if already evaluated

3. **Exception consistency**: If the coroutine raises an exception, all
   threads receive the same exception instance.

4. **Reference replacement**: Only the thread that triggers observation
   performs reference replacement. Other threads may still hold QBox
   references until they trigger their own observation.

Example of concurrent access::

    box = QBox(fetch_data())

    def worker():
        # All workers see the same value (or exception)
        result = box.__wrapped__
        return result

    # Safe: all threads get consistent results
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: worker(), range(10)))

    assert all(r == results[0] for r in results)  # All identical

.. warning::

   While QBox is thread-safe for value access, reference replacement only
   affects the call stack of the observing thread. If you share QBoxes
   between threads, each thread should call ``observe()`` explicitly to
   ensure reference replacement in their own scope.
