# About
My Livestreamer GUI is a very basic PyQt5-based user interface for the excellent [Livestreamer](http://docs.livestreamer.io/) CLI application.

## Licence
This project is released under the MIT licence, described in the LICENCE file.

## Supported streaming sites
Currently, only Twitch is supported.
There are no plans to support other streaming sites.

## Requirements
To run this application, you need these packages:
1. [PyQt5](https://riverbankcomputing.com/software/pyqt/download5)
2. [Livestreamer](http://docs.livestreamer.io/)

If you already have Qt5 libraries installed, you may only need [PyQt5 Python package](https://pypi.python.org/pypi/PyQt5) found on PyPI.

## How to run the GUI
Put the source files in a directory and run the following command:
> python3.4 <path-to-directory>/livestreamer_gui.py

You can also set livestreamer_gui.py's executable bit on Linux and run the file directly:
> chmod u+x <path-to-directory->livestreamer_gui.py
> <path-to-directory>/livestreamer_gui.py

