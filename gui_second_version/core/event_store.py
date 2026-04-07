"""Event Store for comprehensive audit logging of all setup actions.

This module provides a centralized event logging system that records every
action, state change, and result during the setup wizard process. Events
are persisted to a JSON file for later review and debugging.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class EventType(Enum):
    """Categories of events that can be logged."""

    # Step lifecycle events
    STEP_ACTIVATED = "step_activated"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"

    # User actions
    USER_INPUT = "user_input"
    BUTTON_CLICK = "button_click"
    CHECKBOX_CHANGED = "checkbox_changed"
    SELECTION_CHANGED = "selection_changed"

    # Automation events
    AUTOMATION_STARTED = "automation_started"
    AUTOMATION_COMPLETED = "automation_completed"
    AUTOMATION_FAILED = "automation_failed"

    # Process events
    PROCESS_STARTED = "process_started"
    PROCESS_COMPLETED = "process_completed"
    PROCESS_FAILED = "process_failed"
    PROCESS_TERMINATED = "process_terminated"

    # Validation events
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"

    # System events
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    STATE_SAVED = "state_saved"
    STATE_LOADED = "state_loaded"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    # Data events
    DATA_CREATED = "data_created"
    DATA_DELETED = "data_deleted"
    DATA_COPIED = "data_copied"
    FILE_OPERATION = "file_operation"

    # Hardware events
    CAMERA_DETECTED = "camera_detected"
    CAMERA_TEST = "camera_test"
    SMART_PLUG_STATUS = "smart_plug_status"
    RTC_SYNC = "rtc_sync"
    WIFI_STATUS = "wifi_status"


@dataclass
class Event:
    """Represents a single logged event."""

    timestamp: str
    event_type: str
    step_id: int | None
    action: str
    details: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict:
        """Convert event to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Event:
        """Create event from dictionary."""
        return cls(**data)


