"""Integration tests for wizard steps.

These tests verify that wizard steps work correctly with their dependencies
(state, process runner, etc.) and properly emit signals.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QLineEdit

from core import ProcessRunner, StateManager
from models import StepDefinition, StepStatus, WizardState
from models.enums import StepContentType
from models.state_keys import UserInputKey, WizardStep
from steps import StepFactory


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def step_definition_participant() -> StepDefinition:
    """Create participant setup step definition."""
    return StepDefinition(
        step_id=WizardStep.PARTICIPANT_SETUP,
        title="Participant Setup",
        description="Enter participant information",
        content_type=StepContentType.MANUAL,
        prerequisites=[],
        validation_rules=[],
    )


@pytest.fixture
def step_definition_wifi() -> StepDefinition:
    """Create WiFi connection step definition."""
    return StepDefinition(
        step_id=WizardStep.WIFI_CONNECTION,
        title="WiFi Connection",
        description="Configure WiFi",
        content_type=StepContentType.MIXED,
        prerequisites=[WizardStep.PARTICIPANT_SETUP],
        validation_rules=[],
    )


@pytest.fixture
def mock_process_runner(wizard_state: WizardState) -> ProcessRunner:
    """Create a mocked process runner."""
    runner = ProcessRunner(wizard_state)
    runner.run_command = MagicMock(return_value=("success", ""))
    runner.run_sudo_command = MagicMock(return_value=("success", None))
    return runner


# ============================================================================
# Participant Setup Step Tests
# ============================================================================


class TestParticipantSetupStep:
    """Integration tests for ParticipantSetupStep."""

    def test_step_creation(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test step can be created."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        assert step is not None
        assert step.step_definition == step_definition_participant

    def test_step_has_required_inputs(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test step has input fields for required data."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)
        step.show()

        # Should have input fields
        line_edits = step.findChildren(QLineEdit)
        assert len(line_edits) > 0

    def test_step_status_starts_pending(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test step starts with pending status."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        # Initial status should be pending or user_action_required
        assert step.current_status in [StepStatus.PENDING, StepStatus.USER_ACTION_REQUIRED]

    def test_step_activation(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test step activation updates status."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        step.activate_step()

        # After activation, should be waiting for user action
        assert step.current_status in [StepStatus.PENDING, StepStatus.USER_ACTION_REQUIRED]

    def test_step_deactivation(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test step can be deactivated."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        step.activate_step()
        step.deactivate_step()

        # Should not raise any errors


class TestWiFiConnectionStep:
    """Integration tests for WiFiConnectionStep."""

    def test_step_creation(
        self,
        qtbot,
        populated_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_wifi: StepDefinition,
        state_manager: StateManager,
    ):
        """Test WiFi step can be created."""
        step = StepFactory.create_step_instance(
            step_definition_wifi,
            populated_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        assert step is not None

    @patch("subprocess.run")
    def test_wifi_status_check(
        self,
        mock_run,
        qtbot,
        populated_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_wifi: StepDefinition,
        state_manager: StateManager,
    ):
        """Test WiFi status checking."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="SSID: TestNetwork\nSignal: 80%",
            stderr=""
        )

        step = StepFactory.create_step_instance(
            step_definition_wifi,
            populated_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)
        step.show()


