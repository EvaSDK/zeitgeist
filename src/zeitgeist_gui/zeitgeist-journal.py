#! /usr/bin/env python
# -.- encoding: utf-8 -.-

import sys
import os
import signal
import gtk
import gobject
from gettext import ngettext, gettext as _ 

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../"))

from zeitgeist_journal_widgets import *
from zeitgeist_shared.basics import BASEDIR

class Journal(gtk.Window):
	
	def __init__(self):
		
		gtk.Window.__init__(self)
		
		# Window
		self.set_title("GNOME Zeitgeist")
		self.set_resizable(True)
		self.set_default_size(800, -1)
		self.connect("destroy", gtk.main_quit)
		signal.signal(signal.SIGUSR1, lambda: self.emit(gtk.main_quit))
		self.set_icon_from_file("%s/data/Zeitgeist-logo-192x192.png" % BASEDIR)
		
		#self.connect('window-state-event', self.window_state_event_cb)
		self.connect('check-resize', self.window_state_event_cb)
		
		# Vertical box (contains self.hBox and a status bar)
		self.vBox = gtk.VBox(False, 5)
		tagbox = gtk.HBox()
		tagbox.pack_start(htb, True, True)
		self.vBox.pack_start(bb, False, False)
		self.add(self.vBox)
		
		# Horizontal box (contains the main content and a sidebar)
		self.hBox = gtk.HBox()
		self.vBox.pack_start(self.hBox, True, True,1)
		
		# Sidebar
		self.sidebar = gtk.VBox()
		
		self.hBox.pack_start(bookmarks, False, False)
		
		# Filter/options box
		self.sidebar.pack_start(filtersBox, True, True)
		
		# Notebook
		#self.notebook = gtk.Notebook()
		evbox = gtk.EventBox()
		evbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("darkgrey"))
		
		evbox.add(timeline)
		
		#vbox for timeline and tagbar
		vbox = gtk.VBox()
		vbox.pack_start(evbox)
		vbox.pack_start(tagbox,False,True,2)
		
		hbox = gtk.HBox()
		hbox.pack_start(vbox,True,True,1)
		
		self.hBox.pack_start(hbox, True, True,5)
		self.hBox.pack_start(self.sidebar, False, False)
		#self.hBox.pack_start(ctb, True, True,5)
		
		# Timeline view
		#self.notebook.append_page(related, gtk.Label("Related"))
		#self.notebook.append_page(timeline,gtk.Label("Timeline"))
		#self.notebook.set_current_page(-1)
		
		# Status bar
		statusbar = gtk.Statusbar()
		self.vBox.pack_start(statusbar, False, False)
		
		# Show everything
		self.show_all()
		#self.sidebar.hide_all()
		bookmarks.hide_all()
		htb.hide_all()
		filtersBox.option_box.hide_all()
		calendar.hide_all()
		
	
	def window_state_event_cb(self,window):
		width, height = self.get_size()
		
		if bookmarks.get_property("visible"):
			width = width / 5
		else:
			width = width / 4
		
		bookmarks.bookmarks.view.reload_name_cell_size(width)
		timeline.clean_up_dayboxes(width)


if __name__ == "__main__":
	
	journal = Journal()
	# Load data
	timeline.ready()

	try:
		gtk.main()
	except KeyboardInterrupt:
		sys.exit(0)
