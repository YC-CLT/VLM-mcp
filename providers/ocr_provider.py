import asyncio

from rapidocr_onnxruntime import RapidOCR


class OCRProvider:
    def __init__(self, unload_delay: float = 30):
        self._ocr = None
        self._unload_delay = unload_delay
        self._unload_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def recognize(self, image_bytes: bytes) -> list:
        async with self._lock:
            if self._ocr is None:
                self._ocr = await asyncio.to_thread(RapidOCR)
            self._cancel_unload()
            result, _ = await asyncio.to_thread(self._ocr, image_bytes)
            self._schedule_unload()
            return result

    def _cancel_unload(self):
        if self._unload_task and not self._unload_task.done():
            self._unload_task.cancel()

    def _schedule_unload(self):
        self._unload_task = asyncio.create_task(self._unload_after(self._unload_delay))

    async def _unload_after(self, delay: float):
        await asyncio.sleep(delay)
        async with self._lock:
            self._ocr = None


ocr = OCRProvider()