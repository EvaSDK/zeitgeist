#!/usr/bin/python

# Update python path to use local zeitgeist module
import sys
import os
import re
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _zeitgeist.loggers.datasources.recent import SimpleMatch, MimeTypeSet

class SimpleMatchTest(unittest.TestCase):
	
	def testmatch(self):
		self.assertTrue(SimpleMatch("boo/*").match("boo/bar"))
		self.assertTrue(SimpleMatch("boo/bar.*").match("boo/bar.foo"))
		self.assertFalse(SimpleMatch("boo/bar.*").match("boo/barfoo"))

class MimeTypeSetTest(unittest.TestCase):
	
	def testinit(self):
		self.assertEquals(repr(MimeTypeSet("boo", "bar", "foo")), "MimeTypeSet('bar', 'boo', 'foo')")
		self.assertEquals(repr(MimeTypeSet("boo", "foo", "foo")), "MimeTypeSet('boo', 'foo')")
		m = MimeTypeSet("boo", SimpleMatch("bar/*"), re.compile("test.*"))
		self.assertEquals(len(m), 3)
		self.assertRaises(ValueError, MimeTypeSet, 1)
		
	def testcontains(self):
		m = MimeTypeSet("boo", SimpleMatch("bar/*"), re.compile("test.*"))
		self.assertTrue("boo" in m)
		self.assertTrue("bar/boo" in m)
		self.assertTrue("testboo" in m)
		self.assertFalse("boobar" in m)
		self.assertFalse("bar" in m)

if __name__ == '__main__':
	unittest.main()
