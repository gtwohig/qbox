"""Pytest configuration and fixtures for QBox tests."""

import asyncio
from collections.abc import Generator

import pytest

from qbox import QBox, disable_qbox_isinstance, enable_qbox_isinstance


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def int_box() -> QBox[int]:
    """Create a QBox containing an integer value (10)."""

    async def get_value() -> int:
        return 10

    return QBox(get_value())


@pytest.fixture
def list_box() -> QBox[list[int]]:
    """Create a QBox containing a list [1, 2, 3]."""

    async def get_list() -> list[int]:
        return [1, 2, 3]

    return QBox(get_list())


@pytest.fixture
def failing_box() -> QBox[int]:
    """Create a QBox that raises ValueError when evaluated."""

    async def failing() -> int:
        raise ValueError("test error")

    return QBox(failing())


@pytest.fixture
def isinstance_patched() -> Generator[None, None, None]:
    """Temporarily enable isinstance patching for QBox.

    Automatically cleans up after the test.
    """
    enable_qbox_isinstance()
    try:
        yield
    finally:
        disable_qbox_isinstance()
