# -.- coding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009 Siegfried-Angel Gevatter Pujals <rainct@ubuntu.com>
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

import dbus
import dbus.service
import dbus.mainloop.glib
import logging
import os.path
import sys
import logging

from xml.dom.minidom import parseString as minidom_parse

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

from zeitgeist.datamodel import (Event, Subject, TimeRange, StorageState,
	ResultType)

SIG_EVENT = "asaasay"

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("zeitgeist.client")

class ZeitgeistDBusInterface(dbus.Interface):
	""" Central DBus interface to the zeitgeist engine
	
	There does not necessarily have to be one single instance of this
	interface class, but all instances should share the same state
	(like use the same bus and be connected to the same proxy). This is
	achieved by extending the `Borg Pattern` as described by Alex Martelli	
	"""
	__shared_state = {"extension_interfaces": {}}
	
	BUS_NAME = "org.gnome.zeitgeist.Engine"
	INTERFACE_NAME = "org.gnome.zeitgeist.Log"
	OBJECT_PATH = "/org/gnome/zeitgeist/log/activity"
	
	@staticmethod
	def get_members(introspection_xml):
		"""Parses the xml context returned by Introspect() and returns
		a tuple, where the first item is a list of all methods and the
		second one a list of all signals for the related interface
		"""
		doc = minidom_parse(introspection_xml)
		nodes = doc.getElementsByTagName("signal")
		signals = [node.getAttribute("name") for node in nodes]
		nodes = doc.getElementsByTagName("method")
		methods = [node.getAttribute("name") for node in nodes]
		try:
			methods.remove("Introspect") # Introspect is not part of the API
		except ValueError:
			pass
		return methods, signals
	
	@classmethod
	def get_session_bus(cls):
		"""Returns the bus used by the interface.
		
		If there is no bus set, the '_bus' attribute is set to
		dbus.SessionBus() and returned
		"""
		return cls.__shared_state.setdefault("_bus", dbus.SessionBus())
	
	@classmethod
	def _get_proxy(cls):
		"""Returns the proxy instance used by the interface.
		
		If the current interface has no proxy object set, it tries to
		generate one. If this fails because no zeitgeist-daemon is
		running a RuntimeError will be raised
		"""
		try:
			return cls.__shared_state["proxy_object"]
		except KeyError, e:
			bus = cls.get_session_bus()
			try:
				cls.__shared_state["proxy_object"] = bus.get_object(
					cls.BUS_NAME,
					cls.OBJECT_PATH
				)
			except dbus.exceptions.DBusException, e:
				if e.get_dbus_name() == "org.freedesktop.DBus.Error.ServiceUnknown":
					raise RuntimeError(("Found no running instance of the "
						"Zeitgeist daemon: %s") % e.get_dbus_message())
				else:
					raise
			else:
				introspection_xml = cls.__shared_state["proxy_object"].Introspect()
				methods, signals = cls.get_members(introspection_xml)
				cls.__shared_state["__methods"] = methods
				cls.__shared_state["__signals"] = signals
			return cls.__shared_state["proxy_object"]
	
	@classmethod
	def connect(cls, signal, callback, arg0=None):
		"""Connect a callback to a signal of the current proxy instance """
		proxy = cls._get_proxy()
		if signal not in cls.__shared_state["__signals"]:
			raise TypeError("unknown signal name: %s" %signal)
		if arg0 is None:
			proxy.connect_to_signal(
				signal,
				callback,
				dbus_interface=cls.INTERFACE_NAME
			)
		else:
			# TODO: This is ugly and limited to 1 argument. Find a better
			# way to do it.
			proxy.connect_to_signal(
				signal,
				callback,
				dbus_interface=cls.INTERFACE_NAME,
				arg0=arg0
			)
			
	@classmethod
	def connect_exit(cls, callback):
		"""Executes callback when the RemoteInterface exists"""
		bus = cls.get_session_bus()
		bus_obj = bus.get_object(dbus.BUS_DAEMON_IFACE, dbus.BUS_DAEMON_PATH)
		bus_obj.connect_to_signal(
			"NameOwnerChanged",
			lambda *args: callback(),
			dbus_interface=dbus.BUS_DAEMON_IFACE,
			arg0=cls.BUS_NAME, #only match dying zeitgeist engines
			arg2="", #only match services with no new owner
		)
		
	@classmethod
	def version(cls):
		"""Returns the API version"""
		proxy = cls._get_proxy()
		return proxy.get_dbus_method("Get",
			dbus_interface=dbus.PROPERTIES_IFACE)(cls.INTERFACE_NAME, "version")
	
	@classmethod
	def get_extension(cls, name, path):
		""" Returns an interface to the given extension.
		
		Example usage:
			>> reg = get_extension("DatasourceRegistry", "datasource_registry")
			>> reg.RegisterDatasource(...)
		"""
		
		if not name in cls.__shared_state["extension_interfaces"]:
			proxy = cls.get_session_bus().get_object(
			"org.gnome.zeitgeist.Engine", "/org/gnome/zeitgeist/%s" % path)
			cls.__shared_state["extension_interfaces"][name] = dbus.Interface(
			    proxy, "org.gnome.zeitgeist.%s" % name)
		return cls.__shared_state["extension_interfaces"][name]
	
	def __init__(self):
		self.__dict__ = self.__shared_state
		proxy = self._get_proxy()
		dbus.Interface.__init__(
				self,
				proxy,
				self.INTERFACE_NAME
		)

