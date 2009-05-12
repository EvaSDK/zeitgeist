# -.- encoding: utf-8 -.-

import datetime
import time
import math
import gc
import os
import time
import sys
import gtk
import gobject
import pango
import gettext

from zeitgeist_gui.zeitgeist_util import launcher, gconf_bridge
from zeitgeist_gui.zeitgeist_util_widgets import *
from zeitgeist_shared.xdgdirs import xdg_directory
from zeitgeist_gui.zeitgeist_util import launcher, icon_factory
from zeitgeist_gui.zeitgeist_engine_wrapper import engine
from zeitgeist_shared.zeitgeist_shared import *
from zeitgeist_shared.basics import BASEDIR

class TimelineWidget(gtk.ScrolledWindow):
	__gsignals__ = {
		"reset" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
	}
	
	def __init__(self):
		
		# Initialize superclass
		gtk.ScrolledWindow.__init__(self)
		
		# Add children widgets
		self.view = DataIconView(True)
		self.dayboxes=gtk.HBox(False,False)
		
		# A dict of daybox widgets for recycling
		self.days = {}
		
		# Set up default properties
		self.set_border_width(0)
		self.set_size_request(600, 200)
		self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)
		self.add_with_viewport(self.dayboxes)
		
		# This contains the range of dates which we've currently loaded into the GUI
		self.begin = None
		self.end = None
		
		# The current tags that we're using to filter displayed results
		self.tags = []
		
		# The current search string that we're using to filter displayed results
		self.search = ""
		
		# Get list of sources to filter
		self.sources = {}
		self.sources_icons = {}
		
		# Connect to the calendar's (displayed in the sidebar) signals
		calendar.connect("month-changed", self.load_month)
		calendar.connect("day-selected", self.jump_to_day)
		calendar.connect("day-selected-double-click", self.jump_to_day, True)
		
		# GConf settings
		gconf_bridge.connect("changed::compress_empty_days", lambda gb: self.load_month())
		
		self.items = []
		self._ready = False
		self.days_range = 0
		date = calendar.get_date()
		# Get the begin and end of this month
		# each tuple is of format (year, month, day, hours, minutes,
		# seconds, weekday, day_of_year, daylight savings) 
		day = date[2]
		self.begin = (date[0], date[1]+1, day-1,0,0,0,0,0,-1)
		self.end = (date[0], date[1]+1, day+2,0,0,0,0,0,-1)
		self.begin = time.mktime(self.begin) 
		self.end = time.mktime(self.end) -1
	
	def ready(self):
		'''
		Only call this one time, once the GUI has loaded and we can
		start listening to events.
		'''
		
		assert self._ready == False
		self._ready = True
		engine.connect("signal_updated", lambda x: self.load_month(checkrefresh = True))
		
		# Load the GUI
		self.load_month()
	
	
	def load_month(self, widget=None, begin=None, end=None, offset = 0, cached=False, tags=None , search=None, checkrefresh = False):
		'''
		Loads the current month selected on the calendar into the GUI.
		
		This is called when a new date is selected on the calendar
		or when the user types into the search bar. In the second case,
		we need to reload the GUI and only show items that match the tags
		parameter.
		'''
		
		# Begin benchmarking
		t1 = time.time()
		
		if not cached:	
			self.items = []
			# Use old properties if new ones are None else replace them
			if tags:
				self.tags = tags
			if search:
				self.search = search
			if begin:
				self.begin = begin
			if end:
				self.end = end
		
			if len(self.tags) > 0:
				print self.tags
				print "if len(self.tags) > 0:"
				self.begin = sys.maxint
				self.end = - sys.maxint - 1
				for tag in self.tags:
					start, fin = engine.get_timestamps_for_tag(tag)
					if start < self.begin:
						self.begin = start
					if fin > self.end:
						self.end = fin
			
			else:
				self.begin = self.begin + (offset*86400)
				self.end =self.end + (offset*86400)
			
			calendar.clear_marks()
			
			# Get all items in the date range and add them to self.items
			for item in engine.get_items(self.begin, self.end, ""):
				if item.timestamp <= self.end:
					if not self.sources.has_key(item.type):
						self.sources[item.type]=False
						self.sources_icons[item.type] = item.icon
					
					self.items.append(item)
					item.connect("relate", self.set_relation)
			
			try:
				filtersBox.reload()
			except:
				pass
			
		# Update the GUI with the items that match the current search terms/tags
		t3 = time.time()
		print "Time to get items: %s" % str(t3-t1)
		
		self.apply_search(self.tags)
		
		t4 = time.time()
		# Benchmarking
		print "Time to apply search on %s items: %s" % (len(self.items), str(t4 -t3))
		print "Time for operation on %s items: %s \n" % (len(self.items), str(t4 -t1))
		
	def reset_date(self):
		date = calendar.get_date()
		# Get the begin and end of this month
		# each tuple is of format (year, month, day, hours, minutes,
		# seconds, weekday, day_of_year, daylight savings) 
		day = date[2]
		self.begin = (date[0], date[1]+1, day-1,0,0,0,0,0,-1)
		self.end = (date[0], date[1]+1, day+2,0,0,0,0,0,-1)
		self.begin = time.mktime(self.begin) 
		self.end = time.mktime(self.end) -1
	
	def apply_search(self, tags=[]):
		'''
		Adds all items which match tags to the GUI.
		'''	
		self.tags = tags
		self.days.clear()
		self.review_days()
		self.build_days()
		self.clean_up_dayboxes()
	
	def build_days(self):
		for item in self.items:
			if self.sources[item.type]:
				continue
			
			if self.search.strip() =="" and len(self.tags) ==0:
				self._append_to_day(item)
				continue
				
			for tag in self.tags:
				if (tag.lower() in item.name.lower()):
					self._append_to_day(item)
					continue
				elif tag.lower() in item.tags.lower().split(","):
					self._append_to_day(item)
					continue
			
			if self.search.strip() != "":
				if self.search.strip().lower() in item.name.lower():
					self._append_to_day(item)
					continue	
				elif self.search.strip().lower() in item.tags.lower():
					self._append_to_day(item)
					continue	
			
	def jump_to_day(self, widget,focus=False):
		'''
		Jump to the currently selected day in the calendar.
		'''
		
		date = calendar.get_date()
		self.begin =  time.mktime([date[0],date[1]+1,date[2]-1,0,0,0,0,0,-1])
		self.end =  time.mktime([date[0],date[1]+1,date[2]+2,0,0,0,0,0,-1]) - 1
		
		print "jump to day"
		
		self.load_month()
		
		ctimestamp = time.mktime([date[0],date[1]+1,date[2],0,0,0,0,0,0])
		datestring = datetime.datetime.fromtimestamp(ctimestamp).strftime("%d %b %Y")
		if focus == False:
			for w in self.dayboxes:
				w.show_all()
				if w.date == datestring:
					w.emit("set-focus-child", w)
		else:
			for w in self.dayboxes:
				w.hide_all()
				if w.date == datestring:
					w.show_all()
	
	def set_relation(self, item):
		related = RelatedWindow()
		related.set_relation(item)

	#def focus_in(self, widget, event, adj):
	#	alloc = widget.get_allocation() 
	#	if alloc.x < adj.value or alloc.x > adj.value + adj.page_size:
	#		adj.set_value(min(alloc.x, adj.upper-adj.page_size))
	#		del widget 
	
	def get_dayboxes(self):
		return self.days.items()
	
	def step_in_time(self, x=0):
		self.search = ""
		try:
			search.entry.set_text(self.default_search_text)
		except:
			pass

		date = calendar.get_date()
		temp = date[2] + x
		if temp <0 or temp > 31:
			self.begin = self.begin + (x*86400)
			timestamp = datetime.date.fromtimestamp(self.begin).timetuple()[:3]
			
			calendar.select_month(timestamp[1] - 1,timestamp[0])
			temp=timestamp[2]
		calendar.select_day(temp)
		
	def _append_to_day(self, item):
		try:
			daybox = self.days[item.get_datestring()]
			daybox.append_item(item)
			self.days[item.get_datestring()] = daybox
		except:
			self.days[item.get_datestring()]=DayBox(item.get_datestring())
			self.dayboxes.pack_start(self.days[item.get_datestring()])
			daybox = self.days[item.get_datestring()]
			daybox.append_item(item)
			self.days[item.get_datestring()] = daybox
				
	def review_days(self):
		print "reviewing days"
		
		if self.search.strip() != "":
			begin = sys.maxint
			end = -sys.maxint-1
			for item in self.items:
				begin = min(item.timestamp,begin)
				end = max(item.timestamp,end)
			self.begin = begin
			self.end = end
		
		
		try:
			self.days_range = int((self.end - self.begin) / 86400) + 1 # get the days range
		except:
			self.days_range = 3
			
		'''
		Try avoiding rebuiling boxes and use currently available
		'''
		
		if self.days_range == len(self.dayboxes):
			for i, daybox in enumerate(self.dayboxes):
				datestring = datetime.datetime.fromtimestamp(self.begin+(i*86400)).strftime("%a %d %b %Y")
				print datestring
				daybox.clear()
				daybox.refresh(datestring)
				self.days[datestring] = daybox
		else:
			for daybox in self.dayboxes:
				self.dayboxes.remove(daybox)
				daybox.clear()
			# precalculate the number of dayboxes we need and generate the dayboxes
			for i in xrange(self.days_range):
				datestring = datetime.datetime.fromtimestamp(self.begin+(i*86400)).strftime("%a %d %b %Y")
				self.days[datestring]=DayBox(datestring)
				self.dayboxes.pack_start(self.days[datestring])
		
		print "reviewing days done"
	
	def clean_up_dayboxes(self, width=None):
		
		self.compress_empty_days = gconf_bridge.get("compress_empty_days")
		if self.compress_empty_days:
			i = len(self.dayboxes) -1
			for daybox in self.dayboxes:
				if daybox.item_count == 0 and (self.tags or self.search!=""):
					if i == len(self.dayboxes) -1 or i == 0:
						daybox.hide()
					else:
						daybox.set_label(".")
						daybox.view.set_size_request(-1,-1)
						daybox.show()
				else:
					if width and width > 300:
						daybox.view.set_size_request(width-30,-1)
						daybox.set_size_request(width-10,-1)
						daybox.view.reload_name_cell_size(width-50)
					daybox.show()
				i = i - 1
		gc.collect()
	
