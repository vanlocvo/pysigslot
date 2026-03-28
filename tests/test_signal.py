import asyncio
import gc
import pytest
from pysigslot import Signal

def test_sync_handler():
    key = object()
    sig: Signal[[int]] = Signal("test_sync", key)
    
    received = []
    
    def handler(val: int):
        received.append(val)
        
    conn = sig.connect(handler)
    
    # Emit with correct key
    asyncio.run(sig.emit(key, 42))
    assert received == [42]

@pytest.mark.asyncio
async def test_async_handler():
    key = object()
    sig: Signal[[str]] = Signal("test_async", key)
    
    received = []
    
    async def handler(val: str):
        await asyncio.sleep(0)  # mimic async IO
        received.append(val)
        
    conn = sig.connect(handler)
    
    await sig.emit(key, "hello")
    assert received == ["hello"]

@pytest.mark.asyncio
async def test_multiple_handlers():
    key = object()
    sig: Signal[[int]] = Signal("test_multi", key)
    
    results = []
    
    def sync_handler(val: int):
        results.append(f"sync:{val}")
        
    async def async_handler(val: int):
        results.append(f"async:{val}")
        
    conn1 = sig.connect(sync_handler)
    conn2 = sig.connect(async_handler)
    
    await sig.emit(key, 100)
    assert results == ["sync:100", "async:100"]

@pytest.mark.asyncio
async def test_disconnect_manual():
    key = object()
    sig: Signal[[]] = Signal("test_disconnect", key)
    
    calls = []
    def handler():
        calls.append(1)
        
    conn = sig.connect(handler)
    await sig.emit(key)
    assert len(calls) == 1
    
    conn.disconnect()
    await sig.emit(key)
    assert len(calls) == 1

@pytest.mark.asyncio
async def test_no_auto_disconnect_on_gc():
    """Dropping a SignalConnection reference must NOT auto-disconnect.
    The handler stays connected until disconnect() is called explicitly."""
    key = object()
    sig: Signal[[]] = Signal("test_gc", key)

    calls = []
    def handler():
        calls.append(1)

    conn = sig.connect(handler)
    assert sig.handler_count == 1

    # Drop the reference — connection must survive GC
    del conn
    gc.collect()

    assert sig.handler_count == 1
    await sig.emit(key)
    assert len(calls) == 1

@pytest.mark.asyncio
async def test_decorator():
    key = object()
    sig: Signal[[int]] = Signal("test_deco", key)
    
    calls = []
    
    @sig
    def handler(v: int):
        calls.append(v)
        
    await sig.emit(key, 5)
    assert calls == [5]
    assert sig.handler_count == 1

@pytest.mark.asyncio
async def test_security_emit():
    key = object()
    sig: Signal[[]] = Signal("test_security", key)
    
    with pytest.raises(PermissionError):
        await sig.emit(object())

@pytest.mark.asyncio
async def test_security_clear():
    key = object()
    sig: Signal[[]] = Signal("test_clear", key)
    
    conn = sig.connect(lambda: None)
    assert sig.handler_count == 1
    
    with pytest.raises(PermissionError):
        sig.clear(object())
        
    sig.clear(key)
    assert sig.handler_count == 0

@pytest.mark.asyncio
async def test_handler_exception(caplog):
    key = object()
    sig: Signal[[]] = Signal("test_exc", key)
    
    def bad_handler():
        raise ValueError("boom")
        
    conn = sig.connect(bad_handler)
    
    # emit shouldn't raise the error, but log it
    await sig.emit(key)
    
    assert "raised an exception" in caplog.text
    assert "ValueError: boom" in caplog.text

def test_emit_sync():
    key = object()
    sig: Signal[[int]] = Signal("test_sync2", key)
    
    received = []
    def handler(v: int):
        received.append(v)
        
    conn = sig.connect(handler)
    sig.emit_sync(key, 99)
    assert received == [99]

def test_emit_sync_with_async_handler():
    key = object()
    sig: Signal[[int]] = Signal("test_sync_err", key)
    
    async def handler(v: int):
        pass
        
    conn = sig.connect(handler)
    
    with pytest.raises(RuntimeError) as exc_info:
        sig.emit_sync(key, 1)
        
    assert "Cannot call async handler" in str(exc_info.value)
    assert "from emit_sync" in str(exc_info.value)
