#! /usr/bin/env python
# -.- encoding: utf-8 -.-

import sys
import os
import glob
import gettext
import gobject

gettext.install('gnome-zeitgeist', '/usr/share/locale', unicode=1)

installation_dir = os.path.dirname(os.path.realpath(__file__))
datasource_dir = os.path.join(installation_dir, 'datasources')
sys.path.extend((os.path.join(installation_dir, '../'), datasource_dir))

from zeitgeist_shared.zeitgeist_dbus import iface
from zeitgeist_shared.zeitgeist_shared import plainify_dict

class DataHub(gobject.GObject):
	
	__gsignals__ = {
		"reload" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
	}
	
	def __init__(self):
		
		gobject.GObject.__init__(self)
		
		# Load the data sources
		self._sources = []
		for datasource_file in glob.glob(datasource_dir + '/*.py'):
			self._load_datasource_file(os.path.basename(datasource_file))
		for source in self._sources:
			source.connect("reload", self._update_db_with_source)
		
		# Start by fetch new items from all sources
		self._sources_queue = list(self._sources)
		self._db_update_in_progress = True
		gobject.idle_add(self._update_db_async)
	
	def _load_datasource_file(self, datasource_file):
		
		try:
			datasource_object = __import__(datasource_file[:-3])
		except ImportError, err:
			print _("Error: Could not load file: %s" % datasource_file)
			print " ->", err
			return False
		
		if hasattr(datasource_object, "__datasource__"):
			object = datasource_object.__datasource__
			if hasattr(object, "__iter__"):
				self._sources.extend(object)
			else:
				self._sources.append(object)
	
	def _update_db_with_source(self, source):
		'''
		Add new items into the database. This funcion should not be
		called directly, but instead activated through the "reload"
		signal.
		'''
		
		if not source in self._sources_queue:
			print "Adding new source to update queue: %s" % source # TODO: Remove this
			self._sources_queue.append(source)
			if not self._db_update_in_progress:
				self.db_update_in_progress = True
				gobject.idle_add(self._update_db_async)
	
	def _update_db_async(self):
		
		print _("Updating database with new %s items") % \
			self._sources_queue[0].name
		items = self._sources_queue[0].get_items()
		if items:
			iface.insert_items([plainify_dict(item) for item in items])
		del self._sources_queue[0]
		
		if len(self._sources_queue) == 0:
			self.db_update_in_progress = False
			return False # Return False to stop this callback
		
		# Otherwise, if there are more items in the queue return True so
		# that GTK+ will continue to call this function in idle CPU time
		return True

datahub = DataHub()
