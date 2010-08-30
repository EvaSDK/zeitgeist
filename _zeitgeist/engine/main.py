# -.- coding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009 Mikkel Kamstrup Erlandsen <mikkel.kamstrup@gmail.com>
# Copyright © 2009-2010 Siegfried-Angel Gevatter Pujals <rainct@ubuntu.com>
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2009 Markus Korn <thekorn@gmx.net>
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

import sqlite3
import time
import sys
import os
import math
import gettext
import logging
import operator
from itertools import islice
from collections import defaultdict

from zeitgeist.datamodel import Event as OrigEvent, StorageState, TimeRange, \
	ResultType, get_timestamp_for_now, Interpretation, Symbol, NEGATION_OPERATOR, WILDCARD
from _zeitgeist.engine.datamodel import Event, Subject
from _zeitgeist.engine.extension import ExtensionsCollection, get_extensions
from _zeitgeist.engine import constants
from _zeitgeist.engine.sql import get_default_cursor, unset_cursor, \
	TableLookup, WhereClause
	
WINDOW_SIZE = 7

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("zeitgeist.engine")

class NegationNotSupported(ValueError):
	pass

class WildcardNotSupported(ValueError):
	pass

def parse_negation(kind, field, value, parse_negation=True):
	"""checks if value starts with the negation operator,
	if value starts with the negation operator but the field does
	not support negation a ValueError is raised.
	This function returns a (value_without_negation, negation)-tuple
	"""
	negation = False
	if parse_negation and value.startswith(NEGATION_OPERATOR):
		negation = True
		value = value[len(NEGATION_OPERATOR):]
	if negation and field not in kind.SUPPORTS_NEGATION:
		raise NegationNotSupported("This field does not support negation")
	return value, negation
	
def parse_wildcard(kind, field, value):
	"""checks if value ends with the a wildcard,
	if value ends with a wildcard but the field does not support wildcards
	a ValueError is raised.
	This function returns a (value_without_wildcard, wildcard)-tuple
	"""
	wildcard = False
	if value.endswith(WILDCARD):
		wildcard = True
		value = value[:-len(WILDCARD)]
	if wildcard and field not in kind.SUPPORTS_WILDCARDS:
		raise WildcardNotSupported("This field does not support wildcards")
	return value, wildcard
	
def parse_operators(kind, field, value):
	"""runs both (parse_negation and parse_wildcard) parser functions
	on query values, and handles the special case of Subject.Text correctly.
	returns a (value_without_negation_and_wildcard, negation, wildcard)-tuple
	"""
	try:
		value, negation = parse_negation(kind, field, value)
	except ValueError:
		if kind is Subject and field == Subject.Text:
			# we do not support negation of the text field,
			# the text field starts with the NEGATION_OPERATOR
			# so we handle this string as the content instead
			# of an operator
			negation = False
		else:
			raise
	value, wildcard = parse_wildcard(kind, field, value)
	return value, negation, wildcard


