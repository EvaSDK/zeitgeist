#! /usr/bin/env python
# -.- coding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009 Siegfried-Angel Gevatter Pujals <rainct@ubuntu.com>
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

import sys
import os
import glob
import gettext
import logging
import gobject
import dbus.exceptions

from zeitgeist import _config
_config.setup_path()

from zeitgeist.client import ZeitgeistDBusInterface
from _zeitgeist.loggers.zeitgeist_setup_service import DataProviderService

gettext.install("zeitgeist", _config.localedir, unicode=1)
logging.basicConfig(level=logging.DEBUG)

sys.path.insert(0, _config.datasourcedir)

class DataHub(gobject.GObject):
	
	__gsignals__ = {
		"reload" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
	}
	
	def __init__(self):
		
		gobject.GObject.__init__(self)
		
		self._client = ZeitgeistDBusInterface()
		self._client.connect_exit(self._daemon_exit)
				
		# Load the data sources
		self._sources = []
		for datasource_file in glob.glob(_config.datasourcedir + '/*.py'):
			if not datasource_file.startswith('_'):
				self._load_datasource_file(os.path.basename(datasource_file))
		
		# Start by fetch new items from all sources
		self._sources_queue = list(self._sources)
		if not self._sources_queue:
			logging.warning(_("No passive loggers found, bye."))
			sys.exit(1) # Mainloop doesn't exist yet, exit directly
		self._db_update_in_progress = True
		gobject.idle_add(self._update_db_async)
		
		for source in self._sources:
			source.connect("reload", self._update_db_with_source)
		
		self._mainloop = gobject.MainLoop()
		self.dbus_service = DataProviderService(self._sources, None)
		self._mainloop.run()
	
	def _daemon_exit(self):
		self._mainloop.quit()
	
	def _load_datasource_file(self, datasource_file):
		
		try:
			datasource_object = __import__(datasource_file[:-3])
		except ImportError, err:
			logging.exception(_("Could not load file: %s" % datasource_file))
			return False
		
		if hasattr(datasource_object, "__datasource__"):
			object = datasource_object.__datasource__
			if hasattr(object, "__iter__"):
				self._sources.extend(object)
			else:
				self._sources.append(object)
	
	def _update_db_with_source(self, source):
		"""
		Add new items into the database. This funcion should not be
		called directly, but instead activated through the "reload"
		signal.
		"""
		
		if not source in self._sources_queue:
			self._sources_queue.append(source)
			if not self._db_update_in_progress:
				self._db_update_in_progress = True
				gobject.idle_add(self._update_db_async)
	
	def _update_db_async(self):
		
		logging.debug(_("Updating database with new %s items") % \
			self._sources_queue[0].get_name())
		
		events = self._sources_queue[0].get_items()
		if events:
			self._insert_events(self._sources_queue[0].get_name(), events)
		
 		del self._sources_queue[0]
		
		if len(self._sources_queue) == 0:
			self._db_update_in_progress = False
			return False # Return False to stop this callback
		
		# Otherwise, if there are more items in the queue return True so
		# that GTK+ will continue to call this function in idle CPU time
		return True
	
	def _insert_events(self, source_name, events):
		try:
			self._client.InsertEvents(events)
		except dbus.exceptions.DBusException, error:
			error = error.get_dbus_name()
			if error == "org.freedesktop.DBus.Error.ServiceUnknown":
				logging.warning(
					_("Lost connection to zeitgeist-daemon, terminating."))
				self._daemon_exit()
			else:
				logging.exception(_("Error logging item from \"%s\": %s" % \
					(source_name, error)))

datahub = DataHub()