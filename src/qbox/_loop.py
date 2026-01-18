"""Background event loop manager for running async operations."""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import threading
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from concurrent.futures import Future
    from typing import Any

T = TypeVar("T")


class BackgroundLoopManager:
    """Singleton managing a background asyncio event loop.

    This class maintains a single daemon thread running an asyncio event loop
    that can execute coroutines from synchronous code. The loop runs until
    the Python interpreter shuts down.

    The singleton pattern ensures all QBox instances share the same background
    loop, avoiding thread proliferation.
    """

    _instance: BackgroundLoopManager | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> BackgroundLoopManager:
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # pragma: no cover (race condition)
                    instance = super().__new__(cls)
                    instance._initialize()
                    cls._instance = instance
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the background loop and thread."""
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="qbox-background-loop",
        )
        try:
            self._thread.start()
        except Exception:  # pragma: no cover (defensive - thread creation failure)
            self._loop.close()
            raise
        atexit.register(self._shutdown)

    def _run_loop(self) -> None:
        """Run the event loop in the background thread."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _shutdown(self) -> None:  # pragma: no cover (called at atexit)
        """Shutdown the background loop cleanly.

        Attempts to stop the event loop gracefully with a 5-second timeout.
        If the thread doesn't join within the timeout, it's left as a daemon
        thread which will be terminated when the process exits.
        """
        with contextlib.suppress(Exception):
            if self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._thread.join(timeout=5.0)
            # Close the loop after stopping
            if not self._loop.is_closed():
                self._loop.close()

    def submit(self, coro: Coroutine[Any, Any, T]) -> Future[T]:
        """Submit a coroutine for execution on the background loop.

        Args:
            coro: The coroutine to execute.

        Returns:
            A concurrent.futures.Future that will contain the result.
        """
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Get the background event loop."""
        return self._loop

    def __repr__(self) -> str:
        """Return a string representation of the BackgroundLoopManager."""
        loop_running = self._loop.is_running() if hasattr(self, "_loop") else False
        thread_alive = self._thread.is_alive() if hasattr(self, "_thread") else False
        thread_name = self._thread.name if hasattr(self, "_thread") else "N/A"
        return (
            f"<BackgroundLoopManager "
            f"loop_running={loop_running} "
            f"thread_alive={thread_alive} "
            f"thread_name={thread_name!r}>"
        )


def get_loop_manager() -> BackgroundLoopManager:
    """Get the global BackgroundLoopManager instance.

    Returns:
        The singleton BackgroundLoopManager.
    """
    return BackgroundLoopManager()


def submit_to_loop(coro: Coroutine[Any, Any, T]) -> Future[T]:
    """Submit a coroutine for execution on the background event loop.

    The background loop runs on a separate daemon thread, which ensures
    that blocking on the result (via future.result()) never deadlocks,
    regardless of whether the caller is in a sync or async context.

    Args:
        coro: The coroutine to execute.

    Returns:
        A concurrent.futures.Future that will contain the result.
    """
    return get_loop_manager().submit(coro)
