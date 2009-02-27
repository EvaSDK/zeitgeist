import sys
import time
import urllib
from gettext import gettext as _

from zeitgeist_engine.zeitgeist_base import DataProvider
from zeitgeist_engine.zeitgeist_firefox import *
from zeitgeist_engine.zeitgeist_tomboy import *
from zeitgeist_engine.zeitgeist_recent import *
from zeitgeist_engine.zeitgeist_dbcon import db
from zeitgeist_util import difffactory
from zeitgeist_engine.zeitgeist_evolution import EvolutionSource
#from zeitgeist_twitter import TwitterSource

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
		self._db_update_in_progress = False
		
		# Recently used items
		self.videos=RecentlyUsedVideoSource()
		self.videos.connect("reload", self.update_db_with_source)
		self.videos.start()
		self.music=RecentlyUsedMusicSource()
		self.music.connect("reload", self.update_db_with_source)
		self.music.start()
		self.images=RecentlyUsedImagesSource()
		self.images.connect("reload", self.update_db_with_source)
		self.images.start()
		self.docs=RecentlyUsedDocumentsSource()
		self.docs.connect("reload", self.update_db_with_source)
		self.docs.start()
		self.others = RecentlyUsedOthersSource()
		self.others.connect("reload", self.update_db_with_source)
		self.others.start()
		
		
		# Firefox
		self.firefox = FirefoxSource()
		self.firefox.connect("reload", self.update_db_with_source)
		self.firefox.start()
		
		#Evolution
		
		self.evo = EvolutionSource()
		self.evo.start()
		
		# Pidgin
		
		# Tomboy
		self.tomboy = TomboySource()
		self.tomboy.start()
		self.tomboy.connect("reload", self.update_db_with_source)
		
		# Twitter
		#self.twitter=TwitterSource()
		#self.twitter.start()
		
		self.items=[]
		# Initialize all sources
		self.init_sources()
		
		# Update the database
		self.update_db()
	
	def init_sources(self):
	   self.sources=[
					 self.docs,
					 self.firefox,
					 self.images,
					 self.music,
					 self.others,
					 self.evo,
					 self.tomboy,
					 self.videos
					]
	   
	def update_db(self):
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
		
	def update_db_with_source(self, source):
		'''
		Add new items from source into the database.
		'''
		# If the source is already in the queue then just return
		if source in self._sources_queue:
			return False
		
		print "Adding new source to update queue %s" % source
		# Add the source into the queue
		self._sources_queue.append(source)
		
		# Add a new idle callback to update the db only if one doesn't already existt
		if not self._db_update_in_progress and len(self._sources_queue) > 0:
			self.db_update_in_progress = True
			gobject.idle_add(self._update_db_async)
			
	def get_items(self, min=0, max=sys.maxint, tags="",cached=False):
		# Get a list of all document types that we're interested in
		types = []
		self.items=[]
		for source in self.sources:
			if source.get_active():
				types.append(source.get_name())
		# For efficiency, we convert the list to an immutable set
		# Immutable sets (and regular sets) allow us to perform membership testing in O(1)
		#  time. Lists, on the other hand, perform membership testing in O(n) time.
		types = frozenset(types)
		
		# Get a list of all tags/search terms
		# (Here, there's no reason to use sets, because we're not using python's 'in' 
		#  keyword for membership testing.)
		if not tags == "":
			tags = tags.replace(",", "")
			tagsplit = tags.split(" ")
		else:
			tagsplit = []
		
		# Loop over all of the items from the database
		if cached==False or len(self.items)==0:
			print "GETTING UNCACHED"
			for item in db.get_items(min, max):
				if not self.items.__contains__(item):
					self.items.append(item)
					# Check if the document type matches; If it doesn't then don't bother checking anything else
					if item.type in types:
						matches = True
						# Loop over every tag/search term
						for tag in tagsplit:
							# If the document name or uri does NOT match the tag/search terms then skip this item
							if not item.tags.lower().find(tag)> -1 and not item.uri.lower().find(tag)>-1:
								matches = False
								break
						if matches:
							yield item
		else:
			print "GETTING CACHED"
			for item in self.items:
				# Check if the document type matches; If it doesn't then don't bother checking anything else
				if item.type in types:
					matches = True
					# Loop over every tag/search term
					for tag in tagsplit:
						# If the document name or uri does NOT match the tag/search terms then skip this item
						if not item.tags.lower().find(tag)> -1 and not item.uri.lower().find(tag)>-1:
							matches = False
							break
					if matches:
						yield item
						
		gc.collect()
	
	def update_item(self, item):
		print "Updating item: %s" % item
		db.update_item(item)
		self.emit("reload")
	
	def get_items_by_time(self, min=0, max=sys.maxint, tags="", cached=False):
		"Datasink getting all items from DataProviders"
		for item in self.get_items(min, max, tags,cached):
			yield item
	
	def _update_db_async(self):
		if len(self._sources_queue) > 0:
			print "Updating database with new %s items" % self._sources_queue[0].name
			# Update the database with items from the first source in the queue
			db.insert_items(self._sources_queue[0].get_items())
			
			# Remove the source from the queue
			del self._sources_queue[0]
			
			# If there are no more items in the queue then finish up
			if len(self._sources_queue) == 0:
				self.db_update_in_progress = False
				gc.collect()
				self.emit("reload")
				# Important: return False to stop this callback from being called again
				return False
			
			# Otherwise, if there are more items in the queue return True so that gtk+
			#  will continue to call this function in idle cpu time
			return True

	def get_most_used_tags(self,count=10):
		for tag in db.get_most_tags(count):
			yield tag

	def get_related_items(self,item):
		for i in db.get_related_items(item):
		  yield i
		  
		  
datasink= DataSinkSource()
