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

from zeitgeist import config

gettext.install('gnome-zeitgeist', config.localedir, unicode=1)


class ZeitgeistTrayIcon(gtk.StatusIcon):
	
	def __init__(self, mainloop):
		
		gtk.StatusIcon.__init__(self)
		
		self.set_from_file("%s/logo/scalable/apps/gnome-zeitgeist.svg" % config.pkgdatadir)
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
				"%s/zeitgeist-%s.py" % (config.bindir, frontend))
		else:
			os.kill(self._procs[frontend].pid, signal.SIGUSR2)
	
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
		from zeitgeist.gui.zeitgeist_engine_wrapper import engine
		engine.quit()
		
		# Quit
		self._mainloop.quit()


class AboutWindow(gtk.AboutDialog):
	
	def __init__(self):
		
		gtk.AboutDialog.__init__(self)
		
		self.set_name("GNOME Zeitgeist")
		self.set_version("0.0.6")
		self.set_copyright(u"Copyright 2009 © The Zeitgeist Team")
		self.set_website("http://zeitgeist.geekyogre.com")
		gtk.about_dialog_set_url_hook(self.open_url,None)
		gtk.about_dialog_set_email_hook(self.open_mail, None)
		
		self.set_program_name("GNOME Zeitgeist")
		self.set_icon_from_file("%s/logo/32x32/apps/gnome-zeitgeist.png" % config.pkgdatadir)
		
		pixbuf = gtk.gdk.pixbuf_new_from_file("%s/logo/scalable/apps/gnome-zeitgeist.svg" % config.pkgdatadir)
		
		pixbuf.scale_simple(512, 512, gtk.gdk.INTERP_NEAREST)
		
		self.set_logo(pixbuf)
		
		self.set_comments(_("GNOME Zeitgeist is a tool for easily browsing and finding files on your computer."))
		
		self.set_authors([
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
		if os.path.isfile(gplv3):
			self.set_license(open(gplv3).read())
		else:
			self.set_license(
				"GNU General Public License, version 3 or later")
		
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
