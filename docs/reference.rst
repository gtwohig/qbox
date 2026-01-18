Reference
=========

.. contents::
    :local:
    :backlinks: none


Public API
----------

The following are the main exports from ``qbox``:

.. autofunction:: qbox.observe

.. autoclass:: qbox.QBox
   :members:
   :special-members: __new__, __wrapped__, __await__

.. autodata:: qbox.ScopeType

.. autodata:: qbox.StartMode


isinstance Support
------------------

Functions for transparent ``isinstance`` behavior with QBox:

.. autofunction:: qbox.enable_qbox_isinstance

.. autofunction:: qbox.disable_qbox_isinstance

.. autofunction:: qbox.is_qbox_isinstance_enabled

.. autofunction:: qbox.qbox_isinstance


Internal Modules
----------------

These modules are implementation details but documented for completeness.

qbox.qbox
~~~~~~~~~

.. automodule:: qbox.qbox
   :members:
   :undoc-members:
   :show-inheritance:

qbox._loop
~~~~~~~~~~

.. automodule:: qbox._loop
   :members:
   :undoc-members:

qbox._isinstance
~~~~~~~~~~~~~~~~

.. automodule:: qbox._isinstance
   :members:
   :undoc-members:
