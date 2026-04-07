"""Unit tests for WizardState model."""

from __future__ import annotations


from models import WizardState
from models.state_keys import UserInputKey, WizardStep, SystemStateKey


class TestWizardStateInitialization:
    """Tests for WizardState initialization."""

    def test_default_initialization(self, wizard_state: WizardState):
        """Test default state values on initialization."""
        assert wizard_state.current_step == 1
        assert wizard_state.completed_steps == set()
        assert wizard_state.user_inputs == {}
        assert wizard_state.system_state == {}
        assert wizard_state.process_status == {}

    def test_current_step_starts_at_one(self, wizard_state: WizardState):
        """Verify wizard starts at step 1."""
        assert wizard_state.current_step == 1


class TestStepCompletion:
    """Tests for step completion tracking."""

    def test_mark_step_completed_with_enum(self, wizard_state: WizardState):
        """Test marking step complete using WizardStep enum."""
        wizard_state.mark_step_completed(WizardStep.PARTICIPANT_SETUP)
        assert wizard_state.is_step_completed(WizardStep.PARTICIPANT_SETUP)

    def test_mark_step_completed_with_int(self, wizard_state: WizardState):
        """Test marking step complete using integer."""
        wizard_state.mark_step_completed(1)
        assert wizard_state.is_step_completed(1)

    def test_is_step_completed_false_by_default(self, wizard_state: WizardState):
        """Test that steps are not completed by default."""
        assert not wizard_state.is_step_completed(WizardStep.PARTICIPANT_SETUP)

    def test_mark_multiple_steps_completed(self, wizard_state: WizardState):
        """Test completing multiple steps."""
        steps = [WizardStep.PARTICIPANT_SETUP, WizardStep.WIFI_CONNECTION, WizardStep.TIME_SYNC]
        for step in steps:
            wizard_state.mark_step_completed(step)

        for step in steps:
            assert wizard_state.is_step_completed(step)

    def test_completed_steps_is_set(self, wizard_state: WizardState):
        """Verify completed_steps uses set semantics (no duplicates)."""
        wizard_state.mark_step_completed(1)
        wizard_state.mark_step_completed(1)  # Duplicate
        assert len(wizard_state.completed_steps) == 1


class TestUserInputs:
    """Tests for user input handling."""

    def test_set_and_get_user_input_with_enum(self, wizard_state: WizardState):
        """Test setting and getting input with UserInputKey enum."""
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-123456")
        assert wizard_state.get_user_input(UserInputKey.PARTICIPANT_ID) == "P1-123456"

    def test_set_and_get_user_input_with_string(self, wizard_state: WizardState):
        """Test setting and getting input with string key."""
        wizard_state.set_user_input("custom_key", "custom_value")
        assert wizard_state.get_user_input("custom_key") == "custom_value"

    def test_get_user_input_default_value(self, wizard_state: WizardState):
        """Test default value when key doesn't exist."""
        assert wizard_state.get_user_input(UserInputKey.PARTICIPANT_ID, "default") == "default"

    def test_has_user_input(self, wizard_state: WizardState):
        """Test checking if input exists."""
        assert not wizard_state.has_user_input(UserInputKey.PARTICIPANT_ID)
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-123456")
        assert wizard_state.has_user_input(UserInputKey.PARTICIPANT_ID)

    def test_remove_user_input(self, wizard_state: WizardState):
        """Test removing user input."""
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-123456")
        removed = wizard_state.remove_user_input(UserInputKey.PARTICIPANT_ID)
        assert removed == "P1-123456"
        assert not wizard_state.has_user_input(UserInputKey.PARTICIPANT_ID)

    def test_remove_nonexistent_input(self, wizard_state: WizardState):
        """Test removing input that doesn't exist returns None."""
        assert wizard_state.remove_user_input(UserInputKey.PARTICIPANT_ID) is None


