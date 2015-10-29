import sys
import shlex
import os
import os.path

from urllib.parse import urljoin
from datetime import datetime

from PyQt5.QtWidgets import QApplication, qApp, QWidget, QMainWindow, QMessageBox, QAction, QDesktopWidget, QVBoxLayout, QGridLayout, QLabel, QComboBox, QPushButton, QTextEdit, QDialog, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QIcon, QTextCursor, QWindowStateChangeEvent, QFont
from PyQt5 import QtCore
from PyQt5.QtCore import Qt

from .worker import LivestreamerWorker
from .gui_dialogs import AddEditChannelsDialog, AppConfigDialog
from .constants import *

class MainWindow(QMainWindow):
	"""The main GUI application."""
	def __init__(self, config):
		"""Initializer for the GUI widgets. Pass in an instance of Config class, so that it may interact with the config."""
		super().__init__()

		self.config = config

		self.setWindowTitle("Livestreamer GUI v{}".format(APPVERSION))

		self.setup_systray()
		self.setup_menu()
		self.setup_geometry()

		self.livestreamer_thread = None
		self.thread_exit_grace_time = 10000 # How long a thread can take to exit in milliseconds
		self.timestamp_format = self.config.get_config_value("timestamp-format")

		self.setup_control_widgets()
		self.update_colors()

		# Load all streaming-related data
		self.selections = {"streamer": None, "channel": None}
		self.load_streamers()
		self.load_channels(self.streamer_input.currentText())
		
		# Do the first configuration, if the application was run for the first time
		self.do_init_config()

		# Finally show the window and the system tray icon, if it should be shown
		self.show()

		self.close_override = False
		self.show_hide_systray()

		self.check_and_do_database_migration()

	def do_init_config(self):
		do_config = self.config.get_config_value("is-configured")
		if do_config == 0:
			self.menu_cmd_configure()
			self.config.set_config_value("is-configured", 1)
		self.insertText("Using config database version '{}'".format(self.config.get_config_value("db-version")))

	def setup_systray(self):
		if not self.config.get_config_value("enable-systray-icon"):
			self.systray = None
			return

		self.systray = QSystemTrayIcon(self)
		self.systray.activated.connect(self.systray_activated)
		main_menu = QMenu(self)

		quit_action = QAction("&Quit", self)
		quit_action.triggered.connect(self.on_close_override)
		main_menu.addAction(quit_action)

		self.systray.setContextMenu(main_menu)

	def systray_activated(self, reason):
		if reason == QSystemTrayIcon.Trigger:
			if self.isVisible():
				self.hide()
			else:
				self.showNormal()

	def check_and_do_database_migration(self):
		current_version = self.config.get_config_value("db-version")
		if self.config.is_migration_needed():
			self.insertText("Detected pending config database upgrade to version '{}'. Awaiting user input...".format(DBVERSION))
			message = "You are using an older version of the application config database.\n\nWould you like to upgrade the database now? Your existing config database will be backed up."

			upgrade_is_mandatory = current_version < MANDATORY_DBVERSION

			if upgrade_is_mandatory:
				message = message + "\n\nWARNING: Your config database is not compatible with this version of Livestreamer GUI. UPDATE IS MANDATORY! If you cancel the update, the application will exit."

			reply = QMessageBox.question(self, "Pending config database upgrade", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
			if reply == QMessageBox.Yes:
				self.insertText("Backing up config database...")
				backup = self.config.make_database_backup()
				self.insertText("Current config database backed up to '{}'".format(backup))
				self.insertText("Config database update initialized...")
				self.update()
				self.config.execute_migration()
				new_version = self.config.get_config_value("db-version")
				self.insertText("Config database update from version '{}' to '{}' finished.".format(current_version, new_version))
			elif reply == QMessageBox.No and upgrade_is_mandatory:
				QtCore.QTimer.singleShot(500, self.on_close_override)
				# self.on_close_override() # Calling this in an __init__()-called method doesn't seem to work...
			else:
				self.insertText("Config database update cancelled. No changes were made.")

	def setup_menu(self):
		config_action = QAction("&Configure...", self)
		config_action.triggered.connect(self.menu_cmd_configure)

		quit_action = QAction("&Quit", self)
		quit_action.setShortcut("Ctrl+Q")
		quit_action.triggered.connect(self.on_close_override)

		menu = self.menuBar()
		file_menu = menu.addMenu("&File")
		file_menu.addAction(config_action)
		file_menu.addSeparator()
		file_menu.addAction(quit_action)

	def setup_geometry(self):
		width = self.config.get_config_value("root-width")
		height = self.config.get_config_value("root-height")

		topleft = QApplication.desktop().availableGeometry().topLeft()
		if self.config.get_config_value("remember-window-position"):
			xoffset = self.config.get_config_value("root-xoffset")
			yoffset = self.config.get_config_value("root-yoffset")
			topleft.setX(self.config.get_config_value("root-xoffset"))
			topleft.setY(self.config.get_config_value("root-yoffset"))

		self.resize(width, height)
		self.setMinimumSize(500, 300)
		self.move(topleft)

		# Center the window
		# center_point = QApplication.desktop().availableGeometry().center()
		# frame_geometry = self.frameGeometry()
		# frame_geometry.moveCenter(center_point)
		# self.move(frame_geometry.topLeft())

	def setup_control_widgets(self):
		self.cwidget = QWidget(self)
		self.setCentralWidget(self.cwidget)

		layout = QGridLayout(self.cwidget)
		self.cwidget.setLayout(layout)

		fg_fav = self.config.get_config_value("button-foreground-favorite")
		fg_edit = self.config.get_config_value("button-foreground-edit")
		fg_add = self.config.get_config_value("button-foreground-add")
		fg_delete = self.config.get_config_value("button-foreground-delete")

		control_button_width = 30
		control_button_font_style = "QPushButton { font-family: Arial, sans-serif; font-size: 16px }"

		column = 0
		label_streamer_input = QLabel("Streamer", self.cwidget)
		layout.addWidget(label_streamer_input, 0, column)
		label_channel_input = QLabel("Channel", self.cwidget)
		layout.addWidget(label_channel_input, 1, column)
		label_quality_input = QLabel("Stream quality", self.cwidget)
		layout.addWidget(label_quality_input, 2, column)

		column += 1
		self.streamer_input = QComboBox(self.cwidget)
		self.streamer_input.setEnabled(False)
		self.streamer_input.currentIndexChanged.connect(self.on_streamer_select)
		layout.addWidget(self.streamer_input, 0, column)
		self.channel_input = QComboBox(self.cwidget)
		self.channel_input.setEnabled(False)
		self.channel_input.currentIndexChanged.connect(self.on_channel_select)
		layout.addWidget(self.channel_input, 1, column)
		self.quality_input = QComboBox(self.cwidget)
		self.quality_input.addItem("(auto-refresh is disabled; please refresh manually)")
		self.quality_input.setEnabled(False)
		layout.addWidget(self.quality_input, 2, column)
		layout.setColumnStretch(column, 5)

		column += 1
		self.fav_streamer_button = QPushButton("\u2764", self.cwidget)
		self.fav_streamer_button.setMaximumWidth(control_button_width)
		self.fav_streamer_button.setStyleSheet(":enabled {{ color: {0} }} {1}".format(fg_fav, control_button_font_style))
		self.fav_streamer_button.setEnabled(False)
		self.fav_streamer_button.setToolTip("Set the selected streamer as your most favorite streamer")
		self.fav_streamer_button.clicked.connect(self.cmd_set_favorite_streamer)
		layout.addWidget(self.fav_streamer_button, 0, column)
		self.fav_channel_button = QPushButton("\u2764", self.cwidget)
		self.fav_channel_button.setMaximumWidth(control_button_width)
		self.fav_channel_button.setStyleSheet(':enabled {{ color: {0} }} {1}'.format(fg_fav, control_button_font_style))
		self.fav_channel_button.setEnabled(False)
		self.fav_channel_button.setToolTip("Set the selected channel as your most favorite channel")
		self.fav_channel_button.clicked.connect(self.cmd_set_favorite_channel)
		layout.addWidget(self.fav_channel_button, 1, column)
		self.clear_quality_cache_button = QPushButton("Refresh streams", self.cwidget)
		self.clear_quality_cache_button.setEnabled(False)
		self.clear_quality_cache_button.clicked.connect(self.cmd_refresh_quality_cache)
		layout.addWidget(self.clear_quality_cache_button, 2, column, 1, 4)

		column += 1
		self.edit_streamer_button = QPushButton("\u270E", self.cwidget)
		self.edit_streamer_button.setMaximumWidth(control_button_width)
		self.edit_streamer_button.setStyleSheet(":enabled {{ color: {0} }} {1}".format(fg_edit, control_button_font_style))
		self.edit_streamer_button.setEnabled(False)
		self.edit_streamer_button.setToolTip("Edit data about the selected streamer")
		self.edit_streamer_button.clicked.connect(self.cmd_edit_streamer)
		layout.addWidget(self.edit_streamer_button, 0, column)
		self.edit_channel_button = QPushButton("\u270E", self.cwidget)
		self.edit_channel_button.setMaximumWidth(control_button_width)
		self.edit_channel_button.setStyleSheet(":enabled {{ color: {0} }} {1}".format(fg_edit, control_button_font_style))
		self.edit_channel_button.setToolTip("Edit data about the selected channel")
		self.edit_channel_button.clicked.connect(self.cmd_edit_channel)
		layout.addWidget(self.edit_channel_button, 1, column)

		column += 1
		self.add_streamer_button = QPushButton("\u271A", self.cwidget)
		self.add_streamer_button.setMaximumWidth(control_button_width)
		self.add_streamer_button.setStyleSheet(":enabled {{ color: {0} }} {1}".format(fg_add, control_button_font_style))
		self.add_streamer_button.setEnabled(False)
		self.add_streamer_button.setToolTip("Add a new streamer")
		self.add_streamer_button.clicked.connect(self.cmd_add_streamer)
		layout.addWidget(self.add_streamer_button, 0, column)
		self.add_channel_button = QPushButton("\u271A", self.cwidget)
		self.add_channel_button.setMaximumWidth(control_button_width)
		self.add_channel_button.setStyleSheet(":enabled {{ color: {0} }} {1}".format(fg_add, control_button_font_style))
		self.add_channel_button.setToolTip("Add a new channel")
		self.add_channel_button.clicked.connect(self.cmd_add_channel)
		layout.addWidget(self.add_channel_button, 1, column)

		column += 1
		self.delete_streamer_button = QPushButton("\u2716", self.cwidget)
		self.delete_streamer_button.setMaximumWidth(control_button_width)
		self.delete_streamer_button.setStyleSheet(":enabled {{ color: {0} }} {1}".format(fg_delete, control_button_font_style))
		self.delete_streamer_button.setEnabled(False)
		self.delete_streamer_button.setToolTip("Remove the selected streamer permanently")
		self.delete_streamer_button.clicked.connect(self.cmd_delete_streamer)
		layout.addWidget(self.delete_streamer_button, 0, column)
		self.delete_channel_button = QPushButton("\u2716", self.cwidget)
		self.delete_channel_button.setMaximumWidth(control_button_width)
		self.delete_channel_button.setStyleSheet(":enabled {{ color: {0} }} {1}".format(fg_delete, control_button_font_style))
		self.delete_channel_button.setToolTip("Remove the selected channel permanently")
		self.delete_channel_button.clicked.connect(self.cmd_delete_channel)
		layout.addWidget(self.delete_channel_button, 1, column)

		# Add button for running livestreamer at the fourth row
		self.run_livestreamer_button = QPushButton("Run Livestreamer", self.cwidget)
		self.run_livestreamer_button.setEnabled(False)
		self.run_livestreamer_button.clicked.connect(self.run_livestreamer)
		layout.addWidget(self.run_livestreamer_button, 3, 0)

		self.log_widget = QTextEdit(self.cwidget)
		layout.addWidget(self.log_widget, 4, 0, 1, column+1)
		self.log_widget.setAcceptRichText(False)
		self.log_widget.setReadOnly(True)
		self.log_widget.setTabChangesFocus(True)

	def set_window_icon(self):
		"""Sets the root window's icon, which is also shown in the taskbar."""
		streamer = self.config.get_streamer(self.streamer_input.currentText())
		icon = QIcon(os.path.join(IMAGESROOT, streamer["icon"]))
		self.setWindowIcon(icon)

		if self.systray is not None:
			self.systray.setIcon(icon)

	def closeEvent(self, event):
		"""When the QWidget is closed, QCloseEvent is triggered, and this method catches and handles it."""
		if not self.close_override and self.put_to_systray("close"):
			event.ignore()
			return

		if self.livestreamer_thread is not None and self.livestreamer_thread.keep_running:
			reply = QMessageBox.question(self, "Really quit Livestreamer GUI?", "Livestreamer is still running. Quitting will close it and the opened player.\n\nQuit?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
			if reply == QMessageBox.Yes:
				# Terminate the child process, else it'll keep running even after this application is closed
				if self.livestreamer_thread is not None:
					self.livestreamer_thread.term_process()
					self.livestreamer_thread.wait(self.thread_exit_grace_time)
					self.update()
				event.accept()
			else:
				event.ignore()

		# Explicitly hide the icon, if it remains visible after the application closes
		if self.systray is not None:
			self.systray.hide()

		# Remember the position of the window
		self.remember_window_position()

		event.accept()

	def changeEvent(self, event):
		if type(event) is not QWindowStateChangeEvent:
			return

		# It's one of the window state change events (normal, minimize, maximize, fullscreen, active)
		if self.isMinimized():
			self.put_to_systray("minimize")

	def remember_window_position(self):
		if self.config.get_config_value("remember-window-position"):
			point = self.frameGeometry().topLeft()
			self.config.set_config_value("root-xoffset", point.x())
			self.config.set_config_value("root-yoffset", point.y())
			self.insertText("Window position saved.")

	def show_hide_systray(self):
		if self.systray is None:
			self.setup_systray()
			if self.systray is None:
				return

		if self.config.get_config_value("enable-systray-icon"):
			self.systray.show()
		else:
			self.systray.hide()

	def put_to_systray(self, event):
		if event == "minimize":
			config_value = "minimize-to-systray"
		elif event == "close":
			config_value = "close-to-systray"
		else:
			return False

		if self.systray is not None and self.config.get_config_value(config_value) and self.isVisible():
			self.hide()
			return True
		return False

	def menu_cmd_configure(self):
		streamer = self.config.get_streamer(self.streamer_input.currentText())
		dialog = AppConfigDialog(self, self.config, streamer_icon=os.path.join(IMAGESROOT, streamer["icon"]))
		dialog.exec()
		if dialog.result() == QDialog.Accepted:
			self.show_hide_systray()
			self.update_colors()
		dialog.close()
		dialog = None

	def cmd_set_favorite_streamer(self):
		raise NotImplementedException()
		# self.fav_streamer_button.setEnabled(False)
		# self.config.set_favorite_streamer(self.streamer_input.setCurrentText())
		# self.insertText("Favorited streamer '{}'.".format(self.streamer_input.setCurrentText()))

	def cmd_edit_streamer(self):
		raise NotImplementedException()

	def cmd_add_streamer(self):
		raise NotImplementedException()

	def cmd_delete_streamer(self):
		raise NotImplementedException()

	def cmd_set_favorite_channel(self):
		self.fav_channel_button.setEnabled(False)
		self.config.set_favorite_channel(self.streamer_input.currentText(), self.channel_input.currentText())
		self.insertText("Favorited channel '{}'.".format(self.channel_input.currentText()))

	def cmd_edit_channel(self):
		streamer = self.config.get_streamer(self.streamer_input.currentText())
		streamer_icon = os.path.join(IMAGESROOT, streamer["icon"])
		channel_data = self.config.get_streamer_channel(streamer["name"], self.channel_input.currentText())
		dialog = AddEditChannelsDialog(self, self.config, title="Edit the channel", streamer_icon=streamer_icon, streamer=streamer, channel_data=channel_data)
		dialog.exec()
		result = dialog.result_data
		dialog.close()
		dialog = None
		if result is not None:
			self.insertText("Updated channel name '{old_name}' => '{new_name}, URL '{old_url}' => '{new_url}'".format(old_name=channel_data["name"], new_name=result["name"], old_url=channel_data["url"], new_url=result["url"]))
			self.load_channels(streamer["name"])
			
			# Set the active channel to the previously selected (due to possible name change and sorting)
			self.channel_input.setCurrentIndex(self.channel_input.findText(result["name"]))
			
	def cmd_add_channel(self):
		streamer = self.config.get_streamer(self.streamer_input.currentText())
		streamer_icon = os.path.join(IMAGESROOT, streamer["icon"])
		dialog = AddEditChannelsDialog(self, self.config, title="Add a channel", streamer_icon=streamer_icon, streamer=streamer)
		dialog.exec()
		result = dialog.result_data
		dialog.close()
		dialog = None
		if result is not None:
			self.insertText("Added channel '{}' with URL '{}'".format(result["name"], result["url"]))
			self.load_channels(streamer["name"])

	def cmd_delete_channel(self):
		channel = self.config.get_streamer_channel(self.streamer_input.currentText(), self.channel_input.currentText())
		reply = QMessageBox.question(self, "Delete channel", "Are you sure you want to remove the channel?\nName: {}\nURL: {}".format(channel["name"], channel["url"]), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
		if reply == QMessageBox.Yes:
			self.config.delete_channel(self.streamer_input.currentText(), channel["name"])
			self.insertText("Removed channel '{}' with URL '{}'".format(channel["name"], channel["url"]))
			self.load_channels(self.streamer_input.currentText())

	def cmd_refresh_quality_cache(self):
		self.insertText("Refreshing cache for channel '{}'.".format(self.channel_input.currentText()))
		self.clear_quality_cache_button.setEnabled(False)
		self.clear_quality_cache_button.repaint() # Loading streams seems to block repainting of the GUI, so force a repaint here
		self.config.clean_quality_cache(self.streamer_input.currentText(), self.channel_input.currentText(), True)
		self.load_streams(True)
		self.clear_quality_cache_button.setEnabled(True)

	def on_close_override(self):
		self.close_override = True
		self.close()

	def on_streamer_select(self, event):
		# If the previously selected item is selected again, don't do anything
		if self.selections["streamer"] == self.streamer_input.currentText():
			return
		self.selections["streamer"] = self.streamer_input.currentText()
		streamer = self.config.get_streamer(self.streamer_input.currentText())
		self.set_window_icon()
		if streamer["favorite"]:
			self.fav_streamer_button.setEnabled(False)
		else:
			self.fav_streamer_button.setEnabled(True)

	def on_channel_select(self, event):
		# If the previously selected item is selected again, don't do anything
		if self.selections["channel"] == self.channel_input.currentText() or not self.channel_input.currentText():
			return
		self.selections["channel"] = self.channel_input.currentText()
		channel = self.config.get_streamer_channel(self.streamer_input.currentText(), self.channel_input.currentText())
		if channel and channel["favorite"]:
			self.fav_channel_button.setEnabled(False)
		else:
			self.fav_channel_button.setEnabled(True)

		self.load_streams()
		self.channel_input.setFocus(True)

	def load_streamers(self):
		streamers = self.config.get_streamers()
		favorite_streamer_index = 0
		streamer_list = []
		for index, streamer in enumerate(streamers):
			streamer_list.append(streamer["name"])
			if streamer["favorite"]:
				favorite_streamer_index = index
		self.streamer_input.clear()
		self.streamer_input.addItems(streamer_list)
		if len(streamer_list) != 0:
			self.streamer_input.setCurrentIndex(favorite_streamer_index)
		self.selections["streamer"] = self.streamer_input.currentText()
		self.fav_streamer_button.setEnabled(False)

	def load_channels(self, streamer_name):
		channels = self.config.get_streamer_channels(streamer_name)
		self.channel_input.clear()
		favorite_channel = None
		channel_list = []
		self.fav_channel_button.setEnabled(False)
		for index, channel in enumerate(channels):
			channel_list.append(channel["name"])
			if channel["favorite"]:
				favorite_channel = channel["name"]
		self.channel_input.addItems(sorted(channel_list))
		if len(channel_list) == 0:
			self.channel_input.addItem("(no channels exist for this streamer)")
			self.fav_channel_button.setEnabled(False)
			self.edit_channel_button.setEnabled(False)
			self.delete_channel_button.setEnabled(False)
			self.clear_quality_cache_button.setEnabled(False)
			self.channel_input.setEnabled(False)
		else:
			self.edit_channel_button.setEnabled(True)
			self.delete_channel_button.setEnabled(True)
			self.clear_quality_cache_button.setEnabled(True)
			self.channel_input.setEnabled(True)
			
			if favorite_channel is None:
				self.channel_input.setCurrentIndex(0)
				self.fav_channel_button.setEnabled(True)
			else:
				self.channel_input.setCurrentIndex(self.channel_input.findText(favorite_channel))

		self.selections["channel"] = self.channel_input.currentText()

	def display_loaded_streams(self, streams, skip_caching=False):
		self.quality_input.clear()
		if len(streams) == 0:
			self.quality_input.addItem("(channel is currently not streaming)")
		else:
			self.run_livestreamer_button.setEnabled(True)
			self.clear_quality_cache_button.setEnabled(True)
			self.quality_input.addItems(sorted(streams))
			self.quality_input.setCurrentIndex(0)
			self.quality_input.setEnabled(True)
			if not skip_caching:
				self.insertText("Cleaning any cached streams for channel '{}'...".format(self.channel_input.currentText()))
				self.config.clean_quality_cache(self.streamer_input.currentText(), self.channel_input.currentText())
				self.insertText("Adding probed streams for channel '{}' to cache...".format(self.channel_input.currentText()))
				self.config.add_quality_to_cache(self.streamer_input.currentText(), self.channel_input.currentText(), streams)
				self.insertText("Done.")

	def load_streams(self, force_refresh=False):
		self.quality_input.clear()
		self.run_livestreamer_button.setEnabled(False)
		self.channel_input.setEnabled(False)
		self.quality_input.setEnabled(False)

		if self.channel_input.count() == 0:
			return

		streams = self.config.get_quality_from_cache(self.streamer_input.currentText(), self.channel_input.currentText())
		if len(streams) > 0:
			self.display_loaded_streams(streams, True)
			self.insertText("Loaded streams for channel '{}' from cache.".format(self.channel_input.currentText()))
		else:
			self.insertText("No cached channel streams found for channel '{}'".format(self.channel_input.currentText()))
			if not force_refresh and self.config.get_config_value('auto-refresh-quality') == 0:
				self.quality_input.addItem("(auto-refresh is disabled; please refresh manually)")
				self.quality_input.setEnabled(False)
			else:
				stream_url = self.get_streamer_url()
				if stream_url is None:
					self.insertText("Failed to form a complete streamer URL (missing streamer/channel/stream)!")
					return
				self.probe_for_streams(stream_url)
		
		self.channel_input.setEnabled(True)

	def probe_for_streams(self, stream_url):
		self.insertText("Probing streamer's channel for live streams: {}".format(stream_url))
		livestreamer = self.config.get_config_value("livestreamer-path")
		if livestreamer is None or livestreamer.strip() == "" or not os.path.isfile(livestreamer):
			self.insertText("Livestreamer path is not configured or file doesn't exist!")
			return
		command_format = self.config.get_config_value("probe-command-format")
		command = command_format.format(livestreamer=livestreamer, url=stream_url)
		self.livestreamer_thread = LivestreamerWorker(shlex.split(command))
		self.livestreamer_thread.statusMessage.connect(self.parse_probed_streams, False)
		self.livestreamer_thread.start()
		self.livestreamer_thread.wait(self.thread_exit_grace_time)

	def parse_probed_streams(self, event):
		streams = []

		message = event.message.lower()
		if "no streams found on this url" in message:
			self.insertText("No streams found. The channel is probably not streaming.")
		else:
			pos = message.find("available streams:")
			if pos == -1:
				return

			if "(best, worst)" in message:
				message = message.replace("(best, worst)", "(best and worst)")
			elif "(worst, best)" in message:
				message = message.replace("(worst, best)", "(worst and best)")
			qualities = message[pos+18:].split(",")
			for item in qualities:
				streams.append(item.strip())
				left_parenthesis = item.find("(")
				if left_parenthesis == -1:
					continue
				if item.find("worst", left_parenthesis) >= left_parenthesis:
					streams.append("worst")
				if item.find("best", left_parenthesis) >= left_parenthesis:
					streams.append("best")
			streams.sort()
			self.insertText("Found {} stream(s): {}".format(len(streams), ", ".join(streams)))

		self.display_loaded_streams(streams)

	def get_streamer_url(self):
		streamer = self.config.get_streamer(self.streamer_input.currentText())
		if streamer is None:
			self.insertText("No streamer selected!")
			return
		if streamer["url"] is None or streamer["url"].strip() == "":
			self.insertText("Invalid streamer URL!")
			return
		if self.channel_input.count() == 0:
			self.insertText("No channels exist!")
			return
		channel = self.config.get_streamer_channel(streamer["name"], self.channel_input.currentText())
		return urljoin(streamer["url"], channel["url"])

	def run_livestreamer(self):
		if self.livestreamer_thread is not None:
			if self.livestreamer_thread.isRunning():
				self.insertText("Livestreamer should still be running!")
				return
			else:
				self.livestreamer_thread.wait(self.thread_exit_grace_time)
				self.livestreamer_thread = None
				self.update()

		if self.livestreamer_thread is None:
			livestreamer = self.config.get_config_value("livestreamer-path")
			if livestreamer is None or livestreamer.strip() == "" or not os.path.isfile(livestreamer):
				self.insertText("Livestreamer path is not configured or file doesn't exist!")
				return
			player = self.config.get_config_value("player-path")
			if player is None or player.strip() == "" or not os.path.isfile(player):
				self.insertText("Player path is not configured or file doesn't exist!")
				return
			stream_url = self.get_streamer_url()
			if stream_url is None:
				self.insertText("Failed to form a complete streamer URL (missing streamer/channel/stream)!")
				return
			command_format = self.config.get_config_value("command-format")
			quality = self.quality_input.currentText()
			if "(" in quality:
				quality = quality[:quality.find("(")].strip()
			command = command_format.format(livestreamer=livestreamer, player=player, url=stream_url, quality=quality)
			self.livestreamer_thread = LivestreamerWorker(shlex.split(command))
			self.insertText("Starting Livestreamer thread.")
			self.livestreamer_thread.finished.connect(self.handle_livestreamer_thread_finished_signal)
			self.livestreamer_thread.statusMessage.connect(self.handle_livestreamer_thread_message_signal)
			self.livestreamer_thread.start()

	@QtCore.pyqtSlot(object)
	def handle_livestreamer_thread_message_signal(self, event):
		self.insertText(event.message, event.add_newline, event.add_timestamp)

	def handle_livestreamer_thread_finished_signal(self):
		self.livestreamer_thread = None

	def update_colors(self):
		foreground_color = self.config.get_config_value("foreground-color")
		background_color = self.config.get_config_value("background-color")
		self.cwidget.setStyleSheet("QWidget QLabel {{ color: {0} }} .QWidget {{ background-color: {1} }}".format(foreground_color, background_color))
		self.cwidget.update()

	def insertText(self, msg, add_newline=True, timestamp=True):
		"""Helper method for outputting text to the text box."""
		text = ""
		if timestamp and self.timestamp_format is not None:
			timestamp = format(datetime.now().strftime(self.timestamp_format))
			text = "{} ".format(timestamp)
		text += msg
		self.log_widget.moveCursor(QTextCursor.End)
		self.log_widget.insertPlainText(text)
		if add_newline:
			self.log_widget.insertPlainText("\n")
		self.log_widget.update()
