# PySigSlot

A lightweight, rigorous Signal/Slot implementation for Python, heavily inspired by Qt. It supports both synchronous and asynchronous event handlers, automatic disconnection via weak references, and enforces true access control over who can emit signals.

## Why this instead of standard callbacks?
1. **Multiple Listeners**: Any number of functions can connect to a single signal.
2. **Access Control**: Signals are strictly public (connect/disconnect only). The capability to `emit` requires a secret Key assigned to the owner, preventing spaghetti-code where anyone emits everything.
3. **Async Support**: Simply connect `async def` functions, and they are natively awaited when emitted. Mixed sync/async handlers are fully supported.
4. **Auto Cleanup**: Connections via `connect()` auto-disconnect when the connection object is garbage collected.
5. **Clean Decorators**: Permanent connections can be made elegantly using `@signal` syntax.

## Installation

```bash
pip install git+https://github.com/vanlocvo/pysigslot.git
```

## Quick Start

```python
import asyncio
from pysigslot import Signal

class Downloader:
    def __init__(self):
        # 1. Create a secret capability key
        self._emit_key = object()
        
        # 2. Expose the public Signal (passing the secret key)
        self.sig_progress = Signal("progress", self._emit_key)
        self.sig_finished = Signal("finished", self._emit_key)

    async def download(self):
        for i in range(1, 4):
            await asyncio.sleep(0.5)
            # 3. Emit using the secret key
            await self.sig_progress.emit(self._emit_key, i * 33)
            
        await self.sig_finished.emit(self._emit_key, "Done!")

# --- Usage ---

worker = Downloader()

# Method A: Decorator (Permanent connection)
@worker.sig_progress
def on_progress(percent):
    print(f"Progress: {percent}%")

async def main():
    # Method B: Explicit (Auto-disconnects if `conn` is destroyed)
    conn = worker.sig_finished.connect(lambda msg: print(f"Finished: {msg}"))
    
    await worker.download()
    
    # Optional explicit disconnect
    conn.disconnect()

asyncio.run(main())
```

## Security / Access Control

If external code attempts to emit a signal, it will fail:

```python
worker.sig_progress.emit(None, 100)
# PermissionError: Invalid access key for emit on 'progress' signal.
```

---

*✨ This project was created and refined with the assistance of an AI coding assistant.*
