#!/usr/bin/python

# Update python path to use local zeitgeist module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _zeitgeist.engine.storm_base import create_store, set_store
from _zeitgeist.engine import storm_base as base, get_default_engine
from zeitgeist.datamodel import *
from _zeitgeist.engine.storm_engine import ZeitgeistEngine

from time import time
import unittest
import logging

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("test.benchmarks")

class EngineInsertTest (unittest.TestCase):
	"""
	This class tests the performance of clean inserts in the engine
	"""
	def setUp (self):
		storm_url = "sqlite:/tmp/benchmark.sqlite"
		db_file = storm_url.split(":")[1]
		if os.path.exists(db_file):
			os.remove(db_file)
		self.store = create_store(storm_url)
		set_store(self.store)
		self.engine = get_default_engine()
		
		# Assert before each test that the db is indeed empty
		self.assertEquals(0, self.store.find(base.URI).count())
		self.assertEquals(0, self.store.find(base.Item).count())
		self.assertEquals(0, self.store.find(base.Annotation).count())
		self.assertEquals(0, self.store.find(base.Event).count())
		
	def tearDown (self):
		self.store.close()
	
	def newDummyItem(self, uri):
		return {
			"uri" : uri,
			"content" : Content.DOCUMENT.uri,
			"source" : Source.FILE.uri,
			"app" : "/usr/share/applications/gnome-about.desktop",
			"timestamp" : 0,
			"text" : "Text",
			"mimetype" : "mime/type",
			"icon" : "stock_left",
			"use" : Content.CREATE_EVENT.uri,
			"origin" : "http://example.org",
			"bookmark" : False,
			"comment" : "This is a sample comment",
			"tags" : u""
		}
	
	def testInsert1000in200Chunks(self):
		batch = []
		full_start = time()
		for i in range(1,1001):
			batch.append(self.newDummyItem("test://item%s" % i))
			if len(batch) % 200 == 0:
				start = time()
				self.engine.insert_events(batch)
				log.info("Inserted 200 items in: %ss" % (time()-start))
				batch = []
		log.info("Total insertion time for 1000 items: %ss" % (time()-full_start))
	
	def testURICreation(self):
		start = time()	
		for i in range(1,1001):
			base.URI("test://item%s" % i)
		self.store.commit()
		print "Inserted 1000 URIs with Storm in: %ss" % (time()-start)
		self.tearDown()
		self.setUp()
		start = time()
		for i in range(1,1001):
			self.store.execute("INSERT INTO uri(value) VALUES ('test://item%s')" % i)
		self.store.commit()
		print "Inserted 1000 URIs with raw Sql in: %ss" % (time()-start)

if __name__ == '__main__':
	unittest.main()
