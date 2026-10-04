"""
Dual-Engine OCR for job flyers and screenshots.
Combines offline hardware-accelerated Windows Media OCR (Arabic 'ar-SA' + English 'en-US')
with Ollama's vision model (Qwen-VL) for rich semantic extraction.
"""
import asyncio
import io
import logging
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image

logger = logging.getLogger(__name__)

# Check if winrt OCR is available
HAS_WINRT = False
try:
    import winrt.windows.globalization as wg
    import winrt.windows.graphics.imaging as wgi
    import winrt.windows.media.ocr as wmo
    import winrt.windows.storage.streams as wss
    HAS_WINRT = True
except ImportError:
    HAS_WINRT = False


class OCREngine:
    def __init__(self, ollama_client=None):
        self.ollama = ollama_client
        self.has_winrt = HAS_WINRT

    async def _run_winrt_ocr_bytes(self, img_bytes: bytes, lang_tag: str = "ar-SA") -> str:
        """Run Windows Media OCR on image bytes for a specific language."""
        if not self.has_winrt:
            return ""

        lang = wg.Language(lang_tag)
        if not wmo.OcrEngine.is_language_supported(lang):
            logger.warning(f"Language {lang_tag} is not supported by Windows Media OCR.")
            return ""

        engine = wmo.OcrEngine.try_create_from_language(lang)
        if not engine:
            return ""

        # Write bytes to WinRT InMemoryRandomAccessStream
        stream = wss.InMemoryRandomAccessStream()
        writer = wss.DataWriter(stream)
        writer.write_bytes(list(img_bytes))
        await writer.store_async()
        await writer.flush_async()
        writer.detach_stream()
        stream.seek(0)

        decoder = await wgi.BitmapDecoder.create_async(stream)
        software_bitmap = await decoder.get_software_bitmap_async()

        ocr_result = await engine.recognize_async(software_bitmap)
        lines = [line.text for line in ocr_result.lines]
        return "\n".join(lines)

    def extract_text_windows_ocr(self, image_path: Path) -> str:
        """
        Extract text using native Windows OCR.
        Runs both Arabic (ar-SA) and English (en-US) and combines them.
        """
        if not self.has_winrt or not image_path.exists():
            return ""

        try:
            with open(image_path, "rb") as f:
                img_bytes = f.read()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                ar_text = loop.run_until_complete(self._run_winrt_ocr_bytes(img_bytes, "ar-SA"))
                en_text = loop.run_until_complete(self._run_winrt_ocr_bytes(img_bytes, "en-US"))
            finally:
                loop.close()

            # Merge results, removing exact duplicates
            combined = []
            if ar_text.strip():
                combined.append("=== Arabic OCR ===")
                combined.append(ar_text.strip())
            if en_text.strip():
                combined.append("=== English OCR ===")
                combined.append(en_text.strip())

            return "\n\n".join(combined)
        except Exception as e:
            logger.error(f"Windows Media OCR failed: {e}")
            return ""

    def extract_text_qwen_vl(self, image_path: Path) -> str:
        """Extract text and structure using Qwen-VL via Ollama."""
        if not self.ollama:
            return ""

        prompt = (
            "Extract all text and key details from this job advertisement image accurately. "
            "Include: Job Title, Company/Office Name, Required Qualifications, "
            "Experience Years, Contact Email Address, Phone Number, Location/Country, and Deadline. "
            "Read both Arabic and English text accurately."
        )
        try:
            return self.ollama.analyze_image(image_path, prompt=prompt)
        except Exception as e:
            logger.error(f"Qwen-VL OCR failed: {e}")
            return ""

    def process_image(self, image_path: Path) -> Dict[str, str]:
        """
        Complete processing: Uses Windows Media OCR first for raw high-speed fidelity,
        plus Vision model if needed.
        """
        win_text = self.extract_text_windows_ocr(image_path)
        vl_text = ""

        # If Windows OCR text is short or empty, or to enrich layout understanding:
        if len(win_text.strip()) < 50 and self.ollama:
            vl_text = self.extract_text_qwen_vl(image_path)

        return {
            "image_path": str(image_path),
            "windows_ocr_text": win_text,
            "vision_model_text": vl_text,
            "combined_raw": f"{win_text}\n\n{vl_text}".strip()
        }
