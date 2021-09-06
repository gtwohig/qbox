Quantum Box
===========

|PyPI| |Status| |Python Version| |License|

|Read the Docs| |Tests| |Codecov|

|pre-commit| |Black|

.. |PyPI| image:: https://img.shields.io/pypi/v/qbox.svg
   :target: https://pypi.org/project/qbox/
   :alt: PyPI
.. |Status| image:: https://img.shields.io/pypi/status/qbox.svg
   :target: https://pypi.org/project/qbox/
   :alt: Status
.. |Python Version| image:: https://img.shields.io/pypi/pyversions/qbox
   :target: https://pypi.org/project/qbox
   :alt: Python Version
.. |License| image:: https://img.shields.io/pypi/l/qbox
   :target: https://opensource.org/licenses/MIT
   :alt: License
.. |Read the Docs| image:: https://img.shields.io/readthedocs/qbox/latest.svg?label=Read%20the%20Docs
   :target: https://qbox.readthedocs.io/
   :alt: Read the documentation at https://qbox.readthedocs.io/
.. |Tests| image:: https://github.com/gtwohig/qbox/workflows/Tests/badge.svg
   :target: https://github.com/gtwohig/qbox/actions?workflow=Tests
   :alt: Tests
.. |Codecov| image:: https://codecov.io/gh/gtwohig/qbox/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/gtwohig/qbox
   :alt: Codecov
.. |pre-commit| image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
   :target: https://github.com/pre-commit/pre-commit
   :alt: pre-commit
.. |Black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: Black

Overview
--------

Theory
~~~~~~

`Schrödinger wrote`_:

    One can even set up quite ridiculous cases. A cat is penned up in a steel chamber, along with the following device (which must be secured against direct interference by the cat): in a Geiger counter, there is a tiny bit of radioactive substance, so small, that perhaps in the course of the hour one of the atoms decays, but also, with equal probability, perhaps none; if it happens, the counter tube discharges and through a relay releases a hammer that shatters a small flask of hydrocyanic acid. If one has left this entire system to itself for an hour, one would say that the cat still lives if meanwhile no atom has decayed. The first atomic decay would have poisoned it. The psi-function of the entire system would express this by having in it the living and dead cat (pardon the expression) mixed or smeared out in equal parts.

    It is typical of these cases that an indeterminacy originally restricted to the atomic domain becomes transformed into macroscopic indeterminacy, which can then be resolved by direct observation. That prevents us from so naïvely accepting as valid a "blurred model" for representing reality. In itself, it would not embody anything unclear or contradictory. There is a difference between a shaky or out-of-focus photograph and a snapshot of clouds and fog banks.

Application to Asynchronous Code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When dealing with async code, we need to decide when to await the completion of a future.
This awaiting must be done in an asynchronous context.
Wouldn't it be easier to just put our future into Schrödinger's quantum box, allow it to exist in a state of superposition until we need to "open" it and use the result?


Features
--------

Quantum Box gives you a place to put futures. It will get them started as asyncio tasks on another tread and only await them when their value is needed.


Requirements
------------

* Python 3.7+


Installation
------------

You can install *Quantum Box* via pip_ from PyPI_:

.. code:: console

   $ pip install qbox


Usage
-----

Please see the `Command-line Reference <Usage_>`_ for details.


Contributing
------------

Contributions are very welcome.
To learn more, see the `Contributor Guide`_.


License
-------

Distributed under the terms of the `MIT license`_,
*Quantum Box* is free and open source software.


Issues
------

If you encounter any problems,
please `file an issue`_ along with a detailed description.


Credits
-------

This project was generated from `@cjolowicz`_'s `Hypermodern Python Cookiecutter`_ template.

.. _@cjolowicz: https://github.com/cjolowicz
.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _MIT license: https://opensource.org/licenses/MIT
.. _PyPI: https://pypi.org/
.. _Hypermodern Python Cookiecutter: https://github.com/cjolowicz/cookiecutter-hypermodern-python
.. _Schrödinger wrote: https://en.wikipedia.org/wiki/Schr%C3%B6dinger%27s_cat#Thought_experiment
.. _file an issue: https://github.com/gtwohig/qbox/issues
.. _pip: https://pip.pypa.io/
.. github-only
.. _Contributor Guide: CONTRIBUTING.rst
.. _Usage: https://qbox.readthedocs.io/en/latest/usage.html
