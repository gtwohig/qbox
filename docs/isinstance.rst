Type Checking with QBox
=======================

QBox aims to be transparent, but Python's ``isinstance()`` function presents a
challenge. This guide explains the options for type checking QBox instances.

The Challenge
-------------

Python's ``isinstance(obj, cls)`` uses C-level type checking that QBox cannot
intercept. By default::

    data = QBox(fetch_dict())
    isinstance(data, dict)  # Returns False!

The QBox hasn't been observed yet, so the check returns False even though the
wrapped value is a dict.

Solution 1: Use ABCs (Recommended)
----------------------------------

Abstract Base Classes work with QBox's registration system. When you specify
``mimic_type``, the QBox is registered as a virtual subclass::

    from collections.abc import Mapping
    from qbox import QBox

    data = QBox(fetch_dict(), mimic_type=Mapping)
    isinstance(data, Mapping)  # True, without forcing evaluation!

The QBox remains lazy - no evaluation happens. This is the recommended approach
for library code.

Common ABC mappings:

- ``dict`` -> ``collections.abc.Mapping`` or ``MutableMapping``
- ``list`` -> ``collections.abc.Sequence`` or ``MutableSequence``
- ``set`` -> ``collections.abc.Set`` or ``MutableSet``
- ``int`` -> ``numbers.Integral``
- ``float`` -> ``numbers.Real``

Solution 2: Observe First
-------------------------

Explicitly observe before type checking::

    from qbox import observe

    data = QBox(fetch_dict())
    result = observe(data)
    isinstance(result, dict)  # True

Or let observation happen naturally through other operations::

    data = QBox(fetch_dict())
    if data:  # Observation happens here, data is now a dict
        isinstance(data, dict)  # True

Solution 3: Context Manager (Scoped Patching)
---------------------------------------------

For scoped fully transparent operation, use the ``qbox_isinstance`` context manager::

    from qbox import qbox_isinstance

    data = QBox(fetch_dict())

    with qbox_isinstance():
        isinstance(data, dict)  # True! Forces observation automatically
    # Original isinstance restored after block

This is safer than global patching because the change is limited to the
context block.

Solution 4: Global isinstance Patching
--------------------------------------

For fully transparent operation everywhere, patch the builtin ``isinstance`` function::

    from qbox import enable_qbox_isinstance

    enable_qbox_isinstance()

    data = QBox(fetch_dict())
    isinstance(data, dict)  # True! Forces observation automatically

To restore original behavior::

    from qbox import disable_qbox_isinstance

    disable_qbox_isinstance()

.. warning::

   Mixing the ``qbox_isinstance()`` context manager with direct calls to
   ``enable_qbox_isinstance()`` / ``disable_qbox_isinstance()`` is not supported
   and may cause unexpected behavior. Choose one approach and use it consistently.

To check current patching status::

    from qbox import is_qbox_isinstance_enabled

    if is_qbox_isinstance_enabled():
        print("isinstance is transparent")

Tradeoffs
---------

.. list-table::
   :header-rows: 1

   * - Approach
     - Pros
     - Cons
   * - ABCs
     - No evaluation needed, clean API
     - Must use ABC types, not concrete
   * - Observe first
     - Explicit, predictable
     - Extra step required
   * - Context manager
     - Scoped, reversible
     - Must wrap code in ``with`` block
   * - Global patching
     - Fully transparent operation
     - Global mutation, affects all code

When to Use Each Approach
-------------------------

**Use ABCs** when:

- Writing library code
- You know the expected type at QBox creation time
- Lazy evaluation is important

**Use observe first** when:

- You want maximum control
- Working with code that expects concrete types
- You don't mind forcing evaluation

**Use the context manager** when:

- You need isinstance to be fully transparent temporarily
- Working with third-party code in a specific section
- You want to limit the scope of the change

**Use global patching** when:

- Your codebase heavily uses isinstance with concrete types
- You want fully transparent operation
- You control the application entry point

**Avoid global patching** when:

- Writing a library (don't mutate globals for users)
- Working with code that relies on isinstance behavior
- You need fine-grained control over observation timing

Limitations with Third-Party Libraries
--------------------------------------

Some libraries check concrete types rather than ABCs::

    # This library does:
    isinstance(x, dict)  # Won't match QBox[Mapping]

For these cases, use:

1. **Observe before passing to the library**::

       from qbox import observe

       data = observe(qbox_data)
       library.process(data)

2. **Use the context manager around library calls**::

       from qbox import qbox_isinstance

       with qbox_isinstance():
           library.process(qbox_data)  # isinstance(qbox_data, dict) now works

3. **Enable global patching** (application code only)::

       enable_qbox_isinstance()
       library.process(qbox_data)  # isinstance(qbox_data, dict) now works

Known libraries that check concrete types:

- Pydantic (validates with concrete types)
- Some serialization libraries
