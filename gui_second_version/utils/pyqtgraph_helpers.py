"""PyQtGraph helper classes and utilities."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg


class TimeAxisItem(pg.AxisItem):
    """Custom axis item that formats time values as MM:SS with limited tick count.

    This axis item is designed for displaying elapsed time data on plots,
    automatically formatting labels as MM:SS or HH:MM:SS based on the time range.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enableAutoSIPrefix(False)  # Disable SI prefix scaling

    def tickValues(self, minVal, maxVal, size):
        """Override to generate a reasonable number of ticks (max ~20)."""
        # Calculate range
        data_range = maxVal - minVal

        if data_range <= 0:
            return []

        # Determine appropriate tick spacing based on range
        # Aim for 10-20 ticks
        target_ticks = 15
        raw_spacing = data_range / target_ticks

        # Round to nice intervals (1s, 5s, 10s, 30s, 1min, 5min, 10min, 30min, 1hr, etc.)
        nice_intervals = [
            1,
            5,
            10,
            30,
            60,
            300,
            600,
            1800,
            3600,
            7200,
            10800,
            21600,
            43200,
            86400,
        ]

        # Find the closest nice interval
        spacing = min(nice_intervals, key=lambda x: abs(x - raw_spacing))

        # Generate major ticks
        major_ticks = []
        tick = np.ceil(minVal / spacing) * spacing
        while tick <= maxVal:
            major_ticks.append(tick)
            tick += spacing

        # Generate minor ticks (5x denser)
        minor_spacing = spacing / 5
        minor_ticks = []
        tick = np.ceil(minVal / minor_spacing) * minor_spacing
        while tick <= maxVal:
            if tick not in major_ticks:  # Don't duplicate major ticks
                minor_ticks.append(tick)
            tick += minor_spacing

        return [(spacing, major_ticks), (minor_spacing, minor_ticks)]

    def tickStrings(self, values, scale, spacing):
        """Override to format tick labels as MM:SS or HH:MM:SS."""
        strings = []
        for value in values:
            # Handle edge cases
            if not np.isfinite(value):
                strings.append("")
                continue

            total_seconds = int(value)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            if hours > 0:
                # Show HH:MM:SS if duration is over 1 hour
                strings.append(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            else:
                # Show MM:SS for durations under 1 hour
                strings.append(f"{minutes:02d}:{seconds:02d}")

        return strings