class EventStore:
    """Centralized event store for audit logging.

    This class provides a thread-safe singleton for logging all events
    during the setup wizard process. Events are automatically persisted
    to a JSON file.

    Usage:
        from core.event_store import get_event_store

        store = get_event_store()
        store.log_event(
            EventType.BUTTON_CLICK,
            step_id=1,
            action="validate_participant_id",
            details={"participant_id": "P1-1234"}
        )
    """

    _instance: EventStore | None = None
    _lock = threading.Lock()

    def __new__(cls) -> EventStore:
        """Ensure singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the event store."""
        if self._initialized:
            return

        self._events: list[Event] = []
        self._event_lock = threading.RLock()
        self._save_path: Path | None = None
        self._session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._participant_id: str | None = None
        self._auto_save = True
        self._initialized = True

    def configure(
        self,
        participant_id: str,
        data_path: str,
        auto_save: bool = True,
    ) -> bool:
        """Configure the event store with participant-specific settings.

        This method is completely safe - it will never raise exceptions.
        If configuration fails, events will still be logged in memory.

        Args:
            participant_id: Full participant ID (e.g., "P1-1234028A")
            data_path: Path to participant's data folder
            auto_save: Whether to auto-save after each event

        Returns:
            True if configuration succeeded, False otherwise (app continues normally)
        """
        try:
            with self._event_lock:
                self._participant_id = participant_id
                self._auto_save = auto_save

                # Try to create event log file path
                try:
                    data_folder = Path(data_path)
                    data_folder.mkdir(parents=True, exist_ok=True)

                    log_filename = f"{participant_id}_setup_events_{self._session_id}.json"
                    self._save_path = data_folder / log_filename
                except Exception:
                    # If we can't create the path, events will stay in memory only
                    self._save_path = None

                # Log session start (won't fail even if save_path is None)
                self.log_event(
                    EventType.SESSION_STARTED,
                    action="setup_wizard_started",
                    details={
                        "participant_id": participant_id,
                        "session_id": self._session_id,
                        "data_path": str(data_path),
                    },
                )
                return True
        except Exception:
            # Configuration failed but app should continue
            return False

    def log_event(
        self,
        event_type: EventType,
        step_id: int | None = None,
        action: str = "",
        details: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> Event | None:
        """Log an event to the store.

        This method is completely safe - it will never raise exceptions
        or cause any side effects to the application.

        Args:
            event_type: Category of the event
            step_id: Which step this event belongs to (None for global events)
            action: Description of the action taken
            details: Additional context as key-value pairs
            success: Whether the action succeeded
            error_message: Error message if action failed

        Returns:
            The created Event object, or None if logging failed (app continues normally)
        """
        try:
            event = Event(
                timestamp=datetime.now().isoformat(),
                event_type=event_type.value,
                step_id=step_id,
                action=action,
                details=details or {},
                success=success,
                error_message=error_message,
            )

            with self._event_lock:
                self._events.append(event)

                if self._auto_save and self._save_path:
                    self._save_to_file()

            return event
        except Exception:
            # Logging failed but app should continue normally
            return None

    def log_step_activated(self, step_id: int, step_name: str) -> Event | None:
        """Convenience method for logging step activation. Never raises exceptions."""
        try:
            return self.log_event(
                EventType.STEP_ACTIVATED,
                step_id=step_id,
                action=f"activated_{step_name.lower().replace(' ', '_')}",
                details={"step_name": step_name},
            )
        except Exception:
            return None

    def log_step_completed(self, step_id: int, step_name: str) -> Event | None:
        """Convenience method for logging step completion. Never raises exceptions."""
        try:
            return self.log_event(
                EventType.STEP_COMPLETED,
                step_id=step_id,
                action=f"completed_{step_name.lower().replace(' ', '_')}",
                details={"step_name": step_name},
            )
        except Exception:
            return None

    def log_user_action(
        self,
        step_id: int,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> Event | None:
        """Convenience method for logging user actions. Never raises exceptions."""
        try:
            return self.log_event(
                EventType.BUTTON_CLICK,
                step_id=step_id,
                action=action,
                details=details,
            )
        except Exception:
            return None

    def log_validation(
        self,
        step_id: int,
        validation_name: str,
        passed: bool,
        details: dict[str, Any] | None = None,
    ) -> Event | None:
        """Convenience method for logging validation results. Never raises exceptions."""
        try:
            event_type = EventType.VALIDATION_PASSED if passed else EventType.VALIDATION_FAILED
            return self.log_event(
                event_type,
                step_id=step_id,
                action=f"validate_{validation_name}",
                details=details,
                success=passed,
            )
        except Exception:
            return None

    def log_error(
        self,
        step_id: int | None,
        action: str,
        error_message: str,
        details: dict[str, Any] | None = None,
    ) -> Event | None:
        """Convenience method for logging errors. Never raises exceptions."""
        try:
            return self.log_event(
                EventType.ERROR,
                step_id=step_id,
                action=action,
                details=details,
                success=False,
                error_message=error_message,
            )
        except Exception:
            return None

    def log_file_operation(
        self,
        operation: str,
        path: str,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> Event | None:
        """Convenience method for logging file operations. Never raises exceptions."""
        try:
            return self.log_event(
                EventType.FILE_OPERATION,
                action=operation,
                details={"path": path, **(details or {})},
                success=success,
            )
        except Exception:
            return None

    def get_events(
        self,
        event_type: EventType | None = None,
        step_id: int | None = None,
        success_only: bool = False,
        failures_only: bool = False,
        since: datetime | None = None,
    ) -> list[Event]:
        """Query events with optional filtering.

        Args:
            event_type: Filter by event type
            step_id: Filter by step ID
            success_only: Only return successful events
            failures_only: Only return failed events
            since: Only return events after this timestamp

        Returns:
            List of matching events
        """
        with self._event_lock:
            events = self._events.copy()

        if event_type:
            events = [e for e in events if e.event_type == event_type.value]

        if step_id is not None:
            events = [e for e in events if e.step_id == step_id]

        if success_only:
            events = [e for e in events if e.success]

        if failures_only:
            events = [e for e in events if not e.success]

        if since:
            since_str = since.isoformat()
            events = [e for e in events if e.timestamp >= since_str]

        return events

    def get_step_timeline(self, step_id: int) -> list[Event]:
        """Get all events for a specific step in chronological order."""
        return self.get_events(step_id=step_id)

    def get_errors(self) -> list[Event]:
        """Get all error events."""
        return self.get_events(failures_only=True)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the event log.

        Returns:
            Dictionary with statistics about the logged events
        """
        with self._event_lock:
            events = self._events.copy()

        if not events:
            return {"total_events": 0}

        # Count by type
        type_counts: dict[str, int] = {}
        for event in events:
            type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1

        # Count successes/failures
        successes = sum(1 for e in events if e.success)
        failures = len(events) - successes

        # Get step completions
        completed_steps = [
            e.step_id
            for e in events
            if e.event_type == EventType.STEP_COMPLETED.value
        ]

        return {
            "total_events": len(events),
            "successes": successes,
            "failures": failures,
            "events_by_type": type_counts,
            "completed_steps": completed_steps,
            "session_id": self._session_id,
            "participant_id": self._participant_id,
            "first_event": events[0].timestamp if events else None,
            "last_event": events[-1].timestamp if events else None,
        }

    def _save_to_file(self) -> None:
        """Save events to JSON file."""
        if not self._save_path:
            return

        try:
            data = {
                "session_id": self._session_id,
                "participant_id": self._participant_id,
                "events": [e.to_dict() for e in self._events],
                "summary": self.get_summary(),
            }

            # Write atomically
            temp_path = self._save_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            temp_path.replace(self._save_path)

        except Exception as e:
            # Don't raise - logging shouldn't break the app
            print(f"Warning: Failed to save event log: {e}")

    def save(self) -> bool:
        """Manually save events to file.

        Returns:
            True if save succeeded, False otherwise
        """
        try:
            with self._event_lock:
                self._save_to_file()
            return True
        except Exception:
            return False

    def export_to_file(self, path: str | Path) -> bool:
        """Export events to a specific file path.

        Args:
            path: Destination file path

        Returns:
            True if export succeeded, False otherwise
        """
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "session_id": self._session_id,
                "participant_id": self._participant_id,
                "exported_at": datetime.now().isoformat(),
                "events": [e.to_dict() for e in self._events],
                "summary": self.get_summary(),
            }

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True

        except Exception:
            return False

    def clear(self) -> None:
        """Clear all events (use with caution)."""
        with self._event_lock:
            self._events.clear()

    def end_session(self) -> None:
        """Mark the end of the setup session."""
        self.log_event(
            EventType.SESSION_ENDED,
            action="setup_wizard_ended",
            details=self.get_summary(),
        )


# Module-level singleton accessor
_event_store: EventStore | None = None


def get_event_store() -> EventStore:
    """Get the global event store instance.

    Returns:
        The singleton EventStore instance
    """
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
    return _event_store
