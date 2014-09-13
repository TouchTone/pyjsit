#!/usr/bin/python

# Simple app to run on a file server to manage/download JSIT torrents

import sys, os, time, math, urllib, argparse, traceback
import cherrypy, json, collections

import jsit_manager, tools, preferences
pref = preferences.pref
from log import *


VERSION="0.5.0" # Adjusted by make_release

maxlogsize = 500 # Number of lines to keep for log

class Yajsis(object):

    def __init__(self, jsm, root):
        self._jsm = jsm
        self._root = root
        log(INFO, "Yajsis starting up...")
        
        self._nextUpdate = time.time()
        self._logBuf = collections.deque(maxlen = maxlogsize)
        self._deltaLogBuf = collections.deque(maxlen = maxlogsize)
        addLogCallback(self.recordLog)
        
        self._filter = ""
        
        
    def update(self):  
        log(DEBUG2)
        try:
            if time.time() < self._nextUpdate or self._jsm == None:
                return

            self._jsm.update()
            self._nextUpdate = time.time() + pref("yajsis", "updateRate", 5000) / 1000.
        except Exception, e:
            log(ERROR, "Caught %s!" % e)
            log(ERROR, traceback.format_exc())
            
        log(DEBUG2, "Leave")
            
    
    def handleURL(self, name):
        f = open(os.path.join(self._root, "yajsis_resources", name))
        
        tf = f.read()
        
        params = { "updateRate" : pref("yajsis", "updateRate"), "version" : VERSION }
        
        # Collect used labels
        filterlabelbuttons = ""
        for l in self._jsm.labels:
            filterlabelbuttons += "<option value='{0}'>{0}</option>" .format(l, l.replace(' ',''))
        
        params["filter-label-buttons"] = filterlabelbuttons

        
        setlabelbuttons = ""        
        for l in self._jsm.labels:
            setlabelbuttons += "<option>{0}</option>" .format(l)
        # setlabelbuttons += ""
        
        params["set-label-buttons"] = setlabelbuttons
            
        for k,v in params.iteritems():         
            #print type(tf), type(k), type(v)
            tf = tf.replace("{" + k + "}", str(v))
        
        return tf
    
    
    def isFiltered(self, tor):
        if self._filter == "+non-skipped":
            if tor.label in pref("autoDownload", "skipLabels", []):
                return True
            else:
                return False
        elif self._filter == "+all" or len(self._filter) == 0:
            return False
        else:
            if tor.label != self._filter:
                return True
        return False

    
    # Default: main page
    @cherrypy.expose
    def index(self):
        return self.handleURL("yajsis.html")

    @cherrypy.expose
    def yajsis_js(self):        
        return self.handleURL("yajsis.js")
    
    # Log handling
    def recordLog(self, fullmsg, threadName, ltime, level, levelName, caller, msg):
        if level > 3:
            return
         
        m = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M"), msg.replace('\n', '<br/>'))
        lclass = ""
        if level == 2:
            lclass='log_warning'
        elif level == 1:
            lclass='log_error'
        m = "<span class='" + lclass + "'>" + m + "<br/></span>"
        
        self._logBuf.appendleft(m)            
        self._deltaLogBuf.appendleft(m)
            
         
    @cherrypy.expose
    def getLog(self):       
        self._deltaLogBuf.clear()
        return json.dumps(list(self._logBuf))
        
        
    @cherrypy.expose
    def clearLog(self):       
        self._logBuf.clear()
        self._deltaLogBuf.clear()
        
        
    @cherrypy.expose
    def updateLog(self):
    
        data = list(self._deltaLogBuf)
        self._deltaLogBuf.clear()
        
        return json.dumps(data)
        
        
    @cherrypy.expose
    def addTorrents(self, text):       
        log(DEBUG)
        for l in urllib.unquote(text).split('\n'):
            if l.startswith('magnet:') or l.startswith("http"):
                self._jsm.addTorrentURL(l)
                
    
    # Torrent handling
    @cherrypy.expose
    def updateTorrentList(self, *args, **kwargs):
        log(DEBUG)
        self._jsm.update(force = True)
        

    @cherrypy.expose
    def updateTorrents(self, *args, **kwargs):
        if self._jsm == None:
            return
            
        d = []       
        
        skiplabels = pref("autoDownload", "skipLabels", [])
        
        for t in self._jsm:
            if not t.isDownloading and not t.hasFinished and not t.isChecking:
                if self.isFiltered(t):
                    continue

                try:
                    d.append([t.name, t.size, round(float(t._torrent.percentage), 2), t._torrent.label, t.priority,
                              t._torrent.data_rate_in, t._torrent.etc, 
                              t._torrent.elapsed, "<button class='download' onclick='startDownload(event, \"{0}\");'>Download</button><button class='download' onclick='deleteTorrent(event, \"{0}\");'>Delete</button>".format(t.hash)])
                except IOError, e:
                    log(ERROR, "Caught %s, perc = %s" % (e, t._torrent.percentage))
        
        return json.dumps({ "data" : d } )
        
        
    @cherrypy.expose
    def updateChecking(self, *args, **kwargs):
        if self._jsm == None:
            return

        d = []       
        
        for t in self._jsm:
            if t.isChecking:
                d.append([t.name, t.size, "%s / %s / found" % (round(float(t.checkProgress * 100), 2), round(float(t.checkPercentage * 100), 2)), 
                    "<button class='stop' onclick='stopDownload(event, \"%s\");'>Stop Download</button>" % t.hash])
            
        return json.dumps({ "data" : d })
        
        
    @cherrypy.expose
    def updateDownloading(self, *args, **kwargs):
        if self._jsm == None:
            return
            
        d = []       
        
        for t in self._jsm:
            if t.isDownloading and not t.hasFailed and not t.hasFinished:
                d.append([t.name, t.size, 
                    "%s / %s / avail" % (round(float(t.downloadPercentage), 2), round(float(t.tpercentage), 2)), 
                    t.priority, t.downloadSpeed, t.etd, t._torrent.elapsed, 
                    "<button class='stop' onclick='stopDownload(event, \"%s\");'>Stop Download</button>" % t.hash, t.hash])
            
        return json.dumps({ "data" : d, "speed" : self._jsm.downloadSpeed, "left" : self._jsm.leftToDownload } )
        
        
    @cherrypy.expose
    def updateFinished(self, *args, **kwargs):
        if self._jsm == None:
            return
            
        d = []       
        
        for t in self._jsm:
            if t.hasFinished:
                if t.checkedComplete:
                    d.append([t.name, t.size, t._torrent.label, t.finishedAt, "<button class='recheck' disabled onclick='startDownload(event, \"%s\");'>Checked Complete</button>" % t.hash])
                else:
                    d.append([t.name, t.size, t._torrent.label, t.finishedAt, "<button class='recheck' onclick='startDownload(event, \"%s\");'>Recheck</button>" % t.hash])
                
            if t.hasFailed:
                d.append([t.name, t.size, t._torrent.label, "-", "<button class='restart' onclick='startDownload(event, \"%s\");'>Failed! Restart?</button>" % (t.hash)])
            
        return json.dumps({ "data" : d } )

                
    @cherrypy.expose
    def setFilter(self, filter):
        log(DEBUG)
        
        self._filter = filter
                
                
    @cherrypy.expose
    def setLabel(self, hash, label):
        log(DEBUG)
        t = self._jsm.lookupTorrent(hash)
        if not t:
            log(ERROR, "Torrent %s not found!" % hash)
            return
            
        t.label = label
        
                
    @cherrypy.expose
    def setPriority(self, hash, prio):
        t = self._jsm.lookupTorrent(hash)
        if not t:
            log(ERROR, "Torrent %s not found!" % hash)
            return
            
        log(DEBUG, "Setting priority of torrent %s to %s (%d)" % (t.name, prio, jsit_manager.PriorityE.attribs[prio]))       
        t.priority = jsit_manager.PriorityE.attribs[prio]
 
        
    @cherrypy.expose
    def startDownload(self, hash):
        log(DEBUG)
        
        t = self._jsm.lookupTorrent(hash)
        if not t:
            log(ERROR, "Torrent %s not found!" % hash)
            return
            
        t.startDownload()
        
        
    @cherrypy.expose
    def startDownloadAll(self):
        log(DEBUG)
        
        for t in self._jsm:
            if not self.isFiltered(t):
                t.startDownload()
        
         
    @cherrypy.expose
    def stopDownload(self, hash):
        log(DEBUG)
        
        t = self._jsm.lookupTorrent(hash)
        if not t:
            log(ERROR, "Torrent %s not found!" % hash)
            return
            
        t.stopDownload()
 
        
    @cherrypy.expose
    def delete(self, hash):
        log(DEBUG)
        
        t = self._jsm.lookupTorrent(hash)
        if not t:
            log(ERROR, "Torrent %s not found!" % hash)
            return
            
        t.delete()


