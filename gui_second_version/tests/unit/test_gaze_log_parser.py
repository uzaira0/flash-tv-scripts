"""Unit tests for GazeLogParser utility."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.gaze_log_parser import GazeLogParser


class TestGazeLogParserInitialization:
    """Tests for GazeLogParser initialization."""

    def test_default_initialization(self):
        """Test parser initializes without errors."""
        parser = GazeLogParser()
        assert parser is not None

    def test_efficient_tailing_enabled_by_default(self):
        """Test efficient tailing is enabled by default."""
        parser = GazeLogParser()
        assert parser._log_tailer is not None

    def test_efficient_tailing_can_be_disabled(self):
        """Test efficient tailing can be disabled."""
        parser = GazeLogParser(use_efficient_tailing=False)
        assert parser._log_tailer is None


class TestGazeDataParsing:
    """Tests for parsing gaze log lines."""

    @pytest.fixture
    def parser(self) -> GazeLogParser:
        """Create a parser for testing."""
        return GazeLogParser(use_efficient_tailing=False)

    def test_parse_gaze_det_line(self, parser: GazeLogParser):
        """Test parsing a Gaze-det line."""
        line = "2025-01-01 12:00:00.000000 1 1 1 0.1 0.2 0.9 0.0 10 20 50 80 Gaze-det"
        result = parser.parse_gaze_line(line)

        assert result is not None
        assert result.label == "Gaze-det"
        assert result.num_faces == 1
        assert abs(result.pitch_deg - 5.73) < 0.1  # 0.1 radians ≈ 5.73 degrees

    def test_parse_no_face_detected_line(self, parser: GazeLogParser):
        """Test parsing a No-face-detected line."""
        line = "2025-01-01 12:00:00.000000 1 0 0 None None None None None None None None No-face-detected"
        result = parser.parse_gaze_line(line)

        assert result is not None
        assert result.label == "No-face-detected"
        assert result.num_faces == 0

    def test_parse_gaze_no_det_line(self, parser: GazeLogParser):
        """Test parsing a Gaze-no-det line."""
        line = "2025-01-01 12:00:00.000000 1 2 1 None None None None 20 30 60 90 Gaze-no-det"
        result = parser.parse_gaze_line(line)

        assert result is not None
        assert result.label == "Gaze-no-det"
        assert result.num_faces == 2

    def test_parse_invalid_line_returns_none(self, parser: GazeLogParser):
        """Test parsing invalid line returns None."""
        line = "invalid line with not enough fields"
        result = parser.parse_gaze_line(line)
        assert result is None

    def test_parse_empty_line_returns_none(self, parser: GazeLogParser):
        """Test parsing empty line returns None."""
        result = parser.parse_gaze_line("")
        assert result is None

    def test_parse_extracts_timestamp(self, parser: GazeLogParser):
        """Test timestamp is extracted correctly."""
        line = "2025-01-01 12:34:56.789000 1 1 1 0.1 0.2 0.9 0.0 10 20 50 80 Gaze-det"
        result = parser.parse_gaze_line(line)

        assert result is not None
        assert "12:34:56.789" in result.timestamp


class TestWatchingTVEvaluation:
    """Tests for TV watching evaluation."""

    @pytest.fixture
    def parser(self) -> GazeLogParser:
        """Create a parser for testing."""
        return GazeLogParser(use_efficient_tailing=False)

    def test_evaluate_watching_tv_fallback(self, parser: GazeLogParser):
        """Test fallback evaluation when no location limits loaded."""
        parser.loc_lims = None

        # Small angles should be watching
        result = parser.evaluate_watching_tv(0.1, 0.1, 0)
        assert result is True

        # Large angles should be looking away
        result = parser.evaluate_watching_tv(0.5, 0.5, 0)
        assert result is False

    def test_watching_tv_status_in_parsed_data(self, parser: GazeLogParser):
        """Test watching_tv status is set in parsed data."""
        parser.loc_lims = None  # Use fallback

        # Small angles
        line = "2025-01-01 12:00:00.000000 1 1 1 0.05 0.05 0.9 0.0 10 20 50 80 Gaze-det"
        result = parser.parse_gaze_line(line)

        assert result is not None
        assert result.watching_tv is True


class TestGridPosition:
    """Tests for grid position calculation."""

    @pytest.fixture
    def parser(self) -> GazeLogParser:
        """Create a parser for testing."""
        return GazeLogParser(use_efficient_tailing=False)

    def test_get_grid_position_center(self, parser: GazeLogParser):
        """Test grid position for center of frame."""
        # Frame is 608x342, center is approximately 304, 171
        # With cell size 53x35, center cell should be around 5x4
        grid_idx = parser.get_grid_position(150, 280, 190, 340)
        assert 0 <= grid_idx <= 119  # Valid range

    def test_get_grid_position_top_left(self, parser: GazeLogParser):
        """Test grid position for top-left corner."""
        grid_idx = parser.get_grid_position(0, 0, 30, 50)
        assert grid_idx == 0  # First cell

    def test_get_grid_position_bottom_right(self, parser: GazeLogParser):
        """Test grid position clamps to valid range."""
        grid_idx = parser.get_grid_position(300, 550, 340, 600)
        assert grid_idx <= 119


class TestFormatGazeData:
    """Tests for formatting gaze data for display."""

    @pytest.fixture
    def parser(self) -> GazeLogParser:
        """Create a parser for testing."""
        return GazeLogParser(use_efficient_tailing=False)

    def test_format_gaze_det_watching(self, parser: GazeLogParser):
        """Test formatting when watching TV."""
        parser.loc_lims = None  # Use fallback
        line = "2025-01-01 12:00:00.000000 1 1 1 0.05 0.05 0.9 0.0 10 20 50 80 Gaze-det"

        formatted, gaze_tuple = parser.format_gaze_data(line)

        assert "WATCHING TV" in formatted
        assert gaze_tuple is not None
        assert len(gaze_tuple) == 3  # (pitch, yaw, watching)

    def test_format_gaze_det_looking_away(self, parser: GazeLogParser):
        """Test formatting when looking away."""
        parser.loc_lims = None
        line = "2025-01-01 12:00:00.000000 1 1 1 0.5 0.5 0.9 0.0 10 20 50 80 Gaze-det"

        formatted, gaze_tuple = parser.format_gaze_data(line)

        assert "LOOKING AWAY" in formatted

    def test_format_no_face(self, parser: GazeLogParser):
        """Test formatting when no face detected."""
        line = "2025-01-01 12:00:00.000000 1 0 0 None None None None None None None None No-face-detected"

        formatted, gaze_tuple = parser.format_gaze_data(line)

        assert "NO FACES" in formatted
        assert gaze_tuple is None

    def test_format_gaze_no_det(self, parser: GazeLogParser):
        """Test formatting when TC present but no gaze."""
        line = "2025-01-01 12:00:00.000000 1 2 1 None None None None 20 30 60 90 Gaze-no-det"

        formatted, gaze_tuple = parser.format_gaze_data(line)

        assert "TC PRESENT" in formatted
        assert gaze_tuple is None

    def test_format_invalid_line(self, parser: GazeLogParser):
        """Test formatting invalid line."""
        formatted, gaze_tuple = parser.format_gaze_data("invalid")

        assert "Invalid format" in formatted
        assert gaze_tuple is None


class TestKnownErrors:
    """Tests for known error detection."""

    @pytest.fixture
    def parser(self) -> GazeLogParser:
        """Create a parser for testing."""
        return GazeLogParser(use_efficient_tailing=False)

    def test_known_warning_detected(self, parser: GazeLogParser):
        """Test known warnings are detected."""
        assert parser.is_known_minor_error("Corrupt JPEG data: premature end")
        assert parser.is_known_minor_error("DeprecationWarning: something deprecated")
        assert parser.is_known_minor_error("Loading symbol saved by previous version")

    def test_unknown_error_not_detected(self, parser: GazeLogParser):
        """Test unknown errors are not marked as known."""
        assert not parser.is_known_minor_error("RuntimeError: Something unexpected")
        assert not parser.is_known_minor_error("Critical failure in system")


class TestFileReading:
    """Tests for file reading operations."""

    @pytest.fixture
    def parser(self) -> GazeLogParser:
        """Create a parser without efficient tailing."""
        return GazeLogParser(use_efficient_tailing=False)

    def test_get_last_data_line(self, parser: GazeLogParser, sample_gaze_log_file: Path):
        """Test getting last data line from file."""
        last_line = parser.get_last_data_line(str(sample_gaze_log_file))
        assert last_line != ""
        assert "Gaze-det" in last_line

    def test_get_last_data_line_nonexistent_file(self, parser: GazeLogParser):
        """Test getting last line from nonexistent file."""
        last_line = parser.get_last_data_line("/nonexistent/path/file.txt")
        assert last_line == ""

    def test_get_recent_data_lines(self, parser: GazeLogParser, sample_gaze_log_file: Path):
        """Test getting recent data lines."""
        lines = parser.get_recent_data_lines(str(sample_gaze_log_file))
        assert len(lines) > 0

    def test_get_recent_data_lines_with_limit(self, parser: GazeLogParser, sample_gaze_log_file: Path):
        """Test getting limited recent lines."""
        lines = parser.get_recent_data_lines(str(sample_gaze_log_file), max_lines=2)
        assert len(lines) <= 2

    def test_reset_file_state(self, parser: GazeLogParser):
        """Test resetting file state (no-op when tailing disabled)."""
        # Should not raise even when tailing is disabled
        parser.reset_file_state()
        parser.reset_file_state("/some/path")


class TestEfficientTailing:
    """Tests for efficient log tailing integration."""

    def test_tailing_enabled_uses_tailer(self, sample_gaze_log_file: Path):
        """Test that tailing-enabled parser uses LogTailer."""
        parser = GazeLogParser(use_efficient_tailing=True)

        # First read
        lines1 = parser.get_recent_data_lines(str(sample_gaze_log_file))

        # Append new content
        with open(sample_gaze_log_file, "a") as f:
            f.write("2025-01-01 12:00:10.000000 10 1 1 0.2 0.2 0.9 0.0 10 20 50 80 Gaze-det\n")

        # Second read should include new content
        lines2 = parser.get_recent_data_lines(str(sample_gaze_log_file))
        assert len(lines2) >= len(lines1)

    def test_reset_clears_tailer_state(self, sample_gaze_log_file: Path):
        """Test that reset clears tailer state."""
        parser = GazeLogParser(use_efficient_tailing=True)

        # Read file
        parser.get_recent_data_lines(str(sample_gaze_log_file))

        # Reset
        parser.reset_file_state()

        # Verify tailer state was reset
        assert str(sample_gaze_log_file) not in parser._log_tailer._file_states
