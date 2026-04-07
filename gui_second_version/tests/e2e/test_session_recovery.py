"""End-to-end tests for session recovery and persistence.

These tests verify that the wizard correctly saves and restores state,
allowing users to resume from where they left off.
"""

from __future__ import annotations

import json
from pathlib import Path


from core import StateManager
from models import WizardState
from models.state_keys import UserInputKey


class TestSessionPersistence:
    """Tests for session state persistence."""

    def test_state_saved_automatically(self, tmp_path: Path):
        """Test that state is saved automatically."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-AUTO-SAVE")
        state.mark_step_completed(1)

        manager.save_state(state, force=True)

        assert state_file.exists()

        with open(state_file) as f:
            data = json.load(f)

        assert data["user_inputs"]["participant_id"] == "P1-AUTO-SAVE"
        assert 1 in data["completed_steps"]

    def test_state_restored_on_load(self, tmp_path: Path):
        """Test that state is correctly restored on load."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))

        # Save initial state
        original_state = WizardState()
        original_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-RESTORE")
        original_state.set_user_input(UserInputKey.DEVICE_ID, "B")
        original_state.set_user_input(UserInputKey.USERNAME, "testuser")
        original_state.current_step = 5
        original_state.mark_step_completed(1)
        original_state.mark_step_completed(2)
        original_state.mark_step_completed(3)

        manager.save_state(original_state, force=True)

        # Create new manager and load
        new_manager = StateManager(state_file_path=str(state_file))
        loaded_state = new_manager.load_state()

        assert loaded_state is not None
        assert loaded_state.get_participant_id() == "P1-RESTORE"
        assert loaded_state.get_device_id() == "B"
        assert loaded_state.current_step == 5
        assert loaded_state.is_step_completed(1)
        assert loaded_state.is_step_completed(2)
        assert loaded_state.is_step_completed(3)

    def test_incomplete_session_detection(self, tmp_path: Path):
        """Test detection of incomplete sessions."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))

        # Save incomplete state (mid-wizard, not all steps completed)
        state = WizardState()
        state.current_step = 4
        state.mark_step_completed(1)
        state.mark_step_completed(2)
        # Steps 3 and onward not completed

        manager.save_state(state, force=True)

        assert manager.detect_incomplete_session()

    def test_complete_session_no_detection(self, tmp_path: Path):
        """Test that complete sessions are not flagged as incomplete."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))

        # Save with completed_at marker (simulating finished wizard)
        data = {
            "current_step": 11,
            "completed_steps": list(range(1, 12)),
            "user_inputs": {},
            "system_state": {},
            "metadata": {"completed_at": "2025-01-01T12:00:00"},
        }

        with open(state_file, "w") as f:
            json.dump(data, f)

        assert not manager.detect_incomplete_session()


class TestBackupAndRecovery:
    """Tests for backup and recovery functionality."""

    def test_backup_created_on_save(self, tmp_path: Path):
        """Test that backup is created when saving over existing state."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        # First save
        state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-FIRST")
        manager.save_state(state, force=True)

        # Second save (should create backup)
        state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-SECOND")
        manager.save_state(state, force=True)

        assert manager.backup_file_path.exists()

    def test_recovery_from_backup(self, tmp_path: Path):
        """Test recovery from backup when main file is corrupted."""
        state_file = tmp_path / "wizard_state.json"
        backup_file = state_file.with_suffix(".backup")
        manager = StateManager(state_file_path=str(state_file))

        # Create backup directly with known data
        backup_data = {
            "current_step": 3,
            "completed_steps": [1, 2],
            "user_inputs": {"participant_id": "P1-BACKUP-RECOVERY"},
            "system_state": {},
        }
        with open(backup_file, "w") as f:
            json.dump(backup_data, f)

        # Corrupt main file
        with open(state_file, "w") as f:
            f.write("corrupt{{{not json}")

        # Should recover from backup
        loaded = manager.load_state()

        assert loaded is not None
        assert loaded.get_participant_id() == "P1-BACKUP-RECOVERY"
        assert loaded.current_step == 3

    def test_no_recovery_when_both_missing(self, tmp_path: Path):
        """Test behavior when both main and backup files are missing."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))

        loaded = manager.load_state()
        assert loaded is None