class HTagBrowser(gtk.VBox):
	
	def __init__(self):
		
		# Initialize superclass
		gtk.VBox.__init__(self)
		self.set_size_request(-1,-1)
		
		self.tag_widgets = {}
		
		TARGET_TYPE_TEXT = 80
		TARGET_TYPE_PIXMAP = 81
		
		self.fromImage = [ ( "text/plain", 0, TARGET_TYPE_TEXT )]

		self.combobox = gtk.combo_box_new_text()
		self.combobox.append_text(_("Recently used tags"))
		self.combobox.append_text(_("Most used tags"))
		
		self.pack_start(self.combobox, False, False)
		
		self.scroll = gtk.ScrolledWindow()
		ev = gtk.EventBox()
		#ev.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))
		#ev.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("red"))
		#ev.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse("red"))
		self.view = gtk.VBox()
		ev.add(self.view)
		self.scroll.add_with_viewport(ev)
		self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.scroll.set_shadow_type(gtk.SHADOW_NONE)
		self.pack_start(self.scroll,True,True)
		self.show_all()
		self.items = []
		
		self.func = self.get_recent_tags
		self.func()
	
		self.combobox.connect("changed", self.changed_cb)
		self.combobox.set_active(0)
		
		engine.connect("signal_updated", lambda *args: self.func)
		
		self.reset_begin_timestamp = timeline.begin
		self.reset_end_timestamp = timeline.end

	def reload_tags(self, x=None):
		index = self.combobox.get_active()
		if index == 0:
			self.func = self.get_recent_tags
		else:
			self.func = self.get_most_tags

	def changed_cb(self, combobox=None):
		index = self.combobox.get_active()
		if index == 0:
			self.func = self.get_recent_tags()
		else:
			self.func = self.get_most_tags()
	
	def _tag_toggle_button(self, tag):
		
		btn = gtk.ToggleButton(tag)
		image = gtk.image_new_from_file("%s/data/tag3.svg" % BASEDIR)
		btn.connect("drag_data_get", self.sendCallback)
		btn.drag_source_set(gtk.gdk.BUTTON1_MASK, self.fromImage,gtk.gdk.ACTION_COPY)
		btn.set_alignment(0,0.5)

		btn.set_image(image)
		btn.set_size_request(-1, 28)
		btn.set_relief(gtk.RELIEF_NONE)
		btn.set_focus_on_click(False)
		self.view.pack_start(btn, True, True)
		btn.connect("toggled", self.toggle)
		return btn
	
	def sendCallback(self, widget, context, selection, targetType, eventTime):
		selection.set(selection.target, 8, "tag://"+widget.get_label())

	
	def get_recent_tags(self, x=None):
		
		date = calendar.get_date()
		
		begin = time.mktime((date[0], date[1]+1, 1, 0,0,0,0,0,0))
		end = time.mktime((date[0], date[1]+2, 0, 0,0,0,0,0,0))
		
		for w in self.view:
			self.view.remove(w)
		
		for tag in engine.get_recent_used_tags(10, begin, end):
			self.tag_widgets[tag] = self._tag_toggle_button(tag)
			
		self.show_all()
	
	def get_most_tags(self, x=None):
		
		begin = timeline.begin
		end = timeline.end
		
		for w in self.view:
			self.view.remove(w)
		
		for tag in engine.get_most_used_tags(10, begin, end):
			self.tag_widgets[tag] = self._tag_toggle_button(tag)
		
		self.show_all()
	
	def toggle(self, x=None):
		
		timeline.search=""
		search.entry.set_text("")
		using_tags = False
		
		tags = timeline.tags
		if x.get_active():
			if tags.count(x.get_label()) == 0:
				tags.append(x.get_label())
				begin, end = engine.get_timestamps_for_tag(x.get_label())
				timeline.load_month(begin=begin, end=end, tags=tags)
				using_tags = True		
				timeline.search = ""
				
		else:
			if tags.count(x.get_label()) > 0:
				tags.remove(x.get_label())
				timeline.load_month(tags=tags)
		
		if using_tags:
			try:
				timeline.reset_date()
				search.entry.set_text(self.default_search_text)
				timeline.search = ""
			except:
				pass
			bb.set_time_browsing(False)
		else:
			bb.set_time_browsing(True)
			
		bookmarks.get_bookmarks(text =  tags)
		
		
	def is_any_toggled(self):
		for w in self.view:
			if w.get_active():
				return True
		return False
	
	def untoggle_all(self):
		for btn in self.view:
			btn.set_active(False)
		timeline.tags = []

