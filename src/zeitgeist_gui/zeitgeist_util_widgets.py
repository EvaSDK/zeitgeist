import datetime
import gc
import os
import time
import sys
import gtk
import gobject
import pango
from gettext import ngettext, gettext as _ 

from zeitgeist_gui.zeitgeist_util import launcher
from zeitgeist_shared.xdgdirs import xdg_directory
from zeitgeist_gui.zeitgeist_util import launcher
from zeitgeist_gui.zeitgeist_engine_wrapper import engine
from zeitgeist_gui.zeitgeist_bookmarker import bookmarker
from zeitgeist_shared.zeitgeist_shared import *


class DataIconView(gtk.TreeView):
	'''
	Icon view which displays Datas in the style of the Nautilus horizontal mode,
	where icons are right aligned and each column is of a uniform width.  Also
	handles opening an item and displaying the item context menu.
	'''
	
	def __init__(self,parentdays=False):
		gtk.TreeView.__init__(self)
		self.set_size_request(250,-1)
		self.parentdays = parentdays
		
		self.store = gtk.TreeStore(gtk.gdk.Pixbuf, str, str, gobject.TYPE_BOOLEAN, gobject.TYPE_PYOBJECT)
		
		icon_cell = gtk.CellRendererPixbuf()
		icon_column = gtk.TreeViewColumn("",icon_cell,pixbuf=0)
		icon_column.set_fixed_width(32)
		
		name_cell = gtk.CellRendererText()
		name_cell.set_property("wrap-mode", pango.WRAP_WORD_CHAR)
		name_cell.set_property("wrap-width", 125)
		name_column = gtk.TreeViewColumn("Name", name_cell, markup=1)
		name_column.set_fixed_width(125)
		
		time_cell = gtk.CellRendererText()
		time_column = gtk.TreeViewColumn("Time",time_cell,markup=2)
		time_column.set_fixed_width(32)
		
		bookmark_cell = gtk.CellRendererToggle()
		bookmark_cell.set_property('activatable', True)
		bookmark_cell.connect( 'toggled', self.toggle_bookmark, self.store )
		bookmark_column = gtk.TreeViewColumn("bookmark",bookmark_cell)
		bookmark_column.add_attribute( bookmark_cell, "active", 3)
		bookmark_column.set_fixed_width(32)
				
		self.append_column(icon_column)
		self.append_column(name_column)
		self.append_column(time_column)
		self.append_column(bookmark_column)
	 
		self.set_model(self.store)
		self.set_headers_visible(False)
			
		self.set_enable_tree_lines(True)
		self.set_expander_column(icon_column)
		
		self.connect("row-activated", self._open_item)
		self.connect("button-press-event", self._show_item_popup)
		self.connect("drag-data-get", self._item_drag_data_get)
		self.connect("focus-out-event",self.unselect_all)
		
		self.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, [("text/uri-list", 0, 100)], gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY)
		self.last_item=None
		self.day=None
		engine.connect("signal_updated", lambda *args: self._do_refresh_rows())
		
		#self.store.set_sort_column_id(2, gtk.SORT_ASCENDING)
		self.types = {}
		self.days={}
		self.last_item = ""
		self.items_uris=[]
		
	def append_item(self, item,group=True):
		# Add an item to the end of the store
		self._set_item(item, group=group)
		#self.set_model(self.store)
		pass
		
	def prepend_item(self, item,group=True):
		# Add an item to the end of the store
		self._set_item(item, False,group=group)
		#self.set_model(self.store)
		
	def remove_item(self,item):
		# Maybe filtering should be done on a UI level
		pass
	
	def clear_store(self):
		self.types.clear()
		self.days.clear()
		self.day=None
		self.items_uris=[]
		
		self.store.clear()
			
	def unselect_all(self,x=None,y=None):
		try:
			treeselection = self.get_selection()
			model, iter = treeselection.get_selected()
			self.last_item = model.get_value(iter, 4)
			treeselection.unselect_all()
		except:
			pass
			
	def _open_item(self, view, path, x=None):		 
		item = self.get_selected_item()
		if item.get_mimetype() == "x-tomboy/note":
			uri_to_open = "note://tomboy/%s" % os.path.splitext(os.path.split(item.get_uri())[1])[0]
		else:
			uri_to_open = item.get_uri()
		if uri_to_open:
			item.timestamp = time.time()
			launcher.launch_uri(uri_to_open, item.get_mimetype())
	
	def get_selected_item(self):
		treeselection = self.get_selection()
		model, iter = treeselection.get_selected()
		item = model.get_value(iter, 4)
		return item
	
	def _show_item_popup(self, view, ev):
		if ev.button == 3:
			item = self.get_selected_item()
			if item:
				menu = gtk.Menu()
				menu.attach_to_widget(view, None)
				item.populate_popup(menu)
				menu.popup(None, None, None, ev.button, ev.time)
				return True
	
	def _item_drag_data_get(self, view, drag_context, selection_data, info, timestamp):
		# FIXME: Prefer ACTION_LINK if available
		print("_item_drag_data_get")
		uris = []
		treeselection = self.get_selection()
		model, iter = treeselection.get_selected()
		item = model.get_value(iter, 4)
		if not item:
			print "ERROR"
		uris.append(item.get_uri())
		
		pass #print " *** Dropping URIs:", uris
		selection_data.set_uris(uris)
	
	def toggle_bookmark( self, cell, path, model ):
		"""
		Sets the toggled state on the toggle button to true or false.
		"""
		
		model[path][3] = not model[path][3]
		item = model[path][4]
		item.add_bookmark()

	def _do_refresh_rows(self):
		refresh=False
		if len(bookmarker.bookmarks) > 0:	
			for uri in self.items_uris:
				if bookmarker.get_bookmark(uri):
					refresh = True
					break
				
			if refresh:
				iter = self.store.get_iter_root()
				if iter:
					item = self.store.get_value(iter, 4)
					try:
						self.store.set(iter,3,bookmarker.get_bookmark(item.uri))
					except:
						pass
					while True:
						iter = self.store.iter_next(iter)
						if iter:
							item = self.store.get_value(iter, 4)
							try:
								self.store.set(iter,3,bookmarker.get_bookmark(item.uri))
							except:
								pass
						else:
							break
		else:
			iter = self.store.get_iter_root()
			if iter:
				item = self.store.get_value(iter, 4)
				self.store.set(iter,3,False)
				while True:
					iter = self.store.iter_next(iter)
					if iter:
						item = self.store.get_value(iter, 4)
						self.store.set(iter,3,False)
					else:
						break
	
	def _set_item(self, item, append=True, group=True):
		
		func = self.store.append
		bookmark = bookmarker.get_bookmark(item.uri)
		parent = None
		
		if self.parentdays:
			if not self.types.has_key(item.type):
				parent = func(None,[None,#item.get_icon(24),
										"<span size='x-large' color='blue'>%s</span>" % item.type,
										"",
										False,
										None])
				self.types[item.type]=parent
			else:
				parent = self.types[item.type]
			
		self.items_uris.append(item.uri)
		
		if not item.timestamp == -1.0:
			date="<span size='small' color='blue'>%s</span>" % item.get_time()
		else:
			date=""
		
		func(parent,[item.get_icon(24),
				"<span color='black'>%s</span>" % item.get_name(),
				date,
				bookmark,
				item])
		
		self.expand_all()

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
		self.set_current_folder(xdg_directory("desktop", "~/Desktop"))
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

