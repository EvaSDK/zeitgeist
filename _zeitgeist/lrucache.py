# -.- coding: utf-8 -.-

# lrucache.py
#
# Copyright © 2009 Mikkel Kamstrup Erlandsen <mikkel.kamstrup@gmail.com>
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

class LRUCache:
	"""A simple LRUCache implementation backed by a linked list and a dict.
	   It can be accessed and updated just like a dict. To check if an element
	   exists in the cache the following type of statements can be used:
	   
	       if "foo" in cache
	   """
	
	class _Item:		
		def __init__(self, item_id, item_key, item_value):
			self.id = item_id
			self.value = item_value
			self.key = item_key
			self.next = None
			self.prev = None
	
		def __cmp__(self, item):
			return cmp(self.id, item.id)
	
	def __init__(self, max_size):
		"""The size of the cache (in number of cached items) is guaranteed to
		   never exceed 'size'"""
		self._max_size = max_size
		self.clear()
	
	def setdefault(self, key, value):
		try:
			return self[key].value
		except KeyError:
			self[key] = value
			return value
	
	def clear(self):
		self._list_end = None # The newest item
		self._list_start = None # Oldest item
		self._map = {}
		self._current_id = 0		
	
	def __len__(self):
		return len(self._map)
	
	def __contains__(self, key):
		return key in self._map
	
	def __setitem__(self, key, value):
		if key in self._map:
			item = self._map[key]
			item.id = self._current_id
			item.value = value
			self._move_item_to_end(item)
		else:
			new = LRUCache._Item(self._current_id, key, value)
			self._map[key] = new
			self._append_to_list(new)

			if len(self._map) > self._max_size :
				# Remove eldest entry from list
				old = self.remove_eldest_item()				

		self._current_id += 1

	def __getitem__(self, key):
		item = self._map[key]
		item.id = self._current_id
		self._move_item_to_end(item)
		self._current_id += 1
		return item.value
	
	def __iter__(self):
		"""
		Iteration is in order from eldest to newest,
		and returns (key,value) tuples
		"""
		iter = self._list_start
		if iter is None:
			raise StopIteration
		yield (iter.key, iter.value)
		while iter.next:
			iter = iter.next
			yield (iter.key, iter.value)			
	
	def _move_item_to_end(self, item):
		if item.prev:
			item.prev.next = item.next
		if item.next:
			item.next.prev = item.prev
		if item == self._list_start:
			self._list_start = item.next
		self._append_to_list(item)
	
	def _append_to_list(self, item):
		if self._list_end:
			self._list_end.next = item
			item.prev = self._list_end
			item.next = None
			self._list_end = item
		else:
			self._list_start = item
			self._list_end = item
		
		if not self._list_start:
			self._list_start = item
	
	def remove_eldest_item(self):
		if self._list_start:
			old = self._list_start
			del self._map[old.key]
			self._list_start = self._list_start.next
			if self._list_start:
				self._list_start.prev = None
			return old

class LRUCacheMetaclass(type):
	""" Metaclass which has a _CACHE attribute, each subclass has its own,
	fresh cache. As a cache we are using a LRUCache.
	"""
	
	def __init__(cls, name, bases, d):
		super(LRUCacheMetaclass, cls).__init__(name, bases, d)
		cls._CACHE = LRUCache(500)