def stopit():
    log(INFO, "CherryPy is stopping, releasing jsm...")
    jsm.release()
    logRelease()
   
    
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
    parser.add_argument('--port', dest='port', action='store', type=int,
                       default=0, help='port (default: 8282)')

    args = parser.parse_args()

    prefs = args.preferences
   
    if not os.path.isfile(prefs):    
        if not os.path.isabs(prefs):
            if os.path.isfile(os.path.join(basedir, "preferences.json")):
                prefs = os.path.join(basedir, "preferences.json")
            else:
                prefs = os.path.join(basedir, "defaults.json")
        else:
            log(ERROR, "Couldn't load preferences file '%s'!" % prefs)

    prefbase = basedir
    if prefs:            
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
                        'tools.staticdir.dir': '%s/yajsis_resources' % root}, 
            '/images': {'tools.staticdir.on': True,
                        'tools.staticdir.dir': '%s/yajsis_resources/images' % root},
            '/favicon.ico' : {
                          'tools.staticfile.on': True,
                          'tools.staticfile.filename': '%s/yajsis_resources/favicon.ico' % root}
           }

    #cherrypy.engine.subscribe('stop', theD.quit)  

    global jsm
    if args.username and args.password:   
        jsm = jsit_manager.Manager(args.username, args.password)
    elif pref("jsit", "username", None) and pref("jsit", "password", None):
        jsm = jsit_manager.Manager(pref("jsit", "username"), pref("jsit", "password"))
    else:
        log(ERROR, "Need username and password from command line or preferences file!")
        sys.exit(1)

    if args.port != 0:
        port = args.port
    else:
        port = pref("yajsis", "port", 8282)
    
    ys = Yajsis(jsm, root)

    cherrypy.engine.subscribe('stop', stopit, 10)
    
    cherrypy.engine.housekeeper = cherrypy.process.plugins.BackgroundTask(pref("yajsis", "updateRate", 5000) / 1000., ys.update)
    cherrypy.engine.housekeeper.start()

    cherrypy.config.update( { 'server.socket_host': '0.0.0.0', 'server.socket_port': port } ) 


    # Helpers to debug the darn hangups...
    if True:
        import stacktracer
        stacktracer.trace_start("trace.html",interval=5,auto=True) # Set auto flag to always update file!
        cherrypy.quickstart(ys, '/', config = conf)
        stacktracer.trace_stop()
        
    elif False:
        import trace
        tracer = trace.Trace(count=0, trace=1, ignoredirs=[sys.prefix, sys.exec_prefix], ignoremods=[])
        tracer.run("cherrypy.quickstart(ys, '/', config = conf)")
        
    else:    
        cherrypy.quickstart(ys, '/', config = conf)




