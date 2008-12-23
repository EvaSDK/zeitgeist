import datetime
import gc
import os
import time
import sys
import gtk
import gobject
import pango
from gettext import ngettext, gettext as _
 
from zeitgeist_engine.zeitgeist_datasink import datasink
from zeitgeist_engine.zeitgeist_util import launcher

class TimelineWidget(gtk.ScrolledWindow):
	
	# Constants
	DAY = 1
	WEEK = 2
	MONTH = 4

	def __init__(self):
		# Initialize superclass
		gtk.ScrolledWindow.__init__(self)
		
		# Set up default properties
		self.set_border_width(4)
		self.set_size_request(350, 400)
		self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		
		# This contains the range of dates which we've currently loaded into the GUI
		self.begin = None
		self.end = None
		
		# The current tags that we're using to filter displayed results
		self.tags = ''
		
		# Create vertical box
		self.box = gtk.VBox(False, True)
		self.add_with_viewport(self.box)
		
		# Connect to the calendar's (displayed in the sidebar) signals
		calendar.connect("month-changed", self.load_month)
		calendar.connect("day-selected", self.jump_to_day, False)
		#calendar.connect("day-selected-double-click", self.jump_to_day, True)
		
		# Connect to the datasink's signals
		datasink.connect("reload", self.load_month)
		
		# Load the GUI
		self.load_month()
				   
	def load_month(self, widget=None, tags=None):
		'''
		Loads the current month selected on the calendar into the GUI.
		
		This is called when a new date is selected on the calendar
		or when the user types into the search bar. In the second case,
		we need to reload the GUI and only show items that match the tags
		parameter.
		'''
		
		# Get date range
		# Format is (year, month-1, day)
		date = calendar.get_date()
		
		# Get the begin and end of this month
		# each tuple is of format (year, month, day, hours, minutes,
		# seconds, weekday, day_of_year, daylight savings) 
		begin = (date[0], date[1]+1, 1, 0,0,0,0,0,0)
		end = (date[0], date[1]+2, 0, 0,0,0,0,0,0)
		
		# Note: To get the begin and end of a single day we would use the following
		#begin = (date[0], date[1]+1, date[2], 0,0,0,0,0,0)
		#end = (date[0], date[1]+1, date[2]+1, 0,0,0,0,0,0)
		
		# Get date as unix timestamp
		self.begin = time.mktime(begin)
		self.end = time.mktime(end)
		
		if tags is not None:
			self.tags = tags
		
		calendar.clear_marks()
		
		# Begin benchmarking
		time1 = time.time()
		
		# Remove all child widgets
		for w in self.box.get_children():
			self.box.remove(w)
			
		# Get all items in the date range
		
		# Loop over all of the items and add them to the GUI
		date = None
		print filtersBox.timefilter_active
		if filtersBox.timefilter_active == False:
			print "fitlering from DB"
			for i in datasink.get_items_by_time(self.begin, self.end, self.tags,False):
				# If we just reached a new date then create a label
				if date is None or i.datestring != date:
					date = i.datestring
					daybox=Daybox(i.datestring)
					adj = self.get_vadjustment()
					daybox.connect('set-focus-child', self.focus_in, adj)
					self.box.pack_end(daybox)
				
				# Add item to the GUI
				daybox.add_item(i)
		else:
			print "fitlering within current timeline"
			for i in datasink.get_items_by_time(self.begin, self.end, self.tags,True):
				# If we just reached a new date then create a label
				if date is None or i.datestring != date:
					date = i.datestring
					daybox=Daybox(i.datestring)
					adj = self.get_vadjustment()
					daybox.connect('set-focus-child', self.focus_in, adj)
					self.box.pack_end(daybox)
				
				# Add item to the GUI
				daybox.add_item(i)
		
		self.box.show_all()
		
		# Benchmarking
		time2 = time.time()
		print("Time to reorganize: " + str(time2 -time1))
		
		# Manually force garbage collection
		gc.collect()
	
			
	def jump_to_day(self, widget, hide_other_days):
		'''
		Jump to the currently selected day in the calendar.
		
		If hide_other_days is True, show extra information
		for the current day and hide all other days.
		'''
		# TODO: Implement me :-)
		date=calendar.get_date()
		ctimestamp = time.mktime([date[0],date[1]+1,date[2],0,0,0,0,0,0])
		ctimestamp = datetime.datetime.fromtimestamp(ctimestamp).strftime(_("%a %d %b %Y"))
		if hide_other_days:
			for w in self.box.get_children():
				if not w.date== ctimestamp:
					w.hide()
				else:
					w.show()
		else:
			for w in self.box.get_children():
					w.show()
					if w.date== ctimestamp:
						w.emit_focus()
				
	def focus_in(self,widget, event, adj):
		alloc = widget.get_allocation() 
		if alloc.y < adj.value or alloc.y > adj.value + adj.page_size:
			adj.set_value(min(alloc.y, adj.upper-adj.page_size))
		del widget

