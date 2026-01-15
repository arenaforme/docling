import base64
import json
import logging
import os
import threading
import time
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Type

import requests
from docling_core.types.doc import BoundingBox, CoordOrigin
from docling_core.types.doc.page import BoundingRectangle, TextCell

from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import Page
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import BaiduOcrApiType, BaiduOcrOptions, OcrOptions
from docling.datamodel.settings import settings
from docling.models.base_ocr_model import BaseOcrModel
from docling.utils.profiling import TimeRecorder

_log = logging.getLogger(__name__)


class BaiduOcrModel(BaseOcrModel):
    """Baidu Cloud OCR Model implementation."""

    # Class-level token cache (thread-safe)
    _token_lock = threading.Lock()
    _access_token: Optional[str] = None
    _token_expires_at: Optional[float] = None

    # API endpoints
    _TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    _API_URLS = {
        BaiduOcrApiType.GENERAL_BASIC: "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic",
        BaiduOcrApiType.ACCURATE_BASIC: "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic",
    }

    def __init__(
        self,
        enabled: bool,
        artifacts_path: Optional[Path],
        options: BaiduOcrOptions,
        accelerator_options: AcceleratorOptions,
    ):
        super().__init__(
            enabled=enabled,
            artifacts_path=artifacts_path,
            options=options,
            accelerator_options=accelerator_options,
        )
        self.options: BaiduOcrOptions
        self.scale = 3  # multiplier for 72 dpi == 216 dpi

        # Load credentials
        self.api_key: Optional[str] = None
        self.secret_key: Optional[str] = None

        if self.enabled:
            self._load_credentials()

    def _load_credentials(self) -> None:
        """Load API credentials from options, config file, or environment variables.

        Priority order:
        1. Direct parameters (api_key/secret_key in options)
        2. Config file (config_file in options)
        3. Environment variables (BAIDU_OCR_API_KEY/BAIDU_OCR_SECRET_KEY)
        """
        # Priority 1: direct parameters
        if self.options.api_key and self.options.secret_key:
            self.api_key = self.options.api_key
            self.secret_key = self.options.secret_key
        # Priority 2: config file
        elif self.options.config_file:
            config_path = Path(self.options.config_file).expanduser()
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.api_key = config.get("api_key")
                    self.secret_key = config.get("secret_key")
            else:
                raise FileNotFoundError(f"Baidu OCR config file not found: {config_path}")
        # Priority 3: environment variables
        else:
            self.api_key = os.environ.get("BAIDU_OCR_API_KEY")
            self.secret_key = os.environ.get("BAIDU_OCR_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Baidu OCR credentials not provided. "
                "Please set api_key/secret_key, provide a config_file, "
                "or set BAIDU_OCR_API_KEY/BAIDU_OCR_SECRET_KEY environment variables."
            )

    def _get_access_token(self) -> str:
        """Get Baidu OAuth access token with caching."""
        with self._token_lock:
            current_time = time.time()
            # Check if token is still valid (with 1 hour buffer)
            if (
                self._access_token is not None
                and self._token_expires_at is not None
                and current_time < self._token_expires_at - 3600
            ):
                return self._access_token

            # Request new token
            params = {
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key,
            }
            response = requests.post(
                self._TOKEN_URL, params=params, timeout=self.options.timeout
            )
            response.raise_for_status()
            result = response.json()

            if "access_token" not in result:
                raise RuntimeError(f"Failed to get Baidu access token: {result}")

            BaiduOcrModel._access_token = result["access_token"]
            # Token expires in 30 days (2592000 seconds)
            expires_in = result.get("expires_in", 2592000)
            BaiduOcrModel._token_expires_at = current_time + expires_in

            return self._access_token

    def _call_ocr_api(self, image_bytes: bytes) -> List[dict]:
        """Call Baidu OCR API and return recognized text results."""
        access_token = self._get_access_token()
        api_url = self._API_URLS[self.options.api_type]

        # Prepare request
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "image": image_base64,
            "detect_direction": str(self.options.detect_direction).lower(),
        }
        params = {"access_token": access_token}

        # Call API
        response = requests.post(
            api_url,
            headers=headers,
            data=data,
            params=params,
            timeout=self.options.timeout,
        )
        response.raise_for_status()
        result = response.json()

        # Check for API errors
        if "error_code" in result:
            raise RuntimeError(
                f"Baidu OCR API error: {result.get('error_code')} - {result.get('error_msg')}"
            )

        return result.get("words_result", [])

    def __call__(
        self, conv_res: ConversionResult, page_batch: Iterable[Page]
    ) -> Iterable[Page]:
        if not self.enabled:
            yield from page_batch
            return

        for page in page_batch:
            assert page._backend is not None
            if not page._backend.is_valid():
                yield page
            else:
                with TimeRecorder(conv_res, "ocr"):
                    ocr_rects = self.get_ocr_rects(page)

                    all_ocr_cells = []
                    for ocr_rect in ocr_rects:
                        # Skip zero area boxes
                        if ocr_rect.area() == 0:
                            continue

                        high_res_image = page._backend.get_page_image(
                            scale=self.scale, cropbox=ocr_rect
                        )

                        # Convert image to bytes
                        img_buffer = BytesIO()
                        high_res_image.save(img_buffer, format="PNG")
                        image_bytes = img_buffer.getvalue()

                        # Call Baidu OCR API
                        try:
                            words_result = self._call_ocr_api(image_bytes)
                        except Exception as e:
                            _log.warning(f"Baidu OCR API call failed: {e}")
                            continue

                        del high_res_image
                        del img_buffer

                        # Convert Baidu results to TextCell format
                        # Note: general_basic API returns only text, no coordinates
                        # We create cells spanning the full OCR rect
                        for ix, word_info in enumerate(words_result):
                            text = word_info.get("words", "")
                            if not text:
                                continue

                            # Since basic API doesn't return coordinates,
                            # we assign the full ocr_rect to each line
                            cells = [
                                TextCell(
                                    index=ix,
                                    text=text,
                                    orig=text,
                                    from_ocr=True,
                                    confidence=1.0,  # Basic API doesn't return confidence
                                    rect=BoundingRectangle.from_bounding_box(
                                        BoundingBox(
                                            l=ocr_rect.l,
                                            t=ocr_rect.t,
                                            r=ocr_rect.r,
                                            b=ocr_rect.b,
                                            coord_origin=CoordOrigin.TOPLEFT,
                                        )
                                    ),
                                )
                            ]
                            all_ocr_cells.extend(cells)

                    # Post-process the cells
                    self.post_process_cells(all_ocr_cells, page)

                # DEBUG code:
                if settings.debug.visualize_ocr:
                    self.draw_ocr_rects_and_cells(conv_res, page, ocr_rects)

                yield page

    @classmethod
    def get_options_type(cls) -> Type[OcrOptions]:
        return BaiduOcrOptions