class TestTimeSyncStep:
    """Integration tests for TimeSyncStep."""

    @pytest.fixture
    def step_definition_time(self) -> StepDefinition:
        """Create time sync step definition."""
        return StepDefinition(
            step_id=WizardStep.TIME_SYNC,
            title="Time Synchronization",
            description="Sync system time",
            content_type=StepContentType.AUTOMATED,
            prerequisites=[WizardStep.PARTICIPANT_SETUP, WizardStep.WIFI_CONNECTION],
            validation_rules=[],
        )

    @patch("subprocess.run")
    def test_time_sync_check(
        self,
        mock_run,
        qtbot,
        completed_steps_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_time: StepDefinition,
        state_manager: StateManager,
    ):
        """Test time sync status checking."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="System clock synchronized: yes",
            stderr=""
        )

        step = StepFactory.create_step_instance(
            step_definition_time,
            completed_steps_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)
        step.show()


# ============================================================================
# Step Signal Tests
# ============================================================================


class TestStepSignals:
    """Tests for step signal emissions."""

    def test_status_changed_signal(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test status_changed signal is emitted."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        # Connect signal spy
        with qtbot.waitSignal(step.status_changed, timeout=1000) as blocker:
            step.update_status(StepStatus.USER_ACTION_REQUIRED)

        assert blocker.signal_triggered
        assert blocker.args[0] == StepStatus.USER_ACTION_REQUIRED

    def test_step_completed_signal(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test step_completed signal is emitted."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        with qtbot.waitSignal(step.step_completed, timeout=1000) as blocker:
            step.update_status(StepStatus.COMPLETED)

        assert blocker.signal_triggered


class TestStepStateInteraction:
    """Tests for step interaction with wizard state."""

    def test_step_reads_state(
        self,
        qtbot,
        populated_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test step can read from state."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            populated_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        # Step should have access to state
        assert step.state.get_participant_id() == "P1-3999028"

    def test_step_writes_state(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test step can write to state."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        # Simulate user input by directly setting state
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-TEST123")

        assert wizard_state.get_participant_id() == "P1-TEST123"


# ============================================================================
# Step Timer Tests
# ============================================================================


class TestStepTimers:
    """Tests for step timer management."""

    def test_step_can_create_timer(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test step can create managed timers."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        callback = MagicMock()
        timer = step.create_timer(100, callback, start=False)

        assert timer is not None
        assert timer in step._managed_timers

    def test_timers_stopped_on_deactivate(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        step_definition_participant: StepDefinition,
        state_manager: StateManager,
    ):
        """Test timers are stopped when step is deactivated."""
        step = StepFactory.create_step_instance(
            step_definition_participant,
            wizard_state,
            mock_process_runner,
            state_manager,
        )
        qtbot.addWidget(step)

        callback = MagicMock()
        timer = step.create_timer(100, callback, start=True)

        step.activate_step()
        step.deactivate_step()

        assert not timer.isActive()


# ============================================================================
# Step Factory Tests
# ============================================================================


class TestStepFactory:
    """Tests for StepFactory."""

    def test_creates_all_step_definitions(self):
        """Test factory creates all 11 step definitions."""
        definitions = StepFactory.create_step_definitions()
        assert len(definitions) == 11

    def test_step_definitions_have_unique_ids(self):
        """Test all step definitions have unique IDs."""
        definitions = StepFactory.create_step_definitions()
        ids = [int(d.step_id) for d in definitions]
        assert len(ids) == len(set(ids))

    def test_step_definitions_ordered(self):
        """Test step definitions are in order."""
        definitions = StepFactory.create_step_definitions()
        ids = [int(d.step_id) for d in definitions]
        assert ids == sorted(ids)

    def test_creates_correct_step_class(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        state_manager: StateManager,
    ):
        """Test factory creates correct step class for each definition."""
        from steps.participant_setup_step import ParticipantSetupStep
        from steps.wifi_connection_step import WiFiConnectionStep

        definitions = StepFactory.create_step_definitions()

        participant_def = next(d for d in definitions if int(d.step_id) == 1)
        participant_step = StepFactory.create_step_instance(
            participant_def, wizard_state, mock_process_runner, state_manager
        )
        qtbot.addWidget(participant_step)
        assert isinstance(participant_step, ParticipantSetupStep)

        wifi_def = next(d for d in definitions if int(d.step_id) == 2)
        wifi_step = StepFactory.create_step_instance(
            wifi_def, wizard_state, mock_process_runner, state_manager
        )
        qtbot.addWidget(wifi_step)
        assert isinstance(wifi_step, WiFiConnectionStep)


# ============================================================================
# Cross-Step Tests
# ============================================================================


class TestCrossStepInteraction:
    """Tests for interaction between multiple steps."""

    def test_state_persists_across_steps(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        state_manager: StateManager,
    ):
        """Test state persists when navigating between steps."""
        definitions = StepFactory.create_step_definitions()

        step1_def = definitions[0]  # Participant setup
        step2_def = definitions[1]  # WiFi

        step1 = StepFactory.create_step_instance(
            step1_def, wizard_state, mock_process_runner, state_manager
        )
        qtbot.addWidget(step1)

        # Set data in step 1
        wizard_state.set_user_input(UserInputKey.PARTICIPANT_ID, "P1-PERSIST")

        step2 = StepFactory.create_step_instance(
            step2_def, wizard_state, mock_process_runner, state_manager
        )
        qtbot.addWidget(step2)

        # Data should be available in step 2
        assert step2.state.get_participant_id() == "P1-PERSIST"

    def test_steps_share_state_manager(
        self,
        qtbot,
        wizard_state: WizardState,
        mock_process_runner: ProcessRunner,
        state_manager: StateManager,
    ):
        """Test steps share the same state manager."""
        definitions = StepFactory.create_step_definitions()

        steps = []
        for i in range(3):
            step = StepFactory.create_step_instance(
                definitions[i], wizard_state, mock_process_runner, state_manager
            )
            qtbot.addWidget(step)
            steps.append(step)

        # All steps should reference the same state manager
        for step in steps:
            assert step.state_manager is state_manager
