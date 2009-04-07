import gc
import datetime
import os
import re
import glob
from xml.dom.minidom import parse
from xml.parsers.expat import ExpatError

import gobject
import thread
import gtk
import shutil
import sqlite3 as db
import tempfile
import W3CDate
from gettext import gettext as _
from zeitgeist_util import FileMonitor
from zeitgeist_base import Data, DataProvider


class FirefoxSource(DataProvider):
    
    def __init__(self, name="Firefox History", icon="gnome-globe", uri="gzg/firefox"):
        DataProvider.__init__(self, name=name, icon=icon, uri = uri)
        self.name = "Firefox History"
        self.icon="gnome-globe"
        self.type = self.name
        self.comment = "websites visited with Firefox"
            
        self.historydb = glob.glob(os.path.expanduser("~/.mozilla/firefox/*/places.sqlite"))
        
        try:
            self.note_path_monitor = FileMonitor(self.historydb[0])
            self.note_path_monitor.connect("event", self.reload_proxy)
            self.note_path_monitor.open()
        #self.emit("reload")
        except:
            print "Are you using Firefox"
            
        try:
            self.loc = glob.glob(os.path.expanduser("~/.Zeitgeist/"))
            self.loc = self.loc[0]+"firefox.sqlite"
        except:
            pass
        
        try:
            self.last_timestamp = self.get_latest_timestamp()
        except Exception,ex:
            print ex
            self.last_timestamp = 0.0
                        
        
    
    def get_latest_timestamp(self): 
        self.connection = db.connect( self.loc,True)
        cursor = self.connection.cursor()
        
        contents = "visit_date"
        history = cursor.execute("SELECT " + contents + " FROM moz_historyvisits ORDER BY visit_date DESC").fetchone()
        self.timestamp=history[0]
    
    def reload_proxy(self,x=None,y=None,z=None):
        self.__copy_sqlite()
        self.emit("reload")
    
    
    def get_items_uncached(self):
        # create a connection to firefox's sqlite database
        self.connection = db.connect( self.loc,True)
        cursor = self.connection.cursor()
        
        # retrieve all urls from firefox history
        contents = "id, place_id, visit_date,visit_type"
        history = cursor.execute("SELECT " + contents + " FROM moz_historyvisits WHERE visit_date>?",(self.timestamp,)).fetchall()
        
        j = 0
        for i in history:
            # TODO: Fetch full rows above so that we don't need to do another query here
            contents = "id, url, title, visit_count"
            item = cursor.execute("SELECT " + contents +" FROM moz_places WHERE title!='' and id=" +str(i[1])).fetchone()
            if item:
                url = item[1]
                name = item[2]
                count = item[3]
                timestamp = history[j][2] / (1000000)
                self.timestamp =  history[j][2]
                if history[j][3]==2 or history[j][3]==3 or history[j][3]==5:
                    yield Data(uri=url,
                            name=name,
                            timestamp=timestamp,
                            count=count,
                            icon = "gnome-globe",
                            use="visited",
                            type="Firefox History")
                
                else:
                    yield Data(uri=url,
                            name=name,
                            timestamp=timestamp,
                            icon = "gnome-globe",
                            count=count,
                            use="linked",
                            type="Firefox History")
                
            j += 1
            
        cursor.close()
    
    def __copy_sqlite(self):
        '''
        Copy the sqlite file to avoid file locks when it's being used by firefox.
        '''
        try:
            shutil.copy2(self.historydb[0],  self.loc)
        except:
            pass
        
        