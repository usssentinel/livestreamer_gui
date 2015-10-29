#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import QApplication

from lsgui_lib.database import Config
from lsgui_lib.gui import MainWindow
from lsgui_lib.constants import DBVERSION


if __name__ == "__main__":
	config = Config(DBVERSION)
	app = QApplication(sys.argv)
	window = MainWindow(config)
	sys.exit(app.exec_())
