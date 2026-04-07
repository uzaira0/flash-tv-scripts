"""Gaze log parsing utilities for FLASH-TV service monitoring.

This module provides utilities for parsing gaze log files, evaluating
TV watching status, and formatting gaze data for display.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from .log_tailer import LogTailer

if TYPE_CHECKING:
    from numpy.typing import NDArray

    NDArrayFloat = NDArray[np.floating[Any]]
else:
    NDArrayFloat = Any


@dataclass
class GazeData:
    """Parsed gaze data from a log line."""

    pitch_deg: float
    yaw_deg: float
    watching_tv: bool
    timestamp: str = ""
    status: str = ""
    label: str = ""
    num_faces: int = 0
    grid_index: int = 0


class GazeLogParser:
    """Parser for FLASH-TV gaze log files.

    This class handles parsing of gaze log files and evaluation of
    TV watching status using position-specific angle thresholds.
    """

    # Known warnings/errors to ignore in stderr log
    KNOWN_WARNINGS: set[str] = {
        "Corrupt JPEG data",
        "DeprecationWarning",
        "UserWarning",
        "Deprecated in NumPy 1.20",
        "Failed to load image Python extension",
        "Overload resolution failed:",
        "M is not a numpy array, neither a scalar",
        "Expected Ptr<cv::UMat> for argument",
        "Traceback",
        "warpAffine",
        "nimg = face_align.norm_crop(face_img_bgr, pts5)",
        "facen = model.get_input(face, facelmarks.astype(np.int).reshape(1,5,2), face=True)",
        "face = io.imread(os.path.join(path, fname))",
        "detFacesLog, bboxFaces, idxFaces = pipe_frames_data_to_faces",
        "test_vid_frames_batch_v7_2fps_frminp_newfv_rotate.py",
        "insightface/deploy/face_model.py",
        "insightface/utils/face_align.py",
        "RTNETLINK answers: File exists",
    }

    # Normal messages to ignore in stderr log
    NORMAL_MESSAGES: set[str] = {
        "Loading symbol saved by previous version",
        "Symbol successfully upgraded!",
        "Running performance tests",
        "Resource temporarily unavailable",
    }

    def __init__(self, loc_lims_path: str | None = None, use_efficient_tailing: bool = True):
        """Initialize the gaze log parser.

        Args:
            loc_lims_path: Optional path to location limits .npy file.
                          If not provided, will attempt to find it automatically.
            use_efficient_tailing: If True, use LogTailer for efficient file reading.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.loc_lims: NDArrayFloat | None = None
        self._load_location_limits(loc_lims_path)

        # Initialize log tailer for efficient file reading
        self._log_tailer = LogTailer(max_buffer_lines=500) if use_efficient_tailing else None

    def _load_location_limits(self, loc_lims_path: str | None = None) -> None:
        """Load location limits for gaze evaluation.

        Uses "center-big-med" transformation settings.
        """
        try:
            if loc_lims_path is None:
                # Try to find the limits file
                script_dir = os.path.dirname(os.path.abspath(__file__))
                repo_root = os.path.dirname(os.path.dirname(script_dir))
                loc_lims_path = os.path.join(
                    repo_root,
                    "python_scripts",
                    "4331_v3r50reg_reg_testlims_35_53_7_9.npy",
                )

                # Fallback for production environment
                if not os.path.exists(loc_lims_path):
                    username = os.getenv("USER", "flashsys007")
                    loc_lims_path = f"/home/{username}/flash-tv-scripts/python_scripts/4331_v3r50reg_reg_testlims_35_53_7_9.npy"

            if not os.path.exists(loc_lims_path):
                self.logger.warning(f"Location limits file not found: {loc_lims_path}")
                return

            loc_lims = np.load(loc_lims_path).reshape(-1, 4)  # Shape: (120, 4)

            # Apply "center-big-med" transformation
            # pos=center, size=big, height=med
            drl = (loc_lims[:, 1] - loc_lims[:, 0]) / 2.0
            dtb = (loc_lims[:, 3] - loc_lims[:, 2]) / 2.0

            slr = 1.1  # center position
            stb = 1.1
            rls_sc = 0.3  # big TV
            tbs_sc = 0.2  # big TV

            rls = drl * rls_sc
            tbs = dtb * tbs_sc

            loc_lims[:, 0] = slr * loc_lims[:, 0] - rls  # phi_min
            loc_lims[:, 1] = slr * loc_lims[:, 1] + rls  # phi_max
            loc_lims[:, 2] = stb * loc_lims[:, 2] - tbs  # theta_min
            loc_lims[:, 3] = stb * loc_lims[:, 3] + tbs  # theta_max

            self.loc_lims = loc_lims
            self.logger.info(
                f"Loaded location limits with center-big-med setting: shape {loc_lims.shape}"
            )

        except Exception as e:
            self.logger.warning(f"Could not load location limits file: {e}")
            self.loc_lims = None

    def get_grid_position(
        self,
        bbox_top: float,
        bbox_left: float,
        bbox_bottom: float,
        bbox_right: float,
    ) -> int:
        """Calculate grid cell index from bounding box position.

        Grid is 12 rows x 10 columns = 120 cells on a 342x608 frame.

        Args:
            bbox_top: Top coordinate of bounding box
            bbox_left: Left coordinate of bounding box
            bbox_bottom: Bottom coordinate of bounding box
            bbox_right: Right coordinate of bounding box

        Returns:
            Grid cell index (0-119)
        """
        # Grid parameters
        pH = 35  # Cell height
        pW = 53  # Cell width

        # Calculate face center
        center_x = (bbox_left + bbox_right) / 2
        center_y = (bbox_top + bbox_bottom) / 2

        # Determine grid cell
        grid_x = int(center_x / pW)  # 0-9 (10 columns)
        grid_y = int(center_y / pH)  # 0-11 (12 rows)

        # Clamp to valid range
        grid_x = max(0, min(9, grid_x))
        grid_y = max(0, min(11, grid_y))

        return grid_y * 10 + grid_x

    def evaluate_watching_tv(
        self, pitch_rad: float, yaw_rad: float, grid_index: int
    ) -> bool:
        """Evaluate if gaze angles indicate watching TV.

        Uses position-specific thresholds from location limits file.

        Args:
            pitch_rad: Horizontal gaze angle in radians
            yaw_rad: Vertical gaze angle in radians
            grid_index: Grid cell index (0-119)

        Returns:
            True if watching TV, False otherwise
        """
        if self.loc_lims is None:
            # Fallback: use simple angle threshold
            pitch_deg = pitch_rad * 57.2958
            yaw_deg = yaw_rad * 57.2958
            return abs(pitch_deg) < 20 and abs(yaw_deg) < 20

        # Get position-specific limits (in degrees)
        lims = self.loc_lims[grid_index]
        phi_min, phi_max, theta_min, theta_max = lims

        # Convert limits from degrees to radians
        phi_min_rad = (phi_min / 180.0) * math.pi
        phi_max_rad = (phi_max / 180.0) * math.pi
        theta_min_rad = (theta_min / 180.0) * math.pi
        theta_max_rad = (theta_max / 180.0) * math.pi

        # Check if BOTH angles are within bounds
        phi_ok = phi_min_rad < pitch_rad < phi_max_rad
        theta_ok = theta_min_rad < yaw_rad < theta_max_rad

        return phi_ok and theta_ok

    def is_known_minor_error(self, error_message: str) -> bool:
        """Check if an error is a known warning or normal message.

        Args:
            error_message: The error message to check

        Returns:
            True if it's a known safe message, False otherwise
        """
        error_lower = error_message.lower()

        # Check known warnings
        for pattern in self.KNOWN_WARNINGS:
            if pattern in error_message or pattern.lower() in error_lower:
                return True

        # Check normal messages
        for pattern in self.NORMAL_MESSAGES:
            if pattern in error_message or pattern.lower() in error_lower:
                return True

        return False

    def parse_gaze_line(self, line: str) -> GazeData | None:
        """Parse a single gaze log line.

        Format: timestamp frame_num num_faces tc_present pitch yaw roll tc_angle x1 y1 x2 y2 label
        Timestamp format: "2025-10-01 18:24:01.063242" (has spaces!)

        Args:
            line: A single line from the gaze log file

        Returns:
            GazeData if successfully parsed, None otherwise
        """
        try:
            parts = line.split()
            if len(parts) < 14:  # 2 parts for timestamp + 12 data fields
                return None

            # Extract key fields
            timestamp = f"{parts[0]} {parts[1]}"  # Full timestamp
            num_faces = int(parts[3])
            pitch_str = parts[5]
            yaw_str = parts[6]
            bbox_top_str = parts[9]
            bbox_left_str = parts[10]
            bbox_bottom_str = parts[11]
            bbox_right_str = parts[12]
            label = parts[-1]

            time_only = timestamp.split()[1][:12]  # Show time with milliseconds

            if label == "Gaze-det" and pitch_str != "None" and yaw_str != "None":
                try:
                    pitch = float(pitch_str)  # radians
                    yaw = float(yaw_str)  # radians

                    # Parse bounding box
                    bbox_top = float(bbox_top_str)
                    bbox_left = float(bbox_left_str)
                    bbox_bottom = float(bbox_bottom_str)
                    bbox_right = float(bbox_right_str)

                    # Calculate grid position
                    grid_index = self.get_grid_position(
                        bbox_top, bbox_left, bbox_bottom, bbox_right
                    )

                    # Evaluate if watching TV
                    watching_tv = self.evaluate_watching_tv(pitch, yaw, grid_index)

                    # Convert radians to degrees for display
                    pitch_deg = pitch * 57.2958
                    yaw_deg = yaw * 57.2958

                    status = "WATCHING TV" if watching_tv else "LOOKING AWAY"

                    return GazeData(
                        pitch_deg=pitch_deg,
                        yaw_deg=yaw_deg,
                        watching_tv=watching_tv,
                        timestamp=time_only,
                        status=status,
                        label=label,
                        num_faces=num_faces,
                        grid_index=grid_index,
                    )
                except ValueError:
                    return None

            elif label == "Gaze-no-det":
                return GazeData(
                    pitch_deg=0,
                    yaw_deg=0,
                    watching_tv=False,
                    timestamp=time_only,
                    status="TC PRESENT - No gaze",
                    label=label,
                    num_faces=num_faces,
                )

            elif label == "No-face-detected":
                return GazeData(
                    pitch_deg=0,
                    yaw_deg=0,
                    watching_tv=False,
                    timestamp=time_only,
                    status="NO FACES",
                    label=label,
                    num_faces=0,
                )

            else:
                return GazeData(
                    pitch_deg=0,
                    yaw_deg=0,
                    watching_tv=False,
                    timestamp=time_only,
                    status=label,
                    label=label,
                    num_faces=num_faces,
                )

        except Exception as e:
            self.logger.debug(f"Error parsing gaze line: {e}")
            return None

    def format_gaze_data(
        self, line: str
    ) -> tuple[str, tuple[float, float, bool] | None]:
        """Format gaze data line for display with TV watching interpretation.

        Args:
            line: A single line from the gaze log file

        Returns:
            Tuple of (formatted_text, gaze_tuple) where gaze_tuple is
            (pitch_deg, yaw_deg, watching_tv) or None
        """
        gaze_data = self.parse_gaze_line(line)

        if gaze_data is None:
            parts = line.split()
            return f"Invalid format\n({len(parts)} fields)", None

        if gaze_data.label == "Gaze-det" and gaze_data.status in (
            "WATCHING TV",
            "LOOKING AWAY",
        ):
            status_emoji = (
                "🟢 WATCHING TV" if gaze_data.watching_tv else "🔵 LOOKING AWAY"
            )
            formatted = (
                f"[{gaze_data.timestamp}]\n"
                f"{status_emoji}\n"
                f"P:{gaze_data.pitch_deg:+.1f}° Y:{gaze_data.yaw_deg:+.1f}°"
            )
            return formatted, (
                gaze_data.pitch_deg,
                gaze_data.yaw_deg,
                gaze_data.watching_tv,
            )

        elif gaze_data.label == "Gaze-no-det":
            return (
                f"[{gaze_data.timestamp}]\n"
                f"🟡 TC PRESENT\nNo gaze detected\n({gaze_data.num_faces} faces)",
                None,
            )

        elif gaze_data.label == "No-face-detected":
            return f"[{gaze_data.timestamp}]\n🔴 NO FACES\nNo detection", None

        else:
            return (
                f"[{gaze_data.timestamp}]\n"
                f"⚪ {gaze_data.label}\n({gaze_data.num_faces} faces)",
                None,
            )

    def get_last_data_line(self, filepath: str) -> str:
        """Get the last non-empty line from a gaze log file.

        Uses efficient log tailing when available.

        Args:
            filepath: Path to the gaze log file

        Returns:
            Last non-empty, non-comment line, or empty string
        """
        # Use efficient tailer if available
        if self._log_tailer:
            return self._log_tailer.get_last_line(filepath)

        # Fallback to reading entire file
        try:
            with open(filepath, "r") as f:
                lines = f.readlines()
                for line in reversed(lines):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
        except Exception as e:
            self.logger.debug(f"Could not read last line from {filepath}: {e}")
        return ""

    def get_recent_data_lines(self, filepath: str, max_lines: int = 0) -> list[str]:
        """Get non-empty lines from a gaze log file.

        Uses efficient log tailing when available - only reads new content
        since last call, reducing I/O for large log files.

        Args:
            filepath: Path to the gaze log file
            max_lines: Maximum number of lines to return (0 = all)

        Returns:
            List of non-empty, non-comment lines
        """
        # Use efficient tailer if available
        if self._log_tailer:
            # Get all buffered lines (includes any new content)
            all_lines = self._log_tailer.get_all_lines(filepath)
            if max_lines > 0:
                return all_lines[-max_lines:]
            return all_lines

        # Fallback to reading entire file
        try:
            with open(filepath, "r") as f:
                lines = f.readlines()
                data_lines = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        data_lines.append(line)
                if max_lines > 0:
                    return data_lines[-max_lines:]
                return data_lines
        except Exception as e:
            self.logger.debug(f"Could not read lines from {filepath}: {e}")
        return []

    def reset_file_state(self, filepath: str | None = None) -> None:
        """Reset tailer state for a file or all files.

        Call this when you want to re-read a file from the beginning,
        for example after file rotation or when stepping back in the wizard.

        Args:
            filepath: If provided, reset only this file. Otherwise reset all.
        """
        if self._log_tailer:
            self._log_tailer.reset(filepath)
