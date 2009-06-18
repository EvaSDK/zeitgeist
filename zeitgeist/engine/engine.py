# -.- encoding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009 Seif Lotfy <seif@lotfy.com>
# Copyright © 2009 Siegfried-Angel Gevatter Pujals <rainct@ubuntu.com>
# Copyright © 2009 Natan Yellin <aantny@gmail.com>
# Copyright © 2009 Mikkel Kamstrup Erlandsen <mikkel.kamstrup@gmail.com>
# Copyright © 2009 Markus Korn <thekorn@gmx.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import time
import sys
import os
import shutil
import sqlite3
import gettext
import gobject
from xdg import BaseDirectory
from xdg.DesktopEntry import DesktopEntry

import traceback
from random import randint

from zeitgeist import config
from zeitgeist.engine.base import *
from zeitgeist.dbusutils import ITEM_STRUCTURE_KEYS, TYPES_DICT

class ZeitgeistEngine(gobject.GObject):

	def __init__(self, storm_store):
		
		gobject.GObject.__init__(self)
		
		assert storm_store is not None
		self.store = storm_store
		self._apps = set()
		self._last_time_from_app = {}
        
		'''
		path = BaseDirectory.save_data_path("zeitgeist")
		database = os.path.join(path, "zeitgeist.sqlite")
		self.connection = self._get_database(database)
		self.cursor = self.connection.cursor()
		'''
		self.get_most_used_tags()
	
	def _result2data(self, event=None, item=None):
		
		if not item:
			item = event.subject
		
		# Check if the item is bookmarked
		# FIXME: this seems redundant if i am fetching bookmarked items
		bookmark = bool(self.store.find(Item,
			Item.content_id == Content.BOOKMARK.id,
			Annotation.subject_id == item.id,
			Annotation.item_id == Item.id).one())
		
		result = self.get_tags_for_item(item)
		tags = ",".join(set(result)) if result else ""
		
		return (
			event.start if event else 0, # timestamp
			item.uri.value, # uri
			item.text or os.path.basename(item.uri.value), # name
			item.source.value or "", # source
			item.content.value or "", # content
			item.mimetype or "", # mimetype
			tags, # tags
			"", # comment
			bookmark, # bookmark
			# FIXME: I guess event.item.content below should never be None
			event.item.content.value if (event and event.item.content) else "", # usage is determined by the event Content type
			item.icon or "", # icon
			"", # app      # FIXME!
			item.origin or "" # origin
			)
	
	def _ensure_item(self, item, uri_only=False):
		"""
		Takes either a Data object or an URI for an item in the
		database. If it's a Data object it is returned unchanged,
		but if it's an URI it's looked up in the database and the
		its returned converted into a complete Data object.
		
		If uri_only is True, only the URI of the item is returned
		(and no database query needs to take place).
		"""
		
		# Is it a string (can be str, dbus.String, etc.)?
		if hasattr(item, "capitalize"):
			if uri_only:
				return item
			else:
				item = self.get_item(item)
		elif uri_only:
			return item["uri"]
		
		return item
	
	def get_last_timestamp(self, uri=None):
		"""
		Gets the timestamp of the most recent item in the database. If
		`uri' is not empty, it will give the last timestamp for the
		indicated URI.
		
		Returns 0 if there are no items in the database.
		"""
		
		return 0
	
	def _get_basics(self, uri, content, source):
		
		self._insert_basics(uri, content, source)
		if uri:
			uri_id = self.store.execute(
				"SELECT id  FROM uri WHERE VALUE=?", (uri, )).get_one()[0]
		else:
			uri_id = None
		if source:
			source_id = self.store.execute(
				"SELECT id FROM source WHERE VALUE=?", (source, )).get_one()[0]
		else:
			source_id = None
		if content:
		      content_id = self.store.execute(
				"SELECT id FROM content WHERE VALUE=?", (content, )).get_one()[0]
		else:
			content_id = None
		
		return uri_id, content_id, source_id
	
	def _insert_basics(self, uri, content, source):
		try:
			if uri:
				self.store.execute("INSERT INTO uri (value) VALUES (?)", (uri, ))
				#print "Inserted item: "+ uri
		except Exception, ex:
			pass
		try:
			if source:
				self.store.execute("INSERT INTO source (value) VALUES (?)", (source, ))
				#print "Inserted source: "+ source
		except Exception, ex:
			pass
		try:
			if content:
				self.store.execute("INSERT INTO content (value) VALUES (?)", (content, ))
				#print "Inserted content: "+ content
		except Exception, ex:
			pass
		
	def _get_item(self, id, content_id, source_id, text, origin=None, mimetype=None, icon=None):
		self._insert_item(id, content_id, source_id, text, origin, mimetype, icon)
		item = self.store.find(Item, Item.id == id)
		return item
			
	def _insert_item(self, id, content_id, source_id, text, origin=None, mimetype=None, icon=None):
		try:
			self.store.execute("""
				INSERT INTO Item
					(id, content_id, source_id, origin, text, mimetype, icon)
				VALUES (?,?,?,?,?,?,?)
				""", (id, content_id, source_id, origin, text, mimetype, icon))
		except:
			self.store.execute("""
				UPDATE Item SET
					content_id=?, source_id=?, origin=?, text=?,
					mimetype=?, icon=? WHERE id=?
				""", (content_id, source_id, origin, text, mimetype, icon, id))
	
	def insert_item(self, ritem, commit=True, force=False):
		"""
		Inserts an item into the database. Returns True on success,
		False otherwise (for example, if the item already is in the
		database).
		"""
		# we require all  all keys here
		missing = ITEM_STRUCTURE_KEYS - set(ritem.keys())
		if missing:
			raise KeyError(("these keys are missing in order to add "
							"this item properly: %s" %", ".join(missing)))
		if not ritem["uri"].strip():
			print >> sys.stderr, "Discarding item without a URI: %s" % ritem
			return False
		if not ritem["content"].strip():
			print >> sys.stderr, "Discarding item without a Content type: %s" % ritem
			return False
		if not ritem["source"].strip():
			print >> sys.stderr, "Discarding item without a Source type: %s" % ritem
			return False
		if not ritem["mimetype"].strip():
			print >> sys.stderr, "Discarding item without a mimetype: %s" % ritem
			return False
		
		ritem = dict((key, TYPES_DICT[key](value)) for key, value in ritem.iteritems())
		
		try:
			'''
			Init URI, Content and Source
			'''
			uri_id, content_id, source_id = self._get_basics(ritem["uri"],ritem["content"], ritem["source"])
			##########################################################################
			'''
			Create Item for Data
			'''
			item = self._get_item(uri_id, content_id, source_id, ritem["text"], ritem["origin"], ritem["mimetype"], ritem["icon"])
			
			##########################################################################
			'''
			 Extract tags
			'''
			for tag in ritem["tags"].split(","):
				tag = tag.strip()
				if not tag:
					# ignore empty tags
					continue
				anno_uri = "zeitgeist://tag/%s" % tag
				anno_id, x, y = self._get_basics(anno_uri,None,None)
				anno_item = self._get_item(anno_id, Content.TAG.id, Source.USER_ACTIVITY.id, tag)
				try:
					self.store.execute("INSERT INTO annotation (item_id, subject_id) VALUES (?,?)",(anno_id, uri_id))
				except Exception, ex:
					pass
			##########################################################################
			'''
			Bookmark
			'''
			if ritem["bookmark"]:
				
				anno_uri = "zeitgeist://bookmark/%s" % ritem["uri"]
				anno_id, x, y = self._get_basics(anno_uri,None,None)
				anno_item = self._get_item(anno_id, Content.BOOKMARK.id, Source.USER_ACTIVITY.id, u"Bookmark")
				try:
					self.store.execute("INSERT INTO annotation (item_id, subject_id) VALUES (?,?)",(anno_id, uri_id))
				except Exception, ex:
					pass
			##########################################################################
			if force:
				   return True
			##########################################################################
			'''
			Init App
			'''
			# Store the application
			app_info = DesktopEntry(ritem["app"])			
			app_uri_id, app_content_id, app_source_id = self._get_basics(ritem["app"], unicode(app_info.getType()), unicode(app_info.getExec()).split()[0])
			app_item = self._get_item(app_uri_id, app_content_id, app_source_id, unicode(app_info.getName()),icon=unicode(app_info.getIcon()) )
			try:
				self.store.execute("INSERT INTO app (item_id, info) VALUES (?,?)",(app_uri_id, unicode(ritem["app"])))
			except Exception, ex:
				pass
			##########################################################################
			'''
			Set event 
			'''
			e_uri = "zeitgeist://event/%s/%%s/%s#%d" % (ritem["use"],ritem["timestamp"], uri_id)		
			e_id , e_content_id, e_subject_id = self._get_basics(e_uri,ritem["use"],None )
			e_item = self._get_item(e_id, e_content_id, Source.USER_ACTIVITY.id, u"Activity")
			
			try:
				self.store.execute("INSERT INTO event (item_id, subject_id, start, app_id) VALUES (?,?,?,?)",
						   (e_id, uri_id, ritem["timestamp"] ,app_uri_id))
			except Exception, ex:
				print ex
			return True
										
		except Exception, ex:
			print ex
		
	
	def insert_items(self, items):
		"""
		Inserts items into the database and returns the amount of
		items it inserted.
		"""
		
		amount_items = 0
		
		# Check if event is before the last logs
		t1 = time.time()
		for item in items:
			if self.insert_item(item, commit=False):
				amount_items += 1
		self.store.commit()
		t2 = time.time()
		print ">>>>>> Inserted %s items in %ss" % (amount_items,t2-t1)
		
		return amount_items
	
	def get_item(self, uri):
		"""Returns basic information about the indicated URI."""
		item = self.store.find(Item, Item.id == URI.id,
			URI.value == unicode(uri)).one()		
		if item:
			return self._result2data(item=item)
	
	def find_events(self, min=0, max=sys.maxint, limit=0,
	sorting_asc=True, unique=False, filters=()):
		"""
		Returns all items from the database between the indicated
		timestamps `min' and `max'. Optionally the argument `tags'
		may be used to filter on tags or `mimetypes' to filter on
		mimetypes.
		
		Parameter filters is an array of structs containing: (text
		to search in the name, text to search in the URI, tags,
		mimetypes, source, content). The filter between characteristics
		inside the same struct is of type AND (all need to match), but
		between diferent structs it is OR-like (only the conditions
		described in one of the structs need to match for the item to
		be returned).
		"""
		
		# Emulate optional arguments for the D-Bus interface
		if not max: max = sys.maxint
		
		t1 = time.time()
		events = self.store.find(Event, Event.start >= min, Event.start <= max)
		events.order_by(Event.start if sorting_asc else Desc(Event.start))
		
		if limit > 0:
			events = events[:limit]
		if unique:
			events.max(Event.start)
			events.group_by(Event.subject_id)
		
		return [self._result2data(event) for event in events]
	
	def update_item(self, item):
		"""
		Updates an item already in the database.
		
		If the item has tags, then the tags will also be updated.
		"""
		
		#FIXME Delete all annotations of the ITEM
		self.delete_item(item)
		self.store.commit()
		self.store.flush()
		self.insert_item(item, True, True)
		self.store.commit()
		self.store.flush()
	
	def get_tags_for_item(self, item):
		package = []
		id = item.id
		tags = self.store.find(Annotation.item_id, Annotation.subject_id == id)
		for tag in tags:
			tag = self.store.find(Item.text, Item.id == tag).one()
			package.append(tag)
		return package
	
	def delete_item(self, item):
		
		uri_id = self.store.execute("SELECT id FROM URI WHERE value=?",(item["uri"],)).get_one()
		uri_id = uri_id[0]
		annotation_ids = self.store.execute("SELECT item_id FROM Annotation WHERE subject_id=?",(uri_id,)).get_all()
		if len(annotation_ids) > 0:
			for anno in annotation_ids[0]:
				self.store.execute("DELETE FROM Annotation WHERE subject_id=?",(uri_id,))
				self.store.execute("DELETE FROM Item WHERE id=?",(anno,))	
		
		self.store.execute("DELETE FROM Item WHERE id=?",(uri_id,))
		
		pass
	
	def get_types(self):
		"""
		Returns a list of all different types in the database.
		"""
		contents = self.store.find(Content)
		return [content.value for content in contents]
	
	def get_all_tags(self):
		"""
		Returns a list containing the name of all tags.
		"""		
		tags = self.store.find(Item, Item.content_id == Content.TAG.id)
		return [tag.text for tag in tags]
	
	def get_recently_used_tags(self, count=20, min=0, max=sys.maxint):
		"""
		Returns a list containing up to `count' recently used
		tags from between timestamps `min' and `max'.
		"""
		
		# FIXME: What do we consider "Recent"?
		# Does it make sense to returns a list of which were the last
		# tags given to applications? Maybe instead the GUI should keep
		# track itself of which Tags the users use when they filter
		# stuff and show those. Or remove this alltogether?
		return []
	
	def get_most_used_tags(self, count=20, min=0, max=sys.maxint):
		"""
		Returns a list containing up to the `count' most used
		tags from between timestamps `min' and `max'.
		"""
		
		# Simulate optional arguments
		if not count:
			count = 20
		if not max:
			max = sys.maxint
		
		tags = self.store.execute("""
			SELECT text, (SELECT COUNT(rowid)
				FROM annotation WHERE item_id=item.id) AS occurencies
			FROM item
			WHERE content_id=?
			ORDER BY occurencies DESC
			LIMIT ?
			""", (Content.TAG.id, count))
		
		return [tag[0] for tag in tags]
	
	def get_min_timestamp_for_tag(self, tag):
			return None
	
	def get_max_timestamp_for_tag(self, tag):
			return None
	
	def get_last_insertion_date(self, application):
		"""
		Returns the timestamp of the last item which was inserted
		related to the given application. If there is no such record,
		0 is returned.
		"""
		
		app = App.lookup(application)
		
		return self.store.find(Event.start, Event.app == app.item.id
			).order_by(Event.start).last() if app else 0
	
	def get_related_items(self, uri):
		pass
	
	def compare_nbhs(self,nbhs):
		pass
	
	def get_uris_for_timestamp(self, timestamp):
		pass
	
	def get_bookmarks(self):
		uris = self.store.find(URI, Item.content_id == Content.BOOKMARK.id, URI.id == Annotation.subject_id, Annotation.item_id == Item.id)
		for uri in uris:
			#Get the item for the uri
			item = self.store.find(Item, Item.id == uri.id).one()
			yield self._result2data(None, item)
                
_engine = None
def get_default_engine():
	global _engine
	if not _engine:
		_engine = ZeitgeistEngine(get_default_store())
	return _engine
