#! /usr/bin/python
# -.- coding: utf-8 -.-

# remote-test.py
#
# Copyright © 2009-2011 Seif Lotfy <seif@lotfy.com>
# Copyright © 2009-2011 Siegfried-Angel Gevatter Pujals <siegfried@gevatter.com>
# Copyright © 2009-2011 Mikkel Kamstrup Erlandsen <mikkel.kamstrup@gmail.com>
# Copyright © 2009-2011 Markus Korn <thekorn@gmx.de>
# Copyright © 2011 Collabora Ltd.
#             By Siegfried-Angel Gevatter Pujals <siegfried@gevatter.com>
#             By Seif Lotfy <seif@lotfy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
import os
import sys
import logging
import signal
import time
import tempfile
import shutil
import pickle
from subprocess import Popen, PIPE

# DBus setup
import gobject
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
from dbus.exceptions import DBusException

from zeitgeist.datamodel import (Event, Subject, Interpretation, Manifestation,
	TimeRange, StorageState, DataSource, NULL_EVENT, ResultType)

import testutils
from testutils import parse_events, import_events

TEST_ACTOR = "/usr/share/applications/gnome-about.desktop"

test_event_1 = None
def create_test_event_1():
	ev = Event()
	ev.timestamp = 0
	ev.interpretation = Manifestation.USER_ACTIVITY
	ev.manifestation = Interpretation.CREATE_EVENT
	ev.actor = TEST_ACTOR
	subj = Subject()
	subj.uri = u"test://mytest"
	subj.manifestation = "lala"
	subj.interpretation = "tinky winky"
	subj.origin = "test://"
	subj.mimetype = "YOMAMA"
	subj.text = "SUCKS"
	subj.storage = "MyStorage"
	subj.current_uri = u"test://mytest"

	ev.append_subject(subj)
	return ev


