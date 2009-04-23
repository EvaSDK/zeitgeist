import sys
import os
from gettext import gettext as _
import gobject
import gc

from zeitgeist_engine.zeitgeist_base import DataProvider
from zeitgeist_dbcon import db
from zeitgeist_shared.zeitgeist_shared import *

sys.path.append(os.path.dirname(__file__))

class DataSinkSource(DataProvider):
	'''
	Aggregates all of the item-sources together and feeds them into the database when they update.
	'''
	
	def __init__(self, note_path=None):
		DataProvider.__init__(self,
							name=_("Sink"),
							icon=None,
							uri="source:///Datasink")
		self.sources = []
		self._sources_queue = []
		self.threads = []
		self.reload_callbacks = []
		
		self._db_update_in_progress = False
		
		logger_sources = {
			"recent": (
				"RecentlyUsedVideo", "RecentlyUsedMusic",
				"RecentlyUsedImages", "RecentlyUsedDocuments","RecentlyUsedOthers",
				),
			"firefox": ("Firefox",),
			"tomboy": ("Tomboy",),
			"evolution": ("Evolution",),
			# Missing: Pidgin, Twitter...
		}
		
		self.sources = []
		for namespace in logger_sources:
			sourcefile = __import__('zeitgeist_' + namespace)
			for item in logger_sources[namespace]:
				instance = getattr(sourcefile, item + "Source")()
				instance.connect("reload", self._update_db_with_source)
				self.sources.append(instance)
		
		# Update the database
		self._update_db()
	
	def _update_db(self):
		'''
		Add new items from all sources into the database.
		'''
		print "Adding all sources to update queue"
		
		# Update the list of sources;
		# (Note: It's important that we copy the list and don't just reference it.
		#  If we simply used 'self._sources_queue = self.sources' then removing items
		#  from the queue would also remove them from self.sources.)
		self._sources_queue = list(self.sources)
		
		# Add a new idle callback to update the db only if one doesn't already exist
		if not self._db_update_in_progress and len(self._sources_queue) > 0:
			self.db_update_in_progress = True
			gobject.idle_add(self._update_db_async)
	
	def _update_db_with_source(self, source):
		'''
		Add new items from source into the database. This funcion
		should not be called directly, but instead activated through
		the "reload" signal.
		'''
		
		# If the source is already in the queue then just return
		if source in self._sources_queue:
			return False
		
		print "Adding new source to update queue %s" % source
		# Add the source into the queue
		self._sources_queue.append(source)
		
		# Add a new idle callback to update the db only if one doesn't already exist
		if not self._db_update_in_progress and len(self._sources_queue) > 0:
			self.db_update_in_progress = True
			gobject.idle_add(self._update_db_async)
			
	def get_items(self, min=0, max=sys.maxint, tags=""):
		# Emulate optional argument for the D-Bus interface
		if not max: max = sys.maxint
		# Get a list of all tags/search terms
		# (Here, there's no reason to use sets, because we're not using python's "in"
		#  keyword for membership testing.)
		if not tags == "":
			tags = tags.replace(",", " ")
			tagsplit = [tag.lower() for tag in tags.split(" ")]
		else:
			tagsplit = []
		
		# Loop over all of the items from the database
		for item in db.get_items(min, max):
			# Check if the document type matches; If it doesn't then don't bother checking anything else
				matches = True
				# Loop over every tag/search term
				for tag in tagsplit:
					# If the document name or uri does NOT match the tag/search terms then skip this item
					if not tag in item[3].lower().split(',') and not item[0].lower().find(tag) > -1:
						matches = False
						break
				if matches:
					yield item
				del item
			
		gc.collect()
	
	def get_items_for_tag(self, tag):
		return (item for item in db.get_items_for_tag(tag))
	
	def get_bookmarks(self):
		return db.get_bookmarked_items()
	
	def update_item(self, item):
		print "Updating item: %s" % item
		db.update_item(item)		 
	
	def delete_item(self, item):
		print "Deleting item: %s" % item
		db.delete_item(item)
		# optimize this, no full reload required, so no signal should
		# be emitted, instead the GUI should know to delete it
		self.emit("reload")
	
	def get_items_by_time(self, min=0, max=sys.maxint, tags=""):
		"Datasink getting all items from DataProviders"
		return self.get_items(min, max, tags)
	
	def get_items_with_mimetype(self, mimetype, min=0, max=sys.maxint, tags=""):
		items = []
		for item in self.get_items_by_time(min, max, tags):
			if item[4] in mimetype.split(','):
				items.append(item)
		return items
	
	def _update_db_async(self):
		
		if len(self._sources_queue) > 0:
			print "Updating database with new %s items" % self._sources_queue[0].name
			# Update the database with items from the first source in the queue
			items = self._sources_queue[0].get_items()
			
			if db.insert_items(items):
				# If we inserted at least one item...
				# Propagate the reload signal to other interested
				# functions (eg., the D-Bus interface)
				for callback in self.reload_callbacks:
					callback()
					
			gc.enable()		
			gc.set_debug(gc.DEBUG_LEAK)
			# Remove the source from the queue
			del self._sources_queue[0]
			
			# If there are no more items in the queue then finish up
			if len(self._sources_queue) == 0:
				self.db_update_in_progress = False
				gc.collect()
				self.emit("reload")
				# Important: return False to stop this callback from being called again
				return False
			
			gc.collect()
			# Otherwise, if there are more items in the queue return True so that gtk+
			# will continue to call this function in idle cpu time
			return True
	
	def get_most_used_tags(self, count=20, min=0, max=sys.maxint):
		if not count: count = 20
		if not min: min = 0
		if not max: max = sys.maxint
		return db.get_most_tags(count, min, max)
	
	def get_recent_used_tags(self, count=20, min=0, max=sys.maxint):
		if not count: count = 20
		if not min: min = 0
		if not max: max = sys.maxint
		return db.get_recent_tags(count, min, max)
	
	def get_timestamps_for_tag(self, tag):
		begin = db.get_min_timestamp_for_tag(tag)
		end = db.get_max_timestamp_for_tag(tag)
		
		if end - begin > 86400:
			end = end + 86400
		
		return (begin, end)
	
	def get_related_items(self, item):
		return db.get_related_items(item)
	
	def get_items_related_by_tags(self, item):
		return db.get_items_related_by_tags(item)
	
	def insert_item(self, item):
		return db.insert_item(item)
	
	def get_sources_list(self):
		return [plainify_dataprovider(source) for source in self.sources]

datasink = DataSinkSource()