class ZeitgeistEngine:
	
	def __init__ (self):
		self._cursor = cursor = get_default_cursor()
		
		# Find the last event id we used, and start generating
		# new ids from that offset
		row = cursor.execute("SELECT MIN(id), MAX(id) FROM event").fetchone()
		self._last_event_id = row[1] if row[1] else 0
		if row[0] == 0:
			# old database version raise an error for now,
			# maybe just change the id to self._last_event_id + 1
			# looking closer at the old code, it seems like
			# no event ever got an id of 0, but we should leave this check
			# to be 100% sure.
			raise RuntimeError("old database version")
		
		# Load extensions
		default_extensions = get_extensions()
		self.__extensions = ExtensionsCollection(self,
		                                         defaults=default_extensions)
		
		self._interpretation = TableLookup(cursor, "interpretation")
		self._manifestation = TableLookup(cursor, "manifestation")
		self._mimetype = TableLookup(cursor, "mimetype")
		self._actor = TableLookup(cursor, "actor")
	
	@property
	def extensions(self):
		return self.__extensions
	
	def close(self):
		self.extensions.unload()
		self._cursor.connection.close()
		self._cursor = None
		unset_cursor()
	
	def is_closed(self):
		return self._cursor is None
	
	def next_event_id (self):
		self._last_event_id += 1
		return self._last_event_id
	
	def _get_event_from_row(self, row):
		event = Event()
		event[0][Event.Id] = row["id"] # Id property is read-only in the public API
		event.timestamp = row["timestamp"]
		for field in ("interpretation", "manifestation", "actor"):
			setattr(event, field, getattr(self, "_" + field).value(row[field]))
		event.payload = row["payload"] or "" # default payload: empty string
		return event
	
	def _get_subject_from_row(self, row):
		subject = Subject()
		for field in ("uri", "origin", "text", "storage"):
			setattr(subject, field, row["subj_" + field])
		for field in ("interpretation", "manifestation", "mimetype"):
			setattr(subject, field,
				getattr(self, "_" + field).value(row["subj_" + field]))
		return subject
	
	def get_events(self, ids=None, rows=None, sender=None):
		"""
		Look up a list of events.
		"""
		
		t = time.time()
		
		if not ids and not rows:
			return []
		
		if ids:
			rows = self._cursor.execute("""
				SELECT * FROM event_view
				WHERE id IN (%s)
				""" % ",".join("%d" % id for id in ids)).fetchall()
		else:
			ids = (row[0] for row in rows)
		
		events = {}
		for row in rows:
			# Assumption: all rows of a same event for its different
			# subjects are in consecutive order.
			event = self._get_event_from_row(row)
			if event.id not in events:
				events[event.id] = event
			events[event.id].append_subject(self._get_subject_from_row(row))
		
		# Sort events into the requested order
		sorted_events = []
		for id in ids:
			# if we are not able to get an event by the given id
			# append None instead of raising an Error. The client
			# might simply have requested an event that has been
			# deleted
			event = events.get(id, None)
			event = self.extensions.apply_get_hooks(event, sender)
			
			sorted_events.append(event)
		
		log.debug("Got %d events in %fs" % (len(sorted_events), time.time()-t))

		return sorted_events
	
	@staticmethod
	def _build_templates(templates):
		for event_template in templates:
			event_data = event_template[0]
			for subject in (event_template[1] or (Subject(),)):
				yield Event((event_data, [], None)), Subject(subject)
	
	def _build_sql_from_event_templates(self, templates):
	
		where_or = WhereClause(WhereClause.OR)
		
		for template in templates:
			event_template = Event((template[0], [], None))
			if template[1]:
				subject_templates = [Subject(data) for data in template[1]]
			else:
				subject_templates = None
			# first of all we need to check if the query is supported at all
			# we do not support searching by storage field for now
			# see LP: #580364
			if subject_templates is not None:
				if any(data[Subject.Storage] for data in subject_templates):
					raise ValueError("zeitgeist does not support searching by 'storage' field")
			
			subwhere = WhereClause(WhereClause.AND)
			
			if event_template.id:
				subwhere.add("id = ?", event_template.id)
			
			try:
				value, negation, wildcard = parse_operators(Event, Event.Interpretation, event_template.interpretation)
				# Expand event interpretation children
				event_interp_where = WhereClause(WhereClause.OR, negation)
				for child_interp in (Symbol.find_child_uris_extended(value)):
					if child_interp:
						event_interp_where.add_text_condition("interpretation",
						                       child_interp, like=wildcard, cache=self._interpretation)
				if event_interp_where:
					subwhere.extend(event_interp_where)
				
				value, negation, wildcard = parse_operators(Event, Event.Manifestation, event_template.manifestation)
				# Expand event manifestation children
				event_manif_where = WhereClause(WhereClause.OR, negation)
				for child_manif in (Symbol.find_child_uris_extended(value)):
					if child_manif:
						event_manif_where.add_text_condition("manifestation",
						                      child_manif, like=wildcard, cache=self._manifestation)
				if event_manif_where:
					subwhere.extend(event_manif_where)
				
				value, negation, wildcard = parse_operators(Event, Event.Actor, event_template.actor)
				if value:
					subwhere.add_text_condition("actor", value, wildcard, negation, cache=self._actor)
				
				if subject_templates is not None:
					for subject_template in subject_templates:
						value, negation, wildcard = parse_operators(Subject, Subject.Interpretation, subject_template.interpretation)
						# Expand subject interpretation children
						su_interp_where = WhereClause(WhereClause.OR, negation)
						for child_interp in (Symbol.find_child_uris_extended(value)):
							if child_interp:
								su_interp_where.add_text_condition("subj_interpretation",
													child_interp, like=wildcard, cache=self._interpretation)
						if su_interp_where:
							subwhere.extend(su_interp_where)
						
						value, negation, wildcard = parse_operators(Subject, Subject.Manifestation, subject_template.manifestation)
						# Expand subject manifestation children
						su_manif_where = WhereClause(WhereClause.OR, negation)
						for child_manif in (Symbol.find_child_uris_extended(value)):
							if child_manif:
								su_manif_where.add_text_condition("subj_manifestation",
												   child_manif, like=wildcard, cache=self._manifestation)
						if su_manif_where:
							subwhere.extend(su_manif_where)
						
						# FIXME: Expand mime children as well.
						# Right now we only do exact matching for mimetypes
						# thekorn: this will be fixed when wildcards are supported
						value, negation, wildcard = parse_operators(Subject, Subject.Mimetype, subject_template.mimetype)
						if value:
							subwhere.add_text_condition("subj_mimetype",
										 value, wildcard, negation, cache=self._mimetype)
				
						for key in ("uri", "origin", "text"):
							value = getattr(subject_template, key)
							if value:
								value, negation, wildcard = parse_operators(Subject, getattr(Subject, key.title()), value)
								subwhere.add_text_condition("subj_%s" %key, value, wildcard, negation)
			except KeyError, e:
				# Value not in DB
				log.debug("Unknown entity in query: %s" % e)
				where_or.register_no_result()
				continue
			where_or.extend(subwhere) 
		return where_or
	
	def _build_sql_event_filter(self, time_range, templates, storage_state):
		
		# FIXME: We need to take storage_state into account
		if storage_state != StorageState.Any:
			raise NotImplementedError
		
		where = WhereClause(WhereClause.AND)
		where.add("timestamp >= ?", time_range[0])
		where.add("timestamp <= ?", time_range[1])
		
		where.extend(self._build_sql_from_event_templates(templates))
		
		return where
	
	def _find_events(self, return_mode, time_range, event_templates,
		storage_state, max_events, order, sender=None):
		"""
		Accepts 'event_templates' as either a real list of Events or as
		a list of tuples (event_data, subject_data) as we do in the
		DBus API.
		
		Return modes:
		 - 0: IDs.
		 - 1: Events.
		 - 2: (Timestamp, SubjectUri)
		"""
		t = time.time()
		
		where = self._build_sql_event_filter(time_range, event_templates,
			storage_state)
		
		if not where.may_have_results():
			return []
		
		if return_mode == 0:
			sql = "SELECT DISTINCT id FROM event_view"
		elif return_mode == 1:
			sql = "SELECT id FROM event_view"
		elif return_mode == 2:
			sql = "SELECT subj_uri, timestamp FROM event_view"
		else:
			raise NotImplementedError, "Unsupported return_mode."
		
		if order == ResultType.LeastRecentActor:
			sql += """
				NATURAL JOIN (
					SELECT actor, min(timestamp) AS timestamp
					FROM event_view
					GROUP BY actor)
				"""
		
		if where:
			sql += " WHERE " + where.sql
		
		sql += (" ORDER BY timestamp DESC",
			" ORDER BY timestamp ASC",
			" GROUP BY subj_uri ORDER BY timestamp DESC",
			" GROUP BY subj_uri ORDER BY timestamp ASC",
			" GROUP BY subj_uri ORDER BY COUNT(subj_uri) DESC, timestamp DESC",
			" GROUP BY subj_uri ORDER BY COUNT(subj_uri) ASC, timestamp ASC",
			" GROUP BY actor ORDER BY COUNT(actor) DESC, timestamp DESC", 
			" GROUP BY actor ORDER BY COUNT(actor) ASC, timestamp ASC",
			" GROUP BY actor ORDER BY timestamp DESC",
			" GROUP BY actor ORDER BY timestamp ASC",
			" GROUP BY subj_origin ORDER BY timestamp DESC",
			" GROUP BY subj_origin ORDER BY timestamp ASC",
			" GROUP BY subj_origin ORDER BY COUNT(subj_origin) DESC, timestamp DESC",
			" GROUP BY subj_origin ORDER BY COUNT(subj_origin) ASC, timestamp ASC")[order]
		
		if max_events > 0:
			sql += " LIMIT %d" % max_events
		
		result = self._cursor.execute(sql, where.arguments).fetchall()
		
		if return_mode == 0:
			log.debug("Found %d event IDs in %fs" % (len(result), time.time()- t))
			result = [row[0] for row in result]
		elif return_mode == 1:
			log.debug("Found %d events in %fs" % (len(result), time.time()- t))
			result = self.get_events(ids=[row[0] for row in result], sender=sender)			
		elif return_mode == 2:
			log.debug("Found %d (uri,timestamp) tuples in %fs" % (len(result), time.time()- t))
			result = map(lambda row: (row[0], row[1]), result)			
		else:
			raise Exception("%d" % return_mode)
		
		return result
	
	def find_eventids(self, *args):
		return self._find_events(0, *args)
	
	def find_events(self, *args):
		return self._find_events(1, *args)
	
	def __add_window(self, _set, assoc, landmarks, windows):
		if _set & landmarks: # intersection != 0
			windows.append(_set)
			for i in _set.difference(landmarks):
				assoc[i] += 1
	
	def find_related_uris(self, timerange, event_templates, result_event_templates,
		result_storage_state, num_results, result_type):
		"""
		Return a list of subject URIs commonly used together with events
		matching the given template, considering data from within the indicated
		timerange.
		
		Only URIs for subjects matching the indicated `result_event_templates`
		and `result_storage_state` are returned.
		"""
		
		if result_type == 0 or result_type == 1:
			
			t1 = time.time()
			
			if len(result_event_templates) == 0:
				uris = self._find_events(2, timerange, result_event_templates,
					result_storage_state, 0, ResultType.LeastRecentEvents)
			else:
				uris = self._find_events(2, timerange, result_event_templates + event_templates,
					result_storage_state, 0, ResultType.LeastRecentEvents)
			
			assoc = defaultdict(int)
			
			landmarks = self._find_events(2, timerange, event_templates,
					result_storage_state, 0, 4)
			landmarks = set([unicode(event[0]) for event in landmarks])
			
			latest_uris = dict(uris)
			events = [unicode(u[0]) for u in uris]

			furis = filter(lambda x: x[0] in landmarks, uris)
			if len(furis) == 0:
				return []
			
			_min = min(furis, key=operator.itemgetter(1))
			_max = max(furis, key=operator.itemgetter(1))
			min_index = uris.index(_min) - WINDOW_SIZE
			max_index = uris.index(_max) + WINDOW_SIZE
			_min = _min[1]
			_max = _max[1]
			
			if min_index < 0:
				min_index = 0
			if max_index > len(events):
				max_index = -1
				
			func = self.__add_window
			
			if len(events) == 0 or len(landmarks) == 0:
				return []
			
			windows = []
	
			if len(events) <= WINDOW_SIZE:
				#TODO bug! windows is not defined, seems the algorithm never touches these loop
				func(events, assoc, landmarks, windows)
			else:
				events = events[min_index:max_index]
				offset = WINDOW_SIZE/2
				
				for i in xrange(offset):
					func(set(events[0: offset - i]), assoc, landmarks, 
						windows)
					func(set(events[len(events) - offset + i: len(events)]),
						assoc, landmarks, windows)
					
				it = iter(events)
				result = tuple(islice(it, WINDOW_SIZE))
				for elem in it:
					result = result[1:] + (elem,)
					func(set(result), assoc, landmarks, windows)
					
				
			log.debug("FindRelatedUris: Finished sliding windows in %fs." % \
				(time.time()-t1))
			
			if result_type == 0:
				sets = [[v, k] for k, v in assoc.iteritems()]
			elif result_type == 1:
				sets = [[latest_uris[k], k] for k in assoc]
				
			sets.sort(reverse = True)
			sets = map(lambda result: result[1], sets[:num_results])
			
			return sets
		else:
			raise NotImplementedError, "Unsupported ResultType."
			

	def insert_events(self, events, sender=None):
		t = time.time()
		m = map(lambda e: self._insert_event_without_error(e, sender), events)
		self._cursor.connection.commit()
		log.debug("Inserted %d events in %fs" % (len(m), time.time()-t))
		return m
	
	def _insert_event_without_error(self, event, sender=None):
		try:
			return self._insert_event(event, sender)
		except Exception, e:
			log.exception("error while inserting '%r'" %event)
			return 0
	
	def _insert_event(self, event, sender=None):
		if not issubclass(type(event), OrigEvent):
			raise ValueError("cannot insert object of type %r" %type(event))
		if event.id:
			raise ValueError("Illegal event: Predefined event id")
		if not event.subjects:
			raise ValueError("Illegal event format: No subject")
		if not event.timestamp:
			event.timestamp = get_timestamp_for_now()
		
		id = self.next_event_id()
		event[0][Event.Id] = id		
		event = self.extensions.apply_pre_insert(event, sender)
		if event is None:
			raise AssertionError("Inserting of event was blocked by an extension")
		elif not issubclass(type(event), OrigEvent):
			raise ValueError("cannot insert object of type %r" %type(event))		
		
		payload_id = self._store_payload (event)
		
		# Make sure all URIs are inserted
		_origin = [subject.origin for subject in event.subjects if subject.origin]
		self._cursor.execute("INSERT OR IGNORE INTO uri (value) %s"
			% " UNION ".join(["SELECT ?"] * (len(event.subjects) + len(_origin))),
			[subject.uri for subject in event.subjects] + _origin)
		
		# Make sure all mimetypes are inserted
		_mimetype = [subject.mimetype for subject in event.subjects \
			if subject.mimetype and not subject.mimetype in self._mimetype]
		if len(_mimetype) > 1:
			self._cursor.execute("INSERT OR IGNORE INTO mimetype (value) %s"
				% " UNION ".join(["SELECT ?"] * len(_mimetype)), _mimetype)
		
		# Make sure all texts are inserted
		_text = [subject.text for subject in event.subjects if subject.text]
		if _text:
			self._cursor.execute("INSERT OR IGNORE INTO text (value) %s"
				% " UNION ".join(["SELECT ?"] * len(_text)), _text)
		
		# Make sure all storages are inserted
		_storage = [subject.storage for subject in event.subjects if subject.storage]
		if _storage:
			self._cursor.execute("INSERT OR IGNORE INTO storage (value) %s"
				% " UNION ".join(["SELECT ?"] * len(_storage)), _storage)
		
		try:
			for subject in event.subjects:	
				self._cursor.execute("""
					INSERT INTO event VALUES (
						?, ?, ?, ?, ?, ?,
						(SELECT id FROM uri WHERE value=?),
						?, ?,
						(SELECT id FROM uri WHERE value=?),
						?,
						(SELECT id FROM text WHERE value=?),
						(SELECT id from storage WHERE value=?)
					)""", (
						id,
						event.timestamp,
						self._interpretation[event.interpretation],
						self._manifestation[event.manifestation],
						self._actor[event.actor],
						payload_id,
						subject.uri,
						self._interpretation[subject.interpretation],
						self._manifestation[subject.manifestation],
						subject.origin,
						self._mimetype[subject.mimetype],
						subject.text,
						subject.storage))
				
			self.extensions.apply_post_insert(event, sender)
				
		except sqlite3.IntegrityError:
			# The event was already registered.
			# Rollback _last_event_id and return the ID of the original event
			self._last_event_id -= 1
			self._cursor.execute("""
				SELECT id FROM event
				WHERE timestamp=? AND interpretation=? AND manifestation=?
					AND actor=?
				""", (event.timestamp,
					self._interpretation[event.interpretation],
					self._manifestation[event.manifestation],
					self._actor[event.actor]))
			return self._cursor.fetchone()[0]
		
		self._cursor.connection.commit()
		
		return id
	
	def _store_payload (self, event):
		# TODO: Rigth now payloads are not unique and every event has its
		# own one. We could optimize this to store those which are repeated
		# for different events only once, especially considering that
		# events cannot be modified once they've been inserted.
		if event.payload:
			# TODO: For Python >= 2.6 bytearray() is much more efficient
			# than this hack...
			# We need binary encoding that sqlite3 will accept, for
			# some reason sqlite3 can not use array.array('B', event.payload)
			payload = sqlite3.Binary("".join(map(str, event.payload)))
			self._cursor.execute(
				"INSERT INTO payload (value) VALUES (?)", (payload,))
			return self._cursor.lastrowid
		else:
			# Don't use None here, as that'd be inserted literally into the DB
			return ""

	def delete_events (self, ids, sender=None):
		ids = self.extensions.apply_pre_delete(ids, sender)
		# Extract min and max timestamps for deleted events
		self._cursor.execute("""
			SELECT MIN(timestamp), MAX(timestamp)
			FROM event
			WHERE id IN (%s)
		""" % ",".join(str(int(_id)) for _id in ids))
		timestamps = self._cursor.fetchone()

		# Make sure that we actually found some events with these ids...
		# We can't do all(timestamps) here because the timestamps may be 0
		if timestamps and timestamps[0] is not None and timestamps[1] is not None:
			self._cursor.execute("DELETE FROM event WHERE id IN (%s)"
				% ",".join(["?"] * len(ids)), ids)
			self._cursor.connection.commit()
			log.debug("Deleted %s" % map(int, ids))
			
			self.extensions.apply_post_delete(ids, sender)
			
			return timestamps
		else:
			log.debug("Tried to delete non-existing event(s): %s" % map(int, ids))
			return None