class FilterBox(gtk.VBox):
	
	def __init__(self):
		
		gtk.VBox.__init__(self)
		self.option_box = gtk.VBox(False)
		self.timefilter_active=False
		self.filters = {}
		self.filters_active={}
		
		'''
		Filter Box
		'''
		
		self.option_box.set_size_request(-1,-1)
		self.pack_start(self.option_box)
		self.voptionbox = gtk.VBox(False)
		
		self.frame2 = gtk.Frame()
		self.label2 = gtk.Label("Filter")
		self.frame2.set_label_align(0.5, 0.5)
		self.frame2.set_label_widget(self.label2)
		self.option_box.pack_start(self.frame2,False, False)
		
		self.timelinefilter = gtk.CheckButton()
		self.reload()
		
		self.frame2.add(self.voptionbox)
		self.date_dict = None
		
		# GConf settings
		self.show_all()
	
	def reload(self):
		for w in self.voptionbox:
			self.voptionbox.remove(w)
		
		sources = timeline.sources.keys()
		sources.sort()
		for source in sources:
			filter = CheckBox(source)
			filter.set_active(True)
			self.voptionbox.pack_start(filter, False, False, 0)
			self.filters[source] = filter
			if not self.filters_active.has_key(source):
				print source + "	added"
				self.filters_active[source] = True
			filter.set_active(self.filters_active[source])
			filter.connect("toggled", self.toggle_source)
			
			filter.ready = True
	
	def toggle_source(self, widget=None): 
		self.filters_active[widget.source] = widget.get_active()
	
	def set_timelinefilter(self, *discard):
		self.timefilter_active = self.timefilter.get_active()
		
