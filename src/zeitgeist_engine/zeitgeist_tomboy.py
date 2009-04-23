import os
import re
from xml.dom.minidom import parse
from xml.parsers.expat import ExpatError

import gtk
import gnomevfs
import W3CDate
from gettext import gettext as _

from zeitgeist_engine.zeitgeist_base import DataProvider
from zeitgeist_engine.zeitgeist_util import FileMonitor

# FIXME: This should really just use Beagle or Tracker.

class NoteData:
	
	# TODO: Needs to be updated and eventually moved out of here.
	
	def __init__(self, uri, timestamp=None): 
		self.title = None
		self.content_text = None
		self.timestamp = timestamp
		self.uri = uri
		self.type = "Notes"
		self.do_reload()
		self.name = str(self.title)
		self.icon = "stock_notes"
		self.mimetype = "x-tomboy/note"
	
	def do_reload(self):
		try:
			note_doc = parse(self.get_uri())
		except (IOError, ExpatError), err:
			#print " !!! Error parsing note '%s': %s" % (self.get_uri(), err)
			return

		try:
			title_node = note_doc.getElementsByTagName("title")[0]
			self.title = title_node.childNodes[0].data
		except (ValueError, IndexError, AttributeError):
			pass

		try:
			# Parse the ISO timestamp format .NET's XmlConvert class uses:
			# yyyy-MM-ddTHH:mm:ss.fffffffzzzzzz, where f* is a 7-digit partial
			# second, and z* is the timezone offset from UTC in the form -08:00.
			changed_node = note_doc.getElementsByTagName("last-change-date")[0]
			changed_str = changed_node.childNodes[0].data
			changed_str = re.sub("\.[0-9]*", "", changed_str) # W3Date chokes on partial seconds
			self.timestamp = int(W3CDate.W3CDate(changed_str).getSeconds())
		except (ValueError, IndexError, AttributeError):
			pass

		try:
			content_node = note_doc.getElementsByTagName("note-content")[0]
			self.content_text = self._get_text_from_node(content_node).lower()
		except (ValueError, IndexError, AttributeError):
			pass

		note_doc.unlink()
	
	def _get_text_from_node(self, node):
		if node.nodeType == node.TEXT_NODE:
			return node.data
		else:
			return "".join([self._get_text_from_node(x) for x in node.childNodes])
	
	def get_name(self):
		return self.title or os.path.basename(self.get_uri())
	
	def get_uri(self):
		return self.uri
	
	def __getitem__(self, name):
		return getattr(self, name)


class TomboySource(DataProvider):
	
	def __init__(self, note_path=None):
		DataProvider.__init__(self,
							name=_("Notes"),
							icon="stock_notes",
							uri="source:///Documents/Tomboy")
		self.name = _("Notes")
		self.new_note_item = {
			"name": _(u"Create New Note"),
			"comment": _(u"Make a new Tomboy note"),
			"icon": gtk.STOCK_NEW,
			}
		
		if not note_path:
			if os.environ.has_key("TOMBOY_PATH"):
				note_path = os.environ["TOMBOY_PATH"]
			else:
				note_path = "~/.tomboy"
			note_path = os.path.expanduser(note_path)
		self.note_path = unicode(note_path)
		self.comment = u"Notes from Tomboy"
		self.notes = {}
		
		self.note_path_monitor = FileMonitor(self.note_path)
		self.note_path_monitor.connect("event", self._file_event)
		self.note_path_monitor.open()
		
		# Load notes in an idle handler
		#gobject.idle_add(self._idle_load_notes().next, priority=gobject.PRIORITY_LOW)
	
	def _file_event(self, monitor, info_uri, ev):
		filename = os.path.basename(info_uri)

		if ev == gnomevfs.MONITOR_EVENT_CREATED:
			notepath = os.path.join(self.note_path, filename)
			self.notes[filename] = NoteData(notepath)
			self.emit("reload")
		elif self.notes.has_key(filename):
			if ev == gnomevfs.MONITOR_EVENT_DELETED:
			   # delself.notes[filename]
				self.emit("reload")
			else:
				self.notes[filename].emit("reload")

	def get_items_uncached(self):
		try:
			for filename in os.listdir(self.note_path):
				if filename.endswith(".note"):
					notepath = os.path.join(self.note_path, filename)
					note =  NoteData(notepath)
		                        item = {
            			        	"timestamp": note.timestamp,
                		        	"uri": unicode(note.get_uri()),
                	        		"name": unicode(note.title),
                	        		"comment": unicode(note.content_text),
                	        		"type": unicode(note.type),
                	        		"count": 0,
                	        		"use": u"",
                	        		"mimetype": unicode(note.mimetype),
                	        		"tags": u"",
                	        		"icon": unicode(note.icon)
                	        		}
	                                yield item
                                    
		except (OSError, IOError), err:
			pass  #print " !!! Error loading Tomboy notes:", err
