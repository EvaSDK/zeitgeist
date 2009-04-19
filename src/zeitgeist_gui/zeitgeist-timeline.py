#! /usr/bin/env python

import sys
import os
import gtk
import gobject
from gettext import ngettext, gettext as _ 

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../"))

from zeitgeist_widgets import CairoTimeline
from zeitgeist_shared.basics import BASEDIR

class App(gtk.Window):
	
	def __init__(self):
		
		gtk.Window.__init__(self)
		
		# Window
		self.set_title("GNOME Zeitgeist Timeline")
		self.set_resizable(True)
		self.resize(700, 300)
		self.connect("destroy", gtk.main_quit)
		self.set_icon_from_file("%s/data/gnome-zeitgeist.png" % BASEDIR)
		
		self.timeline = CairoTimeline()
		self.add(self.timeline)
		self.show_all()


if __name__ == "__main__":
	
	app = App()

	try:
		gtk.main()
	except KeyboardInterrupt:
		sys.exit(0)
