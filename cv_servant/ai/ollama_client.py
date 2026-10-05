"""
Ollama Client wrapper for local LLM text generation and vision tasks.
Supports JSON mode, streaming, and vision inputs.
"""
import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from cv_servant.config import OLLAMA_BASE_URL, OLLAMA_TEXT_MODEL, OLLAMA_VISION_MODEL

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        text_model: str = OLLAMA_TEXT_MODEL,
        vision_model: str = OLLAMA_VISION_MODEL,
    ):
        self.base_url = base_url.rstrip("/")
        self.text_model = text_model
        self.vision_model = vision_model

    def is_alive(self) -> bool:
        """Check if Ollama server is running."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return res.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        format_json: bool = False,
        temperature: float = 0.2,
        timeout: int = 120,
        num_ctx: int = 8192,
        num_predict: int = 4096,
        think: bool = False,
    ) -> str:
        """Generate text using local model."""
        target_model = model or self.text_model
        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        }
        if not think:
            payload["think"] = False
        if system:
            payload["system"] = system
        if format_json:
            payload["format"] = "json"

        try:
            res = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=timeout,
            )
            res.raise_for_status()
            data = res.json()
            resp = data.get("response", "").strip()
            # If response is empty but thinking contains text (fallback for reasoning models)
            if not resp and data.get("thinking"):
                resp = data.get("thinking", "").strip()
            return resp
        except Exception as e:
            logger.error(f"Ollama generation failed ({target_model}): {e}")
            raise

    def analyze_image(
        self,
        image_path: Path,
        prompt: str,
        system: Optional[str] = None,
        format_json: bool = False,
        timeout: int = 180,
        num_ctx: int = 8192,
        num_predict: int = 4096,
        think: bool = False,
    ) -> str:
        """Analyze an image using the local vision model."""
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload: Dict[str, Any] = {
            "model": self.vision_model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        }
        if not think:
            payload["think"] = False
        if system:
            payload["system"] = system
        if format_json:
            payload["format"] = "json"

        try:
            res = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=timeout,
            )
            res.raise_for_status()
            data = res.json()
            resp = data.get("response", "").strip()
            if not resp and data.get("thinking"):
                resp = data.get("thinking", "").strip()
            return resp
        except Exception as e:
            logger.error(f"Ollama vision analysis failed: {e}")
            raise
