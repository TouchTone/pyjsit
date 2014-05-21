#!/usr/bin/python

# Simple app to run on a file server to manage/download JSIT torrents

import sys, os, time, math, urllib, argparse
import cherrypy, json

import jsit_manager, tools, preferences
pref = preferences.pref
from log import *


VERSION="0.4.0 (57f7b77)" # Adjusted by make_release


class Yajsis(object):

    def __init__(self, jsm):
        self._jsm = jsm
        log(INFO, "Yajsis starting up...")
        
        self._nextUpdate = time.time()
        self._logBuf = ""
        self._deltaLogBuf = ""
        addLogCallback(self.recordLog)
        
        
    def update(self):       
        if time.time() < self._nextUpdate or not self._jsm:
            return
            
        self._jsm.update()
        self._nextUpdate = time.time() + pref("yajsis", "updateRate") / 1000.
        
    
    # Default: main page
    @cherrypy.expose
    def index(self):
        raise cherrypy.HTTPRedirect("res/yajsis.html")
        
    
    # Log handling
    def recordLog(self, fullmsg, threadName, ltime, level, levelName, caller, msg):
        if level > 3:
            return
         
        m = "%s  %s</br>" % (time.strftime("%Y-%m-%d %H:%M"), msg)
        self._logBuf += m
        self._deltaLogBuf += m
        
        
    @cherrypy.expose
    def getLog(self):       
        self._deltaLogBuf = ""
        return json.dumps(self._logBuf)
        
        
    @cherrypy.expose
    def clearLog(self):       
        self._logBuf = ""
        self._deltaLogBuf = ""
        
    @cherrypy.expose
    def updateLog(self):
    
        data = self._deltaLogBuf
        self._deltaLogBuf = ""
        
        return json.dumps(data)
        
    @cherrypy.expose
    def addTorrents(self, text):       
        log(DEBUG)
        for l in urllib.unquote(text).split('\n'):
            if l.startswith('magnet:') or l.startswith("http"):
                self._jsm.addTorrentURL(l)
                
    
    # Torrent handling
    @cherrypy.expose
    def updateTorrents(self, *args, **kwargs):
        if not self._jsm:
            return
            
        d = []       
        
        for t in self._jsm:
            if not t.isDownloading and not t.hasFinished and not t.isChecking:
                try:
                    d.append([t.name, t.size, math.floor(float(t._torrent.percentage)), t._torrent.label, t._torrent.data_rate_in, t._torrent.etc, t._torrent.ttl, 
                        "<button class='download' onclick='startDownload(\"%s\");'>Download</button>" % t.hash])
                except IOError, e:
                    log(ERROR, "Caught %s, perc = %s" % (e, t._torrent.percentage))
            
        return json.dumps({ "data" : d } )
        
        
    @cherrypy.expose
    def updateChecking(self, *args, **kwargs):
        if not self._jsm:
            return

        d = []       
        
        for t in self._jsm:
           if t.isChecking:
                d.append([t.name, t.size, math.floor(float(t.checkProgress)), 
                    "<button class='stop' onclick='stopDownload(\"%s\");'>Stop Download</button>" % t.hash])
            
        return json.dumps({ "data" : d } )
        
        
    @cherrypy.expose
    def updateDownloading(self, *args, **kwargs):
        if not self._jsm:
            return
            
        d = []       
        
        for t in self._jsm:
            if t.isDownloading and not t.isChecking and t.downloadPercentage >= 0 and t.downloadPercentage < 100:
                d.append([t.name, t.size, math.floor(float(t.downloadPercentage)), t.downloadSpeed, t.etd, t._torrent.ttl, 
                    "<button class='stop' onclick='stopDownload(\"%s\");'>Stop Download</button>" % t.hash])
            
        return json.dumps({ "data" : d } )
        
        
    @cherrypy.expose
    def updateFinished(self, *args, **kwargs):
        if not self._jsm:
            return
            
        d = []       
        
        for t in self._jsm:
            if t.hasFinished:
                d.append([t.name, t.size, t._torrent.label, t.finishedAt])
            
        return json.dumps({ "data" : d } )

        
    @cherrypy.expose
    def startDownload(self, hash):
        log(DEBUG)
        
        t = self._jsm.lookupTorrent(hash)
        if not t:
            log(ERROR, "Torrent %s not found!" % hash)
            return
            
        t.startDownload()
         
    @cherrypy.expose
    def stopDownload(self, hash):
        log(DEBUG)
        
        t = self._jsm.lookupTorrent(hash)
        if not t:
            log(ERROR, "Torrent %s not found!" % hash)
            return
            
        t.stopDownload()
       


def stopit():
    log(INFO, "CherryPy is stopping, releasing jsm...")
    jsm.release()
   
    
if __name__=="__main__":

    if getattr(sys, 'frozen', None):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)

    parser = argparse.ArgumentParser(description='JSIT Download Server')
    parser.add_argument('--preferences', dest='preferences', action='store', type=str,
                       default="preferences.json",
                       help='preferences file to use')
    parser.add_argument('--username', '-u', dest='username', action='store', type=str,
                       default=None, help='user name (default: take from preferences)')
    parser.add_argument('--password', '-p', dest='password', action='store', type=str,
                       default=None, help='password (default: take from preferences)')

    args = parser.parse_args()

    prefs = args.preferences
   
    if not os.path.isfile(prefs):    
        if not os.path.isabs(prefs):
            if os.path.isfile(os.path.join(basedir, "preferences.json")):
                prefs = os.path.join(basedir, "preferences.json")
            else:
                prefs = os.path.join(basedir, "defaults.json")
        else:
            log(ERROR, "Couldn't load preferences file '%s', aborting!" % prefs)
            sys.exit(1)
           
    preferences.load(prefs)
    prefbase = prefs.rsplit(os.path.sep, 1)
    if len(prefbase) == 1:
        prefbase = '.'
    else:
        prefbase = prefbase[0]
        
    setLogLevel(pref("yajsis", "logLevel", INFO))
    setFileLog(os.path.join(prefbase, "yajsis.log"), pref("yajsis", "fileLogLevel", DEBUG))

    root = os.path.abspath(os.path.dirname(__file__))
    
    conf = {'/' :      {'tools.sessions.on': True },
            '/res':    {'tools.staticdir.on': True,
                        'tools.staticdir.dir': '%s/yajsis_ressources' % root}, 
            '/images': {'tools.staticdir.on': True,
                        'tools.staticdir.dir': '%s/yajsis_ressources/images' % root}
           }

    #cherrypy.engine.subscribe('stop', theD.quit)  

    global jsm
    if args.username and args.password:   
        jsm = jsit_manager.Manager(args.username, args.password)
    else:
        jsm = jsit_manager.Manager(pref("jsit", "username"), pref("jsit", "password"))

    ys = Yajsis(jsm)

    cherrypy.engine.subscribe('stop', stopit, 10)
    cherrypy.engine.subscribe('main', ys.update, 10)

    cherrypy.config.update( { 'server.socket_host': '0.0.0.0', 'server.socket_port': 8282 } )         
    cherrypy.quickstart(ys, '/', config = conf)




