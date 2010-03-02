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
import gobject
import subprocess
import dbus.mainloop.glib
import gettext
import logging
import optparse

from zeitgeist import _config
_config.setup_path()

gettext.install("zeitgeist", _config.localedir, unicode=1)
logging.basicConfig(level=logging.DEBUG)

parser = optparse.OptionParser(version = _config.VERSION)
parser.add_option(
	"-r", "--replace",
	action = "store_true", default=False, dest = "replace",
	help = _("if another Zeitgeist instance is already running, replace it"))
parser.add_option(
	"--no-datahub",
	action = "store_false", default=True, dest = "start_datahub",
	help = _("do not start zeitgeist-datahub automatically"))
parser.add_option(
	"--quit",
	action = "store_true", default=False, dest = "quit",
	help = _("if another Zeitgeist instance is already running, replace it"))
parser.add_option(
	"--shell-completion",
	action = "store_true", default=False, dest = "shell_completion",
	help = optparse.SUPPRESS_HELP)

(_config.options, _config.arguments) = parser.parse_args()

if _config.options.shell_completion:
	options = set()
	for option in (str(option) for option in parser.option_list):
		options.update(option.split("/"))
	print ' '.join(options)
	sys.exit(0)

from _zeitgeist.engine.remote import RemoteInterface

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
mainloop = gobject.MainLoop()

try:
	RemoteInterface(mainloop = mainloop)
except RuntimeError, e:
	logging.error(unicode(e))
	sys.exit(1)

passive_loggers = os.path.join(_config.bindir, "zeitgeist-datahub.py")
if _config.options.start_datahub:
	if os.path.isfile(passive_loggers):
		subprocess.Popen(passive_loggers)
	else:
		logging.warning(
			_("File \"%s\" not found, not starting datahub") % passive_loggers)

logging.info(_(u"Starting Zeitgeist service..."))
mainloop.run()