class ZeitgeistEngineTest(testutils.RemoteTestCase):

	def testSingleInsertGet(self):
		test_event_1 = create_test_event_1()
		# Insert item and event
		ids = self.insertEventsAndWait([test_event_1])
		self.assertEquals(1, len(ids))
		
		result = self.getEventsAndWait(ids)
		resulting_event = result.pop()
		self.assertEquals(len(resulting_event), len(test_event_1))
		
		# fixing id, the initial event does not have any id set
		test_event_1[0][0] = ids[0]
		resulting_event[2] = ""
		
		self.assertEqual(resulting_event, test_event_1)
		
	def testInsertGetWithoutTimestamp(self):
		# We test two things, that Event creates a default timestamp
		# and that the engine provides one for us if don't do our selves
		
		subj = Subject.new_for_values(interpretation="foo://interp",
					manifestation="foo://manif",
					uri="nowhere")
		ev = Event.new_for_values(interpretation="foo://bar",
					manifestation="foo://quiz",
					actor="actor://myself",
					subjects=[subj])
		
		# Assert that timestamp is set
		self.assertTrue(ev.timestamp)
		
		# Clear the timestamp and insert event
		ev.timestamp = ""
		ids = self.insertEventsAndWait([ev])
		result = self.getEventsAndWait(ids)
		
		self.assertEquals(1, len(result))
		resulting_event = Event(result.pop())
		self.assertEquals("foo://bar", resulting_event.interpretation)
		self.assertTrue(resulting_event.timestamp) # We should have a timestamp again
		
	def testDuplicateEventInsertion(self):
		self.testSingleInsertGet()
		
		# Inserting the same event again should be ok, but not
		# cause duplicates
		self.testSingleInsertGet()
		
		# Find all events, and make sure that this is exactly one event
		result = self.findEventIdsAndWait([])
		self.assertEquals(1, len(result))
		self.assertEquals(1, result[0]) # The single event must have id 1
	
	def testDeleteSingle(self):
		self.testSingleInsertGet()
		self.deleteEventsAndWait([1])
		result = self.getEventsAndWait([1])
		self.assertEquals(0, len(filter(None, result)))

	def testIllegalPredefinedEventId(self):
		event = Event()
		event[0][0] = str(23) # This is illegal, we assert the erro later
		event.timestamp = 0
		event.interpretation = Manifestation.USER_ACTIVITY
		event.manifestation = Interpretation.CREATE_EVENT
		event.actor = "/usr/share/applications/gnome-about.desktop"
		
		subject = Subject()
		subject.uri = "file:///tmp/file.txt"
		subject.manifestation = Manifestation.FILE_DATA_OBJECT
		subject.interpretation = Interpretation.DOCUMENT
		subject.origin = "test://"
		subject.mimetype = "text/plain"
		subject.text = "This subject has no text"
		subject.storage = "368c991f-8b59-4018-8130-3ce0ec944157" # UUID of home partition
		
		event.append_subject(subject)
		
		# Insert item and event
		ids = self.insertEventsAndWait([event,])
		self.assertEquals(len(ids), 1)
		# event is not inserted, id == 0 means error
		self.assertEquals(ids[0], 0)
		# check if really not events were inserted
		ids = self.findEventIdsAndWait([])
		self.assertEquals(len(ids), 0)
		
	def testGetNonExisting(self):
		events = self.getEventsAndWait([23,45,65])
		self.assertEquals(3, len(events))
		for ev in events : self.assertEquals(None, ev)
	
	def testGetDuplicateEventIds(self):
		ids = import_events("test/data/five_events.js", self)
		self.assertEquals(5, len(ids))
		
		events = self.getEventsAndWait([1, 1])
		self.assertEqual(2, len(events))
		self.assertEqual(2, len(filter(None, events))) #FIXME:FAILS HERE
		self.assertTrue(events[0].id == events[1].id == 1)
		
	def testFindEventsId(self):
		test_event_1 = create_test_event_1()
		self.testSingleInsertGet()
		result = self.findEventIdsAndWait([])
		self.assertEquals(1, len(result))
		test_event_1[0][0] = 1
		self.assertEqual(result[0], test_event_1.id)
		
	def testFindNothing(self):
		result = self.findEventIdsAndWait([])
		self.assertEquals(0, len(result))

	def testFindNothingBackwards(self):
		result = self.findEventIdsAndWait([], timerange=(1000000,1))
		self.assertEquals(0, len(result))
		
	def testFindFilteredByEventButNotSubject(self):
		# revision rainct@ubuntu.com-20091128164327-j8ez3fsifd1gygkr (1185)
		# Fix _build_templates so that it works when the Subject is empty.
		self.testSingleInsertGet()
		result = self.findEventIdsAndWait([Event.new_for_values(interpretation=Interpretation.LEAVE_EVENT)])
		self.assertEquals(0, len(result))

	def testFindFive(self):
		import_events("test/data/five_events.js", self)
		result = self.findEventIdsAndWait([])
		self.assertEquals(5, len(result))
		
	def testFindFiveWithStorageState(self):
		import_events("test/data/five_events.js", self)
		# The event's storage is unknown, so we get them back always.
		result = self.findEventIdsAndWait([], storage_state = 1)
		self.assertEquals(5, len(result))
		result = self.findEventIdsAndWait([], storage_state = 0)
		self.assertEquals(5, len(result))

	def testFindWithNonExistantActor(self):
		# Bug 496109: filtering by timerange and a non-existing actor gave an
		# incorrect result.
		import_events("test/data/twenty_events.js", self)
		# The event's storage is unknown, so we get them back always.
		result = self.findEventIdsAndWait([Event.new_for_values(actor="fake://foobar")])
		self.assertEquals(0, len(result))

	def testFindWithSubjectText(self):
		import_events("test/data/five_events.js", self)
		result = self.findEventIdsAndWait([Event.new_for_values(subject_text='this is not real')])
		self.assertEquals(0, len(result))
		result = self.findEventIdsAndWait([Event.new_for_values(subject_text='some text')])
		self.assertEquals(1, len(result))
		result = self.findEventIdsAndWait([Event.new_for_values(subject_text='this *')])
		self.assertEquals(1, len(result)) #FIXME: Seems like we don't support wildcards properly

	def testSortFindByTimeAsc(self):
		import_events("test/data/twenty_events.js", self)
		result = self.findEventIdsAndWait([], num_events = 2, result_type = ResultType.LeastRecentEvents)
		event1 = self.getEventsAndWait([result[0]])[0]
		event2 = self.getEventsAndWait([result[1]])[0]
		self.assertEquals(True, event1.timestamp < event2.timestamp)
		
	def testSortFindByTimeDesc(self):
		import_events("test/data/twenty_events.js", self)
		result = self.findEventIdsAndWait([], num_events = 2, result_type = ResultType.MostRecentEvents)
		event1 = self.getEventsAndWait([result[0]])[0]
		event2 = self.getEventsAndWait([result[1]])[0]
		self.assertEquals(True, event1.timestamp > event2.timestamp)
	
	def testFindWithActor(self):
		test_event_1 = create_test_event_1()
		self.testSingleInsertGet()
		subj = Subject()
		event_template = Event.new_for_values(actor=TEST_ACTOR, subjects=[subj,])
		result = self.findEventIdsAndWait([event_template], num_events = 0, result_type = 1)
		self.assertEquals(1, len(result))
		test_event_1[0][0] = 1
		self.assertEqual(result[0], test_event_1.id)

	def testFindWithInterpretation(self):
		import_events("test/data/five_events.js", self)
		subj = Subject()
		event_template = Event.new_for_values(interpretation="stfu:OpenEvent", subjects=[subj])
		result = self.findEventIdsAndWait([event_template], num_events = 0, result_type = 1)
		self.assertEquals(2, len(result))
		events = self.getEventsAndWait(result)
		for event in events:
			self.assertEqual(event.interpretation, "stfu:OpenEvent")

	def testFindEventTwoInterpretations(self):
		import_events("test/data/twenty_events.js", self)
		result = self.findEventIdsAndWait([
			Event.new_for_values(interpretation="stfu:OpenEvent"),
			Event.new_for_values(interpretation="stfu:EvilEvent")],
			timerange = (102, 117), num_events = 0, result_type = 0)
		self.assertEquals(15, len(result))

	def testFindWithFakeInterpretation(self):
		import_events("test/data/twenty_events.js", self)
		result = self.findEventIdsAndWait([Event.new_for_values(interpretation="this-is-not-an-intrprettin")],
			num_events = 0, result_type = 0)
		self.assertEquals(0, len(result))

	def testFindWithManifestation(self):
		import_events("test/data/five_events.js", self)
		subj = Subject()
		event_template = Event.new_for_values(manifestation="stfu:EpicFailActivity", subjects=[subj])
		
		result = self.findEventIdsAndWait([event_template],
			num_events = 0, result_type = 1)
		self.assertEquals(1, len(result))
		events = self.getEventsAndWait(result)
		for event in events:
			self.assertEqual(event.manifestation, "stfu:EpicFailActivity")
			
	def testFindWithEventOrigin(self):
		import_events("test/data/twenty_events.js", self)
		event_template = Event.new_for_values(origin="origin3")
		result = self.findEventIdsAndWait([event_template], 
			num_events = 0, result_type = 1)
		events = self.getEventsAndWait(result)
		
		self.assertTrue(len(events) > 0)
		self.assertTrue(all(ev.origin == "origin3" for ev in events))
	
	def testFindWithEventOriginNegatedWildcard(self):
		import_events("test/data/twenty_events.js", self)
		event_template = Event.new_for_values(origin="!origin*")
		result = self.findEventIdsAndWait([event_template], 
			num_events = 0, result_type = 1)
		events = self.getEventsAndWait(result)
		
		self.assertTrue(len(events) > 0)
		self.assertFalse(any(ev.origin.startswith("origin") for ev in events))
	
	def testFindWithSubjectOrigin(self):
		import_events("test/data/five_events.js", self)
		subj = Subject.new_for_values(origin="file:///tmp")
		event_template = Event.new_for_values(subjects=[subj])
		result = self.findEventIdsAndWait([event_template], num_events = 0, result_type = 1)
		events = self.getEventsAndWait(result)
		for event in events:
			test = any(subj.origin == "file:///tmp" for subj in event.subjects)
			self.assertTrue(test)

	def testFindMultipleEvents(self):
		import_events("test/data/five_events.js", self)
		subj1 = Subject.new_for_values(uri="file:///home/foo.txt")
		event_template1 = Event.new_for_values(subjects=[subj1])
		subj2 = Subject.new_for_values(uri="file:///tmp/foo.txt")
		event_template2 = Event.new_for_values(subjects=[subj2])
		result = self.findEventIdsAndWait([event_template1, event_template2], num_events = 0, result_type = 4)
		self.assertEquals(2, len(result)) 
		events = self.getEventsAndWait(result)
		
	def testGetWithMultipleSubjects(self):
		subj1 = Subject.new_for_values(uri="file:///tmp/foo.txt")
		subj2 = Subject.new_for_values(uri="file:///tmp/loo.txt")
		event_template = Event.new_for_values(subjects=[subj1, subj2])
		result = self.insertEventsAndWait([event_template])
		events = self.getEventsAndWait(result)
		self.assertEquals(2, len(events[0].subjects))
		self.assertEquals("file:///tmp/foo.txt", events[0].subjects[0].uri)
		self.assertEquals("file:///tmp/loo.txt", events[0].subjects[1].uri)
	
	def testFindEventIdsWithMultipleSubjects(self):
		subj1 = Subject.new_for_values(uri="file:///tmp/foo.txt")
		subj2 = Subject.new_for_values(uri="file:///tmp/loo.txt")
		event = Event.new_for_values(subjects=[subj1, subj2])
		orig_ids = self.insertEventsAndWait([event])
		result_ids = self.findEventIdsAndWait([Event()], num_events = 0, result_type = 1)
		self.assertEquals(orig_ids, list(result_ids)) #FIXME: We need subjects of the same event to be merged
		
	def testFindEventsEventTemplate(self):
		import_events("test/data/five_events.js", self)
		subj = Subject.new_for_values(interpretation="stfu:Bee")
		subj1 = Subject.new_for_values(interpretation="stfu:Bar")
		event_template = Event.new_for_values(subjects=[subj, subj1])
		result = self.findEventIdsAndWait(
			[event_template, ],
			timerange = (0, 200),
			num_events = 100,
			result_type = 0)
		self.assertEquals(0, len(result)) # no subject with two different
										  # interpretations at the same time
		subj = Subject.new_for_values(uri="file:///tmp/foo.txt")
		subj1 = Subject.new_for_values(interpretation="stfu:Image")
		event_template = Event.new_for_values(subjects=[subj, subj1])
		result = self.findEventIdsAndWait(
			[event_template, ],
			timerange = (0, 200),
			num_events = 100,
			result_type = 0)
		self.assertEquals(1, len(result))
		
	def testJsonImport(self):
		import_events("test/data/single_event.js", self)
		results = self.getEventsAndWait([1])
		self.assertEquals(1, len(results))
		ev = results[0]
		self.assertEquals(1, ev.id)
		self.assertEquals("123", ev.timestamp)
		self.assertEquals("stfu:OpenEvent", ev.interpretation)
		self.assertEquals("stfu:UserActivity", ev.manifestation)
		self.assertEquals("firefox", ev.actor)
		self.assertEquals(1, len(ev.subjects))
		
		subj = ev.subjects[0]
		self.assertEquals("file:///tmp/foo.txt", subj.uri)
		self.assertEquals("stfu:Document", subj.interpretation)
		self.assertEquals("stfu:File", subj.manifestation)
		self.assertEquals("text/plain", subj.mimetype)
		self.assertEquals("this item has no text... rly!", subj.text)
		self.assertEquals("368c991f-8b59-4018-8130-3ce0ec944157", subj.storage)
		

if __name__ == "__main__":
	unittest.main()
