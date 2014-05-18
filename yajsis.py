#!/usr/bin/python

# Simple app to run on a file server to manage/download JSIT torrents

import sys, os, time, math
import cherrypy, json

import jsit_manager, tools, preferences
pref = preferences.pref
from log import *


class Yajsis(object):

    def __init__(self, jsm):
        self._jsm = jsm
        log(INFO, "Yajsis starting up...")
        
        self._nextUpdate = time.time()
        self._logBuf = ""
        self._deltaLogBuf = ""
        addLogCallback(self.recordLog)
        
        
    def update(self):       
        if time.time() < self._nextUpdate:
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
                
    
    # Torrent handling
    @cherrypy.expose
    def updateTorrents(self, *args, **kwargs):
        d = []       
        
        for t in self._jsm:
            if not t.isDownloading and not t.hasFinished:
                try:
                    d.append([t.name, t.size, math.floor(float(t._torrent.percentage)), t._torrent.label, t._torrent.ttl, 
                        "<button class='download' onclick='startDownload(\"%s\");'>Download</button>" % t.hash])
                except Exception, e:
                    log(ERROR, "Caught %s, perc = %s" % (e, t._torrent.percentage))
            
        return json.dumps({ "data" : d } )
        
        
    @cherrypy.expose
    def updatePending(self, *args, **kwargs):
        d = []       
        
        for t in self._jsm:
           if t.isDownloading and t.downloadPercentage == 0:
                d.append([t.name, t.size, math.floor(float(t._torrent.percentage)), t._torrent.label, 
                    "<button class='stop' onclick='stopDownload(\"%s\");'>Stop Download</button>" % t.hash])
            
        return json.dumps({ "data" : d } )
        
        
    @cherrypy.expose
    def updateDownloading(self, *args, **kwargs):
        d = []       
        
        for t in self._jsm:
            if t.isDownloading and t.downloadPercentage > 0 and t.downloadPercentage < 100:
                d.append([t.name, t.size, math.floor(float(t.downloadPercentage)), t._torrent.label, t._torrent.ttl, 
                    "<button class='stop' onclick='stopDownload(\"%s\");'>Stop Download</button>" % t.hash])
            
        return json.dumps({ "data" : d } )
        
        
    @cherrypy.expose
    def updateFinished(self, *args, **kwargs):
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

    if os.path.isfile(os.path.join(basedir, "preferences.json")):
        preferences.load(os.path.join(basedir, "preferences.json"))
    else:
        preferences.load(os.path.join(basedir, "defaults.json"))


    setLogLevel(pref("yajsis", "logLevel", INFO))
    setFileLog(os.path.join(basedir, "yajsis.log"), pref("yajsis", "fileLogLevel", DEBUG))

    root = os.path.abspath(os.path.dirname(__file__))
    
    conf = {'/' :      {'tools.sessions.on': True },
            '/res':    {'tools.staticdir.on': True,
                        'tools.staticdir.dir': '%s/yajsis_ressources' % root}, 
            '/images': {'tools.staticdir.on': True,
                        'tools.staticdir.dir': '%s/yajsis_ressources/images' % root}
           }

    #cherrypy.engine.subscribe('stop', theD.quit)  

    if len(sys.argv) < 3:
        print "Call as %s <username> <password>" % sys.argv[0]
        sys.exit(1)

    global jsm
    jsm = jsit_manager.Manager(sys.argv[1], sys.argv[2])

    ys = Yajsis(jsm)

    cherrypy.engine.subscribe('stop', stopit, 10)
    cherrypy.engine.subscribe('main', ys.update, 10)

    cherrypy.config.update( { 'server.socket_host': '127.0.0.1', 'server.socket_port': 8282 } )         
    cherrypy.quickstart(ys, '/', config = conf)