class Daybox(gtk.VBox):
	
	def __init__(self,date):
		gtk.VBox.__init__(self)
		self.date=date
		self.label = gtk.Label(date)	
		self.label.set_padding(5, 5) 
		
		# Add a frame around the label
		evbox = gtk.EventBox()
		evbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("black"))
		evbox1 = gtk.EventBox()
		evbox1.set_border_width(1)
		evbox1.add(self.label)
		evbox.add(evbox1)
		self.pack_start(evbox, False, False)
		
		# Create iconview
		# TODO: This is really just quick hack
		# We should eventually place all items inside one DataIconView
		self.iconview = DataIconView()
		self.pack_start(self.iconview, False, False)
	
	def add_item(self,item):
		self.iconview.prepend_item(item)

	def emit_focus(self):
		self.emit("set-focus-child",self)
	
class FilterAndOptionBox(gtk.VBox):
	def __init__(self):
		gtk.VBox.__init__(self)
		self.option_box = gtk.VBox(False)
		self.create_doc_btn = gtk.Button("Create New Document")
		self.create_doc_btn.connect("clicked",self._show_new_from_template_dialog)
		self.create_note_btn = gtk.Button("Create New Note")
		self.create_note_btn.connect("clicked",self._make_new_note)
		self.option_box.pack_start(self.create_doc_btn,False,False,5)
		self.option_box.pack_start(self.create_note_btn,False,False)
		self.pack_start(self.option_box)
		self.timefilter_active=False
		self.filters=[]
		'''
		Filter Box
		'''
		self.frame2 = gtk.Frame()
		#self.alignment2 = gtk.Alignment(0.5,0.5,1.0,1.0)
		self.label2 = gtk.Label("Filter")
		self.frame2.set_label_align(0.5, 0.5)
		#self.frame2.add(self.alignment2)
		self.frame2.set_label_widget(self.label2)
		
		
		self.timefilter = gtk.CheckButton()
		self.timefilter.set_label("Filter over current period")
		self.timefilter.connect("toggled",self.set_timelinefilter)
		self.option_box.pack_start(self.timefilter,False,False,5)
		self.option_box.pack_start(self.frame2,False, False, 5)
		
		
		self.voptionbox = gtk.VBox(False)
		
		self.search = SearchToolItem()
		self.voptionbox.pack_start( self.search ,False,False,0)
		label = gtk.Label("")
		self.voptionbox.pack_start(label ,False,False,0)
		self.timelinefilter = gtk.CheckButton()
		for source in datasink.sources:
			filter = CheckBox(source)
			filter.set_active(True)
			self.voptionbox.pack_start( filter,False,False,0)
			self.filters.append(filter)
			filter.connect("toggled",self.filter_out)
			
		self.frame2.add(self.voptionbox)
		self.date_dict = None
		
	def set_timelinefilter(self,w=None):
		if self.timefilter.get_active():
			self.timefilter_active=True
			print "timefilter active"
		else:
			self.timefilter_active=False
			print "timefilter inactive"
	
	def _make_new_note(self,x):
		launcher.launch_command("tomboy --new-note")
  
	def _show_new_from_template_dialog(self, x):		
		dlg = NewFromTemplateDialog(".","")
		dlg.show()
		
	def filter_out(self, widget):
		datasink.emit("reload")
		gc.collect()

