import asyncio
from unittest.mock import patch, MagicMock

import pytest

from providers.ocr_provider import OCRProvider, ocr


class TestOCRProvider:

    def test_singleton_exists(self):
        assert ocr is not None
        assert isinstance(ocr, OCRProvider)
        assert ocr._ocr is None

    @pytest.mark.asyncio
    async def test_recognize_loads_on_first_call(self):
        fake_ocr = MagicMock()
        fake_ocr.return_value = ([], None)
        with patch("providers.ocr_provider.RapidOCR", return_value=fake_ocr):
            provider = OCRProvider()
            assert provider._ocr is None
            result = await provider.recognize(b"fake_bytes")
            assert provider._ocr is fake_ocr
            assert result == []

    @pytest.mark.asyncio
    async def test_recognize_reuses_loaded_instance(self):
        fake_ocr = MagicMock()
        fake_ocr.return_value = ([], None)
        with patch("providers.ocr_provider.RapidOCR", return_value=fake_ocr):
            provider = OCRProvider()
            await provider.recognize(b"first")
            await provider.recognize(b"second")
            assert fake_ocr.call_count == 2
            assert provider._ocr is fake_ocr

    @pytest.mark.asyncio
    async def test_recognize_returns_raw_result(self):
        fake_result = [
            [[[9, 6], [83, 6], [83, 29], [9, 29]], "hello", 0.999]
        ]
        fake_ocr = MagicMock()
        fake_ocr.return_value = (fake_result, None)
        with patch("providers.ocr_provider.RapidOCR", return_value=fake_ocr):
            provider = OCRProvider()
            result = await provider.recognize(b"img")
            assert result == fake_result

    @pytest.mark.asyncio
    async def test_unload_after_delay(self):
        fake_ocr = MagicMock()
        fake_ocr.return_value = ([], None)
        with patch("providers.ocr_provider.RapidOCR", return_value=fake_ocr):
            provider = OCRProvider()
            await provider.recognize(b"test")
            assert provider._ocr is not None
            await asyncio.sleep(0.2)
            assert provider._ocr is None

    @pytest.mark.asyncio
    async def test_concurrent_calls_do_not_race(self):
        call_count = 0

        def _fake_ocr(img_bytes):
            nonlocal call_count
            call_count += 1
            return ([], None)

        fake_ocr = MagicMock()
        fake_ocr.side_effect = _fake_ocr
        with patch("providers.ocr_provider.RapidOCR", return_value=fake_ocr):
            provider = OCRProvider()
            await asyncio.gather(
                provider.recognize(b"a"),
                provider.recognize(b"b"),
                provider.recognize(b"c"),
            )
            assert call_count == 3
            assert provider._ocr is fake_ocr

    @pytest.mark.asyncio
    async def test_cancelled_unload_does_not_unload(self):
        fake_ocr = MagicMock()
        fake_ocr.return_value = ([], None)
        with patch("providers.ocr_provider.RapidOCR", return_value=fake_ocr):
            provider = OCRProvider()
            await provider.recognize(b"t1")
            await asyncio.sleep(0.01)
            await provider.recognize(b"t2")
            await asyncio.sleep(0.01)
            await provider.recognize(b"t3")
            assert provider._ocr is not None