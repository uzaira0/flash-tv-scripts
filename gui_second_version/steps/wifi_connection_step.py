"""Simplified WiFi connection step using system network settings."""

from __future__ import annotations

import os
import subprocess

from config.messages import MESSAGES
from core import WizardStep
from core.exceptions import ErrorType, FlashTVError, handle_step_error
from models import StepStatus
from models.state_keys import UserInputKey
from PySide6.QtWidgets import (
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QWidget,
)
from utils.ui_factory import ButtonStyle


class WiFiConnectionStep(WizardStep):
    """Step 2: Simple WiFi Configuration using system network settings."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.available_networks = []  # Store scanned networks

    def create_content_widget(self) -> QWidget:
        """Create the simplified WiFi connection UI with two-column layout."""
        from PySide6.QtWidgets import QHBoxLayout

        content = QWidget()
        main_layout = self.ui_factory.create_main_step_layout()
        content.setLayout(main_layout)

        # Two-column layout for status and instructions
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)

        # Left column: Status
        status_section = self._create_status_section()
        columns_layout.addWidget(status_section, stretch=1)

        # Right column: Instructions
        instructions_section = self._create_instructions_section()
        columns_layout.addWidget(instructions_section, stretch=1)

        main_layout.addLayout(columns_layout)  # No stretch - columns take natural height

        main_layout.addStretch()  # Push buttons to bottom

        # Action buttons - horizontal layout without group box wrapper
        button_row = self._create_action_buttons()
        main_layout.addLayout(button_row)

        # Continue button
        continue_section = self._create_continue_section()
        main_layout.addLayout(continue_section)

        return content

    def _create_status_section(self) -> QWidget:
        """Create the WiFi status section showing current connection state."""
        status_group, status_layout = self.ui_factory.create_group_box(
            "Current WiFi Status"
        )

        # Check current WiFi status
        wifi_connected, network_name = self._check_wifi_connected()

        if wifi_connected:
            self.wifi_status_label = self.ui_factory.create_status_label(
                f"✅ Connected to: {network_name}", status_type="success"
            )
            status_layout.addWidget(self.wifi_status_label)

            # Check internet connectivity
            ntp_reachable, ntp_server = self._check_ntp_reachable()
            if ntp_reachable:
                internet_label = self.ui_factory.create_status_label(
                    f"✅ Internet: Connected (NTP server: {ntp_server})", status_type="success"
                )
            else:
                internet_label = self.ui_factory.create_status_label(
                    "⚠️ Internet: Limited connectivity (NTP servers unreachable)", status_type="warning"
                )
            status_layout.addWidget(internet_label)
        else:
            self.wifi_status_label = self.ui_factory.create_status_label(
                "❌ Not connected to WiFi", status_type="error"
            )
            status_layout.addWidget(self.wifi_status_label)

        return status_group

    def _create_instructions_section(self) -> QWidget:
        """Create the instructions section."""
        instructions_group, instructions_layout = self.ui_factory.create_group_box(
            "Instructions"
        )

        instructions_text = (
            "WiFi is required for automatic time synchronization.\n\n"
            "• Click 'Manual Network Settings' to open system network configuration\n"
            "• Or click 'Skip WiFi Setup' if you will manually set time in the next step"
        )

        instructions_label = self.ui_factory.create_label(instructions_text)
        instructions_layout.addWidget(instructions_label)

        return instructions_group

    def _create_action_buttons(self):
        """Create the action buttons in a horizontal layout."""
        from PySide6.QtWidgets import QHBoxLayout

        button_row = QHBoxLayout()
        button_row.setSpacing(15)

        # Manual network settings button (PRIMARY)
        self.network_settings_button = self.ui_factory.create_action_button(
            "Open Network Settings",
            callback=self._open_network_settings,
            style=ButtonStyle.PRIMARY,
            height=50,
        )
        button_row.addWidget(self.network_settings_button)

        # Skip button
        self.skip_button = self.ui_factory.create_action_button(
            "Skip WiFi Setup (Manual Time)",
            callback=self._skip_wifi_setup,
            style=ButtonStyle.SECONDARY,
            height=50,
        )
        button_row.addWidget(self.skip_button)

        return button_row

    def _create_continue_section(self):
        """Create the continue button section."""
        button_layout, self.continue_button = self.ui_factory.create_continue_button(
            callback=self._on_continue_clicked, text=MESSAGES.UI.CONTINUE
        )
        return button_layout

    def _scan_networks(self, checked: bool = False) -> list[str]:
        """Scan for available WiFi networks."""
        try:
            self.logger.info("Scanning for available WiFi networks")
            self.wifi_status_label.setText("Scanning for networks...")
            self.scan_button.setEnabled(False)

            # Run nmcli to scan networks
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            available_networks = []
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                self.network_display.clear()
                self.network_display.append("📡 Available WiFi Networks:\n")

                seen_ssids = set()
                for line in lines:
                    if line:
                        parts = line.split(":")
                        if len(parts) >= 3:
                            ssid = parts[0].strip()
                            signal = parts[1].strip()
                            security = parts[2].strip()

                            if ssid and ssid not in seen_ssids:
                                seen_ssids.add(ssid)
                                available_networks.append(ssid)

                                # Format with signal strength indicator
                                signal_int = int(signal) if signal.isdigit() else 0
                                signal_bars = "▂▄▆█"[: max(1, signal_int // 25)]
                                security_icon = "🔒" if security else "🔓"

                                self.network_display.append(
                                    f"{security_icon} {ssid:<30} {signal_bars} {signal}% {security if security else '(Open)'}"
                                )

                self.logger.info(f"Found {len(available_networks)} networks")
                self.wifi_status_label.setText(
                    f"✅ Found {len(available_networks)} networks"
                )

                # Store for later use
                self.available_networks = available_networks

                return available_networks
            else:
                self.logger.error(f"Network scan failed: {result.stderr}")
                self.network_display.setText(
                    f"Failed to scan networks: {result.stderr}"
                )
                self.wifi_status_label.setText("❌ Network scan failed")
                return []

        except subprocess.TimeoutExpired:
            self.logger.error("Network scan timeout")
            self.network_display.setText("Network scan timed out")
            self.wifi_status_label.setText("❌ Scan timeout")
            return []
        except Exception as e:
            self.logger.error(f"Error scanning networks: {e}")
            self.network_display.setText(f"Error: {e}")
            self.wifi_status_label.setText("❌ Scan error")
            return []
        finally:
            self.scan_button.setEnabled(True)

    @handle_step_error
    def _open_network_settings(self, checked: bool = False) -> None:
        """Open the system network settings."""
        try:
            self.logger.info("Opening system network settings")

            # Try different network settings commands based on desktop environment
            commands_to_try = [
                ["gnome-control-center", "wifi"],
                ["unity-control-center", "network"],
                ["systemsettings5", "kcm_networkmanagement"],
                ["nm-connection-editor"],
                ["network-manager-gnome"],
            ]

            success = False
            for cmd in commands_to_try:
                try:
                    # Use subprocess.Popen directly to run in background
                    subprocess.Popen(
                        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    success = True
                    self.logger.info(
                        f"Successfully opened network settings using: {' '.join(cmd)}"
                    )
                    break
                except (FileNotFoundError, OSError) as e:
                    self.logger.debug(f"Command {' '.join(cmd)} not found: {e}")
                    continue
                except Exception as e:
                    self.logger.debug(f"Command {' '.join(cmd)} failed: {e}")
                    continue

            if not success:
                # Fallback: show message with manual instructions
                QMessageBox.information(
                    self,
                    "Open Network Settings",
                    "Please open your system's network settings manually to connect to WiFi.\n\n"
                    "Common ways to access network settings:\n"
                    "Click on the network icon in the system tray\n"
                    "Go to System Settings → Network\n"
                    "Search for 'Network' in your application launcher",
                )

        except Exception as e:
            self.logger.error(f"Error opening network settings: {e}")
            QMessageBox.warning(
                self,
                "Error",
                "Could not open network settings automatically. Please open your system's network settings manually to connect to WiFi.",
            )

    @handle_step_error
    def _auto_connect_hotspot(self, checked: bool = False) -> None:
        """Auto-connect to hotspot using the setup_wifi_connection.py script."""
        try:
            self.logger.info("Starting auto-connect to hotspot")

            self.wifi_status_label.setText("Attempting to connect to hotspot...")

            bashrc_path = os.path.expanduser("~/.bashrc")
            self.logger.info(f"Checking for hotspot credentials in: {bashrc_path}")

            # Check which specific hotspots have BOTH SSID and PSK
            existing_hotspots = set()
            if os.path.exists(bashrc_path):
                self.logger.debug(f"Reading {bashrc_path} to check for credentials")
                with open(bashrc_path, "r") as f:
                    content = f.read()
                    for i in range(1, 4):
                        # Check if BOTH SSID and PSK exist
                        if (
                            f"HOTSPOT{i}_SSID" in content
                            and f"HOTSPOT{i}_PSK" in content
                        ):
                            existing_hotspots.add(i)
                            self.logger.info(
                                f"Found complete credentials for HOTSPOT{i}"
                            )

            # Prompt for missing credentials
            hotspot_configs = []
            for i in range(1, 4):
                if i not in existing_hotspots:
                    self.logger.info(f"HOTSPOT{i} credentials missing - prompting user")
                    reply = QMessageBox.question(
                        self,
                        f"Configure HOTSPOT{i}",
                        f"HOTSPOT{i} does not have credentials saved.\n\nDo you want to configure HOTSPOT{i}?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )

                    if reply == QMessageBox.StandardButton.Yes:
                        self.logger.debug(f"User chose to configure HOTSPOT{i}")

                        # Scan networks if not already done
                        if (
                            not hasattr(self, "available_networks")
                            or not self.available_networks
                        ):
                            self.logger.info("Scanning networks for SSID selection")
                            available_networks = self._scan_networks()
                        else:
                            available_networks = self.available_networks

                        # Show SSID selection dialog
                        if available_networks:
                            ssid, ok = QInputDialog.getItem(
                                self,
                                f"HOTSPOT{i} SSID",
                                f"Select the network for HOTSPOT{i}:\n\n"
                                f"If your network is not listed, click Cancel to type it manually.",
                                available_networks,
                                0,
                                False,  # Not editable
                            )

                            # If user cancelled, offer to type manually
                            if not ok:
                                ssid, ok = QInputDialog.getText(
                                    self,
                                    f"HOTSPOT{i} SSID (Manual)",
                                    f"Enter the network name (SSID) for HOTSPOT{i} manually:",
                                    QLineEdit.EchoMode.Normal,
                                )
                        else:
                            # No networks found, use text input
                            ssid, ok = QInputDialog.getText(
                                self,
                                f"HOTSPOT{i} SSID",
                                f"Enter the network name (SSID) for HOTSPOT{i}:",
                                QLineEdit.EchoMode.Normal,
                            )

                        if not ok or not ssid:
                            self.logger.info(
                                f"User cancelled SSID input for HOTSPOT{i}"
                            )
                            continue

                        # Prompt for password
                        password, ok = QInputDialog.getText(
                            self,
                            f"HOTSPOT{i} Password",
                            f"Enter the password for HOTSPOT{i} ({ssid}):",
                            QLineEdit.EchoMode.Normal,
                        )

                        if ok and password:
                            hotspot_configs.append(f"export HOTSPOT{i}_SSID='{ssid}'")
                            hotspot_configs.append(
                                f"export HOTSPOT{i}_PSK='{password}'"
                            )
                            self.logger.info(
                                f"User provided SSID and password for HOTSPOT{i}"
                            )
                        else:
                            self.logger.info(
                                f"User cancelled password input for HOTSPOT{i}"
                            )
                    else:
                        self.logger.debug(f"User skipped configuration for HOTSPOT{i}")

            # Write credentials to .bashrc if any were provided
            if hotspot_configs:
                self.logger.info(
                    f"Writing {len(hotspot_configs)} hotspot credential(s) to .bashrc"
                )
                with open(bashrc_path, "a") as f:
                    f.write("\n# FLASH-TV Hotspot Credentials\n")
                    for config in hotspot_configs:
                        f.write(config + "\n")
                self.logger.info("Successfully saved hotspot credentials to .bashrc")
            elif not existing_hotspots:
                self.logger.warning("No hotspot credentials were provided by user")
                QMessageBox.warning(
                    self,
                    "No Credentials",
                    "No hotspot credentials were configured.\n\nThe WiFi script may not be able to connect.",
                )

            script_path = os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                ),
                "python_scripts",
                "setup_wifi_connection.py",
            )

            self.logger.info(f"WiFi setup script path: {script_path}")

            if not os.path.exists(script_path):
                self.logger.error(f"WiFi setup script not found at: {script_path}")
                raise FileNotFoundError(f"WiFi setup script not found: {script_path}")
            else:
                self.logger.debug(f"WiFi setup script exists at: {script_path}")

            self.logger.info(f"Running WiFi setup script: {script_path}")
            self.logger.info("Executing: python3 " + script_path)

            # Use Popen to stream output in real-time
            # Close stdin to prevent script from blocking on input prompts
            process = subprocess.Popen(
                ["python3", script_path],
                stdin=subprocess.DEVNULL,  # Close stdin to prevent hanging on prompts
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
            )

            # Stream output line by line
            self.logger.info("=== WiFi Script Output (Real-Time) ===")
            output_lines = []
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    self.logger.info(f"  {line}")
                    output_lines.append(line)

                    # Update status label based on script output
                    if "Setting up Hotspot" in line:
                        hotspot_num = line.split("Hotspot")[1].split(":")[0].strip()
                        self.wifi_status_label.setText(
                            f"⚙️ Configuring Hotspot {hotspot_num}..."
                        )
                    elif "Connection attempt cycle" in line:
                        cycle_info = line.split("cycle")[1].strip()
                        self.wifi_status_label.setText(
                            f"🔄 Attempting connection {cycle_info}"
                        )
                    elif "Trying Hotspot" in line:
                        hotspot_num = line.split("Hotspot")[1].split(".")[0].strip()
                        self.wifi_status_label.setText(
                            f"📡 Trying to connect to Hotspot {hotspot_num}..."
                        )
                    elif "Successfully connected" in line:
                        self.wifi_status_label.setText("✅ Successfully connected!")
                    elif (
                        "not available" in line.lower()
                        or "not configured" in line.lower()
                    ):
                        self.wifi_status_label.setText("⏭️ Checking next hotspot...")

            # Wait for completion with timeout
            try:
                returncode = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                self.logger.error("WiFi script timeout - process killed")
                raise

            self.logger.info(
                f"=== WiFi Script Completed with return code: {returncode} ==="
            )

            if returncode == 0:
                self.wifi_status_label.setText("✅ Successfully connected to hotspot!")
                self.logger.info(
                    "WiFi connection successful - script exited with code 0"
                )
                self.state.set_user_input(UserInputKey.WIFI_SSID, "HOTSPOT_CONNECTED")
                self.continue_button.setEnabled(True)
                self.update_status(StepStatus.COMPLETED)

                QMessageBox.information(
                    self,
                    "Connection Successful",
                    "Successfully connected to hotspot!\n\nClick 'Continue' to proceed.",
                )
            else:
                error_msg = (
                    "\n".join(output_lines[-10:])
                    if output_lines
                    else "Unknown error - no output"
                )
                self.logger.error(
                    f"WiFi connection failed with return code {returncode}"
                )
                self.logger.error(f"Last 10 lines of output: {error_msg}")
                self.wifi_status_label.setText("❌ Failed to connect to hotspot")

                reply = QMessageBox.warning(
                    self,
                    "Connection Failed",
                    f"Failed to connect to hotspot.\n\nReturn code: {returncode}\n\nLast output:\n{error_msg}\n\n"
                    "Would you like to try manual network settings instead?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self._open_network_settings()

        except subprocess.TimeoutExpired:
            self.logger.error("WiFi connection timeout")
            self.wifi_status_label.setText("❌ Connection timeout")
            QMessageBox.warning(
                self,
                "Connection Timeout",
                "WiFi connection attempt timed out.\n\nPlease try manual network settings or check your hotspot configuration.",
            )
        except Exception as e:
            self.logger.error(f"Error during auto-connect: {e}")
            self.wifi_status_label.setText("❌ Auto-connect failed")
            QMessageBox.warning(
                self,
                "Auto-Connect Error",
                f"Failed to auto-connect to hotspot: {e}\n\nPlease try manual network settings instead.",
            )

    @handle_step_error
    def _skip_wifi_setup(self, checked: bool = False) -> None:
        """Skip WiFi setup and continue with confirmation."""
        try:
            reply = QMessageBox.question(
                self,
                "Skip WiFi Setup (If You Will Manually Set Time in the Next Step)",
                "Are you sure you want to skip WiFi configuration?\n\nThe device will not be able to sync the time automatically.\nYou will need to set the time manually in the next step.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.logger.info("User chose to skip WiFi setup")

                self.wifi_status_label.setText("WiFi setup skipped")
                self.state.set_user_input(UserInputKey.WIFI_SSID, "SKIPPED")

                # Persist state
                if self.state_manager:
                    self.state_manager.save_state(self.state)

                self.continue_button.setEnabled(True)
                self.update_status(StepStatus.COMPLETED)

        except Exception as e:
            self.logger.error(f"Error skipping WiFi setup: {e}")
            raise FlashTVError(
                f"Failed to skip WiFi setup: {e}",
                ErrorType.UI_ERROR,
                recovery_action="Try clicking skip again",
            )

    def _check_wifi_connected(self) -> tuple[bool, str]:
        """Check if WiFi is connected and get the network name.

        Returns:
            Tuple of (is_connected, network_name)
        """
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "TYPE,NAME,STATE", "connection", "show", "--active"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split(":")
                        if len(parts) >= 3:
                            conn_type = parts[0].strip()
                            conn_name = parts[1].strip()

                            # Check for wireless connection (802-11-wireless or wifi)
                            if "wireless" in conn_type.lower() or "wifi" in conn_type.lower():
                                self.logger.info(f"WiFi connected: {conn_name}")
                                return True, conn_name

                self.logger.info("No active WiFi connection found")
                return False, ""
            else:
                self.logger.warning(f"nmcli command failed: {result.stderr}")
                return False, ""

        except subprocess.TimeoutExpired:
            self.logger.error("WiFi check timed out")
            return False, ""
        except Exception as e:
            self.logger.error(f"Error checking WiFi connection: {e}")
            return False, ""

    def _check_ntp_reachable(self) -> tuple[bool, str]:
        """Check if NTP servers are reachable (indicates working internet for time sync).

        Returns:
            Tuple of (is_reachable, server_name)
        """
        ntp_servers = ["time.google.com", "pool.ntp.org", "time.cloudflare.com"]

        for server in ntp_servers:
            try:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "2", server],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    self.logger.info(f"NTP server reachable: {server}")
                    return True, server

            except subprocess.TimeoutExpired:
                self.logger.debug(f"Ping to {server} timed out")
                continue
            except Exception as e:
                self.logger.debug(f"Error pinging {server}: {e}")
                continue

        self.logger.warning("No NTP servers reachable")
        return False, ""

    @handle_step_error
    def _on_continue_clicked(self, checked: bool = False) -> None:
        """Handle continue button click with WiFi and NTP verification."""
        try:
            # Check if user already skipped WiFi
            wifi_ssid = self.state.get_user_input(UserInputKey.WIFI_SSID, "")
            if wifi_ssid == "SKIPPED":
                self.logger.info("WiFi was skipped, proceeding to next step")
                if self.state_manager:
                    self.state_manager.save_state(self.state)
                self.request_next_step.emit()
                return

            # Update status to show we're checking
            self.wifi_status_label.setText("Checking WiFi connection...")
            self.continue_button.setEnabled(False)

            # Force UI update
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

            # Check WiFi connection
            wifi_connected, network_name = self._check_wifi_connected()

            if not wifi_connected:
                self.wifi_status_label.setText("No WiFi connection detected")
                self.continue_button.setEnabled(True)

                reply = QMessageBox.warning(
                    self,
                    "No WiFi Connection",
                    "No active WiFi connection was detected.\n\n"
                    "Without WiFi, the system cannot automatically sync time.\n"
                    "You will need to set the time manually in the next step.\n\n"
                    "Do you want to continue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self.logger.info("User chose to continue without WiFi")
                    self.state.set_user_input(UserInputKey.WIFI_SSID, "NO_CONNECTION")
                    if self.state_manager:
                        self.state_manager.save_state(self.state)
                    self.request_next_step.emit()
                return

            # WiFi is connected, now check NTP reachability
            self.wifi_status_label.setText(f"Connected to: {network_name}. Checking NTP servers...")
            QApplication.processEvents()

            ntp_reachable, ntp_server = self._check_ntp_reachable()

            if not ntp_reachable:
                self.wifi_status_label.setText(f"Connected to: {network_name} (NTP unreachable)")
                self.continue_button.setEnabled(True)

                reply = QMessageBox.warning(
                    self,
                    "NTP Servers Unreachable",
                    f"Connected to WiFi network: {network_name}\n\n"
                    "However, NTP time servers are not reachable.\n"
                    "This may indicate limited internet connectivity.\n"
                    "Automatic time sync may not work properly.\n\n"
                    "Do you want to continue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self.logger.info("User chose to continue with unreachable NTP")
                    self.state.set_user_input(UserInputKey.WIFI_SSID, network_name)
                    if self.state_manager:
                        self.state_manager.save_state(self.state)
                    self.request_next_step.emit()
                return

            # Everything is good - WiFi connected and NTP reachable
            self.wifi_status_label.setText(f"Connected to: {network_name} (NTP OK)")
            self.logger.info(f"WiFi step completed successfully: {network_name}, NTP: {ntp_server}")

            self.state.set_user_input(UserInputKey.WIFI_SSID, network_name)
            self.update_status(StepStatus.COMPLETED)

            # Persist final state
            if self.state_manager:
                self.state_manager.save_state(self.state)

            self.continue_button.setEnabled(True)
            self.request_next_step.emit()

        except Exception as e:
            self.logger.error(f"Error during continue action: {e}")
            self.continue_button.setEnabled(True)
            raise FlashTVError(
                f"Failed to complete WiFi step: {e}",
                ErrorType.PROCESS_ERROR,
                recovery_action="Check WiFi connection or skip setup",
            )

    @handle_step_error
    def activate_step(self) -> None:
        """Activate the network configuration step."""
        super().activate_step()
        self.logger.info("WiFi connection step activated")

    def update_ui(self) -> None:
        """Update UI elements periodically."""
        super().update_ui()
        # Don't continuously check WiFi - user will click Continue when ready

    def _cleanup_step_resources(self) -> None:
        """Clean up step-specific resources."""
        try:
            if self.state_manager:
                self.state_manager.save_state(self.state)

            self.logger.info("WiFi connection step cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during step cleanup: {e}")
