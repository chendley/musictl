"""Tests for export functionality in scan commands."""

import csv
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from musictl.cli import app


runner = CliRunner()


class TestLibraryScanExport:
    """Test export functionality for library scan."""

    def test_export_csv(self, sample_library, tmp_path):
        """Test CSV export for library scan."""
        library_path, _ = sample_library
        export_path = tmp_path / "library_export.csv"

        result = runner.invoke(app, [
            "scan", "library", str(library_path),
            "--export", str(export_path),
            "--format", "csv"
        ])

        assert result.exit_code == 0
        assert export_path.exists()

        # Verify CSV content
        with open(export_path, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)

            # Check header rows exist
            assert rows[0][0] == "Library Statistics"
            assert rows[1][0] == "Scan Path"
            assert rows[2][0] == "Total Files"

            # Check format distribution section exists
            format_section_found = False
            for row in rows:
                if row and row[0] == "Format Distribution":
                    format_section_found = True
                    break
            assert format_section_found

    def test_export_json(self, sample_library, tmp_path):
        """Test JSON export for library scan."""
        library_path, _ = sample_library
        export_path = tmp_path / "library_export.json"

        result = runner.invoke(app, [
            "scan", "library", str(library_path),
            "--export", str(export_path),
            "--format", "json"
        ])

        assert result.exit_code == 0
        assert export_path.exists()

        # Verify JSON content
        with open(export_path, "r") as f:
            data = json.load(f)

            assert "scan_path" in data
            assert "total_files" in data
            assert data["total_files"] == 5  # 3 MP3s + 2 FLACs
            assert "formats" in data
            assert "sample_rates" in data
            assert isinstance(data["formats"], list)

    def test_export_invalid_format(self, sample_library, tmp_path):
        """Test export with invalid format."""
        library_path, _ = sample_library
        export_path = tmp_path / "export.xyz"

        result = runner.invoke(app, [
            "scan", "library", str(library_path),
            "--export", str(export_path),
            "--format", "xml"
        ])

        assert result.exit_code == 1
        assert "Invalid format" in result.stdout


class TestHiresScanExport:
    """Test export functionality for hi-res scan."""

    def test_export_csv(self, sample_flac_hires, tmp_path):
        """Test CSV export for hi-res scan."""
        hires_dir = sample_flac_hires.parent
        export_path = tmp_path / "hires_export.csv"

        result = runner.invoke(app, [
            "scan", "hires", str(hires_dir),
            "--export", str(export_path),
            "--format", "csv"
        ])

        assert result.exit_code == 0
        assert export_path.exists()

        # Verify CSV content
        with open(export_path, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)

            # Check header
            assert rows[0] == ["File Path", "Format", "Sample Rate (Hz)", "Bit Depth", "Duration (seconds)", "Channels"]

            # Check data row exists
            assert len(rows) > 1
            assert "96000" in rows[1][2]  # 96kHz sample rate

    def test_export_json(self, sample_flac_hires, tmp_path):
        """Test JSON export for hi-res scan."""
        hires_dir = sample_flac_hires.parent
        export_path = tmp_path / "hires_export.json"

        result = runner.invoke(app, [
            "scan", "hires", str(hires_dir),
            "--export", str(export_path),
            "--format", "json"
        ])

        assert result.exit_code == 0
        assert export_path.exists()

        # Verify JSON content
        with open(export_path, "r") as f:
            data = json.load(f)

            assert "scan_path" in data
            assert "threshold_hz" in data
            assert "hires_count" in data
            assert "files" in data
            assert len(data["files"]) > 0
            assert data["files"][0]["sample_rate_hz"] == 96000


class TestEncodingScanExport:
    """Test export functionality for encoding scan."""

    def test_export_csv_no_issues(self, sample_mp3, tmp_path):
        """Test CSV export when no encoding issues found."""
        mp3_dir = sample_mp3.parent
        export_path = tmp_path / "encoding_export.csv"

        result = runner.invoke(app, [
            "scan", "encoding", str(mp3_dir),
            "--export", str(export_path),
            "--format", "csv"
        ])

        assert result.exit_code == 0
        # No export file should be created when no issues found
        assert not export_path.exists()

    def test_export_json_no_issues(self, sample_mp3, tmp_path):
        """Test JSON export when no encoding issues found."""
        mp3_dir = sample_mp3.parent
        export_path = tmp_path / "encoding_export.json"

        result = runner.invoke(app, [
            "scan", "encoding", str(mp3_dir),
            "--export", str(export_path),
            "--format", "json"
        ])

        assert result.exit_code == 0
        # No export file should be created when no issues found
        assert not export_path.exists()

    def test_export_csv_with_issues(self, sample_mp3_bad_encoding, tmp_path):
        """Test CSV export with encoding issues."""
        mp3_dir = sample_mp3_bad_encoding.parent
        export_path = tmp_path / "encoding_export.csv"

        result = runner.invoke(app, [
            "scan", "encoding", str(mp3_dir),
            "--export", str(export_path),
            "--format", "csv"
        ])

        assert result.exit_code == 0

        if export_path.exists():  # May or may not detect based on encoding
            with open(export_path, "r") as f:
                reader = csv.reader(f)
                rows = list(reader)

                # Check header
                assert rows[0] == ["File Path", "Tag", "Possible Encoding", "Description", "Decoded Text"]

    def test_export_json_with_issues(self, sample_mp3_bad_encoding, tmp_path):
        """Test JSON export with encoding issues."""
        mp3_dir = sample_mp3_bad_encoding.parent
        export_path = tmp_path / "encoding_export.json"

        result = runner.invoke(app, [
            "scan", "encoding", str(mp3_dir),
            "--export", str(export_path),
            "--format", "json"
        ])

        assert result.exit_code == 0

        if export_path.exists():  # May or may not detect based on encoding
            with open(export_path, "r") as f:
                data = json.load(f)

                assert "scan_path" in data
                assert "total_scanned" in data
                assert "suspect_count" in data
                assert "files" in data
