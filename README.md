# QBox

[![PyPI](https://img.shields.io/pypi/v/qbox.svg)](https://pypi.org/project/qbox/)
[![Python Version](https://img.shields.io/pypi/pyversions/qbox)](https://pypi.org/project/qbox)
[![License](https://img.shields.io/pypi/l/qbox)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/gtwohig/qbox/workflows/CI/badge.svg)](https://github.com/gtwohig/qbox/actions?workflow=CI)
[![Read the Docs](https://img.shields.io/readthedocs/qbox/latest.svg?label=Read%20the%20Docs)](https://qbox.readthedocs.io/)
[![Codecov](https://codecov.io/gh/gtwohig/qbox/branch/main/graph/badge.svg)](https://codecov.io/gh/gtwohig/qbox)

**A lazily awaited container for async operations.**

QBox solves the "colored functions" problem by wrapping async operations in a transparent proxy that defers evaluation until the value is "observed."

## The Problem

Async/await creates a viral pattern where every function that uses async code must also be async:

```python
# The traditional way - async spreads everywhere
async def get_user_data():
    user = await fetch_user()
    profile = await fetch_profile(user.id)
    return await process_data(user, profile)

# Every caller must also be async
async def main():
    data = await get_user_data()
    if data.score > 100:
        print("High score!")
```

## The Solution

QBox lets you write normal synchronous code that transparently handles async operations:

```python
from qbox import QBox

# Wrap async calls in QBox - think of the variable as your data
user = QBox(fetch_user())
profile = QBox(fetch_profile(user.id))  # Lazy - chains without blocking
score = (user.score + profile.bonus) * 2  # Still lazy!

# Only blocks when you actually need the value
if score > 100:  # Observation happens here
    print("High score!")
```

## The Quantum Metaphor

Like Schrödinger's cat, a QBox value exists in superposition until observed:

```python
import asyncio
import random
from qbox import QBox, observe

class Cat:
    pass

class AliveCat(Cat):
    def speak(self) -> str:
        return "Meow!"

class DeadCat(Cat):
    def speak(self) -> str:
        return "..."

async def infernal_device() -> Cat:
    """The cat's fate is determined only when observed."""
    await asyncio.sleep(0.1)  # Quantum uncertainty...
    return AliveCat() if random.random() > 0.5 else DeadCat()

# The cat exists in superposition
cat = QBox(infernal_device())  # cat is a QBox[Cat], fate undetermined

# Observation collapses the wave function
observed_cat = observe(cat)  # NOW the cat is either alive or dead
print(observed_cat.speak())  # "Meow!" or "..."

# After observation, 'cat' IS the actual Cat object (not a QBox)
print(type(cat))  # <class 'AliveCat'> or <class 'DeadCat'>
```

## Installation

```bash
pip install qbox
```

## Quick Start

```python
import asyncio
from qbox import QBox

async def fetch_number() -> int:
    await asyncio.sleep(0.1)  # Simulate async work
    return 42

# Create a QBox - starts the async operation immediately (default)
number = QBox(fetch_number())

# Chain operations - all lazy, no blocking
result = (number + 8) * 2 - 10  # Returns QBox, not int

# Value is computed only when needed
if result > 50:  # Blocks here, evaluates entire chain
    print(f"Result: {result}")  # Prints "Result: 90"
```

## When Does Code Execute?

### Default behavior (start='soon'):

```python
async def log_and_fetch():
    print("EXECUTING")
    return await fetch_data()

data = QBox(log_and_fetch())  # Coroutine submitted NOW, starts running
print("Continuing...")        # "EXECUTING" may print during this line
if data:                      # Blocks until result ready (may already be done)
    print(data)
```

### Deferred behavior (start='observed'):

```python
data = QBox(log_and_fetch(), start='observed')
# "EXECUTING" has NOT printed - coroutine not submitted yet

print("Doing other work...")  # Nothing happening in background
if data:                      # NOW coroutine submitted, blocks for result
    print(data)
# Output:
# Doing other work...
# EXECUTING
# <the data>
```

**When to use each:**

| `start=` | Use When |
|----------|----------|
| `'soon'` (default) | You'll likely need the value; want parallelism with other sync work |
| `'observed'` | Might not need the value; building lazy chains; deferring expensive work |

## API Reference

### Creating a QBox

```python
from qbox import QBox
from collections.abc import Mapping

# Basic creation (starts immediately by default)
user = QBox(some_coroutine())

# Deferred execution
config = QBox(load_config(), start='observed')

# With type hint for isinstance support
data = QBox(fetch_dict(), mimic_type=Mapping)

# With custom observation scope
result = QBox(fetch_data(), scope='locals')  # 'locals', 'stack', or 'globals'

# With repr that triggers observation
debug_value = QBox(fetch_value(), repr_observes=True)
```

### Constructor Parameters

```python
QBox(
    awaitable,            # The coroutine or awaitable to wrap
    mimic_type=None,      # Type for isinstance mimicry (e.g., Mapping)
    scope='stack',        # Reference replacement scope
    start='soon',         # When to start: 'soon' or 'observed'
    repr_observes=False,  # Whether repr() triggers observation
    cancel_on_delete=True,  # Whether to cancel pending work on deletion
)
```

### Type Checking with QBox
QBox is transparent to static type checkers. For runtime checks, use
`QBox._qbox_is_qbox()` and prefer ABCs via `mimic_type` to keep laziness. See
[Type Checking Guide](https://qbox.readthedocs.io/en/latest/isinstance.html) and
[Static Typing](https://qbox.readthedocs.io/en/latest/static-typing.html) for details.

### Accessing the Value

```python
from qbox import QBox, observe

# Explicit observation (recommended - also replaces references)
value = observe(data)

# Safe observation (works on non-QBox values too)
value = observe(maybe_a_qbox)

# Or use in boolean/comparison context (auto-evaluates)
if data > 10:
    print("Large!")
```

### Lazy Operations (return new QBox)

- Arithmetic: `+`, `-`, `*`, `/`, `//`, `%`, `**`
- Bitwise: `&`, `|`, `^`, `<<`, `>>`
- Unary: `-data`, `+data`, `abs(data)`, `~data`
- Item access: `data[key]`, `data[start:end]`
- Attribute access: `data.attribute`
- Calling: `data(args)`
- `repr()` with default `repr_observes=False`

### Force Evaluation (return concrete values)

- Comparisons: `<`, `<=`, `==`, `!=`, `>=`, `>`
- Type conversions: `bool()`, `str()`, `int()`, `float()`
- Container operations: `len()`, `in`, iteration
- Math functions: `round()`, `math.floor()`, `math.ceil()`
- `repr()` with `repr_observes=True`

## Side Effects and Exceptions

Since execution is lazy by default with `start='observed'`, side effects and exceptions occur during observation, not during QBox creation.

### Side Effects

```python
async def write_to_database(record):
    await db.insert(record)  # Side effect!
    return record.id

record_id = QBox(write_to_database(user_record), start='observed')
# Database write has NOT happened yet!

# To ensure side effects have occurred:
observe(record_id)  # Write happens HERE
```

### Exceptions

```python
async def might_fail():
    raise ValueError("Something went wrong")

result = QBox(might_fail())
# No exception raised yet - exceptions surface on observation, not creation

try:
    if result:  # Exception raised HERE on observation
        print(result)
except ValueError:
    print("Caught during observation")

# Exceptions are cached - subsequent access re-raises the same exception
```

## Type Mimicry

QBox aims to be invisible - when you observe a value, the box disappears:

```python
user = QBox(fetch_user())
print(user.name)  # After this, `user` IS the User object
```

### isinstance Support

Use ABCs for lazy type checking without forcing evaluation:

```python
from collections.abc import Mapping
from qbox import QBox

data = QBox(fetch_dict(), mimic_type=Mapping)
isinstance(data, Mapping)  # True, stays lazy!
```

Or opt-in to full transparency:

```python
from qbox import enable_qbox_isinstance

enable_qbox_isinstance()
isinstance(data, dict)  # Works! Forces observation automatically
```

Or use the context manager for scoped transparency:

```python
from qbox import qbox_isinstance

with qbox_isinstance():
    isinstance(data, dict)  # Works within this block
# Original isinstance restored after block
```

### Explicit Observation

Use the `observe()` function for explicit control:

```python
from qbox import observe

value = observe(data)  # Force evaluation, returns unwrapped value
value = observe(non_qbox)  # Safe for non-QBox values (returns unchanged)
```

See [Type Checking Guide](https://qbox.readthedocs.io/en/latest/isinstance.html) for details.

## Error Handling

Exceptions from the wrapped coroutine are cached and re-raised on access:

```python
async def failing():
    raise ValueError("oops")

result = QBox(failing())

try:
    observe(result)  # Raises ValueError
except ValueError:
    pass

observe(result)  # Raises same ValueError (cached)
```

## Thread Safety

QBox is designed for thread-safe access:

- A singleton background event loop runs on a daemon thread
- Value caching uses proper locking
- Multiple threads can safely access the same QBox

## Requirements

- Python 3.10+
- No runtime dependencies (pure stdlib)

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.rst` for guidelines.

## License

Distributed under the MIT License. See `LICENSE.rst` for details.