class TestCheckpoints:
    """Tests for checkpoint functionality."""

    def test_create_named_checkpoint(self, tmp_path: Path):
        """Test creating a named checkpoint."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-CHECKPOINT")
        state.current_step = 5

        manager.create_state_checkpoint(state, "before_gallery")

        # Checkpoint file should exist
        checkpoint_files = list(tmp_path.glob("*.checkpoint"))
        assert len(checkpoint_files) == 1
        assert "before_gallery" in str(checkpoint_files[0])

    def test_list_multiple_checkpoints(self, tmp_path: Path):
        """Test listing multiple checkpoints."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        # Create multiple checkpoints
        state.current_step = 3
        manager.create_state_checkpoint(state, "step3_complete")

        state.current_step = 5
        manager.create_state_checkpoint(state, "step5_complete")

        state.current_step = 7
        manager.create_state_checkpoint(state, "before_final")

        checkpoints = manager.list_checkpoints()

        assert len(checkpoints) == 3
        checkpoint_names = [cp["name"] for cp in checkpoints]
        assert "step3_complete" in checkpoint_names
        assert "step5_complete" in checkpoint_names
        assert "before_final" in checkpoint_names

    def test_checkpoint_includes_state_data(self, tmp_path: Path):
        """Test that checkpoints include full state data."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-FULL-DATA")
        state.set_user_input(UserInputKey.DEVICE_ID, "C")
        state.current_step = 4
        state.mark_step_completed(1)
        state.mark_step_completed(2)

        manager.create_state_checkpoint(state, "test_checkpoint")

        checkpoints = manager.list_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0]["step"] == 4


class TestConcurrentAccess:
    """Tests for handling concurrent access to state files."""

    def test_thread_safe_save(self, tmp_path: Path):
        """Test that saves are thread-safe."""
        import threading

        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))

        errors = []

        def save_state(participant_id: str):
            try:
                state = WizardState()
                state.set_user_input(UserInputKey.PARTICIPANT_ID, participant_id)
                manager.save_state(state, force=True)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=save_state, args=(f"P1-THREAD-{i}",))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0
        # File should exist and be valid JSON
        assert state_file.exists()
        with open(state_file) as f:
            data = json.load(f)
        assert "participant_id" in data["user_inputs"]


class TestStateVersioning:
    """Tests for state file versioning."""

    def test_version_included_in_save(self, tmp_path: Path):
        """Test that version is included in saved state."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        manager.save_state(state, force=True)

        with open(state_file) as f:
            data = json.load(f)

        assert "version" in data

    def test_timestamps_updated_on_save(self, tmp_path: Path):
        """Test that created_at is preserved and modified_at is updated on each save."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        # First save
        manager.save_state(state, force=True)
        with open(state_file) as f:
            data1 = json.load(f)
        created_at = data1.get("created_at")
        modified_at1 = data1.get("modified_at")

        # Wait briefly and save again
        import time
        time.sleep(0.1)

        state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-UPDATED")
        manager.save_state(state, force=True)

        with open(state_file) as f:
            data2 = json.load(f)

        # Verify created_at is preserved and modified_at is updated
        assert data2["created_at"] == created_at  # Should be preserved!
        assert data2["modified_at"] > modified_at1  # Should be updated


class TestEdgeCases:
    """Tests for edge cases in session handling."""

    def test_empty_state_save_and_load(self, tmp_path: Path):
        """Test saving and loading empty state."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        manager.save_state(state, force=True)
        loaded = manager.load_state()

        assert loaded is not None
        assert loaded.current_step == 1
        assert len(loaded.completed_steps) == 0

    def test_large_state_save_and_load(self, tmp_path: Path):
        """Test saving and loading state with lots of data."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        # Add lots of data
        for i in range(100):
            state.set_user_input(f"custom_key_{i}", f"value_{i}" * 100)

        for step in range(1, 12):
            state.mark_step_completed(step)

        manager.save_state(state, force=True)
        loaded = manager.load_state()

        assert loaded is not None
        assert len(loaded.user_inputs) == 100
        assert len(loaded.completed_steps) == 11

    def test_special_characters_in_state(self, tmp_path: Path):
        """Test state with special characters."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        special_value = "Test with émojis 🎉 and spëcial çharacters <>&\""
        state.set_user_input(UserInputKey.PARTICIPANT_ID, special_value)

        manager.save_state(state, force=True)
        loaded = manager.load_state()

        assert loaded.get_participant_id() == special_value

    def test_clear_removes_all_state_files(self, tmp_path: Path):
        """Test that clear removes all state-related files."""
        state_file = tmp_path / "wizard_state.json"
        manager = StateManager(state_file_path=str(state_file))
        state = WizardState()

        # Create main file, backup, and checkpoints
        manager.save_state(state, force=True)
        state.set_user_input("key", "value")
        manager.save_state(state, force=True)  # Creates backup
        manager.create_state_checkpoint(state, "test")

        # Verify files exist
        assert state_file.exists()
        assert manager.backup_file_path.exists()

        # Clear all
        manager.clear_state()

        # Main and backup should be removed
        assert not state_file.exists()
        assert not manager.backup_file_path.exists()
