#!/usr/bin/python

# Helper module to control aria2c from Python

import subprocess, requests, random, xmlrpclib, time, urllib
import os, errno, weakref
import pprint

from log import *


# Helper functions

# From http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise


# Download set handler class

class Download(object):

    _status_keys = ["gid", "status", "totalLength", "completedLength", "downloadSpeed", "errorCode", "dir", "files" ]
    
    def __init__(self, aria, uris, basedir = u".", fullsize = None, unquoteNames = True, interpretDirectories = True, startPaused = True):
    
        self._aria = weakref.ref(aria)
        
        self._fullsize = fullsize
        
        if isinstance(uris, str):
            uris = [uris]

        self._gids = []
        
        for u in uris:
            
            name = u.rsplit('/', 1)[1]
            dir = basedir
            if dir == None:
                dir = u"."
            
            # Make absolute in case aria was started somwhere else...
            dir = os.path.abspath(dir)
            
            if unquoteNames:
                name = urllib.unquote(name)
          
            ##print "A:name=%s dir=%s" % (name, dir)
            
            if interpretDirectories:
                nf = name.rsplit(u'/', 1)
                ##print "B:nf=%s" % (nf)
                
                if len(nf) > 1:
                    dir += u"/" + nf[0]
                    name = nf[1]
           
            ##print "B:name=%s dir=%s" % (name, dir)
           
            log(DEBUG, u"Download: will download %s to %s as %s\n" % (u, dir, name))
            
            mkdir_p(dir)
            
            # Basic Options
            opts = {"continue" : "true"}

            if startPaused:
                opts["pause"] = "true"

            if dir != ".":
                opts["dir"] = dir
                
            opts["out"] = name
            
            g = self._aria()._server.aria2.addUri([u], opts)
           
            self._gids.append(g)
            
        
        self._aria()._downloads.append(self)
        
    def statusAll(self):
        s = []
        
        for g in self._gids:
            s.append(self._aria()._server.aria2.tellStatus(g, self._status_keys))
        
        return s
    
    def pause(self):
        for g in self._gids:
            self._aria()._server.aria2.pause(g)
     
    def unpause(self):
        for g in self._gids:
            self._aria()._server.aria2.unpause(g)
   
    @property
    def percentage(self):
        total = 0.
        completed = 0.
        
        for g in self._gids:
            s = self._aria()._server.aria2.tellStatus(g, ["completedLength", "totalLength"])
            total     += float(s["totalLength"])
            completed += float(s["completedLength"])
        
        # Do we know the full size a priory?
        if self._fullsize:
            total = self._fullsize
            
        # This can happen at startup, before any sizes are known
        if total == 0:
            return 0
        
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
        
        # Start aria process
        self._username = "user" + str(random.randint(0,100000)) * private
        self._password = "pass" + str(random.randint(0,100000)) * private
        
        
        self._proc = subprocess.Popen(["aria2c", "--enable-rpc=true", "--rpc-user="+self._username, "--rpc-passwd="+self._password, "--rpc-listen-port=%d" % port], 
                                      stdout=subprocess.PIPE)
        self._server = xmlrpclib.ServerProxy('http://%s:%s@localhost:%d/rpc' % (self._username, self._password, port))
        
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
        self._server.aria2.changeGlobalOption({'log':''})

        self._server.aria2.changeGlobalOption({'max-overall-download-limit':'0'})
        self._server.aria2.changeGlobalOption({'max-concurrent-downloads':'10'})
        ##self._server.aria2.changeGlobalOption({'max-overall-download-limit':'20K'})
        ##self._server.aria2.changeGlobalOption({'max-concurrent-downloads':'2'})
     
        
        # Currently running downloads
        self._downloads = []
        
        
    
    def __del__(self):
        
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
    
    def download(self, uris, basedir = u".", fullsize = None, unquoteNames = True, interpretDirectories = True, startPaused = True):
        d = Download(self, uris, fullsize=fullsize, basedir=basedir, unquoteNames=unquoteNames, interpretDirectories=interpretDirectories, startPaused=startPaused)
        return d
   
    def pauseAll(self):
        self._server.aria2.pauseAll()
    
    def unpauseAll(self):
        self._server.aria2.unpauseAll()
        
    def cleanup(self):
        self._server.aria2.purgeDownloadResult()      

