Contributor Guide
=================

Thank you for your interest in improving this project.
This project is open-source under the `MIT license`_ and
welcomes contributions in the form of bug reports, feature requests, and pull requests.

Here is a list of important resources for contributors:

- `Source Code`_
- `Documentation`_
- `Issue Tracker`_

.. _MIT license: https://opensource.org/licenses/MIT
.. _Source Code: https://github.com/gtwohig/qbox
.. _Documentation: https://qbox.readthedocs.io/
.. _Issue Tracker: https://github.com/gtwohig/qbox/issues

How to report a bug
-------------------

Report bugs on the `Issue Tracker`_.

When filing an issue, make sure to answer these questions:

- Which operating system and Python version are you using?
- Which version of this project are you using?
- What did you do?
- What did you expect to see?
- What did you see instead?

The best way to get your bug fixed is to provide a test case,
and/or steps to reproduce the issue.


How to request a feature
------------------------

Request features on the `Issue Tracker`_.


How to set up your development environment
------------------------------------------

You need Python 3.10+ and uv_ for package management.

Install the package with development requirements:

.. code:: console

   $ uv sync

You can now run an interactive Python session:

.. code:: console

   $ uv run python

.. _uv: https://docs.astral.sh/uv/


How to test the project
-----------------------

Run the full test suite:

.. code:: console

   $ uv run pytest

Run tests with verbose output:

.. code:: console

   $ uv run pytest -v

Run tests with coverage:

.. code:: console

   $ uv run pytest --cov=qbox --cov-report=term-missing

Unit tests are located in the ``tests`` directory,
and are written using the pytest_ testing framework.

.. _pytest: https://pytest.readthedocs.io/


How to check code quality
-------------------------

Run linting:

.. code:: console

   $ uv run ruff check src tests

Auto-fix linting issues:

.. code:: console

   $ uv run ruff check src tests --fix

Format code:

.. code:: console

   $ uv run ruff format src tests

Run type checking:

.. code:: console

   $ uv run ty check src


How to build documentation
--------------------------

Build the documentation:

.. code:: console

   $ uv run sphinx-build -b html docs docs/_build/html

Or use live-reload for development:

.. code:: console

   $ uv run sphinx-autobuild docs docs/_build/html


How to submit changes
---------------------

Open a `pull request`_ to submit changes to this project.

Your pull request needs to meet the following guidelines for acceptance:

- The test suite must pass without errors.
- Include unit tests. This project maintains 100% code coverage.
- Code must pass linting (ruff) and type checking (ty).
- If your changes add functionality, update the documentation accordingly.

Feel free to submit early, though—we can always iterate on this.

To run linting and code formatting checks before committing your change,
you can install pre-commit as a Git hook:

.. code:: console

   $ uv run pre-commit install

It is recommended to open an issue before starting work on anything.
This will allow a chance to talk it over with the owners and validate your approach.

.. _pull request: https://github.com/gtwohig/qbox/pulls