class CalendarWidget(gtk.Calendar):
	
	def __init__(self):
		gtk.Calendar.__init__(self)
		self.show_all()

class CheckBox(gtk.CheckButton):
	
	def __init__(self, source):
		
		gtk.CheckButton.__init__(self)
		self.set_border_width(5)
		self.set_focus_on_click(False)
		
		self.source = source
		self.set_label(source)
		self.set_active(timeline.sources[source])
		
		icon = icon_factory.load_icon(timeline.sources_icons[source], icon_size = 24)
		self.image = gtk.Image()
		self.image.set_from_pixbuf(icon)
		self.set_image(self.image)
		
		# Leave this at the end, as else the callback will reload
		# the GUI several times.
		
		self.show_all()
		self.ready = False
		
		self.connect("toggled", self.toggle_source)
		
	
	def toggle_source(self, widget=None):
		if self.ready:
			timeline.sources[self.source] = not self.get_active()
			timeline.load_month(cached=True)

class SearchToolItem(gtk.ToolItem):
	
	__gsignals__ = {
		"clear" : (gobject.SIGNAL_RUN_FIRST,
				   gobject.TYPE_NONE,
				   ()),
		"search" : (gobject.SIGNAL_RUN_FIRST,
					gobject.TYPE_NONE,
					(gobject.TYPE_STRING,))
		}
	
	def __init__(self, accel_group = None):
		gtk.ToolItem.__init__(self)
		self.search_timeout = None
		self.default_search_text = _("Search")
		box = gtk.HBox(False, 5)
		box.show()

		self.clearbtn = None
		self.iconentry = None
		self.entry = gtk.Entry()
		box.pack_start(self.entry, True, True, 5)

		self.entry.set_width_chars(30)
		self.entry.set_text(self.default_search_text)
		self.entry.show()
		
		# Needs cleanup
		calendar.connect("month-changed", lambda w: self.emit("clear"))
		self.entry.connect("activate", lambda w: self._typing_timeout())
		self.entry.connect("focus-in-event", lambda w, x: self._entry_focus_in())
		self.entry.connect("key-press-event", self._entry_key_press)
		
		# Hold on to this id so we can block emission when initially clearing text
		self.change_handler_id = self.entry.connect("changed", lambda w: self._queue_search())
		
		if accel_group:
			# Focus on Ctrl-L
			self.entry.add_accelerator("grab-focus",
									   accel_group,
									   ord('l'),
									   gtk.gdk.CONTROL_MASK,
									   0)

		self.add(box)
		self.show_all()
	
	def do_clear(self):
		if self.clearbtn and self.clearbtn.child:
			self.clearbtn.remove(self.clearbtn.child)
		self._entry_clear_no_change_handler()
		timeline.reset_date()
		bookmarks.get_bookmarks(text="")
		timeline.search = ""
		timeline.load_month()
	
	def do_search(self, text):
		# Get date range
		# Format is (year, month-1, day)
		date = calendar.get_date()
		
		# Get the begin and end of this month
		# each tuple is of format (year, month, day, hours, minutes,
		# seconds, weekday, day_of_year, daylight savings) 
		
		
		# FIXME: We need to look for the frist entry and last entry in the DB
		begin = (date[0], date[1]+1,0, 0,0,0,0,0,0)
		end = (date[0], date[1]+2, 0, 0,0,0,0,0,0)
		begin = time.mktime(begin)
		end = time.mktime(end) -1
		#timeline.load_month(begin=begin, end=end, tags = timeline.tags)
		
		if self.clearbtn and not self.clearbtn.child:
			img = icon_factory.load_image(gtk.STOCK_CLOSE, 16)
			img.show()
			self.clearbtn.add(img)
		if not text.strip() == "":
			htb.untoggle_all()
			timeline.load_month(begin=0, end=sys.maxint, search = text.lower())
			bookmarks.get_bookmarks(text = [text.lower()])
		

	def _entry_clear_no_change_handler(self):
		'''Avoids sending \'changed\' signal when clearing text.'''
		self.entry.handler_block(self.change_handler_id)
		self.entry.set_text("")
		self.entry.handler_unblock(self.change_handler_id)

	def _entry_focus_in(self):
		'''Clear default search text'''
		if self.entry.get_text() == self.default_search_text:
			self._entry_clear_no_change_handler()

	def _typing_timeout(self):
		if len(self.entry.get_text()) > 0:
			self.emit("search", self.entry.get_text())
		self.search_timeout = None
		return False

	def _queue_search(self):
		if self.search_timeout is not None:
			gobject.source_remove(self.search_timeout)
			self.search_timeout = None

		if len(self.entry.get_text()) == 0:
			self.emit("clear")
		else:
			self.search_timeout = gobject.timeout_add(500, self._typing_timeout)

	def _entry_key_press(self, w, ev):
		if ev.keyval == gtk.gdk.keyval_from_name("Escape") \
			   and len(self.entry.get_text()) > 0:
			self.emit("clear")
			return True

	def get_search_text(self):
		return self.entry.get_text()

	def cancel(self):
		'''Cancel a pending/active search without sending the \'clear\' signal.'''
		if self.entry.get_text() != self.default_search_text:
			self.do_clear()

