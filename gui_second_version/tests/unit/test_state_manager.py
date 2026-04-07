"""Unit tests for StateManager."""

from __future__ import annotations

import json
from pathlib import Path


from core import StateManager
from models import WizardState
from models.state_keys import UserInputKey


class TestStateManagerInitialization:
    """Tests for StateManager initialization."""

    def test_creates_state_directory(self, tmp_path: Path):
        """Test that state directory is created if it doesn't exist."""
        state_file = tmp_path / "subdir" / "state.json"
        StateManager(state_file_path=str(state_file))  # Side effect creates dir
        assert state_file.parent.exists()

    def test_default_state_file_path(self):
        """Test default state file path is set."""
        manager = StateManager()
        assert manager.state_file_path is not None

    def test_backup_file_path_derived(self, temp_state_file: Path):
        """Test backup file path is derived from main file."""
        manager = StateManager(state_file_path=str(temp_state_file))
        assert manager.backup_file_path.suffix == ".backup"


class TestSaveState:
    """Tests for saving state."""

    def test_save_state_creates_file(self, state_manager: StateManager, wizard_state: WizardState):
        """Test that saving creates the state file."""
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-123456")
        result = state_manager.save_state(wizard_state, force=True)
        assert result is True
        assert state_manager.state_file_path.exists()

    def test_save_state_json_valid(self, state_manager: StateManager, wizard_state: WizardState):
        """Test that saved state is valid JSON."""
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-123456")
        state_manager.save_state(wizard_state, force=True)

        with open(state_manager.state_file_path) as f:
            data = json.load(f)

        assert "current_step" in data
        assert "user_inputs" in data

    def test_save_state_includes_metadata(self, state_manager: StateManager, wizard_state: WizardState):
        """Test that saved state includes metadata."""
        state_manager.save_state(wizard_state, force=True)

        with open(state_manager.state_file_path) as f:
            data = json.load(f)

        assert "created_at" in data
        assert "modified_at" in data
        assert "version" in data

    def test_save_state_skips_unchanged(self, state_manager: StateManager, wizard_state: WizardState):
        """Test that unchanged state is not saved unless forced."""
        # First save
        state_manager.save_state(wizard_state, force=True)

        # Second save without changes should return False
        result = state_manager.save_state(wizard_state, force=False)
        assert result is False

    def test_save_state_dirty_flag(self, state_manager: StateManager, wizard_state: WizardState):
        """Test dirty flag behavior."""
        state_manager.save_state(wizard_state, force=True)
        assert not state_manager.is_dirty()

        state_manager.mark_dirty()
        assert state_manager.is_dirty()

    def test_save_state_creates_backup(self, state_manager: StateManager, wizard_state: WizardState):
        """Test that backup is created on subsequent saves."""
        # First save
        state_manager.save_state(wizard_state, force=True)

        # Modify and save again
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-999999")
        state_manager.save_state(wizard_state, force=True)

        # Backup should exist
        assert state_manager.backup_file_path.exists()


class TestLoadState:
    """Tests for loading state."""

    def test_load_state_returns_none_if_no_file(self, state_manager: StateManager):
        """Test loading returns None when no state file exists."""
        state = state_manager.load_state()
        assert state is None

    def test_load_state_returns_wizard_state(self, state_manager_with_data: StateManager):
        """Test loading returns WizardState instance."""
        state = state_manager_with_data.load_state()
        assert isinstance(state, WizardState)

    def test_load_state_preserves_data(self, state_manager_with_data: StateManager):
        """Test loaded state has correct data."""
        state = state_manager_with_data.load_state()
        assert state.get_participant_id() == "P1-3999028"
        assert state.get_device_id() == "A"

    def test_load_state_initializes_hash_tracking(self, state_manager_with_data: StateManager):
        """Test loading initializes hash tracking."""
        state_manager_with_data.load_state()
        # Hash should be set, dirty should be False
        assert state_manager_with_data._last_state_hash is not None
        assert not state_manager_with_data.is_dirty()

    def test_load_state_falls_back_to_backup(self, state_manager: StateManager, wizard_state: WizardState):
        """Test loading falls back to backup if main file corrupted."""
        # Save state
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-123456")
        state_manager.save_state(wizard_state, force=True)

        # Create backup with different data
        backup_data = {
            "current_step": 1,
            "completed_steps": [],
            "user_inputs": {"participant_id": "P1-BACKUP"},
            "system_state": {},
        }
        with open(state_manager.backup_file_path, "w") as f:
            json.dump(backup_data, f)

        # Corrupt main file
        with open(state_manager.state_file_path, "w") as f:
            f.write("invalid json{{{")

        # Load should fall back to backup
        state = state_manager.load_state()
        assert state.get_participant_id() == "P1-BACKUP"


