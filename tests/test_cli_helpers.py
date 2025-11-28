"""Tests for CLI helper functions."""

import os
from unittest.mock import patch

import pytest

from duplexer.cli import (
    create_process_callback,
    load_watch_config,
    log_watch_config,
    setup_watch_directories,
    str_to_bool,
)


class TestStrToBool:
    """Tests for str_to_bool helper."""

    def test_true_values(self):
        """Test various string representations of true."""
        assert str_to_bool("true") is True
        assert str_to_bool("True") is True
        assert str_to_bool("TRUE") is True
        assert str_to_bool("1") is True
        assert str_to_bool("yes") is True
        assert str_to_bool("YES") is True
        assert str_to_bool("on") is True
        assert str_to_bool("ON") is True

    def test_false_values(self):
        """Test various string representations of false."""
        assert str_to_bool("false") is False
        assert str_to_bool("False") is False
        assert str_to_bool("FALSE") is False
        assert str_to_bool("0") is False
        assert str_to_bool("no") is False
        assert str_to_bool("off") is False
        assert str_to_bool("anything") is False


class TestLoadWatchConfig:
    """Tests for load_watch_config helper."""

    def test_default_config(self):
        """Test loading config with all defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_watch_config(None, None, None)

            assert config["scan_pattern"] == "*.pdf"
            assert config["stability_seconds"] == 5.0
            assert config["require_ready_file"] is False
            assert config["reverse_backs"] is True
            assert config["insert_blank_lastback"] is False
            assert config["output_suffix"] == ".duplex"

    def test_cli_overrides(self):
        """Test CLI arguments override environment variables."""
        with patch.dict(
            os.environ,
            {
                "SCAN_GLOB": "*.PDF",
                "FILE_STABILITY_SECONDS": "10.0",
                "REQUIRE_READY_FILE": "true",
            },
        ):
            config = load_watch_config(
                pattern="scan_*.pdf",
                stability_seconds=3.0,
                require_ready_file=False,
            )

            # CLI overrides should take precedence
            assert config["scan_pattern"] == "scan_*.pdf"
            assert config["stability_seconds"] == 3.0
            assert config["require_ready_file"] is False

    def test_env_var_config(self):
        """Test loading config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "SCAN_GLOB": "document_*.pdf",
                "FILE_STABILITY_SECONDS": "15.5",
                "REQUIRE_READY_FILE": "yes",
                "REVERSE_BACKS": "false",
                "INSERT_BLANK_LASTBACK": "true",
                "OUTPUT_SUFFIX": ".processed",
            },
        ):
            config = load_watch_config(None, None, None)

            assert config["scan_pattern"] == "document_*.pdf"
            assert config["stability_seconds"] == 15.5
            assert config["require_ready_file"] is True
            assert config["reverse_backs"] is False
            assert config["insert_blank_lastback"] is True
            assert config["output_suffix"] == ".processed"


class TestLogWatchConfig:
    """Tests for log_watch_config helper."""

    def test_logs_configuration(self, caplog, tmp_path):
        """Test that configuration is logged correctly."""
        import logging

        caplog.set_level(logging.INFO)

        config = {
            "scan_pattern": "*.pdf",
            "stability_seconds": 5.0,
            "require_ready_file": False,
            "reverse_backs": True,
            "insert_blank_lastback": False,
            "output_suffix": ".duplex",
        }

        log_watch_config(
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            archive_dir=tmp_path / "archive",
            failed_dir=tmp_path / "failed",
            config=config,
        )

        # Check that key configuration items were logged
        log_text = caplog.text
        assert "Duplexer Configuration" in log_text
        assert "Input directory" in log_text
        assert "Output directory" in log_text
        assert "Scan pattern: *.pdf" in log_text
        assert "Stability seconds: 5.0s" in log_text
        assert "Reverse backs: True" in log_text


class TestSetupWatchDirectories:
    """Tests for setup_watch_directories helper."""

    def test_creates_directories(self, tmp_path):
        """Test that output directories are created."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        archive_dir = tmp_path / "archive"
        failed_dir = tmp_path / "failed"

        # Create input directory
        input_dir.mkdir()

        setup_watch_directories(input_dir, output_dir, archive_dir, failed_dir)

        # Check all directories were created
        assert output_dir.exists()
        assert archive_dir.exists()
        assert failed_dir.exists()

    def test_fails_if_input_missing(self, tmp_path):
        """Test that SystemExit is raised if input directory doesn't exist."""
        input_dir = tmp_path / "nonexistent"
        output_dir = tmp_path / "output"
        archive_dir = tmp_path / "archive"
        failed_dir = tmp_path / "failed"

        with pytest.raises(SystemExit) as exc_info:
            setup_watch_directories(input_dir, output_dir, archive_dir, failed_dir)

        assert exc_info.value.code == 1


class TestCreateProcessCallback:
    """Tests for create_process_callback helper."""

    def test_creates_callable(self, tmp_path):
        """Test that a callable function is returned."""
        callback = create_process_callback(
            output_dir=tmp_path / "output",
            archive_dir=tmp_path / "archive",
            failed_dir=tmp_path / "failed",
            output_suffix=".duplex",
            reverse_backs=True,
            insert_blank_lastback=False,
        )

        assert callable(callback)

    def test_callback_signature(self, tmp_path):
        """Test that callback accepts a file path."""
        from conftest import create_test_pdf

        # Setup directories
        output_dir = tmp_path / "output"
        archive_dir = tmp_path / "archive"
        failed_dir = tmp_path / "failed"

        output_dir.mkdir()
        archive_dir.mkdir()
        failed_dir.mkdir()

        # Create test PDF
        input_pdf = tmp_path / "test.pdf"
        create_test_pdf(input_pdf, ["F1", "F2", "B2", "B1"])

        callback = create_process_callback(
            output_dir=output_dir,
            archive_dir=archive_dir,
            failed_dir=failed_dir,
            output_suffix=".duplex",
            reverse_backs=True,
            insert_blank_lastback=False,
        )

        # Should not raise an error
        callback(input_pdf)

        # Verify processing occurred
        output_pdf = output_dir / "test.duplex.pdf"
        assert output_pdf.exists()
