#!/usr/bin/python
# -.- coding: utf-8 -.-

# Update python path to use local zeitgeist module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import _zeitgeist.engine
from _zeitgeist.engine import create_engine
from zeitgeist.datamodel import *
from testutils import import_events

import unittest

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

	ev.append_subject(subj)
	return ev
	
	
class _engineTestClass(unittest.TestCase):
	
	def setUp (self):
		global test_event_1
		test_event_1 = create_test_event_1()
		_zeitgeist.engine.DB_PATH = ":memory:"
		self.engine = create_engine()
		
	def tearDown (self):
		self.engine.close()
		_zeitgeist.engine._engine = None
	
	
class ZeitgeistEngineTest (_engineTestClass):
	"""
	This class tests that the zeitgeist.engine.engine.ZeitgeistEngine class
	"""
		
	def testSingleInsertGet(self):
		global test_event_1			
		# Insert item and event
		ids = self.engine.insert_events([test_event_1])
		result = self.engine.get_events(ids)
		
		self.assertEquals(1, len(result))
		resulting_event = result.pop()
		self.assertEquals(len(resulting_event), len(test_event_1))
		
		# fixing id, the initial event does not have any id set
		test_event_1[0][0] = 1
		
		self.assertEqual(resulting_event, test_event_1)		
		
		# Reset the id because other test cases rely on this one
		test_event_1[0][0] = None
	
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
		ids = self.engine.insert_events([ev])
		result = self.engine.get_events(ids)
		
		self.assertEquals(1, len(result))
		resulting_event = Event(result.pop())
		self.assertEquals("foo://bar", resulting_event.interpretation)
		self.assertTrue(ev.timestamp) # We should have a timestamp again
	
	def testDuplicateEventInsertion(self):
		self.testSingleInsertGet()
		self.assertRaises(KeyError, self.testSingleInsertGet)
	
	def testDeleteSingle(self):
		self.testSingleInsertGet()
		self.engine.delete_events([1])
		result = self.engine.get_events([1])
		self.assertEquals(0, len(filter(None, result)))
	
	def testIllegalPredefinedEventId(self):
		event = Event()
		event[0][0] = 23 # This is illegal, we assert the erro later
		event.timestamp = 0
		event.interpretation = Manifestation.USER_ACTIVITY
		event.manifestation = Interpretation.CREATE_EVENT
		event.actor = "/usr/share/applications/gnome-about.desktop"
		
		subject = Subject()
		subject.uri = "file:///tmp/file.txt"
		subject.manifestation = Manifestation.FILE
		subject.interpretation = Interpretation.DOCUMENT
		subject.origin = "test://"
		subject.mimetype = "text/plain"
		subject.text = "This subject has no text"
		subject.storage = "368c991f-8b59-4018-8130-3ce0ec944157" # UUID of home partition
		
		event.append_subject(subject)
		
		# Insert item and event
		self.assertRaises(ValueError, self.engine.insert_events, [event])
		
	def testGetNonExisting(self):
		events = self.engine.get_events([23,45,65])
		self.assertEquals(3, len(events))
		for ev in events : self.assertEquals(None, ev)
		
	def testFindEventsId(self):
		global test_event_1
		self.testSingleInsertGet()
		result = self.engine.find_eventids(
			(0, 100),
			[],
			0,
			5,
			0,)
		self.assertEquals(1, len(result))
		test_event_1[0][0] = 1
		self.assertEqual(result[0], test_event_1.id)
	
	def testFindNothing(self):
		result = self.engine.find_eventids(
			(10000, 1000000),
			[],
			0,
			5,
			0,)
		self.assertEquals(0, len(result))

	def testFindNothingBackwards(self):
		result = self.engine.find_eventids(
			(1000000, 1),
			[],
			0,
			5,
			0,)
		self.assertEquals(0, len(result))

	def testFindFive(self):
		import_events("test/data/five_events.js", self.engine)
		result = self.engine.find_eventids(
			(1, 10000000),
			[],
			0,
			5,
			0,)
		self.assertEquals(5, len(result))
	
	def testSortFindByTimeAsc(self):
		import_events("test/data/twenty_events.js", self.engine)
		result = self.engine.find_eventids(
			(1, 10000000),
			[],
			0,
			2,
			0,)
		event1 = self.engine.get_events([result[0]])[0]
		event2 = self.engine.get_events([result[1]])[0]
		self.assertEquals(True, event1.timestamp < event2.timestamp)
		
	def testSortFindByTimeDesc(self):
		import_events("test/data/twenty_events.js", self.engine)
		result = self.engine.find_eventids(
			(1, 10000000),
			[],
			0,
			2,
			1,)
		event1 = self.engine.get_events([result[0]])[0]
		event2 = self.engine.get_events([result[1]])[0]
		self.assertEquals(True, event1.timestamp > event2.timestamp)
	
	def testFindWithActor(self):
		global test_event_1
		self.testSingleInsertGet()
		subj = Subject()
		event_template = Event.new_for_values(actor=TEST_ACTOR, subjects=[subj,])
		result = self.engine.find_eventids(
			(0, 100),
			[event_template, ],
			0,
			0,
			1,)
		self.assertEquals(1, len(result))
		test_event_1[0][0] = 1
		self.assertEqual(result[0], test_event_1.id)

	def testFindWithInterpretation(self):
		import_events("test/data/five_events.js", self.engine)
		subj = Subject()
		event_template = Event.new_for_values(interpretation="stfu:OpenEvent", subjects=[subj])
		result = self.engine.find_eventids((0, 0), [event_template, ], 0, 0, 1)
		self.assertEquals(2, len(result))
		events = self.engine.get_events(result)
		for event in events:
			self.assertEqual(event.interpretation, "stfu:OpenEvent")
	
	def testFindWithManifestation(self):
		import_events("test/data/five_events.js", self.engine)
		subj = Subject()
		event_template = Event.new_for_values(manifestation="stfu:EpicFailActivity", subjects=[subj])
		result = self.engine.find_eventids((0, 0), [event_template, ], 0, 0, 1)
		self.assertEquals(1, len(result))
		events = self.engine.get_events(result)
		for event in events:
			self.assertEqual(event.manifestation, "stfu:EpicFailActivity")
	
	def testFindWithSubjectOrigin(self):
		import_events("test/data/five_events.js", self.engine)
		subj = Subject.new_for_values(origin="file:///tmp")
		event_template = Event.new_for_values(subjects=[subj])
		result = self.engine.find_eventids((0, 1000), [event_template, ], 0, 0, 1)
		events = self.engine.get_events(result)
		for event in events:
			test = any(subj.origin == "file:///tmp" for subj in event.subjects)
			self.assertTrue(test)
	
	def testDontFindState(self):
		# searchin by storage state is currently not implemented
		# checking for the error
		import_events("test/data/twenty_events.js", self.engine)
		self.assertRaises(NotImplementedError, self.engine.find_eventids,
			(1, 10000000),
			[],
			45,
			1,
			0,)
			
	def testFindEventsEventTemplate(self):
		import_events("test/data/five_events.js", self.engine)
		subj = Subject.new_for_values(interpretation="stfu:Bee")
		subj1 = Subject.new_for_values(interpretation="stfu:Bar")
		event_template = Event.new_for_values(subjects=[subj, subj1])
		result = self.engine.find_eventids(
			(0, 200),
			[event_template, ],
			0,
			100,
			0,)
		self.assertEquals(2, len(result))
	
	def testJsonImport(self):
		import_events("test/data/single_event.js", self.engine)
		results = self.engine.get_events([1])
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
		self.assertEquals("this item has not text... rly!", subj.text)
		self.assertEquals("368c991f-8b59-4018-8130-3ce0ec944157", subj.storage)
	
	def testGetHighestTimestampForActor(self):
		import_events("test/data/five_events.js", self.engine)
		result = self.engine.get_highest_timestamp_for_actor("firefox")
		self.assertEquals(163, result)
		
	def testInsertSubjectOptionalAttributes(self):
		ev = Event.new_for_values(
			timestamp=123,
			interpretation=Interpretation.VISIT_EVENT.uri,
			manifestation=Manifestation.USER_ACTIVITY.uri,
			actor="Freak Mamma"
		)
		subj = Subject.new_for_values(
			uri="void://foobar",
			interpretation=Interpretation.DOCUMENT.uri,
			manifestation=Manifestation.FILE.uri,
			)
		ev.append_subject(subj)
		
		ids = self.engine.insert_events([ev,])
		result = self.engine.get_events(ids)
		self.assertEquals(len(ids), len(result))
	
	def testEventWithoutSubject(self):
		ev = Event.new_for_values(timestamp=123,
					interpretation=Interpretation.VISIT_EVENT.uri,
					manifestation=Manifestation.USER_ACTIVITY.uri,
					actor="Freak Mamma")
		self.assertRaises(ValueError, self.engine.insert_events, [ev])
		
	def testUnicodeEventInsert(self):
		ids = import_events("test/data/unicode_event.js", self.engine)
		self.assertEquals(len(ids), 1)
		result = self.engine.get_events(ids)
		self.assertEquals(len(ids), len(result))
		subj = Subject.new_for_values(text="hällö, I'm gürmen")
		event_template = Event.new_for_values(subjects=[subj,])
		result = self.engine.find_eventids(
			(0, 200),
			[event_template, ],
			0,
			100,
			0,)
		self.assertEquals(len(result), 1)
		
		
class ZeitgeistRelevancyProviderTest(_engineTestClass):
	
	def testInsertFocusEvent(self):
		self.engine.register_focus("boo","boo")
		#self.assertRaises(ValueError, self.engine.insert_events, [ev])

if __name__ == "__main__":
	unittest.main()
