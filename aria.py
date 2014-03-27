#!/usr/bin/python

# Helper module to control aria2c from Python

import subprocess, requests, random, xmlrpclib, time, urllib
import os, errno, weakref, hashlib

from bencode import *
from log import *

import unicodedata

# Helper functions

# From http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise


# Based on http://stackoverflow.com/questions/816285/where-is-pythons-best-ascii-for-this-unicode-database
def unicode_cleanup(s):
   
    # Fix up messy punctuation
    punctuation = { u'\u2018' : u'\u0027', u'\u2019' : u'\u0027',  u'\u201c' : u'\u0022',  u'\u201d' : u'\u0022',
                    u'\xe2\x80\x99' : u'\u0027', u'\xe2\x80\x98' : u'\u0027',  
                    u'\xe2\x80\x9c' : u'\u0022', u'\xe2\x80\x9d' : u'\u0022', 
                    u'\xe2\x80\x9e' : u'\u0022', u'\xe2\x80\x9f' : u'\u0022' }
    for a,b in punctuation.iteritems():
        s = s.replace(a, b)
    
    s = unicodedata.normalize('NFKD', s)
    
    return s
    
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
            finished = self.checkFinishedFiles(torrentdata)
        else:
            finished = []
            
        self._gids = []
        
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


    def checkFinishedFiles(self, torrentdata):
        
        # Get hashes and piece info from torrent
        # Code based on btshowmetainfo.py
        metainfo = bdecode(torrentdata)
        info = metainfo['info']
        
        piece_length = info['piece length']
        piece_hash = [info['pieces'][x:x+20] for x in xrange(0, len(info['pieces']), 20)]
        
        tfiles = []
        file_length = 0
        
        if info.has_key('length'):
            tfiles.append((info['name'], info['length']))
            file_length = info['length']
        else:
            for file in info['files']:
                path = ""
                for item in file['path']:
                    if (path != ''):
                       path = path + "/"
                    path = path + item
                tfiles.append((path, file['length']))
                file_length += file['length']
       
        piece_number, last_piece_length = divmod(file_length, piece_length)
        
        pi = 0
        pleft = piece_length
        hash = hashlib.sha1()
        
        finished = []
        unfinished = []
        curpiece = [] # Files completing in current piece
        
        for fn,fl in tfiles:

            fn = unicode_cleanup(fn.decode('utf-8'))            
            fn = os.path.abspath(os.path.join(self._basedir, fn))
            try:
                st = os.stat(fn)

                # Size ok?
                if st.st_size == fl:
                    f = open(fn, "rb")   
                else:
                    f = None
            except OSError, e:
                if 'No such file or directory' in e:
                    f = None
                    
            fleft = fl
            
            while fleft > 0:
                
                rs = min(fleft, pleft)
                if f:
                    buf = f.read(rs)
                else:
                    buf = '0' * rs
                
                hash.update(buf)                
                pleft -=rs
                fleft -=rs
                
                if fleft == 0 and f != None:
                    curpiece.append(fn)
                
                if pleft == 0:
                    
                    if hash.digest() == piece_hash[pi]:
                    
                        finished += curpiece                        
                        
                    else:
                        f = None    # Mark file as failed
                    
                    curpiece = []
                        
                    hash = hashlib.sha1()
                    pi += 1

                    if pi == piece_number:
                        pleft = last_piece_length
                    else:
                        pleft = piece_length
 
        return finished    
        
        
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
    
    def download(self, uris, basedir = u".", fullsize = None, unquoteNames = True, interpretDirectories = True, startPaused = True, torrentdata = None):
        d = Download(self, uris, fullsize=fullsize, basedir=basedir, unquoteNames=unquoteNames, interpretDirectories=interpretDirectories, startPaused=startPaused, torrentdata = torrentdata)
        return d
   
    def pauseAll(self):
        self._server.aria2.pauseAll()
    
    def unpauseAll(self):
        self._server.aria2.unpauseAll()
        
    def cleanup(self):
        self._server.aria2.purgeDownloadResult()      

