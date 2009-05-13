#! /usr/bin/env python
# -.- encoding: utf-8 -.-

import sys
import os
import signal
import gtk
import gobject
import gettext

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../"))
gettext.install('gnome-zeitgeist', '/usr/share/locale', unicode=1)

from zeitgeist_journal_widgets import *
from zeitgeist_shared.basics import BASEDIR

class Journal(gtk.Window):
	
	def __init__(self):
		
		gtk.Window.__init__(self)
		
		# Window
		self.set_title("GNOME Zeitgeist")
		self.set_resizable(True)
		self.set_default_size(800, -1)
		self.set_icon_from_file("%s/data/logo/scalable/apps/gnome-zeitgeist.svg" % BASEDIR)
		self.connect("destroy", gtk.main_quit)
		self.connect('check-resize', self.window_state_event_cb)
		self.connect("key-press-event",self.on_window_key_press_event)
		signal.signal(signal.SIGUSR1, lambda *discard: self.emit(gtk.main_quit))
		
		# Sidebar
		self.sidebar = gtk.VBox()
		
		#self.hBox.pack_start(bookmarks, False, False)
		
		# Filter/options box
		self.sidebar.pack_start(calendar, False, False)
		self.sidebar.pack_start(filtersBox, True, True)
		
		# Event box
		
		# Notebook
		self.notebook = gtk.Notebook()
		self.notebook.connect("switch-page",self.switch_page)
		self.notebook.set_homogeneous_tabs(True)
		self.notebook.set_property("tab-pos",gtk.POS_BOTTOM)
		self.notebook.set_show_tabs(False)
		
		# Notebook components
		starred = "%s/data/bookmark-new.svg" % BASEDIR
		label = self.create_tab_label(_("Stars"), starred)
		self.notebook.append_page(bookmarks, label)
		self.notebook.set_tab_label_packing(bookmarks, True, True, gtk.PACK_START)
		
		journal = "%s/data/calendar.svg" % BASEDIR
		label = self.create_tab_label(_("Journal"), journal)
		self.notebook.append_page(timeline, label)
		self.notebook.set_tab_label_packing(timeline, True, True, gtk.PACK_START)
		
		
		box = gtk.VBox()
		self.notebook.append_page(box, gtk.Label("Most Used Stuff (not yet  implemented)"))
		self.notebook.set_tab_label_packing(box, True, True, gtk.PACK_START)
		
		# Status bar
		statusbar = gtk.Statusbar()
		
		
		
		# Vertical box (contains self.hBox and a status bar)
		self.vBox = gtk.VBox(False)
		#self.vBox.pack_start(bb, False, False)
		self.add(self.vBox)
		
		# Horizontal box (contains the main content and a sidebar)
		self.hBox = gtk.HBox()
		self.vBox.pack_start(self.hBox, True, True)
		
		self.hBox.pack_start(bb, False, False)
		self.hBox.pack_start(searchbox,False,False,5)
		self.hBox.pack_start(self.notebook,True,True)
		self.hBox.pack_start(self.sidebar, False, False)
		self.vBox.pack_start(statusbar, False, False)
		
		# Show everything
		self.show_all()
		filtersBox.option_box.hide_all()
		calendar.hide_all()
		searchbox.hide_all()
		
		self.set_focus(None)
		self.create_toolbar_buttons()
		self.notebook.set_current_page(1)
		
		
	def create_toolbar_buttons(self):
		self.star_button = gtk.ToggleToolButton()
		pixbuf= gtk.gdk.pixbuf_new_from_file_at_size("%s/data/bookmark-new.svg" % BASEDIR, 24, 24)
		icon = gtk.image_new_from_pixbuf(pixbuf)
		del pixbuf
		self.star_button.set_icon_widget(icon)
				
		self.star_button.connect("toggled",self.toggled_starred)
			
		bb.pack_start(self.star_button,False,False)
		bb.show_all()
		
	
	def toggled_starred(self,widget):
		if widget.get_active():
			self.notebook.set_current_page(0)
			bb.set_time_browsing(False)
		else:
			self.notebook.set_current_page(1)
			bb.set_time_browsing(True)
		
		
	
	def ignore_toggle(self,widget):
		pass
		
	'''
	Check which tab is active and bind the keys event to it
	'''
	def on_window_key_press_event(self,timelime,event):
		
		if bb.timebrowse==True:
			if event.keyval==65360:
				timeline.jump_to_day(str(datetime.datetime.today().strftime("%d %m %Y")).split(" "))
				self.set_focus(None)
				
			# KEY == LEFT
			if event.keyval==65361:
				timeline.step_in_time(-1)
				self.set_focus(None)
			
			# KEY == Right
			if event.keyval==65363:
				timeline.step_in_time(+1)
				self.set_focus(None)
		
	def switch_page(self, notebook, page, page_num):	
		if page_num == 0 or page_num ==2:
			
			bb.set_time_browsing(False)
		else:
			bb.set_time_browsing(True)
			
	def create_tab_label(self, title, stock):
			icon = gtk.Image()
			icon = gtk.image_new_from_pixbuf(icon_factory.load_icon(stock, icon_size = 16 ,cache = False))

			label = gtk.Label(title)
			
			box = gtk.HBox()	
			box.pack_start(icon, False, False)
			box.pack_start(label, True, True)
			box.show_all()
			
			del label
			del icon
			return box

	def window_state_event_cb(self, window):
		
		width, height = self.get_size()
		
		if width < 800:
			self.set_size_request(800,-1)
			width = 800
	
		timeline.clean_up_dayboxes(width/3 - 38)
		bookmarks.clean_up_dayboxes(width)

if __name__ == "__main__":
	
	journal = Journal()
	# Load data
	timeline.ready()

	try:
		gtk.main()
	except KeyboardInterrupt:
		sys.exit(0)
