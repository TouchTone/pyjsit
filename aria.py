#!/usr/bin/python

# Helper module to control aria2c from Python

import subprocess, requests, random, xmlrpclib, time, urllib, socket
import os, weakref

from log import *
from tools import *


class AriaError(Exception):
    def __init__(self, value):
        self.value = value
    
    def __str__(self):
        return "AriaError: " + repr(self.value)
        
   
# Download set handler class

class Download(object):

    _status_keys = ["gid", "status", "totalLength", "completedLength", "downloadSpeed", "errorCode", "dir", "files" ]
    
    def __init__(self, aria, uris, basedir = u".", fullsize = None, unquoteNames = True, interpretDirectories = True, startPaused = True, torrentdata = None):
    
        self._aria = weakref.ref(aria)
        
        self._fullsize = fullsize
        self._basedir = basedir
        
        if isinstance(uris, str):
            uris = [uris]

        if torrentdata:
            finished, dummy, finishedBytes = checkTorrentFiles(self._basedir, torrentdata)
        else:
            finished = []
            finishedBytes = 0
        
        self._finishedBytes = finishedBytes
        self._gids = []
        
        mc = xmlrpclib.MultiCall(self._aria()._server)
        
        for u in uris:
            
            name = u.rsplit('/', 1)[1]
            dir = basedir
            if dir == None:
                dir = u"."
            
            # Make absolute in case aria executable was started somewhere else...
            dir = os.path.abspath(dir)
            
            if unquoteNames:
                name = urllib.unquote(name)
          
            name = unicode_cleanup(name)
            
            #print "A:name=%r dir=%r\n" % (name, dir)
            
            if interpretDirectories:
                nf = name.rsplit(u'/', 1)
                ##print "B:nf=%s" % (nf)
                
                if len(nf) > 1:
                    dir += u"/" + nf[0]
                    name = nf[1]
           
            ##print "B:name=%s dir=%s" % (name, dir)
           
            if os.path.join(dir, name) in finished:
                log(DEBUG, u"Download: %s/%s already finished, skipped.\n" % (dir, name))
                continue
                
            log(DEBUG, u"Download: will download %s to %s as %s\n" % (u, dir, name))
            
            mkdir_p(dir)
            
            # Basic Options
            opts = {"continue" : "true"}

            if startPaused:
                opts["pause"] = "true"

            if dir != ".":
                opts["dir"] = dir
                
            opts["out"] = name
            
            mc.aria2.addUri([u], opts)
           
        r = mc()  

        self._gids += list(r)
        
        
        # Info data
        self._dataValidUntil = 0
    
        self._downloaded        = 0
        self._downloadSpeed     = 0.
        self._filesPending      = 0
            
    
    def __repr__(self):
        return "aria:Download(%r (0x%x))"% (self._basedir, id(self))
        
        
    # Set up properties for attributes
    downloaded                    = property(lambda x: x.getUpdateValue("_downloaded"),      None)
    downloadSpeed                 = property(lambda x: x.getUpdateValue("_downloadSpeed"),   None)
    filesPending                  = property(lambda x: x.getUpdateValue("_filesPending"),    None)
  


    def startAriaDownloads(self, finished, finishedBytes, basedir, startPaused):
        
        self._finishedBytes = finishedBytes
        self._gids = []
        
        mc = xmlrpclib.MultiCall(self._aria()._server)
        
        for u in uris:
            
            name = u.rsplit('/', 1)[1]
            dir = basedir
            if dir == None:
                dir = u"."
            
            # Make absolute in case aria executable was started somewhere else...
            dir = os.path.abspath(dir)
            
            if unquoteNames:
                name = urllib.unquote(name)
          
            name = unicode_cleanup(name)
            
            #print "A:name=%r dir=%r\n" % (name, dir)
            
            if interpretDirectories:
                nf = name.rsplit(u'/', 1)
                ##print "B:nf=%s" % (nf)
                
                if len(nf) > 1:
                    dir += u"/" + nf[0]
                    name = nf[1]
           
            ##print "B:name=%s dir=%s" % (name, dir)
           
            if os.path.join(dir, name) in finished:
                log(DEBUG, u"Download: %s/%s already finished, skipped.\n" % (dir, name))
                continue
                
            log(DEBUG, u"Download: will download %s to %s as %s\n" % (u, dir, name))
            
            mkdir_p(dir)
            
            # Basic Options
            opts = {"continue" : "true"}

            if startPaused:
                opts["pause"] = "true"

            if dir != ".":
                opts["dir"] = dir
                
            opts["out"] = name
            
            mc.aria2.addUri([u], opts)
           
        r = mc()  

        self._gids += list(r)
        
           

    # Generic getter

    def getUpdateValue(self, name):
        self.updateData()
        return getattr(self, name)
    
    
    def updateData(self, force = False):
        log(DEBUG)
        
        if time.time() < self._dataValidUntil and not force:
            return
        
        st = self.statusAll()
       
        self._downloaded = 0
        self._downloadSpeed = 0.
        self._filesPending = 0
       
        for s in st:
            self._downloaded += int(s["completedLength"])
            self._downloadSpeed += float(s["downloadSpeed"])
       
            if not s["status"] == "complete":
                self._filesPending += 1
       
        self._dataValidUntil =  time.time() + 0.5 # Just to keep from hitting the aria server for every variable access
        
        
    def statusAll(self):
        s = []
        
        # Use multicall to reduce pressure on aria2
        mc = xmlrpclib.MultiCall(self._aria()._server)
        
        for g in self._gids:
            mc.aria2.tellStatus(g, self._status_keys)
        
        res = mc()
        
        for r in res:
            s.append(r)
        
        return s
    
    
    def stop(self):
        mc = xmlrpclib.MultiCall(self._aria()._server)
        for g in self._gids:
            mc.aria2.pause(g)
        res = mc()
        return res
        
     
    def start(self):
        mc = xmlrpclib.MultiCall(self._aria()._server)
        for g in self._gids:
            mc.aria2.unpause(g)
        res = mc()
        return res
        
     
    def cleanup(self):
        mc = xmlrpclib.MultiCall(self._aria()._server)
        for g in self._gids:
            mc.aria2.removeDownloadResult(g)
        res = mc()
        return res
        
   
    def delete(self):
        self._aria().deleteTorrent(self)
    
    
    def recheckDownload(self, torrentdata):
        log(ERROR, "Not implemented yet!\n")
        return
        # Remove all downloads
        if self._gids:

            # Use multicall to reduce pressure on aria2
            mc = xmlrpclib.MultiCall(self._aria()._server)

            for g in self._gids:
                mc.aria2.remove(g)

            res = mc()
        
        
        
        
    @property
    def percentage(self):
        # This can happen if everything has been downloaded already.
        if len(self._gids) == 0:
            return 100.
            
        total = 0.
        completed = 0.
        
        # Use multicall to reduce pressure on aria2
        mc = xmlrpclib.MultiCall(self._aria()._server)
        
        for g in self._gids:
            mc.aria2.tellStatus(g, ["completedLength", "totalLength"])

        res = mc()
                
        for i,s in enumerate(res):
            log(DEBUG2, "%s: total=%s completed=%s\n" % (self._gids[i], s["totalLength"], s["completedLength"]))
            total     += int(s["totalLength"])
            completed += int(s["completedLength"])
       
        # Do we know the full size a priory?
        if self._fullsize:
            total = self._fullsize
            completed += self._finishedBytes    # Add completed a priori parts
        
        # This can happen at startup, before any sizes are known
        if total == 0:
            return 0
        
        # Make sure we return 100 for completion. Float math is tricky.
        if total == completed:
            return 100.
            
        return completed * 100. / total
        
   
    @property
    def hasFinished(self):
        for g in self._gids:
            s = self._aria()._server.aria2.tellStatus(g, ["status"])
            if s["status"] != "complete":
                return False
        
        return True

        
        