class TestParticipantInfo:
    """Tests for participant information methods."""

    def test_get_participant_id(self, populated_state: WizardState):
        """Test getting participant ID."""
        assert populated_state.get_participant_id() == "P1-3999028"

    def test_get_device_id(self, populated_state: WizardState):
        """Test getting device ID."""
        assert populated_state.get_device_id() == "A"

    def test_get_combined_id(self, populated_state: WizardState):
        """Test getting combined participant+device ID."""
        assert populated_state.get_combined_id() == "P1-3999028A"

    def test_get_combined_id_missing_parts(self, wizard_state: WizardState):
        """Test combined ID when parts are missing."""
        assert wizard_state.get_combined_id() is None

    def test_get_username(self, populated_state: WizardState):
        """Test getting username."""
        assert populated_state.get_username() == "testuser"


class TestWiFiInfo:
    """Tests for WiFi information methods."""

    def test_is_wifi_connected_false_by_default(self, wizard_state: WizardState):
        """Test WiFi not connected by default."""
        assert not wizard_state.is_wifi_connected()

    def test_set_wifi_info(self, wizard_state: WizardState):
        """Test setting WiFi information."""
        wizard_state.set_wifi_info("TestNetwork", connected=True)
        assert wizard_state.is_wifi_connected()
        assert wizard_state.get_wifi_ssid() == "TestNetwork"

    def test_get_wifi_ssid_none_by_default(self, wizard_state: WizardState):
        """Test WiFi SSID is None by default."""
        assert wizard_state.get_wifi_ssid() is None


class TestCameraInfo:
    """Tests for camera information methods."""

    def test_get_camera_index_none_by_default(self, wizard_state: WizardState):
        """Test camera index is None by default."""
        assert wizard_state.get_camera_index() is None

    def test_set_and_get_camera_index(self, wizard_state: WizardState):
        """Test setting and getting camera index."""
        wizard_state.set_camera_index(2)
        assert wizard_state.get_camera_index() == 2


class TestDirectoryPaths:
    """Tests for directory path generation."""

    def test_get_data_directory(self, populated_state: WizardState):
        """Test getting data directory path."""
        data_dir = populated_state.get_data_directory()
        assert data_dir is not None
        assert "testuser" in str(data_dir)
        assert "P1-3999028A" in str(data_dir)

    def test_get_gallery_directory(self, populated_state: WizardState):
        """Test getting gallery directory path."""
        gallery_dir = populated_state.get_gallery_directory()
        assert gallery_dir is not None
        assert "_faces" in str(gallery_dir)

    def test_get_log_file_path(self, populated_state: WizardState):
        """Test getting log file path."""
        log_path = populated_state.get_log_file_path()
        assert log_path is not None
        assert "flash_log" in str(log_path)


class TestSystemState:
    """Tests for system state handling."""

    def test_set_and_get_system_state(self, wizard_state: WizardState):
        """Test setting and getting system state."""
        wizard_state.set_system_state(SystemStateKey.DETECTED_CAMERAS, [0, 1, 2])
        assert wizard_state.get_system_state(SystemStateKey.DETECTED_CAMERAS) == [0, 1, 2]

    def test_has_system_state(self, wizard_state: WizardState):
        """Test checking if system state exists."""
        assert not wizard_state.has_system_state(SystemStateKey.DETECTED_CAMERAS)
        wizard_state.set_system_state(SystemStateKey.DETECTED_CAMERAS, [0])
        assert wizard_state.has_system_state(SystemStateKey.DETECTED_CAMERAS)


