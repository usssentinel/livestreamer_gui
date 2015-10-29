import sys
import traceback
import subprocess
import platform

from PyQt5 import QtCore

class MessageEvent(object):
	def __init__(self, message, add_newline=False, add_timestamp=False):
		self.message = message
		self.add_newline = add_newline
		self.add_timestamp = add_timestamp

class LivestreamerWorker(QtCore.QThread):
	"""This thread will keep the GUI responsive and make the subprocess handling correct."""

	keep_running = True
	process = None
	statusMessage = QtCore.pyqtSignal(object)

	def __init__(self, command, verbose=True):
		super().__init__()
		self.command = command	# The list with commands
		self.verbose = verbose

	def term_process(self):
		if self.process is not None:
			self.process.terminate()

	def send_message(self, message, add_newline=True, add_timestamp=True):
		msg = MessageEvent(message, add_newline, add_timestamp)
		self.statusMessage.emit(msg)

	def run(self):
		try:
			if self.verbose:
				self.send_message("Running command: {}".format(' '.join(self.command)))

			# Specify the startup info to hide the console of the subprocess on Windows
			if platform.system() == "Windows":
				startup_info = subprocess.STARTUPINFO()
				startup_info.dwFlags = subprocess.STARTF_USESTDHANDLES | subprocess.STARTF_USESHOWWINDOW
			else:
				startup_info = None

			try:
				self.process = subprocess.Popen(self.command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=startup_info)
			except Exception as e:
				self.keep_running = False
				self.send_message("Failed to run Livestreamer; {}".format(str(e)))

			while self.keep_running:
				line = self.process.stdout.readline()
				if line == b'' and self.process.poll() is None:
					break
				elif self.process.poll() is not None:
					self.keep_running = False
					continue
				self.send_message("(livestreamer) ", False)
				self.send_message(line.decode("utf-8"), False, False)
				QtCore.QThread.msleep(100)
		except Exception:
			t, val, tb = sys.exc_info()
			self.send_message(''.join(traceback.format_exception(t, val, tb)))
			t = val = tb = None
		self.process = None
		if self.verbose:
			self.send_message("Livestreamer thread ended gracefully.")
		self.quit()
