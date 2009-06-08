# -.- encoding: utf-8 -.-

import time
import sys
import os
import shutil
import sqlite3
import gettext
import gobject
from xdg import BaseDirectory

from zeitgeist import config
from zeitgeist.shared.zeitgeist_shared import *
from zeitgeist.engine.base import *

class ZeitgeistEngine(gobject.GObject):
	
	def __init__(self):
		
		gobject.GObject.__init__(self)
		self.reload_callback = None
		'''
		path = BaseDirectory.save_config_path("zeitgeist")
		database = os.path.join(path, "zeitgeist.sqlite")
		self.connection = self._get_database(database)
		self.cursor = self.connection.cursor()
		'''
		self._apps = set()
	
	def _result2data(self, result, timestamp=0, start=0, end=sys.maxint, app="", usage=""):
		
		res = self.cursor.execute(
			"""SELECT tagid FROM tags WHERE uri = ?""",(result[0],)
			).fetchall()
		
		tags = ",".join([unicode(tag[0]) for tag in res]) or ""
		
		return (
			timestamp,
			result[0], # uri
			result[1], # name
			result[6] or "N/A", # type
			result[5] or "N/A", # mimetype
			tags, # tags
			result[2] or "", # comment
			usage, # use
			result[4], # bookmark
			result[3], # icon
			app, # app
			)
	
	def get_count_for_item(self, uri, start=0, end=sys.maxint):
		# Emulate optional arguments for D-Bus
		if not end:
			end = sys.maxint
		
		query = "SELECT COUNT(uri) FROM timetable where start >=? and end<=? and uri=?"
		result = self.cursor.execute(query,(start, end, uri,)).fetchone()
		return result[0]
	
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
	
	def _get_database(self, database):
		"""
		Return a connection to the indicated SQLite 3 database. If
		it doesn't already exist, create it. If something fails, abort
		the execution with error code 1.
		"""
		
		if not os.path.isfile(database):
			try:
				# Copy the empty database skeleton into .zeitgeist
				shutil.copy("%s/zeitgeist.sqlite" % config.pkgdatadir, database)
			except OSError, e:
				print _("Could not create database: %s") % e.strerror
				sys.exit(1)
		
		try:
			connection = sqlite3.connect(database, True,
				check_same_thread = False)
		except sqlite3.OperationalError, error:
			print _("Error connecting with database: %s") % error
			sys.exit(1)
		else:
			return connection
	
	def get_last_timestamp(self, uri=None):
		"""
		Gets the timestamp of the most recent item in the database. If
		`uri' is not empty, it will give the last timestamp for the
		indicated URI.
		
		Returns 0 if there are no items in the database.
		"""
		
		if uri:
			filter = "WHERE uri=\"%s\"" % uri
		else:
			filter = ""
		
		query = "SELECT * FROM timetable %s LIMIT 1" % filter
		
		result = self.cursor.execute(query).fetchone()
		if result is None:
			return 0
		else:
			return result[0]
	
	def insert_item(self, ritem, commit=True):
		"""
		Inserts an item into the database. Returns True on success,
		False otherwise (for example, if the item already is in the
		database).
		"""
		
		
		try:		
			'''
			Init Item
			'''		
			item = Item(ritem["uri"])		
			item.content = Content(ritem["type"])
			item.source = Source(u"file")
			item.text = unicode(ritem["name"])
			
			if commit:
				store.commit()
			'''
			# Insert into timetable
			self.cursor.execute('INSERT INTO timetable VALUES (?,?,?,?,?,?)',
				(item["timestamp"],
				None,
				item["uri"],
				item["use"],
				"%d-%s" % (item["timestamp"], item["uri"]),
				item["app"]
				))
			# Insert into timetable
			
			
			# Insert into data, if it isn't there yet
			try:
				self.cursor.execute('INSERT INTO data VALUES (?,?,?,?,?,?,?)',
					(item["uri"],
					item["name"],
					item["comment"],
					item["icon"],
					0,
					item["mimetype"],
					item["type"]))
			except sqlite3.IntegrityError:
				pass
			
			try:
				# Add tags into the database
				for tag in (tag.strip() for tag in item["tags"].split(",") if tag.strip()):
					self.cursor.execute('INSERT INTO tags VALUES (?,?)',
						(tag.capitalize(), item["uri"]))
			except Exception, ex:
				print "Error inserting tags: %s" % ex
			
			if not item["app"] in self._apps:
				self._apps.add(item["app"])
				try:
					# Add app into the database
					self.cursor.execute('INSERT INTO app VALUES (?,?)',
						(item["app"],0))
				except Exception, ex:
					print "Error inserting application: %s" % ex
		'''
		except sqlite3.IntegrityError, ex:
			return False
		
		else:
			return True
	
	def insert_items(self, items):
		"""
		Inserts items into the database and returns the amount of
		items it inserted.
		"""
		amount_items = 0
		for item in items:
			# Insert without committing. We commit it as one transaction later
			if self.insert_item(item, commit=False):
				amount_items += 1
		
		#self.connection.commit()
		store.commit()
		print "DONE"
		return amount_items
	
	def get_item(self, uri):
		"""Returns basic information about the indicated URI."""
		
		item = self.cursor.execute(
			"""SELECT * FROM data WHERE data.uri=?""", (uri,)).fetchone()
		
		if item:
			return self._result2data(item)
	
	def get_items(self, min=0, max=sys.maxint, tags="", mimetypes=""):
		"""
		Yields all items from the database between the indicated
		timestamps `min' and `max'. Optionally the argument `tags'
		may be used to filter on tags.
		"""
		func = self._result2data
		
		# Emulate optional arguments for the D-Bus interface
		if not max: max = sys.maxint
		
		# Get a list of all tags
		if tags:
			tagsql = []
			for tag in tags.split(","):
				tagsql.append("""(data.uri LIKE '%%%s%%'
					OR data.name LIKE '%%%s%%' OR '%s' in
					(SELECT tags.tagid FROM tags
						WHERE tags.uri=data.uri))""" % (tag, tag, tag))
			condition = "(" + " AND ".join(tagsql) + ")"
		else:
			condition = "1"
		
		if mimetypes:
			condition += " AND data.mimetype IN (%s)" % \
				",".join(("\"%s\"" % mime for mime in mimetypes.split(",")))
		
		# Loop over all items in the timetable table which are between min and max
		query = """
			SELECT start, data.uri, app, usage FROM timetable
			JOIN data ON (data.uri=timetable.uri)
			WHERE usage != 'linked' AND start >= ? AND start <= ?
			AND %s
			ORDER BY start ASC
			""" % condition
		#print query
		res = self.cursor.execute(query, (str(min), str(max))).fetchall()
		pack = []
		for start, uri, app, usage in res:
			# Retrieve the item from the data table
			# TODO: Integrate this into the previous SQL query.
			item = self.cursor.execute(
				"""SELECT * FROM data WHERE data.uri=?""", (uri,)).fetchone()
			
			if item:
				item = func(item, timestamp = start, usage=usage, app=app)
				print item
				pack.append(item)
		return pack
	
	def update_item(self, item):
		"""
		Updates an item already in the database.
		
		If the item has tags, then the tags will also be updated.
		"""
		# Delete this item from the database if it's already present.
		self.cursor.execute('DELETE FROM data where uri=?',(item["uri"],))
		
		# (Re)insert the item into the database
		self.cursor.execute('INSERT INTO data VALUES (?,?,?,?,?,?,?)',
							 (item["uri"],
								unicode(item["name"]),
								item["comment"],
								item["icon"],
								item["bookmark"],
								item["mimetype"],
								item["type"]))
		self.connection.commit()
		
		# Delete old tags for this item
		self.cursor.execute('DELETE FROM tags where uri=?', (item["uri"],))
		
		# (Re)insert tags into the database
		for tag in (tag.strip() for tag in item["tags"].split(",") if tag.strip()):
			try:
				self.cursor.execute('INSERT INTO tags VALUES (?,?)',
					(unicode(tag.capitalize()), item["uri"]))
			except sqlite3.IntegrityError:
				pass
		self.connection.commit()
	
	def delete_item(self, item):
		item_uri = self._ensure_item(item, uri_only=True)
		self.cursor.execute('DELETE FROM data where uri=?', (item_uri,))
		self.cursor.execute('DELETE FROM tags where uri=?', (item_uri,))
		self.connection.commit()
	
	def _get_tags(self, order_by, count, min, max):
		"""
		Private class used to retrive a list of tags according to a
		desired condition (eg., most used tags, recently used tags...).
		"""
		
		# We simulate optional values in D-Bus; reset the defaults
		if not count: count = 20
		if not max: max = sys.maxint
		
		# TODO: This is awful.
		
		uris = [] 
		tags = []
		
		# Get uri's in in time interval sorted desc by time
		query = """SELECT uri 
				FROM timetable
				WHERE usage != 'linked'
					AND start >= ?
					AND start <= ?
				ORDER BY %s DESC""" % order_by
		
		for uri in self.cursor.execute(query, (str(int(min)), str(int(max)))).fetchall():
			
			# Retrieve the item from the data table:
			uri = uri[0]
			
			if uris.count(uri) <= 0 and len(tags) < count:
				uris.append(uri)
				uri = self.cursor.execute(
					"SELECT * FROM data WHERE uri=?", (uri,)).fetchone()
			
			if uri:
				res = self.cursor.execute(
					"""SELECT tagid FROM tags WHERE uri = ?""",
					(uri[0],)).fetchall()
			
				for tag in res:
					tag = unicode(tag[0])
					if tags.count(tag) <= 0:
						if len(tags) < count:
							tags.append(tag)
				
				if len(tags) == count:
					break
		
		return tags
	
	def get_all_tags(self):
		"""
		Returns a list containing the name of all tags.
		"""
		
		for tag in self.cursor.execute(
		"SELECT DISTINCT(tagid) FROM tags").fetchall():
			yield unicode(tag[0])
	
	def get_types(self):
		"""
		Returns a list of all different types in the database.
		"""
		
		for type, icon in self.cursor.execute(
		"SELECT DISTINCT(type), icon FROM data").fetchall():
			yield(unicode(type), icon)
	
	def get_recently_used_tags(self, count=20, min=0, max=sys.maxint):
		"""
		Returns a list containing up to `count' recently used
		tags from between timestamps `min' and `max'.
		"""
		
		return self._get_tags("key", count, min, max)
	
	def get_most_used_tags(self, count=20, min=0, max=sys.maxint):
		"""
		Returns a list containing up to the `count' most used
		tags from between timestamps `min' and `max'.
		"""
		
		return self._get_tags("uri", count, min, max)
	
	def get_min_timestamp_for_tag(self, tag):
		res = self.cursor.execute("""
			SELECT
				(SELECT min(start) FROM timetable WHERE uri=tags.uri)
				AS value
			FROM tags WHERE tagid=?
			ORDER BY value ASC LIMIT 1
			""", (tag,)).fetchall()
		if res:
			return res[0][0]
		else:
			return None
	
	def get_max_timestamp_for_tag(self, tag):
		res = self.cursor.execute("""
			SELECT
				(SELECT max(start) FROM timetable WHERE uri=tags.uri)
				AS value
			FROM tags WHERE tagid=?
			ORDER BY value DESC LIMIT 1
			""", (tag,)).fetchall()
		if res:
			return res[0][0]
		else:
			return None
	
	def get_timestamps_for_tag(self, tag):
		
		begin = self.get_min_timestamp_for_tag(tag)
		end = self.get_max_timestamp_for_tag(tag)
		
		if begin and end:
			if end - begin > 86400:
				# TODO: Why do we do this?
				end = end + 86400
		else:
			begin = end = 0
		
		return (begin, end)
	
	def get_items_related_by_tags(self, item):
		
		# TODO: Is one matching tag enough or should more/all of them
		# match?
		for tag in self._ensure_item(item)[4]:
			res = self.cursor.execute('SELECT uri FROM tags WHERE tagid=? GROUP BY uri ORDER BY COUNT(uri) DESC', (tag,)).fetchall()
			for raw in res:
				item = self.cursor.execute("SELECT * FROM data WHERE uri=?", (raw[0],)).fetchone()
				if item:
					yield self._result2data(item)
	
	def get_related_items(self, uri):
		
		print uri
		print "\n\n\n"
		list = []
		dict = {}
		radius = 120 #radius is half a day

		'''
		Create pins to create neighbourhoods around 
		'''
		results = self.cursor.execute( "SELECT start FROM timetable WHERE uri=? ORDER BY start",
			( uri, ) ).fetchall()
		pins = [r[0] for r in results]

		'''
		Determine neighbourhoods
		'''
		nbhs = {}
		for p in pins:

			start = p - radius
			end = p + radius

			info = {"start":start, "pin":p, "end":end, "uri":uri}

			try:
				start = ( p + pins[pins.index( p ) - 1] ) / 2
				print + "+ " + start + " +"
				if p - start < radius:
					info["start"] = start
			except Exception, ex:
				pass

			try:
				end = ( p + pins[pins.index( p ) + 1] ) / 2
				if end - p < radius:
						info["end"] = end
			except Exception, ex:
				pass
			
			nbh = []
			for i in self.get_items(info["start"],info["end"]):
				nbh.append(i)
			nbhs[p] = nbh 
		
		self.compare_nbhs(nbhs)		

		'''
		get items for each nbh and store in a list in a hash'
		'''
		for item in self.common_items.values():
			if item[1] >= 3:
				print len(nbhs)
				yield item[0]
	

	def compare_nbhs(self,nbhs):
		self.common_items = {}
		for nbh in nbhs.values():
			try:
				for item in nbh:
					for tempnbh in nbhs.values(): 
						for tempitem in tempnbh:
							if tempitem[2] == item[2]:
								if self.common_items.has_key(item[2]):
								    self.common_items[item[2]][1] +=1
								else:
								    self.common_items[item[2]] = [item,1]
									
			except Exception, ex:
				print "\n"
				print ex
				print "\n"
	
	
	def get_items_with_mimetype(self, mimetype, min=0, max=sys.maxint, tags=""):
		return self.get_items(min, max, tags, mimetype)
	
	def get_uris_for_timestamp(self, timestamp):
		return [x[0] for x in
			self.cursor.execute("SELECT uri FROM timetable WHERE start=?",
			(timestamp,)).fetchall()]
	
	def get_bookmarks(self):
		for item in self.cursor.execute("SELECT * FROM data WHERE boomark=1").fetchall():
			yield self._result2data(item, timestamp = -1)

engine = ZeitgeistEngine()