class BookmarksView(gtk.VBox):
	def __init__(self):
		gtk.VBox.__init__(self)
		
		vbox=gtk.VBox()
		
		self.label = gtk.Label("Bookmarks")
		#self.label.set_padding(5,5)
		vbox.pack_start(self.label, False, True, 5)
		self.view = DataIconView()

		ev = gtk.EventBox()
		ev.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#FFFAAA"))
		evbox = gtk.EventBox()
		evbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("darkgrey"))
		evbox1 = gtk.EventBox()
		evbox1.set_border_width(1)
		evbox1.add(ev)
		evbox.add(evbox1)
		ev.set_border_width(1)
		ev.add(vbox)
				
		evbox2 = gtk.EventBox()
		evbox2.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("darkgrey"))
		evbox3 = gtk.EventBox()
		evbox3.set_border_width(1)
		evbox3.add(self.view)
		evbox2.add(evbox3)
					
		vbox.pack_start(evbox2,True,True)
		self.pack_start(evbox,True,True)
		self.get_bookmarks()
		engine.connect("signal_updated", self.get_bookmarks)

	def get_bookmarks(self, x=None):
		self.view.clear_store()
		for item in bookmarker.get_items_uncached():
			self.view.append_item(item, group=False)

class RelatedWindow(gtk.Window):
	
	def __init__(self):
		
		# Initialize superclass
		gtk.Window.__init__(self)
		
		self.set_resizable(True)
		self.connect("destroy", lambda w: self.destroy)
		
		self.baseitem = gtk.HBox(False)
		self.img = gtk.Image()
		self.itemlabel = gtk.Label()
		self.baseitem.pack_start(self.img,False,False,5)
		self.baseitem.pack_start(self.itemlabel,False,False,5)
		
		self.vbox=gtk.VBox()
		self.vbox.pack_start(self.baseitem,False,False,5)
		self.label = gtk.Label("Related files")
		# Add a frame around the label
		self.label.set_padding(5, 5) 
		self.vbox.pack_start(self.label, False, False)
		
		self.scroll = gtk.ScrolledWindow()
		self.view = DataIconView()
		self.scroll.add_with_viewport(self.view)
		self.set_border_width(5)
		self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.vbox.set_size_request(400, 400)
		self.vbox.pack_start(self.scroll)
		self.add(self.vbox)
		self.show_all()
		self.items = []
	
	def set_relation(self, item):
		'''
		Find the items that share same tags with the current item
		Later to be done by monitoring the active files
		'''
		self.img.set_from_pixbuf(item.get_icon(64))
		string = item.get_name() +"\n"+"\n"+"Last Usage:			"+item.get_datestring() + " " + item.get_time()+"\n"+"\n"+"tags:				"+str(item.get_tags())+"\n"
		self.itemlabel.set_label(string)
		self.set_title("GNOME Zeitgeist - Files related to "+item.name)
		self.view.clear_store()
		uris = {}
		if not item.tags == "":
			for i in timeline.items:
				for tag in item.get_tags():
					try:
						if i.tags.index(tag) >= 0:
							#print tag
							i.timestamp=-1.0
							uris[i.uri]=i
						else:
							pass
					except Exception: # TODO: Why this?
						pass
		items = []
		for uri in uris.keys():
			if items.count(uri) == 0:
				items.append(uri)
				self.view.append_item(uris[uri])
		
		for related_item in engine.get_related_items(item):
			if items.count(related_item.uri) == 0:
				items.append(related_item.uri)
				self.view.append_item(related_item)
		
		items = []

class DayBox(gtk.VBox):
	def __init__(self,date):
		gtk.VBox.__init__(self)
		self.date=date
		self.label=gtk.Label(date)
		vbox = gtk.VBox()
		
		self.ev = gtk.EventBox()
		self.ev.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#FFFAAA"))
		self.ev.add(vbox)
		self.ev.set_border_width(1)
		vbox.pack_start(self.label,True,True,5)
		
		self.pack_start(self.ev,False,False)
		self.view=DataIconView()
		if date.startswith("Sat") or date.startswith("Sun"):
			color = gtk.gdk.rgb_get_colormap().alloc_color('#EEEEEE')
			self.view.modify_base(gtk.STATE_NORMAL,color)

		self.scroll = gtk.ScrolledWindow()		
		self.scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		self.scroll.add_with_viewport(self.view)
		self.pack_start(self.scroll)
		self.show_all()
		self.item_count=0
	
	def append_item(self,item):
		self.view.append_item(item)
		self.item_count +=1
		del item 
		
	def clear(self):
		self.view.clear_store()
		self.item_count = 0
	   
	def emit_focus(self):
			self.emit("set-focus-child", self)
