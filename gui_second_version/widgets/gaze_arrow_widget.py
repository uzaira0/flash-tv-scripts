"""Gaze arrow visualization widget for displaying gaze direction."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


class GazeArrowWidget(QWidget):
    """Widget that draws a gaze direction arrow based on pitch/yaw angles.

    This widget visualizes gaze direction as an arrow within a circle,
    with color coding to indicate whether the subject is watching TV
    (green) or looking away (blue).
    """

    pitch_deg: float
    yaw_deg: float
    watching_tv: bool
    has_data: bool
    timestamp: str
    status_text: str

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.pitch_deg = 0.0
        self.yaw_deg = 0.0
        self.watching_tv = False
        self.has_data = False
        self.timestamp = ""
        self.status_text = ""
        self.setMinimumSize(150, 200)
        self.setMaximumSize(220, 280)

    def set_gaze(
        self,
        pitch_deg: float,
        yaw_deg: float,
        watching_tv: bool,
        timestamp: str = "",
        status: str = "",
    ):
        """Update the gaze arrow display.

        Args:
            pitch_deg: Pitch angle in degrees
            yaw_deg: Yaw angle in degrees
            watching_tv: Whether the subject is watching TV
            timestamp: Optional timestamp string
            status: Optional status text
        """
        self.pitch_deg = pitch_deg
        self.yaw_deg = yaw_deg
        self.watching_tv = watching_tv
        self.has_data = True
        self.timestamp = timestamp
        self.status_text = status
        self.update()  # Trigger repaint

    def clear_gaze(self):
        """Clear the gaze display."""
        self.has_data = False
        self.timestamp = ""
        self.status_text = ""
        self.update()

    def paintEvent(self, a0: QPaintEvent | None) -> None:  # noqa: N802
        """Draw the gaze arrow."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get widget dimensions
        width = self.width()
        height = self.height()

        # Position circle in upper portion of widget - scale based on widget size
        circle_radius = min(width, height) * 0.35  # Scale to 35% of smaller dimension
        circle_center_x = width / 2
        circle_center_y = circle_radius + 10  # Position from top with small margin

        # Draw background circle
        painter.setPen(QPen(QColor(200, 200, 200), 2))
        painter.setBrush(QColor(240, 240, 240))
        painter.drawEllipse(
            int(circle_center_x - circle_radius),
            int(circle_center_y - circle_radius),
            int(circle_radius * 2),
            int(circle_radius * 2),
        )

        if not self.has_data:
            # Draw "No Data" text centered in circle
            painter.setPen(QColor(150, 150, 150))
            painter.setFont(QFont("Arial", 11))
            painter.drawText(
                int(circle_center_x - circle_radius),
                int(circle_center_y - 10),
                int(circle_radius * 2),
                20,
                Qt.AlignmentFlag.AlignCenter,
                "No Data",
            )
            return

        # Draw center point (face position)
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        painter.setBrush(QColor(0, 0, 0))
        painter.drawEllipse(int(circle_center_x - 5), int(circle_center_y - 5), 10, 10)

        # Calculate arrow endpoint based on gaze angles
        # Using the EXACT same formula as draw_gz in visualizer.py
        # x = -length * cos(yaw) * sin(pitch)
        # y = -length * sin(yaw)
        # The magnitude varies naturally based on the angles (this is correct!)

        pitch_rad = self.pitch_deg / 57.2958  # Convert back to radians
        yaw_rad = self.yaw_deg / 57.2958

        # Scale the arrow so maximum magnitude reaches edge of circle
        # Maximum magnitude from formula is when pitch=90° and yaw=90°: sqrt(1^2 + 1^2) = sqrt(2)
        # So we scale by circle_radius / sqrt(2) to make max magnitude = circle_radius
        arrow_scale = circle_radius  # Full radius for max magnitude

        x = -arrow_scale * math.cos(yaw_rad) * math.sin(pitch_rad)
        y = -arrow_scale * math.sin(yaw_rad)

        end_x = circle_center_x + x
        end_y = circle_center_y + y

        # Choose color based on watching TV status (using center-big-med evaluation)
        if self.watching_tv:
            arrow_color = QColor(0, 255, 0)  # Green - watching TV
        else:
            arrow_color = QColor(0, 0, 255)  # Blue - looking away

        # Draw arrow line
        painter.setPen(QPen(arrow_color, 3))
        painter.drawLine(
            int(circle_center_x), int(circle_center_y), int(end_x), int(end_y)
        )

        # Draw arrowhead - scale based on circle size
        arrow_size = max(8, int(circle_radius * 0.15))
        angle = math.atan2(y, x)

        p1 = QPointF(end_x, end_y)
        p2 = QPointF(
            end_x - arrow_size * math.cos(angle - math.pi / 6),
            end_y - arrow_size * math.sin(angle - math.pi / 6),
        )
        p3 = QPointF(
            end_x - arrow_size * math.cos(angle + math.pi / 6),
            end_y - arrow_size * math.sin(angle + math.pi / 6),
        )

        painter.setBrush(arrow_color)
        painter.drawPolygon(QPolygonF([p1, p2, p3]))

        # Draw captions below the circle - all centered
        text_start_y = int(circle_center_y + circle_radius + 5)

        # Draw pitch/yaw angles - centered
        painter.setPen(QColor(0, 0, 0))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        angle_text = f"P:{self.pitch_deg:+.1f}° Y:{self.yaw_deg:+.1f}°"
        painter.drawText(
            0, text_start_y, width, 16, Qt.AlignmentFlag.AlignHCenter, angle_text
        )

        # Draw timestamp if available - centered
        if self.timestamp:
            painter.setFont(QFont("Arial", 9))
            painter.drawText(
                0,
                text_start_y + 16,
                width,
                14,
                Qt.AlignmentFlag.AlignHCenter,
                self.timestamp,
            )

        # Draw status text if available - centered with word wrap
        if self.status_text:
            painter.setFont(QFont("Arial", 9))
            # Color code the status text
            if "LOOKING AWAY" in self.status_text or "👁️" in self.status_text:
                painter.setPen(QColor(0, 0, 255))  # Blue
            elif "WATCHING TV" in self.status_text or "📺" in self.status_text:
                painter.setPen(QColor(0, 128, 0))  # Green

            # Draw with word wrap, centered
            painter.drawText(
                2,
                text_start_y + 30,
                width - 4,
                40,
                Qt.AlignmentFlag.AlignHCenter
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap,
                self.status_text,
            )
