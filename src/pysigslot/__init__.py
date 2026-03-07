"""
Signal/Slot System for event-driven communication.

A lightweight Signal implementation inspired by Qt's signal/slot mechanism.
Signals can be emitted, and any number of handlers (slots) can be connected.

Access control is enforced using an **Access Key**:
  - The creator of the signal passes a unique `access_key` (e.g. an `object()`).
  - To `emit()` or `clear()`, the caller must provide that exact key.
  - External code receives the `Signal` directly, allowing them to `connect()`
    or `disconnect()`, but they cannot emit without the secret key.

Usage:
    from pysignals import Signal

    class MyClass:
        def __init__(self):
            # Create a secret key for emitting
            self._emit_key = object()
            
            # Create the signal, locking emit/clear with the key
            self.sig_data_ready = Signal("data_ready", self._emit_key)

        async def _fetch_data(self):
            data = "Hello"
            # Only the owner can emit successfully by passing the key
            await self.sig_data_ready.emit(self._emit_key, data)

    obj = MyClass()

    # ── Decorator usage (permanent connection) ──
    @obj.sig_data_ready
    async def on_data(data):
        print(f"Data: {data}")

    # ── Explicit usage (auto-disconnect when connection is destroyed) ──
    conn = obj.sig_data_ready.connect(some_handler)
    conn.disconnect()   # manual disconnect
    # or let `conn` go out of scope → auto-disconnects
"""

import asyncio
import logging
import weakref
from typing import Any, Callable, Coroutine

__version__ = "0.1.0"
__all__ = ["Signal"]

logger = logging.getLogger("pysigslot")

AsyncHandler = Callable[..., Coroutine[Any, Any, None]]
SyncHandler = Callable[..., None]
Handler = AsyncHandler | SyncHandler


class SignalConnection:
    """
    Represents a connection between a Signal and a handler.

    Returned by Signal.connect(). Auto-disconnects when this object
    is garbage-collected (destructor).

    Usage:
        conn = some_signal.connect(my_handler)
        conn.disconnect()   # explicit
        # or let `conn` go out of scope → auto-disconnects
    """

    __slots__ = ("_signal_ref", "_handler", "_is_connected")

    def __init__(self, signal: "Signal", handler: Handler) -> None:
        self._signal_ref = weakref.ref(signal)
        self._handler = handler
        self._is_connected = True

    def disconnect(self) -> None:
        """Manually disconnect the handler from the signal."""
        if not self._is_connected:
            return
        self._is_connected = False
        signal_obj = self._signal_ref()
        if signal_obj is not None and self._handler in signal_obj._handlers:
            signal_obj._handlers.remove(self._handler)

    @property
    def is_connected(self) -> bool:
        """Whether this connection is still active."""
        return self._is_connected

    def __del__(self) -> None:
        self.disconnect()

    def __repr__(self) -> str:
        status = "connected" if self._is_connected else "disconnected"
        handler_name = getattr(self._handler, "__name__", repr(self._handler))
        return f"<SignalConnection {status} handler={handler_name}>"


class Signal:
    """
    A signal that can be connected to multiple handlers (slots).

    Handlers can be sync or async functions. When the signal is emitted,
    all connected handlers are called in order with the emitted arguments.

    Emit access is protected by an access key provided at initialization.

    Two connection styles:
        @signal          — decorator, returns handler (permanent)
        signal.connect() — returns SignalConnection (auto-disconnect on destruction)

    Methods:
        connect(handler)           — connect; returns SignalConnection
        disconnect(handler)        — disconnect a previously connected handler
        emit(access_key, *args)    — emit the signal (requires secret key)
        clear(access_key)          — disconnect all handlers (requires secret key)
    """

    __slots__ = ("_name", "_access_key", "_handlers", "__weakref__")

    def __init__(self, name: str = "", access_key: Any = None):
        """
        Initialize the Signal.

        Args:
            name: Optional name for debugging
            access_key: Secret key required to emit or clear. If None,
                        a unique internal key is generated (making it impossible
                        to emit unless you extract it, which is intentionally hard).
        """
        self._name = name
        self._access_key = access_key if access_key is not None else object()
        self._handlers: list[Handler] = []

    # ── Handler management ─────────────────────────────────────────

    def __call__(self, handler: Handler) -> Handler:
        """
        Decorator usage: connect a handler permanently, returning the handler.

        Example:
            @signal
            async def on_event(data):
                print(data)
        """
        if handler not in self._handlers:
            self._handlers.append(handler)
        return handler

    def connect(self, handler: Handler) -> SignalConnection:
        """
        Connect a handler and return a SignalConnection.

        The connection auto-disconnects when garbage-collected.

        Args:
            handler: sync or async callable to invoke on emit

        Returns:
            SignalConnection that can disconnect() manually or auto-disconnects
        """
        if handler not in self._handlers:
            self._handlers.append(handler)
        return SignalConnection(self, handler)

    def disconnect(self, handler: Handler) -> None:
        """
        Disconnect a handler from this signal.

        Args:
            handler: the handler to remove

        Raises:
            ValueError: if the handler was not connected
        """
        try:
            self._handlers.remove(handler)
        except ValueError as e:
            raise ValueError(
                f"Handler {handler!r} is not connected to signal '{self._name}'"
            ) from e

    # ── Protected Operations (Requires Key) ────────────────────────

    async def emit(self, access_key: Any, *args: Any, **kwargs: Any) -> None:
        """
        Emit this signal, calling all connected handlers.

        Args:
            access_key: Must match the key provided at initialization.
            *args:       positional arguments forwarded to handlers
            **kwargs:    keyword arguments forwarded to handlers

        Raises:
            PermissionError: If the access key is incorrect.
        """
        if access_key is not self._access_key:
            raise PermissionError(f"Invalid access key for emit on '{self._name}' signal.")

        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    handler(*args, **kwargs)
            except Exception:  # noqa: BLE001  # pylint: disable=broad-except
                handler_name = getattr(handler, "__name__", repr(handler))
                logger.error(
                    "Signal '%s' handler '%s' raised an exception",
                    self._name, handler_name,
                    exc_info=True,
                )

    def clear(self, access_key: Any) -> None:
        """
        Disconnect all handlers. Requires the access key.
        """
        if access_key is not self._access_key:
            raise PermissionError(f"Invalid access key for clear on '{self._name}' signal.")
        self._handlers.clear()

    @property
    def handler_count(self) -> int:
        """Number of connected handlers."""
        return len(self._handlers)

    def __repr__(self) -> str:
        name = f" '{self._name}'" if self._name else ""
        return f"<Signal{name} handlers={self.handler_count}>"
