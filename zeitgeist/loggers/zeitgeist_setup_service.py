# -.- encoding: utf-8 -.-

# Zeitgeist
#
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

import dbus
import dbus.service
import gobject
import gconf

import dbus.mainloop.glib
import ConfigParser

from ConfigParser import SafeConfigParser
from xdg import BaseDirectory
from StringIO import StringIO

class _Configuration(gobject.GObject):
	
	@staticmethod
	def like_bool(value):
		if isinstance(value, bool):
			return value
		elif value.lower() in ("true", "1", "on"):
			return True
		elif value.lower() in ("false", "0", "off"):
			return False
		else:
			raise ValueError
	
	def __init__(self, internal_name=None):
		gobject.GObject.__init__(self)
		self.__required = set()
		self.__items = dict()
		self.__internal_name = internal_name
		
	def get_internal_name(self):
		return self.__internal_name
		
	def add_option(self, name, type=str, default=None, required=True, secret=False):
		if name in self.__items:
			raise ValueError
		if required:
			self.__required.add(name)
		if type is None:
			type = lambda x: x
		self.__items[name] = (type(default), type, secret)
		
	def __getattr__(self, name):
		return self.__items[name][0]
		
	def get_as_string(self, name):
		return str(getattr(self, name))
		
	def set_attribute(self, name, value, check_configured=True):
		if name not in self.__items:
			raise ValueError
		_, type, secret = self.__items[name]
		self.__items[name] = (type(value), type, secret)
		if name in self.__required:
			self.remove_requirement(name)
		if check_configured and self.isConfigured():
			print "BOOO"
			import glib
			glib.idle_add(self.emit, "configured")
			print "BAR"
			
	def remove_requirement(self, name):
		self.__required.remove(name)
		
	def add_requirement(self, name):
		if not name in self.__items:
			raise ValueError
		self.__required.add(name)
		
	def isConfigured(self):
		return not self.__required
		
	def read_config(self, filename, section):
		config = SafeConfigParser()
		config.readfp(open(filename))
		if config.has_section(section):
			for name, value in config.items(section):
				self.set_attribute(name, value)
				
	def dump_config(self, config=None):
		section = self.get_internal_name()
		if config is None:
			config = SafeConfigParser()
		try:
			config.add_section(section)
		except ConfigParser.DuplicateSectionError:
			pass
		for key, value in self.__items.iteritems():
			value, _, secret = value
			if not secret:
				config.set(section, key, str(value))
		f = StringIO()
		config.write(f)
		return f.getvalue()
		
	def get_requirements(self):
		return self.__required
		
	def get_options(self):
		return [(str(key), key in self.__required) for key in self.__items]
			
		
gobject.signal_new("configured", _Configuration,
				   gobject.SIGNAL_RUN_LAST,
				   gobject.TYPE_NONE,
				   tuple())
				
				
class DefaultConfiguration(_Configuration):
	
	CONFIGFILE = BaseDirectory.load_first_config("zeitgeist", "dataprovider.conf")
	DEFAULTS = [
		("enabled", _Configuration.like_bool, True, False),
	]
	
	def __init__(self, dataprovider):
		super(DefaultConfiguration, self).__init__(dataprovider)
		for default in self.DEFAULTS:
			self.add_option(*default)
		if self.CONFIGFILE:
			self.read_config(self.CONFIGFILE, dataprovider)
				
	def save_config(self):
		if self.CONFIGFILE:
			config = SafeConfigParser()
			config.readfp(open(self.CONFIGFILE))
			self.dump_config(config)
			f = StringIO()
			config.write(f)
			with open(self.CONFIGFILE, "w") as configfile:
				config.write(configfile)
		
			

class MetaClass(dbus.service.InterfaceType, gobject.GObjectMeta):
	pass

class SetupService(dbus.service.Object, gobject.GObject):
	
	__metaclass__ = MetaClass
	
	def __init__(self, datasource, default_config=None, mainloop=None):
		bus_name = dbus.service.BusName("org.gnome.Zeitgeist.dataprovider", dbus.SessionBus())
		dbus.service.Object.__init__(self,
			bus_name, "/org/gnome/Zeitgeist/DataProvider/%s" %datasource)
		self._mainloop = mainloop
		gobject.GObject.__init__(self)
		self.__configuration = default_config or DefaultConfiguration
		if not isinstance(self.__configuration, _Configuration):
			raise TypeError
		self.__setup_is_running = None
		self.__configuration.connect_object("configured", self.emit, "reconfigured")
		
	def get_configuration(self):
		if self.needs_setup():
			raise RuntimeError("Needs Configuration")
		return self.__configuration
		
	@dbus.service.method("org.gnome.Zeitgeist.dataprovider",
						 in_signature="iss")
	def set_configuration(self, token, option, value):
		if token != self.__setup_is_running:
			raise RuntimeError("wrong client")
		self.__configuration.set_attribute(option, value)
		
	@dbus.service.signal("org.gnome.Zeitgeist.dataprovider")
	def NeedsSetup(self):
		pass
		
	@dbus.service.method("org.gnome.Zeitgeist.dataprovider",
						 in_signature="i", out_signature="b")
	def RequestSetupRun(self, token):
		if self.__setup_is_running is None:
			self.__setup_is_running = token
			return True
		else:
			raise False
		
	@dbus.service.method("org.gnome.Zeitgeist.dataprovider",
						 out_signature="a(sb)")
	def GetOptions(self, token):
		if token != self.__setup_is_running:
			raise RuntimeError("wrong client")
		return self.__configuration.get_options()		
			
	def needs_setup(self):
		return not self.__configuration.isConfigured()
		
gobject.signal_new("reconfigured", SetupService,
				   gobject.SIGNAL_RUN_LAST,
				   gobject.TYPE_NONE,
				   tuple())
		
		
if __name__ == '__main__':
	
	dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
	mainloop = gobject.MainLoop()
	
	config = _Configuration()
	config.add_option("enabled", Configuration.like_bool, False)
	object = SetupService("test", config, mainloop=None)
	mainloop.run()

