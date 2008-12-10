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
from zeitgeist_twitter import TwitterSource

class DataSinkSource(DataProvider):
	def __init__(self, note_path=None):
		DataProvider.__init__(self,
							name=_("Sink"),
							icon=None,
							uri="source:///Datasink")
		self.sources=[]
		
		'''
		Recently Used
		'''
		
		self.videos=RecentlyUsedVideoSource()
		self.videos.start()
		self.music=RecentlyUsedMusicSource()
		self.music.start()
		self.images=RecentlyUsedImagesSource()
		self.images.start()
		self.docs=RecentlyUsedDocumentsSource()
		self.docs.start()
		self.others = RecentlyUsedOthersSource()
		self.others.start()
		recent_model.connect("reload", self.log)
		self.firefox = FirefoxSource()
		self.firefox.start()
		
		self.tomboy = TomboySource()
		self.tomboy.start()
		self.tomboy.connect("reload", self.log)
		
		
		self.twitter=TwitterSource()
		
		self.init_sources()
		
		self.log()
	
	def init_sources(self):
	   self.sources=[
					 self.docs,
					 self.firefox,
					 self.images,
					 self.music,
					 self.others,
					 self.twitter,
					 self.tomboy,
					 self.videos
					]
	   
	
	def log(self,x=None):
		for source in self.sources:
			db.insert_items(source.get_items())
			del source
			
		gc.collect()
		self.emit("reload")
			
	   
	def get_items(self,min=0,max=sys.maxint,tags=""):
		tags = tags.replace(",","")
		filters = []
		for source in self.sources:
			if source.get_active():
				filters.append(source.get_name())
			del source
		
		# Used for benchmarking
		time1 = time.time()
		tagsplit = tags.split(" ")
		#print "TAGS COUNT " + str(len(tagsplit))
		for item in db.get_items(min,max):
				counter = 0	
				for tag in tagsplit:
					try:
						if filters.index(item.type)>=0 and (item.tags.lower().find(tag)> -1 or item.uri.lower().find(tag)>-1):
							counter = counter +1
						if counter == len(tagsplit):
							yield item
					except:
						pass
					del item
		del filters
		
		time2 = time.time()
		print("Got all items: " + str(time2 -time1))
		gc.collect()
	
	def update_item(self,item):
		db.update_item(item)
		self.emit("reload")
	
	def get_items_by_time(self,min=0,max=sys.maxint,tags=""):
		"Datasink getting all items from DaraProviders"
		for item in self.get_items(min,max,tags):
			yield item

				
	def get_freq_items(self,min=0,max=sys.maxint):
		items =[]
		for source in self.sources:
			if source.get_active():
				sourcelist= source.get_freq_items(min,max)
				for i in range(5):
					try:
						items.append(sourcelist[i])
					except:
						pass
			del source
		items.sort(self.comparecount)
		for item in items:
			yield item
			del item
		del items
		gc.collect()

datasink= DataSinkSource()