class Monitor(dbus.service.Object):
	"""
	DBus interface for monitoring the Zeitgeist log for certain types
	of events.
	
	When using the Python bindings monitors are normally instantiated
	indirectly by calling :meth:`ZeitgeistClient.install_monitor`.
	
	It is important to understand that the Monitor instance lives on the
	client side, and expose a DBus service there, and the Zeitgeist engine
	calls back to the monitor when matching events are registered.
	"""
	
	# Used in Monitor._next_path() to generate unique path names
	_last_path_id = 0

	def __init__ (self, time_range, event_templates, insert_callback,
		delete_callback, monitor_path=None):
		if not monitor_path:
			monitor_path = Monitor._next_path()
		elif isinstance(monitor_path, (str, unicode)):
			monitor_path = dbus.ObjectPath(monitor_path)
		
		self._time_range = time_range
		self._templates = event_templates
		self._path = monitor_path
		self._insert_callback = insert_callback
		self._delete_callback = delete_callback
		dbus.service.Object.__init__(self, dbus.SessionBus(), monitor_path)

	
	def get_path (self): return self._path
	path = property(get_path,
		doc="Read only property with the DBus path of the monitor object")
	
	def get_time_range(self): return self._time_range
	time_range = property(get_time_range,
		doc="Read only property with the :class:`TimeRange` matched by this monitor")
	
	def get_templates (self): return self._templates
	templates = property(get_templates,
		doc="Read only property with installed templates")
	
	@dbus.service.method("org.gnome.zeitgeist.Monitor",
	                     in_signature="(xx)a("+SIG_EVENT+")")
	def NotifyInsert(self, time_range, events):
		"""
		Receive notification that a set of events matching the monitor's
		templates has been recorded in the log.
		
		This method is the raw DBus callback and should normally not be
		overridden. Events are received via the *insert_callback*
		argument given in the constructor to this class.
		
		:param time_range: A two-tuple of 64 bit integers with the minimum
		    and maximum timestamps found in *events*. DBus signature (xx)
		:param events: A list of DBus event structs, signature a(asaasay)
		    with the events matching the monitor.
		    See :meth:`ZeitgeistClient.install_monitor`
		"""
		self._insert_callback(TimeRange(time_range[0], time_range[1]),
			map(Event, events))
	
	@dbus.service.method("org.gnome.zeitgeist.Monitor",
	                     in_signature="(xx)au")
	def NotifyDelete(self, time_range, event_ids):
		"""
		Receive notification that a set of events within the monitor's
		matched time range has been deleted. Note that this notification
		will also be emitted for deleted events that doesn't match the
		event templates of the monitor. It's just the time range which
		is considered here.
		
		This method is the raw DBus callback and should normally not be
		overridden. Events are received via the *delete_callback*
		argument given in the constructor to this class.
		
		:param time_range: A two-tuple of 64 bit integers with the minimum
		    and maximum timestamps found in *events*. DBus signature (xx)
		:param event_ids: A list of event ids. An event id is simply
		    and unsigned 32 bit integer. DBus signature au.
		"""
		self._delete_callback(TimeRange(time_range[0], time_range[1]), event_ids)
	
	def __hash__ (self):
		return hash(self._path)
	
	@classmethod
	def _next_path(cls):
		"""
		Generate a new unique DBus object path for a monitor
		"""
		cls._last_path_id += 1
		return dbus.ObjectPath("/org/gnome/zeitgeist/monitor/%s" % \
			cls._last_path_id)

