#!/usr/bin/python

import os
import glob
import unittest
import doctest
import logging
import sys

from optparse import OptionParser
parser = OptionParser()
parser.add_option("-v", action="count", dest="verbosity")
(options, args) = parser.parse_args()

if options.verbosity:
	# do more fine grained stuff later
	# redirect all debugging output to stderr
	logging.basicConfig(stream=sys.stderr)
else:
	logging.basicConfig(filename="/dev/null")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Find the test/ directory
testdir = os.path.dirname(os.path.abspath(__file__))
doctests = glob.glob(os.path.join(testdir, "*.rst"))

# Create a test suite to run all tests
# first, add all doctests
arguments = {"module_relative": False, "globs": {"sys": sys}}
suite = doctest.DocFileSuite(*doctests, **arguments)

# Add all of the tests from each file that ends with "-test.py"
for fname in os.listdir(testdir):
	if fname.endswith("-test.py"):
		fname = os.path.basename(fname)[:-3] # Get the filename and chop off ".py"
		module = __import__(fname)
		suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(module))

# Run all of the tests
unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