class CalendarWidget(gtk.Calendar):
	def __init__(self):
		gtk.Calendar.__init__(self)

class CheckBox(gtk.CheckButton):
	
	def __init__(self,source):
		gtk.CheckButton.__init__(self)
		self.set_label(source.name)
		self.set_border_width(5)
		self.img = gtk.Image()
		
		self.source = source
		
		#icon = source.icon
		#self.img.set_from_pixbuf(icon)
		try:
			self.img.set_from_icon_name(source.get_icon(16),4)
		except:
		    self.img.set_from_pixbuf(source.get_icon(16))
		self.set_image(self.img)
		
		self.set_focus_on_click(False)
		self.connect("toggled", self.toggle_source)

	def toggle_source(self,widget):
		if self.get_active():
			self.source.set_active(True)
			# FIXME
			#search.emit("clear")
		else:
			self.source.set_active(False)
	  
class NewFromTemplateDialog(gtk.FileChooserDialog):
	'''
	Dialog to create a new document from a template
	'''
	
	__gsignals__ = {
		"response" : "override"
		}

	def __init__(self, name, source_uri):
		# Extract the template's file extension
		try:
			self.file_extension = name[name.rindex('.'):]
			name = name[:name.rindex('.')]
		except ValueError:
			self.file_extension = None
		self.source_uri = source_uri
		parent = gtk.Window()
		gtk.FileChooserDialog.__init__(self,
									   _("New Document"),
									   parent,
									   gtk.FILE_CHOOSER_ACTION_SAVE,
									   (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
										gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
		self.set_current_name(name)
		self.set_current_folder(os.path.expanduser("~/Desktop"))
		self.set_do_overwrite_confirmation(True)
		self.set_default_response(gtk.RESPONSE_ACCEPT)

	def do_response(self, response):
		if response == gtk.RESPONSE_ACCEPT:
			file_uri = self.get_filename()

			# Create a new document from the template and display it
			try:
				if not self.source_uri:
					# Create an empty file
					f = open(file_uri, 'w')
					f.close()
				else:
					shutil.copyfile(self.source_uri, file_uri)
				launcher.launch_uri(file_uri)
			except IOError:
				pass

		self.destroy()
		
class DataIconView(gtk.TreeView):
	'''
	Icon view which displays Datas in the style of the Nautilus horizontal mode,
	where icons are right aligned and each column is of a uniform width.  Also
	handles opening an item and displaying the item context menu.
	'''

	
	def __init__(self):
		gtk.TreeView.__init__(self)
		
		#self.set_selection_mode(gtk.SELECTION_MULTIPLE)
		self.store = gtk.TreeStore(gtk.gdk.Pixbuf, str, str, str, gobject.TYPE_PYOBJECT)
		#self.use_cells = isinstance(self, gtk.CellLayout)
		
		
		icon_cell = gtk.CellRendererPixbuf()
		icon_column = gtk.TreeViewColumn("Icon",icon_cell,pixbuf=0)
		
		name_cell = gtk.CellRendererText()
		name_cell.set_property("wrap-mode", pango.WRAP_WORD_CHAR)
		name_cell.set_property("yalign", 0.0)
		name_cell.set_property("xalign", 0.0)
		name_cell.set_property("wrap-width", 200)
		name_column = gtk.TreeViewColumn("Name", name_cell, markup=2)
		
		#count_cell = gtk.CellRendererText()
		#count_column = gtk.TreeViewColumn("Count", count_cell, markup=3)
		time_cell = gtk.CellRendererText()
		time_column = gtk.TreeViewColumn("Time",time_cell,markup=1)
		
		self.append_column(time_column)
		self.append_column(icon_column)
		self.append_column(name_column)
		#self.append_column(count_column)
	 
		self.set_model(self.store)
		self.set_headers_visible(False)
		
		self.connect("destroy", self._on_destroy)
		self.connect("row-activated", self._open_item)
		self.connect("button-press-event", self._show_item_popup)
		self.connect("drag-data-get", self._item_drag_data_get)
		self.connect("focus-out-event",self.unselect_all)
		
		self.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, [("text/uri-list", 0, 100)], gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY)
		self.last_item=None
			
		self.items = []
		self._create_parents()
	
	def append_item(self, item):
		# Add an item to the end of the store
		self._set_item(item)
		self.set_model(self.store)
	
	def prepend_item(self, item):
		# Add an item to the end of the store
		self._set_item(item, False)
		self.set_model(self.store)
		
	def remove_item(self,item):
		#Maybe filtering should be done on a  UI level
		pass
		
	def unselect_all(self,x=None,y=None):
		try:
			treeselection = self.get_selection()
			model, iter = treeselection.get_selected()
			self.last_item = model.get_value(iter, 4)
			treeselection.unselect_all()
		except:
			pass
	
	def _on_destroy(self, widget):
		self.store.clear()
		self.destroy()
		gc.collect()
		
	def _open_item(self, view, path, x=None):		 
		treeselection = self.get_selection()
		model, iter = treeselection.get_selected()
		item = model.get_value(iter, 4)
		item.open()
		del item
		del iter
		del model
		gc.collect()

	def _show_item_popup(self, view, ev):
		if ev.button == 3:
			   treeselection = self.get_selection()
			   model, iter = treeselection.get_selected()
			   if iter:
				   item = model.get_value(iter, 4)
				   if item:
						menu = gtk.Menu()
						menu.attach_to_widget(view, None)
						item.populate_popup(menu)
						menu.popup(None, None, None, ev.button, ev.time)
						return True
				

	def _item_drag_data_get(self, view, drag_context, selection_data, info, timestamp):
		# FIXME: Prefer ACTION_LINK if available
		if info == 100: # text/uri-list
			
			if self.last_item:
				uris = []
				uris.append(self.last_item.get_uri())
				selection_data.set_uris(uris)
	
	def _set_item(self, item, append=True):
		if append:
			func = self.store.append
		else:
			func = self.store.prepend
		
		func(self.types[item.type],[item.get_icon(24),
				    "<span size='small' color='red'>%s</span>" % item.get_comment(),
				    item.get_name(),
				    #<span size='small' color='blue'> %s </span>" % str(item.count),
				    item.count,
				    item])
		
	
	def _create_parents(self):    	
		self.types={}
		for item in datasink.sources:
			iter =self.store.append(None,[item.get_icon(24),
			    "",
			    item.get_name(),
			    #<span size='small' color='blue'> %s </span>" % str(item.count),
			    item.count,
			    None])
			self.types[item.name]=iter

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

		box = gtk.HBox(False, 0)
		box.show()

		self.clearbtn = None
		self.iconentry = None
		self.entry = gtk.Entry()
		box.pack_start(self.entry, True, True, 0)

		self.entry.set_width_chars(14)
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
		self.do_search("")
		
	def do_search(self, text):
		if self.clearbtn and not self.clearbtn.child:
			img = icon_factory.load_image(gtk.STOCK_CLOSE, 16)
			img.show()
			self.clearbtn.add(img)
		timeline.load_month(tags=text.lower())

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
			self.search_timeout = gobject.timeout_add(100, self._typing_timeout)

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


calendar = CalendarWidget()
filtersBox = FilterAndOptionBox()
timeline = TimelineWidget()
