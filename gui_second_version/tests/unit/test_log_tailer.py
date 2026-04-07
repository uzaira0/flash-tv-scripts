"""Unit tests for LogTailer utility."""

from __future__ import annotations

from pathlib import Path


from utils.log_tailer import LogTailer, StderrLogTailer, LogFileState


class TestLogTailerInitialization:
    """Tests for LogTailer initialization."""

    def test_default_initialization(self):
        """Test tailer initializes with defaults."""
        tailer = LogTailer()
        assert tailer.max_buffer_lines == 1000

    def test_custom_buffer_size(self):
        """Test custom buffer size."""
        tailer = LogTailer(max_buffer_lines=500)
        assert tailer.max_buffer_lines == 500


class TestGetNewLines:
    """Tests for getting new lines from files."""

    def test_first_read_gets_all_lines(self, tmp_path: Path):
        """Test first read gets all lines."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\nline3\n")

        tailer = LogTailer()
        lines = tailer.get_new_lines(str(log_file))

        assert len(lines) == 3
        assert "line1" in lines
        assert "line2" in lines
        assert "line3" in lines

    def test_subsequent_read_only_new_lines(self, tmp_path: Path):
        """Test subsequent reads only get new lines."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\n")

        tailer = LogTailer()

        # First read
        lines1 = tailer.get_new_lines(str(log_file))
        assert len(lines1) == 2

        # Append new content
        with open(log_file, "a") as f:
            f.write("line3\nline4\n")

        # Second read should only get new lines
        lines2 = tailer.get_new_lines(str(log_file))
        assert len(lines2) == 2
        assert "line3" in lines2
        assert "line4" in lines2

    def test_no_new_lines_returns_empty(self, tmp_path: Path):
        """Test no new content returns empty list."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\n")

        tailer = LogTailer()
        tailer.get_new_lines(str(log_file))

        # No new content
        lines = tailer.get_new_lines(str(log_file))
        assert len(lines) == 0

    def test_include_all_returns_buffered_lines(self, tmp_path: Path):
        """Test include_all returns all buffered lines."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\n")

        tailer = LogTailer()
        tailer.get_new_lines(str(log_file))

        # Append new content
        with open(log_file, "a") as f:
            f.write("line3\n")

        # Get all lines including buffered
        lines = tailer.get_new_lines(str(log_file), include_all=True)
        assert len(lines) == 3

    def test_nonexistent_file_returns_empty(self):
        """Test nonexistent file returns empty list."""
        tailer = LogTailer()
        lines = tailer.get_new_lines("/nonexistent/path/file.log")
        assert lines == []

    def test_skips_empty_lines(self, tmp_path: Path):
        """Test empty lines are skipped."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\n\n\nline2\n")

        tailer = LogTailer()
        lines = tailer.get_new_lines(str(log_file))

        assert len(lines) == 2

    def test_skips_comment_lines(self, tmp_path: Path):
        """Test comment lines are skipped."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# This is a comment\nline1\n# Another comment\nline2\n")

        tailer = LogTailer()
        lines = tailer.get_new_lines(str(log_file))

        assert len(lines) == 2
        assert "line1" in lines
        assert "line2" in lines


class TestFileRotation:
    """Tests for file rotation detection."""

    def test_detects_file_truncation(self, tmp_path: Path):
        """Test detection of file truncation (size decrease)."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\nline3\nline4\nline5\n")

        tailer = LogTailer()
        tailer.get_new_lines(str(log_file))

        # Truncate file
        log_file.write_text("new_line1\n")

        # Should detect rotation and read from beginning
        lines = tailer.get_new_lines(str(log_file))
        assert "new_line1" in lines


class TestBufferManagement:
    """Tests for buffer management."""

    def test_buffer_respects_max_size(self, tmp_path: Path):
        """Test buffer doesn't exceed max size."""
        log_file = tmp_path / "test.log"

        # Write many lines
        with open(log_file, "w") as f:
            for i in range(100):
                f.write(f"line{i}\n")

        tailer = LogTailer(max_buffer_lines=50)
        tailer.get_new_lines(str(log_file), include_all=True)

        # Check internal buffer
        state = tailer._file_states.get(str(log_file))
        assert state is not None
        assert len(state.buffered_lines) <= 50