class TestStepNavigation:
    """Tests for step navigation logic."""

    def test_can_proceed_to_first_step(self, wizard_state: WizardState):
        """Test can always proceed to first step."""
        can_proceed, reason = wizard_state.can_proceed_to_step(WizardStep.PARTICIPANT_SETUP)
        assert can_proceed
        assert reason == ""

    def test_cannot_proceed_without_prerequisites(self, wizard_state: WizardState):
        """Test cannot proceed to step without completing prerequisites."""
        can_proceed, reason = wizard_state.can_proceed_to_step(WizardStep.WIFI_CONNECTION)
        assert not can_proceed
        assert "steps" in reason.lower()

    def test_can_proceed_after_prerequisites(self, completed_steps_state: WizardState):
        """Test can proceed after completing prerequisites."""
        can_proceed, reason = completed_steps_state.can_proceed_to_step(WizardStep.SMART_PLUG_PHYSICAL)
        assert can_proceed

    def test_get_next_incomplete_step(self, wizard_state: WizardState):
        """Test getting next incomplete step."""
        next_step = wizard_state.get_next_incomplete_step()
        assert next_step == 1  # First step

    def test_get_next_incomplete_step_after_completion(self, wizard_state: WizardState):
        """Test next incomplete step updates after completion."""
        wizard_state.mark_step_completed(1)
        next_step = wizard_state.get_next_incomplete_step()
        assert next_step == 2


class TestCompletionPercentage:
    """Tests for completion percentage calculation."""

    def test_completion_percentage_zero_initially(self, wizard_state: WizardState):
        """Test completion is 0% initially."""
        assert wizard_state.get_completion_percentage() == 0

    def test_completion_percentage_increases(self, wizard_state: WizardState):
        """Test completion percentage increases with completed steps."""
        wizard_state.mark_step_completed(WizardStep.PARTICIPANT_SETUP)
        percentage = wizard_state.get_completion_percentage()
        assert percentage > 0

    def test_completion_percentage_full(self, fully_completed_state: WizardState):
        """Test completion is 100% when all steps complete."""
        assert fully_completed_state.get_completion_percentage() == 100


class TestSerialization:
    """Tests for state serialization/deserialization."""

    def test_to_dict(self, populated_state: WizardState):
        """Test converting state to dictionary."""
        data = populated_state.to_dict()
        assert "current_step" in data
        assert "completed_steps" in data
        assert "user_inputs" in data
        assert isinstance(data["completed_steps"], list)

    def test_from_dict(self):
        """Test creating state from dictionary."""
        data = {
            "current_step": 3,
            "completed_steps": [1, 2],
            "user_inputs": {"participant_id": "P1-123456"},
            "system_state": {},
        }
        state = WizardState.from_dict(data)
        assert state.current_step == 3
        assert state.completed_steps == {1, 2}
        assert state.get_user_input("participant_id") == "P1-123456"

    def test_round_trip_serialization(self, populated_state: WizardState):
        """Test serializing and deserializing produces same state."""
        populated_state.mark_step_completed(1)
        data = populated_state.to_dict()
        restored = WizardState.from_dict(data)

        assert restored.current_step == populated_state.current_step
        assert restored.completed_steps == populated_state.completed_steps
        assert restored.get_participant_id() == populated_state.get_participant_id()


class TestValidation:
    """Tests for state validation."""

    def test_validate_for_step_with_prerequisites(self, wizard_state: WizardState):
        """Test validation checks prerequisites."""
        is_valid, errors = wizard_state.validate_for_step(WizardStep.WIFI_CONNECTION)
        assert not is_valid
        assert len(errors) > 0

    def test_validate_for_step_success(self, completed_steps_state: WizardState):
        """Test validation passes with prerequisites."""
        is_valid, errors = completed_steps_state.validate_for_step(WizardStep.SMART_PLUG_PHYSICAL)
        assert is_valid
        assert len(errors) == 0


class TestStateSummary:
    """Tests for state summary generation."""

    def test_get_summary(self, populated_state: WizardState):
        """Test getting state summary."""
        summary = populated_state.get_summary()
        assert "current_step" in summary
        assert "participant_id" in summary
        assert "completion_percentage" in summary
        assert summary["participant_id"] == "P1-3999028"