# Main class providing aria process and access

class Aria(object):
    
    def __init__(self, cleanupLeftovers = False, port = 6800, private = False):
        
        log(DEBUG, "Starting aria process...\n");
        
        # Currently running downloads
        self._downloads = []
        
        # Start aria process
        self._username = "user" + str(random.randint(0,100000)) * private
        self._password = "pass" + str(random.randint(0,100000)) * private
        
        
        try:
            self._proc = subprocess.Popen(["aria2c", "--enable-rpc=true", "--rpc-user="+self._username, "--rpc-passwd="+self._password, "--rpc-listen-port=%d" % port], 
                                          stdout=subprocess.PIPE)
        except OSError:
            raise AriaError("Couldn't start aria, is it installed and in your PATH?")
            
        self._server = xmlrpclib.ServerProxy('http://%s:%s@localhost:%d/rpc' % (self._username, self._password, port))
        
        socket.setdefaulttimeout(5) # Do a quick timeout to catch problems
        
        # wait for server to start up
        running = False
        while not running:
            try:
                self._server.aria2.tellActive()
                running = True
            except IOError:
                time.sleep(0.2)
            except xmlrpclib.ProtocolError, e:
                log(ERROR, u"Couldn't connect to aria process. Is an old one still running? Aborting...\n")
                raise e
        
        # Any leftovers?
        s = self.status
        if s["numStopped"] or s["numWaiting"] or s["numActive"]:
            log(WARNING, u"Found leftovers in aria process (%d active, %d waiting, %d stopped)!\n" % (s["numActive"], s["numWaiting"], s["numStopped"]))
            if cleanupLeftovers:
                log(WARNING, u"Cleaning them up.\n")
                self._server.aria2.pauseAll()
                for dl in self._server.aria2.tellActive() + self._server.aria2.tellWaiting(0, 10000):
                    if dl["status"]  != "complete":
                        self._server.aria2.remove(dl["gid"])
                self._server.aria2.purgeDownloadResult()
                s = self.status
                if s["numStopped"] or s["numWaiting"] or s["numActive"]:
                    log(ERROR, u"Couldn't finish cleanup of aria process (%d active, %d waiting, %d stopped), aborting!\n" % 
                                (s["numActive"], s["numWaiting"], s["numStopped"]))
                    sys.exit(1)
                    
        # Some basic setup
        self._server.aria2.changeGlobalOption({'log':'aria.log'})
        self._server.aria2.changeGlobalOption({'log-level':'debug'})
        ##self._server.aria2.changeGlobalOption({'log-level':'error'})

        self._server.aria2.changeGlobalOption({'max-overall-download-limit':'0'})
        self._server.aria2.changeGlobalOption({'max-concurrent-downloads':'10'})
        ##self._server.aria2.changeGlobalOption({'max-overall-download-limit':'20K'})
        ##self._server.aria2.changeGlobalOption({'max-concurrent-downloads':'2'})
         
    
    def __repr__(self):
        return "Aria(0x%x)"% id(self)
        
    
    def __del__(self):
        log(DEBUG)
        self.release()
    
    def __enter__(self):
        log(DEBUG)
        return self
    
    def __exit__(self, type, value, traceback):
        log(DEBUG)
        self.release()

       
    def release(self):     
        log(DEBUG, "Stopping aria process...\n");
        self._proc.terminate()
  
  
    # Iterator access to downloads list 
           
    def __iter__(self):
        return iter(self._downloads)

    # Status 

    @property
    def hasFinished(self):
        s = self.status     
        return s["numActive"] + s["numWaiting"] == 0

    @property
    def status(self):
        s = self._server.aria2.getGlobalStat()
        for k,v in s.iteritems():
            if u"Speed" in k:
                s[k] = float(v)
            else:
                s[k] = int(v)
            
        return s

        
    # Control
    
    def download(self, uris, basedir = u".", fullsize = None, unquoteNames = True, interpretDirectories = True, startPaused = True, torrentdata = None):
        d = Download(self, uris, fullsize=fullsize, basedir=basedir, unquoteNames=unquoteNames, interpretDirectories=interpretDirectories, startPaused=startPaused, torrentdata = torrentdata)
        self._downloads.append(d)
        return d
   
    def pauseAll(self):
        self._server.aria2.pauseAll()
    
    def unpauseAll(self):
        self._server.aria2.unpauseAll()
        
    def cleanup(self):
        self._server.aria2.purgeDownloadResult()      


    def deleteTorrent(self, tor):
            
        log(INFO, u"Deleting torrent %s...\n" % (tor._hash))
        
        if tor._gids:

            # Use multicall to reduce pressure on aria2
            mc = xmlrpclib.MultiCall(self._aria()._server)

            for g in tor._gids:
                mc.aria2.remove(g)

            res = mc()

        self.cleanup()
        