class TestGetLastLine:
    """Tests for getting last line."""

    def test_get_last_line(self, tmp_path: Path):
        """Test getting last line from file."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\nlast_line\n")

        tailer = LogTailer()
        last = tailer.get_last_line(str(log_file))

        assert last == "last_line"

    def test_get_last_line_uses_buffer(self, tmp_path: Path):
        """Test get_last_line uses buffer if available."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\nlast_line\n")

        tailer = LogTailer()
        tailer.get_new_lines(str(log_file))  # Fill buffer

        last = tailer.get_last_line(str(log_file))
        assert last == "last_line"

    def test_get_last_line_skips_comments(self, tmp_path: Path):
        """Test get_last_line skips comment lines."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nlast_real_line\n# comment\n")

        tailer = LogTailer()
        last = tailer.get_last_line(str(log_file))

        assert last == "last_real_line"

    def test_get_last_line_empty_file(self, tmp_path: Path):
        """Test get_last_line with empty file."""
        log_file = tmp_path / "test.log"
        log_file.write_text("")

        tailer = LogTailer()
        last = tailer.get_last_line(str(log_file))

        assert last == ""


class TestGetAllLines:
    """Tests for getting all lines."""

    def test_get_all_lines(self, tmp_path: Path):
        """Test getting all lines from file."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\nline3\n")

        tailer = LogTailer()
        lines = tailer.get_all_lines(str(log_file))

        assert len(lines) == 3

    def test_get_all_lines_updates_state(self, tmp_path: Path):
        """Test get_all_lines updates tailer state."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\n")

        tailer = LogTailer()
        tailer.get_all_lines(str(log_file))

        # Append new content
        with open(log_file, "a") as f:
            f.write("line3\n")

        # get_new_lines should only get new content
        new_lines = tailer.get_new_lines(str(log_file))
        assert len(new_lines) == 1
        assert "line3" in new_lines


class TestReset:
    """Tests for reset functionality."""

    def test_reset_specific_file(self, tmp_path: Path):
        """Test resetting specific file state."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\n")

        tailer = LogTailer()
        tailer.get_new_lines(str(log_file))

        assert str(log_file) in tailer._file_states

        tailer.reset(str(log_file))

        assert str(log_file) not in tailer._file_states

    def test_reset_all_files(self, tmp_path: Path):
        """Test resetting all file states."""
        log_file1 = tmp_path / "test1.log"
        log_file2 = tmp_path / "test2.log"
        log_file1.write_text("line1\n")
        log_file2.write_text("line2\n")

        tailer = LogTailer()
        tailer.get_new_lines(str(log_file1))
        tailer.get_new_lines(str(log_file2))

        assert len(tailer._file_states) == 2

        tailer.reset()

        assert len(tailer._file_states) == 0


class TestStderrLogTailer:
    """Tests for StderrLogTailer."""

    def test_initialization_with_error_func(self):
        """Test initialization with error detection function."""
        def is_safe(line: str) -> bool:
            return "WARNING" in line

        tailer = StderrLogTailer(is_error_func=is_safe)
        assert tailer._is_known_safe is not None

    def test_default_error_func_returns_false(self):
        """Test default error function returns False."""
        tailer = StderrLogTailer()
        assert tailer._is_known_safe("any line") is False

    def test_get_new_content_with_errors(self, tmp_path: Path):
        """Test getting content categorized by errors."""
        log_file = tmp_path / "stderr.log"
        log_file.write_text("WARNING: safe warning\nERROR: real error\nWARNING: another safe\n")

        def is_safe(line: str) -> bool:
            return "WARNING" in line

        tailer = StderrLogTailer(is_error_func=is_safe)
        all_lines, error_lines = tailer.get_new_content_with_errors(str(log_file))

        assert len(all_lines) == 3
        assert len(error_lines) == 1
        assert "ERROR" in error_lines[0]

    def test_all_safe_messages(self, tmp_path: Path):
        """Test when all messages are safe."""
        log_file = tmp_path / "stderr.log"
        log_file.write_text("INFO: info message\nDEBUG: debug message\n")

        def is_safe(line: str) -> bool:
            return "INFO" in line or "DEBUG" in line

        tailer = StderrLogTailer(is_error_func=is_safe)
        all_lines, error_lines = tailer.get_new_content_with_errors(str(log_file))

        assert len(all_lines) == 2
        assert len(error_lines) == 0


class TestLogFileState:
    """Tests for LogFileState dataclass."""

    def test_default_values(self):
        """Test default values of LogFileState."""
        state = LogFileState(path="/test/path")

        assert state.path == "/test/path"
        assert state.last_position == 0
        assert state.last_size == 0
        assert state.last_inode == 0
        assert state.buffered_lines == []


class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_long_lines(self, tmp_path: Path):
        """Test handling of very long lines."""
        log_file = tmp_path / "test.log"
        long_line = "x" * 10000
        log_file.write_text(f"{long_line}\nshort line\n")

        tailer = LogTailer()
        lines = tailer.get_new_lines(str(log_file))

        assert len(lines) == 2
        assert long_line in lines

    def test_binary_content_handling(self, tmp_path: Path):
        """Test handling of files with binary content."""
        log_file = tmp_path / "test.log"
        # Write some binary-ish content
        with open(log_file, "wb") as f:
            f.write(b"normal line\n\x00\x01\x02binary\nmore text\n")

        tailer = LogTailer()
        # Should not raise, may skip problematic lines
        lines = tailer.get_new_lines(str(log_file))
        assert isinstance(lines, list)

    def test_concurrent_writes(self, tmp_path: Path):
        """Test reading while file is being written."""
        log_file = tmp_path / "test.log"
        log_file.write_text("initial\n")

        tailer = LogTailer()
        tailer.get_new_lines(str(log_file))

        # Simulate concurrent write
        with open(log_file, "a") as f:
            f.write("concurrent1\n")
            f.flush()

            # Read while file is open
            lines = tailer.get_new_lines(str(log_file))
            assert "concurrent1" in lines

            f.write("concurrent2\n")
            f.flush()

        # Final read
        lines = tailer.get_new_lines(str(log_file))
        assert "concurrent2" in lines