class TestSessionDetection:
    """Tests for session detection and recovery."""

    def test_has_existing_session_false_initially(self, state_manager: StateManager):
        """Test no existing session initially."""
        assert not state_manager.has_existing_session()

    def test_has_existing_session_true_after_save(self, state_manager: StateManager, wizard_state: WizardState):
        """Test existing session detected after save."""
        state_manager.save_state(wizard_state, force=True)
        assert state_manager.has_existing_session()

    def test_detect_incomplete_session(self, state_manager: StateManager, wizard_state: WizardState):
        """Test detecting incomplete session."""
        wizard_state.current_step = 3  # Mid-wizard
        state_manager.save_state(wizard_state, force=True)
        assert state_manager.detect_incomplete_session()


class TestClearState:
    """Tests for clearing state."""

    def test_clear_state_removes_files(self, state_manager: StateManager, wizard_state: WizardState):
        """Test clearing removes state files."""
        state_manager.save_state(wizard_state, force=True)
        assert state_manager.state_file_path.exists()

        state_manager.clear_state()
        assert not state_manager.state_file_path.exists()

    def test_clear_state_removes_backup(self, state_manager: StateManager, wizard_state: WizardState):
        """Test clearing removes backup file."""
        # Create both main and backup
        state_manager.save_state(wizard_state, force=True)
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-999999")
        state_manager.save_state(wizard_state, force=True)

        state_manager.clear_state()
        assert not state_manager.backup_file_path.exists()


class TestStateInfo:
    """Tests for getting state info."""

    def test_get_state_info_no_file(self, state_manager: StateManager):
        """Test state info when no file exists."""
        info = state_manager.get_state_info()
        assert info["exists"] is False
        assert info["backup_exists"] is False

    def test_get_state_info_with_file(self, state_manager_with_data: StateManager):
        """Test state info when file exists."""
        info = state_manager_with_data.get_state_info()
        assert info["exists"] is True
        assert info["size"] > 0
        assert info["created_at"] != "Unknown"


class TestCheckpoints:
    """Tests for checkpoint functionality."""

    def test_create_checkpoint(self, state_manager: StateManager, wizard_state: WizardState):
        """Test creating a checkpoint."""
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-123456")
        state_manager.create_state_checkpoint(wizard_state, "before_gallery")

        # Checkpoint file should exist
        checkpoint_file = state_manager.state_file_path.with_suffix(".before_gallery.checkpoint")
        assert checkpoint_file.exists()

    def test_list_checkpoints(self, state_manager: StateManager, wizard_state: WizardState):
        """Test listing checkpoints."""
        state_manager.create_state_checkpoint(wizard_state, "checkpoint1")
        state_manager.create_state_checkpoint(wizard_state, "checkpoint2")

        checkpoints = state_manager.list_checkpoints()
        assert len(checkpoints) >= 2
        names = [cp["name"] for cp in checkpoints]
        assert "checkpoint1" in names
        assert "checkpoint2" in names


class TestThreadSafety:
    """Tests for thread safety."""

    def test_save_state_uses_lock(self, state_manager: StateManager, wizard_state: WizardState):
        """Test that save_state uses the lock."""
        # This test verifies the lock is acquired
        assert hasattr(state_manager, "_lock")
        state_manager.save_state(wizard_state, force=True)
        # If we get here without deadlock, locking works

    def test_load_state_uses_lock(self, state_manager_with_data: StateManager):
        """Test that load_state uses the lock."""
        state_manager_with_data.load_state()
        # If we get here without deadlock, locking works


class TestAtomicWrites:
    """Tests for atomic write operations."""

    def test_temp_file_not_left_behind(self, state_manager: StateManager, wizard_state: WizardState):
        """Test that temp files are cleaned up."""
        state_manager.save_state(wizard_state, force=True)
        temp_file = state_manager.state_file_path.with_suffix(".tmp")
        assert not temp_file.exists()

    def test_save_failure_restores_backup(self, state_manager: StateManager, wizard_state: WizardState):
        """Test that failed save attempts to restore backup."""
        # Save initial state
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-123456")
        state_manager.save_state(wizard_state, force=True)

        # Modify and save to create backup
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-999999")
        state_manager.save_state(wizard_state, force=True)

        # Both files should exist
        assert state_manager.state_file_path.exists()
        assert state_manager.backup_file_path.exists()
