#! /usr/bin/env python
# -.- encoding: utf-8 -.-

import sys
import os
import gtk
import gobject
import signal
import subprocess
import webbrowser
import gettext

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../"))
gettext.install('gnome-zeitgeist', '/usr/share/locale', unicode=1)

from zeitgeist_shared.basics import BASEDIR


class ZeitgeistTrayIcon(gtk.StatusIcon):
	
	def __init__(self, mainloop):
		
		gtk.StatusIcon.__init__(self)
		
		self.set_from_file("%s/data/gnome-zeitgeist.png" % BASEDIR)
		self.set_visible(True)
		
		self._mainloop = mainloop
		self._procs = {}
		self._about = None
		
		menu = gtk.Menu()
		for (icon, name, callback, frontend) in (
				(gtk.STOCK_HOME, _("Open Journal"), None, 'journal'),
				#(gtk.STOCK_DIRECTORY, _("Open Project Viewer"), None, 'projectviewer'),
				#(gtk.STOCK_DIRECTORY, _("Open Timeline"), None, 'timeline'),
				#(gtk.STOCK_PREFERENCES, None, self.open_about, None),
				(gtk.STOCK_ABOUT, None, self.open_about, None),
				(gtk.STOCK_QUIT, None, self.quit, None),
			):
			menu_item = gtk.ImageMenuItem(icon)
			if name:
				menu_item.get_children()[0].set_label(name)
			menu.append(menu_item)
			if callback:
				menu_item.connect('activate', callback)
			elif frontend:
				menu_item.connect('activate', self._open_frontend, frontend)
		
		self.set_tooltip("GNOME Zeitgeist")
		self.connect('popup-menu', self.popup_menu_cb, menu)
		self.connect('activate', self._open_frontend, 'journal')
	
	def _open_frontend(self, widget, frontend):
		# If .poll does return None the process hasn't terminated yet.
		if frontend not in self._procs or self._procs[frontend].poll() != None:
			self._procs[frontend] = subprocess.Popen(
				"%s/src/zeitgeist_gui/zeitgeist-%s.py" % (BASEDIR, frontend))
	
	def open_about(self, widget):
		if not self._about:
			self._about = AboutWindow()
			self._about.connect("destroy", self._about_destroyed)
		self._about.show()
	
	def _about_destroyed(self, *discard):
		self._about = None
	
	def popup_menu_cb(self, widget, button, time, data=None):
		if button == 3 and data:
			data.show_all()
			data.popup(None, None, None, 3, time)
	
	def quit(self, *discard):
		# Stop the frontends
		for proc in (proc for proc in self._procs.values() if proc.poll() == None):
			os.kill(proc.pid, signal.SIGUSR1)
		
		# Stop the daemon
		from zeitgeist_gui.zeitgeist_engine_wrapper import engine
		engine.quit()
		
		# Quit
		self._mainloop.quit()


class AboutWindow(gtk.AboutDialog):
	
	def __init__(self):
		
		gtk.AboutDialog.__init__(self)
		
		self.set_name("GNOME Zeitgeist")
		self.set_version("0.0.5")
		self.set_copyright(u"Copyright 2009 © The Zeitgeist Team")
		self.set_website("http://zeitgeist.geekyogre.com")
		gtk.about_dialog_set_url_hook(self.open_url,None)
		gtk.about_dialog_set_email_hook(self.open_mail, None)
		
		self.set_program_name("GNOME Zeitgeist")
		self.set_icon_from_file("%s/data/gnome-zeitgeist.png" % BASEDIR)
		self.set_logo(gtk.gdk.pixbuf_new_from_file("%s/data/gnome-zeitgeist.png" % BASEDIR))
		
		self.set_comments(_("GNOME Zeitgeist is a tool for easily browsing and finding files on your computer."))
		
		self.set_authors([
						"Federico Mena-Quintero <federico@gnome.org>",
						"Jason Smith <jassmith@gmail.com>",
						"Ketil W. Aanensen <ketil.w.aanensen@gmail.com>",
						"Natan Yellin <aantny@gmail.com>",
						"Seif Lotfy <seilo@geekyogre.com>",
						"Siegfried-Angel Gevatter <rainct@ubuntu.com>",
						"Thorsten Prante <thorsten@prante.eu>"])
		
		self.set_artists([
						"Jason Smith <jassmith@gmail.com>",
						"José Luis Ricón <artirj@gmail.com>",
						"Kalle Persson <kalle@nemus.se>",
						"Martin Pinto-Bazurco <martinpintob@gmail.com>"])
		
		self.set_documenters([
						"Kalle Persson <kalle@nemus.se>",
						"Natan Yellin <aantny@gmail.com>",
						"Shane-Patrick Fagan <shanepatrickfagan@yahoo.ie>",
						"Seif Lotfy <seilo@geekyogre.com>",
						"Siegfried-Angel Gevatter <rainct@ubuntu.com>"])
		
		gplv3 = "/usr/share/common-licenses/GPL-3"
		if not os.path.isfile(gplv3):
			gplv3 = "%s/COPYING" % BASEDIR
		self.set_license(open(gplv3).read())
		
		self.connect("response", self.close)
		self.hide()
	
	def close(self, w, res=None):
		if res == gtk.RESPONSE_CANCEL:
			self.hide()
	
	def open_url(self, dialog, link, ignored):
		webbrowser.open_new(link)

	def open_mail(self, dialog, link, ignored):
		webbrowser.open_new("mailto:%s" % link)


if __name__ == "__main__":
	
	mainloop = gobject.MainLoop()
	
	trayicon = ZeitgeistTrayIcon(mainloop)
	
	mainloop.run()
