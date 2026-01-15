"""Tests for Baidu OCR model."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docling.datamodel.pipeline_options import BaiduOcrApiType, BaiduOcrOptions


class TestBaiduOcrOptions:
    """Test BaiduOcrOptions configuration class."""

    def test_default_options(self):
        """Test default option values."""
        options = BaiduOcrOptions(api_key="test_key", secret_key="test_secret")
        assert options.kind == "baidu"
        assert options.lang == ["CHN_ENG"]
        assert options.api_type == BaiduOcrApiType.GENERAL_BASIC
        assert options.timeout == 10.0
        assert options.detect_direction is False
        assert options.confidence_threshold == 0.5

    def test_custom_options(self):
        """Test custom option values."""
        options = BaiduOcrOptions(
            api_key="test_key",
            secret_key="test_secret",
            api_type=BaiduOcrApiType.ACCURATE_BASIC,
            timeout=20.0,
            detect_direction=True,
        )
        assert options.api_type == BaiduOcrApiType.ACCURATE_BASIC
        assert options.timeout == 20.0
        assert options.detect_direction is True

    def test_config_file_option(self):
        """Test config file path option."""
        options = BaiduOcrOptions(config_file="~/.baidu_ocr.json")
        assert options.config_file == "~/.baidu_ocr.json"
        assert options.api_key is None
        assert options.secret_key is None


class TestBaiduOcrModelCredentials:
    """Test BaiduOcrModel credential loading."""

    def test_load_credentials_from_options(self):
        """Test loading credentials from direct options."""
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.models.stages.ocr.baidu_ocr_model import BaiduOcrModel

        options = BaiduOcrOptions(api_key="test_key", secret_key="test_secret")
        model = BaiduOcrModel(
            enabled=True,
            artifacts_path=None,
            options=options,
            accelerator_options=AcceleratorOptions(),
        )
        assert model.api_key == "test_key"
        assert model.secret_key == "test_secret"

    def test_load_credentials_from_config_file(self):
        """Test loading credentials from config file."""
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.models.stages.ocr.baidu_ocr_model import BaiduOcrModel

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"api_key": "file_key", "secret_key": "file_secret"}, f)
            config_path = f.name

        try:
            options = BaiduOcrOptions(config_file=config_path)
            model = BaiduOcrModel(
                enabled=True,
                artifacts_path=None,
                options=options,
                accelerator_options=AcceleratorOptions(),
            )
            assert model.api_key == "file_key"
            assert model.secret_key == "file_secret"
        finally:
            Path(config_path).unlink()

    def test_missing_credentials_raises_error(self):
        """Test that missing credentials raises ValueError."""
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.models.stages.ocr.baidu_ocr_model import BaiduOcrModel

        options = BaiduOcrOptions()
        with pytest.raises(ValueError, match="credentials not provided"):
            BaiduOcrModel(
                enabled=True,
                artifacts_path=None,
                options=options,
                accelerator_options=AcceleratorOptions(),
            )

    def test_load_credentials_from_environment(self):
        """Test loading credentials from environment variables."""
        import os
        from unittest.mock import patch

        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.models.stages.ocr.baidu_ocr_model import BaiduOcrModel

        env_vars = {
            "BAIDU_OCR_API_KEY": "env_api_key",
            "BAIDU_OCR_SECRET_KEY": "env_secret_key",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            options = BaiduOcrOptions()  # No direct params or config file
            model = BaiduOcrModel(
                enabled=True,
                artifacts_path=None,
                options=options,
                accelerator_options=AcceleratorOptions(),
            )
            assert model.api_key == "env_api_key"
            assert model.secret_key == "env_secret_key"

    def test_direct_params_override_environment(self):
        """Test that direct parameters take priority over environment variables."""
        import os
        from unittest.mock import patch

        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.models.stages.ocr.baidu_ocr_model import BaiduOcrModel

        env_vars = {
            "BAIDU_OCR_API_KEY": "env_api_key",
            "BAIDU_OCR_SECRET_KEY": "env_secret_key",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            options = BaiduOcrOptions(api_key="direct_key", secret_key="direct_secret")
            model = BaiduOcrModel(
                enabled=True,
                artifacts_path=None,
                options=options,
                accelerator_options=AcceleratorOptions(),
            )
            # Direct params should take priority
            assert model.api_key == "direct_key"
            assert model.secret_key == "direct_secret"


class TestBaiduOcrModelApi:
    """Test BaiduOcrModel API interactions with mocking."""

    @patch("docling.models.stages.ocr.baidu_ocr_model.requests.post")
    def test_get_access_token(self, mock_post):
        """Test access token retrieval."""
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.models.stages.ocr.baidu_ocr_model import BaiduOcrModel

        # Mock token response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_token_123",
            "expires_in": 2592000,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        options = BaiduOcrOptions(api_key="test_key", secret_key="test_secret")
        model = BaiduOcrModel(
            enabled=True,
            artifacts_path=None,
            options=options,
            accelerator_options=AcceleratorOptions(),
        )

        # Clear any cached token
        BaiduOcrModel._access_token = None
        BaiduOcrModel._token_expires_at = None

        token = model._get_access_token()
        assert token == "test_token_123"
        mock_post.assert_called_once()

    @patch("docling.models.stages.ocr.baidu_ocr_model.requests.post")
    def test_call_ocr_api(self, mock_post):
        """Test OCR API call."""
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.models.stages.ocr.baidu_ocr_model import BaiduOcrModel

        # Mock responses for token and OCR
        token_response = MagicMock()
        token_response.json.return_value = {"access_token": "token", "expires_in": 2592000}
        token_response.raise_for_status = MagicMock()

        ocr_response = MagicMock()
        ocr_response.json.return_value = {
            "words_result": [{"words": "Hello"}, {"words": "World"}],
            "words_result_num": 2,
        }
        ocr_response.raise_for_status = MagicMock()

        mock_post.side_effect = [token_response, ocr_response]

        options = BaiduOcrOptions(api_key="test_key", secret_key="test_secret")
        model = BaiduOcrModel(
            enabled=True,
            artifacts_path=None,
            options=options,
            accelerator_options=AcceleratorOptions(),
        )

        # Clear cached token
        BaiduOcrModel._access_token = None
        BaiduOcrModel._token_expires_at = None

        result = model._call_ocr_api(b"fake_image_bytes")
        assert len(result) == 2
        assert result[0]["words"] == "Hello"
        assert result[1]["words"] == "World"