class BrowserBar(gtk.HBox):
	
	def __init__(self, htb):
		
		self.htb = htb
		gtk.HBox.__init__(self)   
		self.tooltips = gtk.Tooltips()

		self.home = gtk.ToolButton("gtk-home")
		self.home.set_label("Recent")
		self.home.connect("clicked", self.focus_today)
		self.tooltips.set_tip(self.home, _("Show recent activities"))

		self.back = gtk.ToolButton("gtk-go-back")
		self.back.set_label("Older")
		self.back.connect("clicked", self.add_day)
		self.tooltips.set_tip(self.back, _("Go back in time"))
		
		self.forward = gtk.ToolButton("gtk-go-forward")
		self.forward.set_label("Newer")
		self.forward.connect("clicked", self.remove_day)
		self.tooltips.set_tip(self.forward, _("Go forward in time"))
		
		'''
		self.options = gtk.ToggleToolButton()
		pixbuf= gtk.gdk.pixbuf_new_from_file_at_size("%s/data/filter.svg" % BASEDIR, 32, 32)
		icon = gtk.image_new_from_pixbuf(pixbuf)
		del pixbuf
		self.options.set_icon_widget(icon)
		'''
		self.options = gtk.ToggleToolButton("gtk-select-color")
		self.tooltips.set_tip(self.options, _("Filter your current view"))
		self.options.set_label("Filters")
		self.options.connect("toggled",self.toggle_options)
		
		self.calendar = gtk.ToggleToolButton()
		pixbuf= gtk.gdk.pixbuf_new_from_file_at_size("%s/data/calendar.svg" % BASEDIR, 32, 32)
		icon = gtk.image_new_from_pixbuf(pixbuf)
		del pixbuf
		self.calendar.set_icon_widget(icon)
		self.tooltips.set_tip(self.calendar, _("View journal for a specific date"))
		self.calendar.set_label("Calendar")
		self.calendar.connect("toggled",self.toggle_calendar)
		
		'''
		self.star = gtk.ToggleToolButton()
		icon = gtk.image_new_from_file("%s/data/bookmark-new.svg" % BASEDIR)
		self.star.set_icon_widget(icon)
		self.star.set_label("Bookmarks")
		self.tooltips.set_tip(self.star, _("View bookmarked activities"))
		self.star.connect("toggled",self.toggle_bookmarks)
		'''
		
		self.tags = gtk.ToggleToolButton()
		icon = gtk.image_new_from_file("%s/data/tag3.svg" % BASEDIR)
		icon.set_pixel_size(24)
		self.tags.set_icon_widget(icon)
		self.tags.set_label("Tags")
		self.tooltips.set_tip(self.tags, _("View tagged activities"))
		self.tags.connect("toggled", self.toggle_tags)
		
		toolbar = gtk.Toolbar()
		toolbar.insert(self.back, -1)
		toolbar.insert(self.home, -1)
		toolbar.insert(self.forward, -1)
		
		self.sep = gtk.SeparatorToolItem()
		
		toolbar.insert(self.sep,-1)
		#toolbar.insert(self.star, -1)
		toolbar.insert(self.tags, -1)
		toolbar.insert(self.options, -1)
		toolbar.insert(self.calendar, -1)
		toolbar.set_style(gtk.TOOLBAR_ICONS)
		
		hbox = gtk.HBox()
		hbox.pack_start(toolbar,True,True)
		
		toolbar2 = gtk.Toolbar()
		searchbox = gtk.HBox()
		# Search Area
		searchbox.pack_start(search, True, True)
		clear_btn = gtk.ToolButton("gtk-clear")
		clear_btn.connect("clicked", lambda x: search.do_clear())
		searchbox.pack_start(clear_btn, False, False)
		toolbar2.add(searchbox)
		
		hbox2 = gtk.HBox(True)
		hbox2.pack_start(toolbar2)
		
		self.pack_start(hbox, True, True)
		self.pack_start(hbox2, False, False)

	
	def set_time_browsing(self, bool):
		if bool:
				
				self.calendar.set_sensitive(True)
				self.options.set_sensitive(True)
				self.tags.set_sensitive(True)
				self.sep.set_sensitive(True)
				self.forward.set_sensitive(True)
				self.home.set_sensitive(True)
				self.back.set_sensitive(True)
		
		else:
				self.back.set_sensitive(False)
				self.home.set_sensitive(False)
				self.sep.set_sensitive(False)
				self.options.set_sensitive(False)
				#self.tags.set_sensitive(False)
				self.forward.set_sensitive(False)
				self.calendar.set_sensitive(False)
				
				self.calendar.set_active(False)
				self.options.set_active(False)
				#self.tags.set_active(False)
	
	def remove_day(self, x=None):
		self.htb.untoggle_all()
		timeline.step_in_time(1)
	
	def toggle_options(self, x=None):
		if self.options.get_active():
			filtersBox.option_box.show_all()
		else:
			filtersBox.option_box.hide_all()
	
	def toggle_bookmarks(self, x=None):
		if self.star.get_active():
			bookmarks.show_all()
		else:
			bookmarks.hide_all()
			
	def toggle_calendar(self, x=None):
		if self.calendar.get_active():
			calendar.show_all()
		else:
			calendar.hide_all()
	
	def toggle_tags(self, x=None):
		if self.tags.get_active():
			self.htb.show_all()
		else:
			self.htb.hide_all()
		
	def add_day(self, x=None):
		self.htb.untoggle_all()
		timeline.step_in_time(-1)

	def focus_today(self, x=None):
		today = str(datetime.datetime.today().strftime("%d %m %Y")).split(" ")
		date = calendar.get_date()
		calendar.select_day(int(today[0]))
		if not int(today[1])-1 == int(date[1]):
			calendar.select_month(int(today[1])-1, int(today[2]))
		
class ItemInfo(gtk.VBox): 
	def __init__(self):
		gtk.VBox.__init__(self)
		self.frame = gtk.Frame()
		self.label = gtk.Label("Item Info")
		self.frame.set_label_align(0.5, 0.5)
		self.frame.set_label_widget(self.label)
		self.pack_start(self.frame2,False, False)
		self.vbox = gtk.VBox(False)
		self.frame.add(self.vbox)
		
		self.name = ""
		self.comment = ""
		self.icon = None
		self.tags = []
		
	def set_item(self,item):
		pass
			
	def set_tag_btn(self,tag):
		pass

calendar = CalendarWidget()
bookmarks = BookmarksView()
timeline = TimelineWidget()
htb = HTagBrowser()
search = SearchToolItem()
filtersBox = FilterBox()
bb = BrowserBar(htb)
