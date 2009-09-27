# -.- coding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009 Markus Korn <thekorn@gmx.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import time
import logging
import gobject
import sys

from functools import wraps

from _zeitgeist.lrucache import LRUCache

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("zeitgeist.engine.engine_base")

def time_insert(function):
	@wraps(function)
	def wrapper(*args, **kwargs):
		t1 = time.time()
		result = function(*args, **kwargs)
		log.debug("Inserted %s events in %.5f s." % \
			(len(result[0]), time.time() - t1))
		return result
	return wrapper

class BaseEngine(gobject.GObject):
	
	ALLOWED_FILTER_KEYS = set(["name", "uri", "tags", "mimetypes",
		"source", "content", "application", "bookmarked"])
	
	def __init__(self):
		
		gobject.GObject.__init__(self)
		
		self._apps = set()
		self._last_time_from_app = {}
		self._applications = LRUCache(100)
		
	def insert_event(self, event, item, commit=True, force=False):
		"""
		Inserts an item into the database. Returns a positive number on success,
		zero otherwise (for example, if the item already is in the
		database). In case the positive number is 1, the inserted event is new,
		in case it's 2 the event already existed and was updated (this only
		happens when `force' is True).
		"""
		
		raise NotImplementedError
	
	@time_insert
	def insert_events(self, events, items, annotations = []):
		"""
		Inserts events and their related items into the database and returns
		those items which were successfully inserted. If an item fails, that's
		usually because it already was in the database.
		
		The third argument (annotations) is passed to set_annotations, and is
		only available as a shorthand.
		"""
		
		raise NotImplementedError
	
	def get_items(self, uris):
		""" Returns Item objects containing basic information about the
		indicated URIs."""
		
		raise NotImplementedError
	
	def find_events(self, min=0, max=sys.maxint, limit=0,
			sorting_asc=True, mode="event", filters=(), return_mode=0):
		"""
		Returns all items from the database between the indicated
		timestamps `min' and `max'. Optionally the argument `tags'
		may be used to filter on tags or `mimetypes' to filter on
		mimetypes.
		
		Parameter `mode' can be one of "event", "item" or "mostused".
		The first mode returns all events, the second one only returns
		the last event when items are repeated and the "mostused" mode
		is like "item" but returns the results sorted by the number of
		events.
		
		Parameter `filters' is an array of structs containing: (text
		to search in the name, text to search in the URI, tags,
		mimetypes, source, content). The filter between characteristics
		inside the same struct is of type AND (all need to match), but
		between diferent structs it is OR-like (only the conditions
		described in one of the structs need to match for the item to
		be returned).
		
		Possible values for return_mode, which is an internal variable
		not exposed in the API:
		 - 0: Return the events/items.
		 - 1: Return the amount of events/items which would be returned.
		 - 2: Return only the applications for the matching events.
		"""
		raise NotImplementedError
	
	# FIXME: update_items() appear unused so I commented it out // kamstrup
	#def update_items(self, items):
	#	raise NotImplementedError
	
	def delete_items(self, items):
		raise NotImplementedError
	
	def get_types(self):
		"""
		Returns a list of all different types in the database.
		"""
		raise NotImplementedError
	
	def get_tags(self, min_timestamp=0, max_timestamp=0, limit=0, name_filter=""):
		"""
		Returns a list containing tuples with the name and the number of
		occurencies of the tags matching `name_filter', or all existing
		tags in case it's empty, sorted from most used to least used. `limit'
		can base used to limit the amount of results.
		
		Use `min_timestamp' and `max_timestamp' to limit the time frames you
		want to consider.
		"""
		raise NotImplementedError
	
	def get_last_insertion_date(self, application):
		"""
		Returns the timestamp of the last item which was inserted
		related to the given application. If there is no such record,
		0 is returned.
		"""
		raise NotImplementedError
	
	def close(self):
		"""
		Close the engine and free any resources associated with it.
		After calling close() on an engine all other method calls will fail.		
		"""
		raise NotImplementedError
		
	def is_closed(self):
		"""
		Returns True if close() has been called on this engine instance
		"""
		raise NotImplementedError
