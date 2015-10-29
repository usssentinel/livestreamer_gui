#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

# Requires: py -3.4 -m pip install livestreamer PyQt5
# Execute with: py -3.4 build_with_py2exe.py py2exe

import os.path, site
MY_SITE_PACKAGES = site.getsitepackages().pop()

from distutils.core import setup
import py2exe
setup(
		windows = [{
			"script": "livestreamer_gui.py",
			"icon_resources": [(0, "images/livestreamer_gui.ico")],
		}],
		options = {
			"py2exe": {
				"optimize": 2,
				"compressed": True,
				"bundle_files": 2,
				"includes": ["sip", "PyQt5.QtCore", "PyQt5.QtGui"]
			}
		},
		data_files = [
				("platforms", [os.path.join(MY_SITE_PACKAGES, "PyQt5", "plugins", "platforms", "qwindows.dll")]),
				("imageformats", [
					os.path.join(MY_SITE_PACKAGES, "PyQt5", "plugins", "imageformats", "qgif.dll"),
					os.path.join(MY_SITE_PACKAGES, "PyQt5", "plugins", "imageformats", "qico.dll"),
				]),
				('images', ["images/livestreamer_gui.ico", "images/twitch.gif", "images/youtube.gif"]),
		]
	)
