import sys
import os.path
import platform

from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QCheckBox, QPushButton, QMessageBox, QFileDialog, QColorDialog, QSpinBox, QTableWidget
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import QRegExp, Qt

class BaseDialog(QDialog):
	"""The base class of all our config windows. All common setup should be done in here."""
	def __init__(self, parent, config, modal=True, streamer_icon=None, title=None, geometry=None, resizable=False):
		super().__init__(parent)
		self.parent = parent				# The parent object (probably an instance of QMainWindow)
		self.config = config				# Config database's connection
		self.modal = modal					# If modal, the focus will be held by this window
		self.streamer_icon = streamer_icon	# Path to the icon for this window
		self.window_geometry = geometry
		self.is_resizable = resizable

		self.result_data = None	 # For use if a dialog needs to return something back to the caller

		self.setWindowTitle(title)
		self.setModal(self.modal)
		self.setup_window_icon()
		self.setup_layout()
		self.setup_geometry()
		self.setup_dialog_layout()

		if self.is_resizable:
			self.setSizeGripEnabled(False)

		self.rejected.connect(self.closeEvent)

		self.made_changes = False

	def setup_geometry(self):
		if self.window_geometry:
			if self.is_resizable:
				self.setGeometry(self.window_geometry[0], self.window_geometry[1])
				self.setMinimumSize(self.window_geometry[0], self.window_geometry[1])
			else:
				self.setFixedSize(self.window_geometry[0], self.window_geometry[1])

		center_point = QApplication.desktop().availableGeometry().center()
		frame_geometry = self.frameGeometry()
		frame_geometry.moveCenter(center_point)
		self.move(frame_geometry.topLeft())
		
	def setup_window_icon(self):
		# Set the same window icon as the parent
		if self.streamer_icon is not None:
			self.setWindowIcon(QIcon(self.streamer_icon))

	def setup_layout(self):
		self.layout = QGridLayout(self)
		self.setLayout(self.layout)

	def update_colors(self, fg_override=None, bg_override=None):
		"""This applies the foreground color to all the widgets in the list. This method is not called in this base class."""
		if fg_override is not None:
			foreground_color = fg_override
		else:
			foreground_color = self.config.get_config_value("foreground-color")
		if bg_override is not None:
			background_color = bg_override
		else:
			background_color = self.config.get_config_value("background-color")
		self.setStyleSheet("QDialog QLabel {{ color: {0} }} QDialog {{ background: {1} }}".format(foreground_color, background_color))
		self.update()

	def save_changes(self):
		raise NotImplementedException("Implement me!")

	def closeEvent(self, event=None):
		if self.made_changes:
			reply = QMessageBox(self, "Save changes?", "Save changes before dialog closes?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
			if reply == QMessageBox.Yes:
				self.save_changes()


class AppConfigDialog(BaseDialog):
	"""The window with application's global configuration settings."""

	cache_max_value = 999999

	def __init__(self, parent, config, modal=True, streamer_icon=None, title=None):
		super().__init__(parent, config, modal=modal, streamer_icon=streamer_icon, title="Application configuration", geometry=(500, 260))
		if self.config.get_config_value("db-version") >= 2:
			self.window_geometry = (500, 320)
			self.setup_geometry()

		self.original_values = {}

		self.load_config_values()
		self.update_colors()

	def setup_dialog_layout(self):
		row = 0
		label_livestreamer = QLabel("Livestreamer path", self)
		self.layout.addWidget(label_livestreamer, row, 0)
		self.input_livestreamer = QLineEdit(self)
		self.input_livestreamer.setReadOnly(True)
		self.layout.addWidget(self.input_livestreamer, row, 1)
		button_livestreamer = QPushButton("Browse...", self)
		button_livestreamer.clicked.connect(self.on_livestreamer_click)
		self.layout.addWidget(button_livestreamer, row, 2)

		row += 1
		label_player = QLabel("Player path", self)
		self.layout.addWidget(label_player, row, 0)
		self.input_player = QLineEdit(self)
		self.input_player.setReadOnly(True)
		self.layout.addWidget(self.input_player, row, 1)
		button_player = QPushButton("Browse...", self)
		button_player.clicked.connect(self.on_player_click)
		self.layout.addWidget(button_player, row, 2)

		row += 1
		label_fgcolor = QLabel("Foreground color", self)
		self.layout.addWidget(label_fgcolor, row, 0)
		self.input_fgcolor = QLineEdit(self)
		self.input_fgcolor.setReadOnly(True)
		self.layout.addWidget(self.input_fgcolor, row, 1)
		button_fgcolor = QPushButton("Pick...", self)
		button_fgcolor.clicked.connect(self.on_fgcolor_click)
		self.layout.addWidget(button_fgcolor, row, 2)

		row += 1
		label_bgcolor = QLabel("Background color", self)
		self.layout.addWidget(label_bgcolor)
		self.input_bgcolor = QLineEdit(self)
		self.input_bgcolor.setReadOnly(True)
		self.layout.addWidget(self.input_bgcolor)
		button_bgcolor = QPushButton("Pick...", self)
		button_bgcolor.clicked.connect(self.on_bgcolor_click)
		self.layout.addWidget(button_bgcolor)

		row += 1
		label_check_auto_refresh = QLabel("Stream quality auto-refresh", self)
		self.layout.addWidget(label_check_auto_refresh, row, 0)
		self.check_auto_refresh = QCheckBox(self)
		self.check_auto_refresh.setTristate(False)
		self.layout.addWidget(self.check_auto_refresh, row, 1)

		row += 1
		label_cache_lifetime = QLabel("Stream quality cache\nlifetime (in minutes)", self)
		self.layout.addWidget(label_cache_lifetime, row, 0)
		self.input_cache_lifetime = QSpinBox(self)
		self.input_cache_lifetime.setRange(0, self.cache_max_value)
		self.input_cache_lifetime.setSuffix(" minute(s)")
		self.layout.addWidget(self.input_cache_lifetime, row, 1)

		if self.config.get_config_value("db-version") >= 2:
			row += 1
			label_enable_systray_icon = QLabel("Enable system tray icon", self)
			self.layout.addWidget(label_enable_systray_icon, row, 0)
			self.check_enable_systray_icon = QCheckBox(self)
			self.check_enable_systray_icon.setTristate(False)
			self.layout.addWidget(self.check_enable_systray_icon, row, 1)

			row += 1
			label_minimize_to_systray = QLabel("Minimize to system tray", self)
			self.layout.addWidget(label_minimize_to_systray, row, 0)
			self.check_minimize_to_systray = QCheckBox(self)
			self.check_minimize_to_systray.setTristate(False)
			self.layout.addWidget(self.check_minimize_to_systray, row, 1)

			row += 1
			label_close_to_systray = QLabel("Close to system tray", self)
			self.layout.addWidget(label_close_to_systray, row, 0)
			self.check_close_to_systray = QCheckBox(self)
			self.check_close_to_systray.setTristate(False)
			self.layout.addWidget(self.check_close_to_systray, row, 1)

		if self.config.get_config_value("db-version") >= 3:
			row += 1
			label_remember_position = QLabel("Remember window position", self)
			self.layout.addWidget(label_remember_position, row, 0)
			self.check_remember_position = QCheckBox(self)
			self.check_remember_position.setTristate(False)
			self.layout.addWidget(self.check_remember_position, row, 1)

		row += 1
		button_close = QPushButton("Save && close", self)
		button_close.clicked.connect(self.save_changes_and_close)
		self.layout.addWidget(button_close, row, 2)

	def closeEvent(self, event=None):
		# if Esc key was pressed, the event is None (and the method gets called the second time, with populated event)
		if event is None:
			return
		
		if self.changes_made():
			reply = QMessageBox.question(self, "Save changes?", "The dialog will close. Save changes?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
			if reply == QMessageBox.Yes:
				self.save_changes()

	def load_config_values(self, update_widgets=True):
		self.original_values = {
			"input_livestreamer": self.config.get_config_value("livestreamer-path"),
			"input_player": self.config.get_config_value("player-path"),
			"input_fgcolor": self.config.get_config_value("foreground-color"),
			"input_bgcolor": self.config.get_config_value("background-color"),
			"check_auto_refresh": bool(self.config.get_config_value("auto-refresh-quality")),
			"input_cache_lifetime": int(self.config.get_config_value("quality-cache-persistance")),
		}

		if self.config.get_config_value("db-version") >= 2:
			self.original_values["check_enable_systray_icon"] = bool(self.config.get_config_value("enable-systray-icon"))
			self.original_values["check_minimize_to_systray"] = bool(self.config.get_config_value("minimize-to-systray"))
			self.original_values["check_close_to_systray"] = bool(self.config.get_config_value("close-to-systray"))
		if self.config.get_config_value("db-version") >= 3:
			self.original_values["check_remember_position"] = bool(self.config.get_config_value("remember-window-position"))

		if not update_widgets:
			return

		self.input_livestreamer.setText(self.original_values["input_livestreamer"])
		self.input_player.setText(self.original_values["input_player"])
		self.input_fgcolor.setText(self.original_values["input_fgcolor"])
		self.input_bgcolor.setText(self.original_values["input_bgcolor"])
		self.check_auto_refresh.setChecked(self.original_values["check_auto_refresh"])
		self.input_cache_lifetime.setValue(self.original_values["input_cache_lifetime"])

		if self.config.get_config_value("db-version") >= 2:
			self.check_enable_systray_icon.setChecked(self.original_values["check_enable_systray_icon"])
			self.check_minimize_to_systray.setChecked(self.original_values["check_minimize_to_systray"])
			self.check_close_to_systray.setChecked(self.original_values["check_close_to_systray"])
		if self.config.get_config_value("db-version") >= 3:
			self.check_remember_position.setChecked(self.original_values["check_remember_position"])

	def changes_made(self):
		base = self.original_values["input_livestreamer"] != self.input_livestreamer.text() \
			or self.original_values["input_player"] != self.input_player.text() \
			or self.original_values["input_fgcolor"] != self.input_fgcolor.text() \
			or self.original_values["input_bgcolor"] != self.input_bgcolor.text() \
			or self.original_values["check_auto_refresh"] != self.check_auto_refresh.isChecked() \
			or self.original_values["input_cache_lifetime"] != self.input_cache_lifetime.value()

		extended = base
		if self.config.get_config_value("db-version") >= 2:
			extended = extended \
				or self.original_values["check_enable_systray_icon"] != self.check_enable_systray_icon.isChecked() \
				or self.original_values["check_minimize_to_systray"] != self.check_minimize_to_systray.isChecked() \
				or self.original_values["check_close_to_systray"] != self.check_close_to_systray.isChecked()
		if self.config.get_config_value("db-version") >= 3:
			extended = extended \
				or self.original_values["check_remember_position"] != self.check_remember_position.isChecked()

		return extended

	def save_changes(self):
		self.config.set_config_value("livestreamer-path", self.input_livestreamer.text())
		self.config.set_config_value("player-path", self.input_player.text())
		self.config.set_config_value("foreground-color", self.input_fgcolor.text())
		self.config.set_config_value("background-color", self.input_bgcolor.text())
		self.config.set_config_value("auto-refresh-quality", int(self.check_auto_refresh.isChecked()))
		self.config.set_config_value("quality-cache-persistance", int(self.input_cache_lifetime.value()))
		
		if self.config.get_config_value("db-version") >= 2:
			self.config.set_config_value("enable-systray-icon", int(self.check_enable_systray_icon.isChecked()))
			self.config.set_config_value("minimize-to-systray", int(self.check_minimize_to_systray.isChecked()))
			self.config.set_config_value("close-to-systray", int(self.check_close_to_systray.isChecked()))
		if self.config.get_config_value("db-version") >= 3:
			self.config.set_config_value("remember-window-position", int(self.check_remember_position.isChecked()))

		self.load_config_values(update_widgets=False)

	def save_changes_and_close(self):
		if self.changes_made():
			self.save_changes()
		self.accept()

	def get_filename_from_dialog(self, existing_path, dialog_caption):
		if os.path.exists(existing_path):
			existing_path = os.path.dirname(existing_path) # assume the path always points to a file
		else:
			existing_path = os.path.dirname(sys.argv[0])

		file_filters = []
		if platform.system().lower() == "windows":
			file_filters.append("Windows executables (*.exe *.bat)")
		file_filters.append("All files (*.*)")

		path, selected_filter = QFileDialog.getOpenFileName(self, dialog_caption, existing_path, ';;'.join(file_filters))
		return path

	def on_livestreamer_click(self):
		existing_path = self.input_livestreamer.text()
		path = self.get_filename_from_dialog(existing_path, "Select livestreamer executable")
		
		if path and os.path.isfile(path):
			
			self.input_livestreamer.setText(path)

	def on_player_click(self):
		existing_path = self.input_player.text()
		path = self.get_filename_from_dialog(existing_path, "Select VLC player executable")
		if path and os.path.isfile(path):
			
			self.input_player.setText(path)

	def on_fgcolor_click(self):
		initial = self.input_fgcolor.text()
		color = QColorDialog.getColor(QColor(initial), self, "Choose foreground color")
		if color.isValid():
			
			self.input_fgcolor.setText(color.name())
			self.update_colors(fg_override=color.name(), bg_override=self.input_bgcolor.text())
			
	def on_bgcolor_click(self):
		initial = self.input_bgcolor.text()
		color = QColorDialog.getColor(QColor(initial), self, "Choose background color")
		if color.isValid():
			
			self.input_bgcolor.setText(color.name())
			self.update_colors(fg_override=self.input_fgcolor.text(), bg_override=color.name())


class AddEditChannelsDialog(BaseDialog):

	entry_max_size = 255

	"""The window for adding or editing streamer's channels."""
	def __init__(self, parent, config, title=None, modal=True, streamer_icon=None, streamer=None, channel_data=None):
		if streamer is None:
			raise Exception("No streamer defined!")
		self.streamer = streamer
		self.channel_data = channel_data

		super().__init__(parent, config, modal=modal, streamer_icon=streamer_icon, title=title, geometry=(400, 150))

	def setup_dialog_layout(self):
		row = 0
		label_name = QLabel("Channel name", self)
		self.layout.addWidget(label_name, row, 0)
		self.input_name = QLineEdit(self)
		self.input_name.setMaxLength(self.entry_max_size)
		self.input_name.setToolTip("Name the channel for your reference, e.g. Kitchen cats")
		self.layout.addWidget(self.input_name, row, 1)

		row += 1
		label_url = QLabel("Relative URL", self)
		self.layout.addWidget(label_url, row, 0)
		self.input_url = QLineEdit(self)
		self.input_url.setMaxLength(self.entry_max_size)
		self.input_url.setToolTip("URL path to the channel relative to the streamer, e.g. kitchencatschannel\nfor twitch.tv. When livestreamer is run, the resulting URL is composed\ninto http://www.twitch.tv/kitchencatschannel, where kitchencatschannel\nis the value entered into this edit box.")
		self.layout.addWidget(self.input_url, row, 1)

		row += 1
		label_check = QLabel("Is favorite channel", self)
		self.layout.addWidget(label_check, row, 0)
		self.check_fav = QCheckBox(self)
		self.check_fav.setTristate(False)
		self.check_fav.setToolTip("Mark this channel as your most favorite channel")
		self.layout.addWidget(self.check_fav, row, 1)

		row += 1
		self.button_save = QPushButton("Save && close", self)
		self.button_save.clicked.connect(self.save_changes)
		self.layout.addWidget(self.button_save, row, 0)

		# Apply the foreground and background color to the widgets
		self.update_colors()

		# Load the data, if provided, into the entry widgets
		if self.channel_data is not None:
			self.input_name.setText(self.channel_data["name"])
			self.input_url.setText(self.channel_data["url"])
			self.check_fav.setChecked(bool(self.channel_data["favorite"]))

	def save_changes(self):
		channel_name = self.input_name.text().strip()
		channel_url = self.input_url.text().strip()
		if channel_name == "":
			self.input_name.setFocus(True)
			QMessageBox.warning(self, "Input error", "Please name the channel.", QMessageBox.Ok, QMessageBox.Ok)
			return
		if channel_url == "":
			self.input_url.setFocus(True)
			QMessageBox.warning(self, "Input error", "Please provide the channel's URL.", QMessageBox.Ok, QMessageBox.Ok)
			return

		set_result = True
		if self.channel_data is None:
			# We're adding a new record
			channel = self.config.get_streamer_channel(self.streamer["name"], channel_name)
			if channel is not None:
				self.input_name.setFocus(True)
				QMessageBox.warning(self, "Input error", "Channel name already exists!\nName: {}\nURL: {}".format(channel["name"], channel["url"]), QMessageBox.Ok, QMessageBox.Ok)
				return
			channel = self.config.get_channel_by_url(self.streamer["name"], channel_url)
			if channel is not None:
				self.input_url.setFocus(True)
				QMessageBox.warning(self, "Input error", "Channel URL already exists!\nName: {}\nURL: {}".format(channel["name"], channel["url"]), QMessageBox.Ok, QMessageBox.Ok)
				return
			self.config.add_new_channel(self.streamer["name"], channel_name, channel_url, self.check_fav.isChecked())
		else:
			# We're editing an existing record
			if channel_name != self.channel_data["name"]:
				# User changed the name of the channel
				channel = self.config.get_streamer_channel(self.streamer["name"], channel_name)
				if channel is not None:
					self.input_name.setFocus(True)
					QMessageBox.warning(self, "Input error", "Channel name already exists!\nName: {}\nURL: {}".format(channel["name"], channel["url"]), QMessageBox.Ok, QMessageBox.Ok)
					return
			if channel_url != self.channel_data["url"]:
				# User changed the channel's URL
				channel = self.config.get_channel_by_url(self.streamer["name"], channel_url)
				if channel is not None:
					self.input_url.setFocus(True)
					QMessageBox.warning(self, "Input error", "Channel URL already exists!\nName: {}\nURL: {}".format(channel["name"], channel["url"]), QMessageBox.Ok, QMessageBox.Ok)
					return
			if channel_name != self.channel_data["name"] or channel_url != self.channel_data["url"] or bool(self.channel_data["favorite"]) != self.check_fav.isChecked():
				self.config.update_existing_channel(self.streamer["name"], channel_name, channel_url, self.check_fav.isChecked(), self.channel_data["name"], self.channel_data["url"])
			else:
				set_result = False

		if set_result:
			self.result_data = {
				"name": channel_name,
				"url": channel_url,
				"favorite": self.check_fav.isChecked(),
			}
		self.done(QDialog.Accepted)