class ZeitgeistClient:
	"""
	Convenience APIs to have a Pythonic way to call and monitor the running
	Zeitgeist engine. For raw DBus access use the
	:class:`ZeitgeistDBusInterface` class.
	
	Note that this class only does asynchronous DBus calls. This is almost
	always the right thing to do. If you really want to do synchronous
	DBus calls use the raw DBus API found in the ZeitgeistDBusInterface class.
	"""
	def __init__ (self):
		self._iface = ZeitgeistDBusInterface()
	
	def _safe_error_handler(self, error_handler, *args):
		if error_handler is not None:
			if callable(error_handler):
				return error_handler
			raise TypeError(
				"Error handler not callable, found %s" % error_handler)
		return lambda raw: self._stderr_error_handler(raw, *args)
	
	def _safe_reply_handler(self, reply_handler):
		if reply_handler is not None:
			if callable(reply_handler):
				return reply_handler
			raise TypeError(
				"Reply handler not callable, found %s" % reply_handler)
		return self._void_reply_handler
	
	def get_version(self):
		return [int(i) for i in self._iface.version()]
	
	def insert_event (self, event, ids_reply_handler=None, error_handler=None):
		"""
		Send an event to the Zeitgeist event log. The 'event' parameter
		must be an instance of the Event class.
		
		The insertion will be done via an asynchronous DBus call and
		this method will return immediately. This means that the
		Zeitgeist engine will most likely not have inserted the event
		when this method returns. There will be a short delay.
		
		If the ids_reply_handler argument is set to a callable it will
		be invoked with a list containing the ids of the inserted events
		when they have been registered in Zeitgeist.
		
		In case of errors a message will be printed on stderr, and
		an empty result passed to ids_reply_handler (if set).
		To override this default set the error_handler named argument
		to a callable that takes a single exception as its sole
		argument.
		
		In order to use this method there needs to be a mainloop
		runnning. Both Qt and GLib mainloops are supported.
		"""
		self.insert_events([event],
				ids_reply_handler=ids_reply_handler,
				error_handler=error_handler)
	
	def insert_event_for_values (self, **values):
		"""
		Send an event to the Zeitgeist event log. The keyword arguments
		must match those as provided to Event.new_for_values().
		
		The insertion will be done via an asynchronous DBus call and
		this method will return immediately. This means that the
		Zeitgeist engine will most likely not have inserted the event
		when this method returns. There will be a short delay.
		
		If the ids_reply_handler argument is set to a callable it will
		be invoked with a list containing the ids of the inserted events
		when they have been registered in Zeitgeist.
		
		In case of errors a message will be printed on stderr, and
		an empty result passed to ids_reply_handler (if set).
		To override this default set the error_handler named argument
		to a callable that takes a single exception as its sole
		argument.
		
		In order to use this method there needs to be a mainloop
		runnning. Both Qt and GLib mainloops are supported.
		"""
		ev = Event.new_for_values(**values)
		self.insert_events([ev],
				values.get("ids_reply_handler", None),
				values.get("error_handler", None))
	
	def insert_events (self, events, ids_reply_handler=None, error_handler=None):
		"""
		Send a collection of events to the Zeitgeist event log. The
		*events* parameter must be a list or tuple containing only
		members of of type :class:`Event <zeitgeist.datamodel.Event>`.
		
		The insertion will be done via an asynchronous DBus call and
		this method will return immediately. This means that the
		Zeitgeist engine will most likely not have inserted the events
		when this method returns. There will be a short delay.
		
		In case of errors a message will be printed on stderr, and
		an empty result passed to *ids_reply_handler* (if set).
		To override this default set the *error_handler* named argument
		to a callable that takes a single exception as its sole
		argument.
		
		In order to use this method there needs to be a mainloop
		runnning. Both Qt and GLib mainloops are supported.
		"""
		
		self._check_list_or_tuple(events)
		self._check_members(events, Event)
		self._iface.InsertEvents(events,
					reply_handler=self._safe_reply_handler(ids_reply_handler),
					error_handler=self._safe_error_handler(error_handler,
						self._safe_reply_handler(ids_reply_handler), []))
	
	def find_event_ids_for_templates (self,
					event_templates,
					ids_reply_handler,
					timerange = None,
					storage_state = StorageState.Any,
					num_events = 20,
					result_type = ResultType.MostRecentEvents,
					error_handler=None):
		"""
		Send a query matching a collection of
		:class:`Event <zeitgeist.datamodel.Event>` templates to the
		Zeitgeist event log. The query will match if an event matches
		any of the templates. If an event template has more
		than one subject the query will match if any one of the subject
		templates match.
		
		The query will be done via an asynchronous DBus call and
		this method will return immediately. The return value
		will be passed to 'ids_reply_handler' as a list
		of integer event ids. This list must be the sole argument for
		the callback.
		
		The actual :class:`Events` can be looked up via the
		:meth:`get_events()` method.
		
		This method is intended for queries potentially returning a
		large result set. It is especially useful in cases where only
		a portion of the results are to be displayed at the same time
		(eg., by using paging or dynamic scrollbars), as by holding a
		list of IDs you keep a stable ordering, and you can ask for
		the details associated to them in batches, when you need them. For
		queries with a small amount of results, or where you need the
		information about all results at once no matter how many of them
		there are, see :meth:`find_events_for_templates`.
		 
		In case of errors a message will be printed on stderr, and
		an empty result passed to ids_reply_handler.
		To override this default set the error_handler named argument
		to a callable that takes a single exception as its sole
		argument.
		
		In order to use this method there needs to be a mainloop
		runnning. Both Qt and GLib mainloops are supported.
		
		:param event_templates: List or tuple of
		    :class:`Event <zeitgeist.datamodel.Event>` instances
		:param ids_reply_handler: Callable taking a list of integers
		:param timerange: A
		    :class:`TimeRange <zeitgeist.datamodel.TimeRange>` instance
		    that the events must have occured within. Defaults to
		    :meth:`TimeRange.until_now()`.
		:param storage_state: A value from the
		    :class:`StorageState <zeitgeist.datamodel.StorageState>`
		    enumeration. Defaults to :const:`StorageState.Any`
		:param num_events: The number of events to return; default is 20
		:param result_type: A value from the
		    :class:`ResultType <zeitgeist.datamodel.ResultType>`
		    enumeration. Defaults to ResultType.MostRecentEvent
		:param error_handler: Callback to catch error messages.
		        Read about the default behaviour above
		"""
		self._check_list_or_tuple(event_templates)
		self._check_members(event_templates, Event)
		
		if not callable(ids_reply_handler):
			raise TypeError(
				"Reply handler not callable, found %s" % ids_reply_handler)
		
		if timerange is None:
			timerange = TimeRange.until_now()
		
		self._iface.FindEventIds(timerange,
					event_templates,
					storage_state,
					num_events,
					result_type,
					reply_handler=self._safe_reply_handler(ids_reply_handler),
					error_handler=self._safe_error_handler(error_handler,
						ids_reply_handler, []))
	
	def find_event_ids_for_template (self, event_template, ids_reply_handler,
		**kwargs):
		"""
		Alias for :meth:`find_event_ids_for_templates`, for use when only
		one template is needed.
		"""
		self.find_event_ids_for_templates([event_template],
						ids_reply_handler,
						**kwargs)
	
	def find_event_ids_for_values(self, ids_reply_handler, **kwargs):
		"""
		Alias for :meth:`find_event_ids_for_templates`, for when only
		one template is needed. Instead of taking an already created
		template, like :meth:`find_event_ids_for_template`, this method
		will construct the template from the parameters it gets. The
		allowed keywords are the same as the ones allowed by
		:meth:`Event.new_for_values() <zeitgeist.datamodel.Event.new_for_values>`.
		"""
		ev = Event.new_for_values(**kwargs)
		
		self.find_event_ids_for_templates([ev],
						ids_reply_handler,
						**kwargs)
	
	def find_events_for_templates (self,
					event_templates,
					events_reply_handler,
					timerange = None,
					storage_state = StorageState.Any,
					num_events = 20,
					result_type = ResultType.MostRecentEvents,
					error_handler=None):
		"""
		Send a query matching a collection of
		:class:`Event <zeitgeist.datamodel.Event>` templates to the
		Zeitgeist event log. The query will match if an event matches
		any of the templates. If an event template has more
		than one subject the query will match if any one of the subject
		templates match.
		
		The query will be done via an asynchronous DBus call and
		this method will return immediately. The return value
		will be passed to 'events_reply_handler' as a list
		of :class:`Event`s. This list must be the sole argument for
		the callback.
		
		If you need to do a query yielding a large (or unpredictable)
		result set and you only want to show some of the results at the
		same time (eg., by paging them), consider using
		:meth:`find_event_ids_for_templates`.
		 
		In case of errors a message will be printed on stderr, and
		an empty result passed to events_reply_handler.
		To override this default set the error_handler named argument
		to a callable that takes a single exception as its sole
		argument.
		
		In order to use this method there needs to be a mainloop
		runnning. Both Qt and GLib mainloops are supported.
		
		:param event_templates: List or tuple of
		    :class:`Event <zeitgeist.datamodel.Event>` instances
		:param events_reply_handler: Callable taking a list of integers
		:param timerange: A
		    :class:`TimeRange <zeitgeist.datamodel.TimeRange>` instance
		    that the events must have occured within. Defaults to
		    :meth:`TimeRange.until_now()`.
		:param storage_state: A value from the
		    :class:`StorageState <zeitgeist.datamodel.StorageState>`
		    enumeration. Defaults to :const:`StorageState.Any`
		:param num_events: The number of events to return; default is 20
		:param result_type: A value from the
		    :class:`ResultType <zeitgeist.datamodel.ResultType>`
		    enumeration. Defaults to ResultType.MostRecentEvent
		:param error_handler: Callback to catch error messages.
		        Read about the default behaviour above
		"""
		self._check_list_or_tuple(event_templates)
		self._check_members(event_templates, Event)
		
		if not callable(events_reply_handler):
			raise TypeError(
				"Reply handler not callable, found %s" % events_reply_handler)
		
		if timerange is None:
			timerange = TimeRange.until_now()
		
		self._iface.FindEvents(timerange,
					event_templates,
					storage_state,
					num_events,
					result_type,
					reply_handler=lambda raw: events_reply_handler(
						map(Event.new_for_struct, raw)),
					error_handler=self._safe_error_handler(error_handler,
						events_reply_handler, []))
	
	def find_events_for_template (self, event_template, events_reply_handler,
		**kwargs):
		"""
		Alias for :meth:`find_events_for_templates`, for use when only
		one template is needed.
		"""
		self.find_event_ids_for_templates([event_template],
						events_reply_handler,
						**kwargs)
	
	def find_events_for_values(self, events_reply_handler, **kwargs):
		"""
		Alias for :meth:`find_events_for_templates`, for when only
		one template is needed. Instead of taking an already created
		template, like :meth:`find_event_ids_for_template`, this method
		will construct the template from the parameters it gets. The
		allowed keywords are the same as the ones allowed by
		:meth:`Event.new_for_values() <zeitgeist.datamodel.Event.new_for_values>`.
		"""
		ev = Event.new_for_values(**kwargs)
		
		self.find_events_for_templates([ev],
						events_reply_handler,
						**kwargs)
	
	def get_events (self, event_ids, events_reply_handler, error_handler=None):
		"""
		Look up a collection of :class:`Events <zeitgeist.datamodel.Event>`
		in the Zeitgeist event log given a collection of event ids.
		This is useful for looking up the event data for events found
		with the *find_event_ids_** family of functions.
		
		Each event which is not found in the event log is represented
		by `None` in the resulting collection.
		
		The query will be done via an asynchronous DBus call and
		this method will return immediately. The returned events
		will be passed to *events_reply_handler* as a list
		of Events, which must be the only argument of the function.
		 
		In case of errors a message will be printed on stderr, and
		an empty result passed to *events_reply_handler*.
		To override this default set the *error_handler* named argument
		to a callable that takes a single exception as its sole
		argument.
		
		In order to use this method there needs to be a mainloop
		runnning. Both Qt and GLib mainloops are supported.
		"""
		
		if not callable(events_reply_handler):
			raise TypeError(
				"Reply handler not callable, found %s" % events_reply_handler)
		
		# Generate a wrapper callback that does automagic conversion of
		# the raw DBus reply into a list of Event instances
		self._iface.GetEvents(event_ids,
				reply_handler=lambda raw: events_reply_handler(
					map(Event.new_for_struct, raw)),
				error_handler=self._safe_error_handler(error_handler,
						events_reply_handler, []))
	
	def delete_events(self, event_ids, reply_handler=None, error_handler=None):
		"""
		Warning: This API is EXPERIMENTAL and is not fully supported yet.
		
		Delete a collection of events from the zeitgeist log given their
		event ids.
		
		The deletion will be done asynchronously, and this method returns
		immediately. To check whether the deletions went well supply
		the *reply_handler* and/or *error_handler* funtions. The
		reply handler should not take any argument. The error handler
		must take a single argument - being the error.
		
		With custom handlers any errors will be printed to stderr.
		
		In order to use this method there needs to be a mainloop
		runnning.
		"""
		self._check_list_or_tuple(event_ids)
		self._check_members(event_ids, int)
		
		self._iface.DeleteEvents(event_ids,
					reply_handler=self._safe_reply_handler(reply_handler),
					error_handler=self._safe_error_handler(error_handler))
	
	def find_related_uris_for_events(self, event_templates, uris_reply_handler,
		time_range = None, result_event_templates=[],
		storage_state=StorageState.Any, error_handler=None):
		"""
		Warning: This API is EXPERIMENTAL and is not fully supported yet.
		
		Get a list of URIs of subjects which frequently occur together
		with events matching `event_templates`. Possibly restricting to
		`time_range` or to URIs that occur as subject of events matching
		`result_event_templates`.
		
		:param event_templates: Templates for events that you want to
		    find URIs that relate to
		:param uris_reply_handler: A callback that takes a list of strings
		    with the URIs of the subjects related to the requested events
		:param time_range: A :class:`TimeRange <zeitgeist.datamodel.TimeRange>`
		    to restrict to
		:param result_event_templates: The related URIs must occur
		    as subjects of events matching these templates
		:param storage_state: The returned URIs must have this
		    :class:`storage state <zeitgeist.datamodel.StorageState>`
		:param error_handler: An optional callback in case of errors.
		    Must take a single argument being the error raised by the
		    server. The default behaviour in case of errors is to call
		    `uris_reply_handler` with an empty list and print an error
		    message on standard error.
		"""
		if not callable(uris_reply_handler):
			raise TypeError(
				"Reply handler not callable, found %s" % uris_reply_handler)
		
		if time_range is None:
			time_range = TimeRange.always()
		
		self._iface.FindRelatedUris(time_range, event_templates,
			result_event_templates, storage_state,
			reply_handler=self._safe_reply_handler(uris_reply_handler),
			error_handler=self._safe_error_handler(error_handler,
			                                       uris_reply_handler,
			                                       []))
	
	def find_related_uris_for_uris(self, subject_uris, uris_reply_handler,
		time_range=None, result_event_templates=[],
		storage_state=StorageState.Any, error_handler=None):
		"""
		Warning: This API is EXPERIMENTAL and is not fully supported yet.
		
		Same as :meth:`find_related_uris_for_events`, but taking a list
		of subject URIs instead of event templates.
		"""
		
		event_template = Event.new_for_values(subjects=
			[Subject.new_for_values(uri=uri) for uri in subject_uris])
		
		self.find_related_uris_for_events([event_template],
		                                  uris_reply_handler,
		                                  time_range=time_range,
		                                  result_event_templates=result_event_templates,
		                                  storage_state=storage_state,
		                                  error_handler=error_handler)
	
	def install_monitor (self, time_range, event_templates,
		notify_insert_handler, notify_delete_handler, monitor_path=None):
		"""
		Install a monitor in the Zeitgeist engine that calls back
		when events matching *event_templates* are logged. The matching
		is done exactly as in the *find_** family of methods and in
		:meth:`Event.matches_template <zeitgeist.datamodel.Event.matches_template>`.
		Furthermore matched events must also have timestamps lying in
		*time_range*.
		
		To remove a monitor call :meth:`remove_monitor` on the returned
		:class:`Monitor` instance.
		
		The *notify_insert_handler* will be called when events matching
		the monitor are inserted into the log. The *notify_delete_handler*
		function will be called when events lying within the monitored
		time range are deleted.
		
		:param time_range: A :class:`TimeRange <zeitgeist.datamodel.TimeRange>`
		    that matched events must lie within. To obtain a time range
		    from now and indefinitely into the future use
		    :meth:`TimeRange.from_now() <zeitgeist.datamodel.TimeRange.from_now>`
		:param event_templates: The event templates to look for
		:param notify_insert_handler: Callback for receiving notifications
		    about insertions of matching events. The callback should take
		    a :class:`TimeRange` as first parameter and a list of
		    :class:`Events` as the second parameter.
		    The time range will cover the minimum and maximum timestamps
		    of the inserted events
		:param notify_delete_handler: Callback for receiving notifications
		    about deletions of events in the monitored time range.
		    The callback should take a :class:`TimeRange` as first
		    parameter and a list of event ids as the second parameter.
		    Note that an event id is simply an unsigned integer.
		:param monitor_path: Optional argument specifying the DBus path
		    to install the client side monitor object on. If none is provided
		    the client will provide one for you namespaced under
		    /org/gnome/zeitgeist/monitor/*
		:returns: a :class:`Monitor`
		"""
		self._check_list_or_tuple(event_templates)
		self._check_members(event_templates, Event)
		if not callable(notify_insert_handler):
			raise TypeError("notify_insert_handler not callable, found %s" % \
				notify_reply_handler)
			
		if not callable(notify_delete_handler):
			raise TypeError("notify_delete_handler not callable, found %s" % \
				notify_reply_handler)
		
		
		mon = Monitor(time_range, event_templates, notify_insert_handler,
			notify_delete_handler, monitor_path=monitor_path)
		self._iface.InstallMonitor(mon.path,
		                           mon.time_range,
		                           mon.templates,
		                           reply_handler=self._void_reply_handler,
		                           error_handler=lambda err: log.warn(
									"Error installing monitor: %s" % err))
		return mon
	
	def remove_monitor (self, monitor, monitor_removed_handler=None):
		"""
		Remove a :class:`Monitor` installed with :meth:`install_monitor`
		
		:param monitor: Monitor to remove. Either as a :class:`Monitor`
		    instance or a DBus object path to the monitor either as a
		    string or :class:`dbus.ObjectPath`
		:param monitor_removed_handler: A callback function taking
		    one integer argument. 1 on success, 0 on failure.
		"""
		if isinstance(monitor, (str,unicode)):
			path = dbus.ObjectPath(monitor)
		elif isinstance(monitor, Monitor):
			path = monitor.path
		else:
			raise TypeError(
				"Monitor, str, or unicode expected. Found %s" % type(monitor))
		
		if callable(monitor_removed_handler):
			
			def dispatch_handler (error=None):
				if error :
					log.warn("Error removing monitor %s: %s" % (monitor, error))
					monitor_removed_handler(0)
				else: monitor_removed_handler(1)
				
			reply_handler = dispatch_handler
			error_handler = dispatch_handler
		else:
			reply_handler = self._void_reply_handler
			error_handler = lambda err: log.warn(
				"Error removing monitor %s: %s" % (monitor, err))
		
		self._iface.RemoveMonitor(path,
		                          reply_handler=reply_handler,
		                          error_handler=error_handler)
		
	def _check_list_or_tuple(self, collection):
		"""
		Raise a ValueError unless 'collection' is a list or tuple
		"""
		if not (isinstance(collection, list) or isinstance(collection, tuple)):
			raise TypeError("Expected list or tuple, found %s" % type(collection))
	
	def _check_members (self, collection, member_class):
		"""
		Raise a ValueError unless all of the members of 'collection'
		are of class 'member_class'
		"""
		for m in collection:
			if not isinstance(m, member_class):
				raise TypeError(
					"Collection contains member of invalid type %s. Expected %s" % \
					(m.__class__, member_class))
	
	def _void_reply_handler(self, *args, **kwargs):
		"""
		Reply handler for async DBus calls that simply ignores the response
		"""
		pass
		
	def _stderr_error_handler(self, exception, normal_reply_handler=None,
		normal_reply_data=None):
		"""
		Error handler for async DBus calls that prints the error
		to sys.stderr
		"""
		print >> sys.stderr, "Error from Zeitgeist engine:", exception
		
		if callable(normal_reply_handler):
			normal_reply_handler(normal_reply_data)
