#!/usr/bin/python

# Manager class to handle torrents and downloads

import time, re

import jsit, aria
from log import *


# Helpers

def enum(*sequential, **named):
    if isinstance(sequential[0], tuple):
        enums = dict(zip([s[0] for s in sequential], range(len(sequential))), **named)
        reverse = dict((value, key) for key, value in enums.iteritems())
        enums['attribs'] = dict(zip([s[0] for s in sequential], [s[1:] for s in sequential]))
        enums['enum_attribs'] = [s[1:] for s in sequential]
    else:
        enums = dict(zip(sequential, range(len(sequential))), **named)
        reverse = dict((value, key) for key, value in enums.iteritems())
    enums['reverse_mapping'] = reverse
    enums['count'] = len(enums)
    return type('Enum', (), enums)


# Handler class for single torrents
   
TStates = enum("TSTARTED", "TSTOPPED", "TFINISHED", "DSTARTED", "DSTOPPED", "DFINISHED")

class Torrent(object):

    def __init__(self, mgr, fname = None, url = None, jsittorrent = None, maximum_ratio = None, basedir = None, unquoteNames = True, interpretDirectories = True, autoStartDownload = True):
     
        self._mgr = mgr
        self._aria = None
        
        if jsittorrent:
            self._torrent = jsittorrent
            
        elif ( fname == None and url == None ) or ( fname != None and url != None ):
            log(ERROR, "Mgr:Torrent: need to have either filename or url!\n")
            raise Exception("Mgr:Torrent: need to have either filename or url!")
        else:
            if fname:
                self._torrent = self._mgr._jsit.addTorrentFile(fname, maximum_ratio = maximum_ratio)
            elif url:
                self._torrent = self._mgr._jsit.addTorrentURL(url, maximum_ratio = maximum_ratio)
            else:
                raise Exception("Torrent: need something to base myself on!")
            
            if not self._torrent:
                raise ValueError("Torrent: failed to create JSIT torrent!")
        
        
        self.hash = self._torrent._hash        
        
        # Save download-related options for later
        self.autoStartDownload = autoStartDownload
        self.basedir = basedir
        self.unquoteNames = unquoteNames
        self.interpretDirectories = interpretDirectories
        
        # State vars
        self.percentage = 0      
 
    def __repr__(self):
        return "MTorrent(%r (%r))"% (self.name, self.hash)
    
    # Forwarded attributes from _torrent or _aria      
    
    # From jsit.Torrent
    def set_label(self, l):
        self._torrent.label = l
        
    name = property(lambda s: s._torrent.name)
    size = property(lambda s: s._torrent.size)
    label = property(lambda s: s._torrent.label, set_label)
     
    # From aria.Download
    

    # Other properties
    
    @property
    def hasFinished(self):
        return self.percentage == 100
    
    # Worker Methods
    
    def startDownload(self):
        if not self._aria:
            self._aria = aria.Download(self._mgr._aria, [f.url for f in self._torrent.files],  fullsize = self._torrent.size,
                                        basedir = self.basedir, unquoteNames = self.unquoteNames, startPaused = False,
                                        interpretDirectories = self.interpretDirectories, torrentdata = self._torrent.torrent) 
        
        
        
    def update(self):
        """To be called in regular intervals to check torrent status and initiate next steps if needed."""
    
        log(DEBUG)
        
        # Not finished yet?
        self.percentage = self._torrent.percentage / 2
           
        if self._torrent.hasFinished and not self._aria and self.autoStartDownload:
            self.startDownload()

        if self._aria:    
            self.percentage += self._aria.percentage / 2
    
    
    def start(self):
        log(DEBUG)
        
        self._torrent.start()
        
        if self._aria:
            self._aria.start()
       
    
    def stop(self):
        log(DEBUG)

        self._torrent.stop()
        
        if self._aria:
            self._aria.stop()
            


# Manager class for all torrents

class Manager(object):

    def __init__(self, username, password):
        
        self._jsit = jsit.JSIT(username, password)
        self._aria = aria.Aria(cleanupLeftovers = True)
        
        self._torrents = []
 
        self.syncTorrents()
        
        
    def __repr__(self):
        return "Manager(%r)"% id(self)
 
    # Iterator access to torrent list
    def __iter__(self):
         return self._torrents.__iter__()

    def __getitem__(self, index):
        return self._torrents[index]

    def __len__(self):
        return len(self._torrents)

 
    def syncTorrents(self, autoStartDownload = False):       
        '''Synchronize local list with data from JSIT server: add new, remove deleted ones'''
        
        log(DEBUG, "%s:syncTorrents\n" % self)
        
        self._jsit.updateTorrents(force = True)
        
        new, deleted = self._jsit.resetNewDeleted()
        
        for d in deleted:
            t = self.lookupTorrent(d)
            if t:
                self._torrents.remove(t)
        
        for n in new:
            # Do we have this one already?
            t = self.lookupTorrent(n)
            if not t:
                t = self._jsit.lookupTorrent(n)
                self._torrents.append(Torrent(self, jsittorrent = t, autoStartDownload = autoStartDownload))
        
        return new, deleted


    def update(self):
        log(DEBUG, "%s:update\n" % self)
        new, deleted = self.syncTorrents()
        
        for t in self:
            t.update()
        
        return new, deleted

   
    @property
    def allFinished(self):     
        af = True
        for t in self:
            t.update()
            if not t.hasFinished:
                af = False
        
        return af
        
       
    def addTorrentFile(self, fname, maximum_ratio = None, basedir=None, unquoteNames = True, interpretDirectories = True):
    
        log(DEBUG, "%r:addTorrentFile(%s)\n" % (self, fname))
        
        try:
            t = Torrent(self, fname = fname, maximum_ratio = maximum_ratio, basedir = basedir, unquoteNames = unquoteNames, interpretDirectories = interpretDirectories) 
            self._torrents.append(t)
        except ValueError, e:
            log(ERROR, "%r::addTorrentFile: Caught '%s', aborting.\n" % (self, e))
            t = None
            
        return t
        
        
    def addTorrentURL(self, url, maximum_ratio = None, basedir=None, unquoteNames = True, interpretDirectories = True):
    
        log(DEBUG, "%r:addTorrentURL(%s)\n" % (self, url))
         
        try:
            t = Torrent(self, url = url, maximum_ratio = maximum_ratio, basedir = basedir, unquoteNames = unquoteNames, interpretDirectories = interpretDirectories) 
            self._torrents.append(t)
        except ValueError, e:
            log(ERROR, "%r::addTorrentURL: Caught '%s', aborting.\n" % (self, e))
            t = None
            
        return t
 
     
    def findTorrents(self, search):
        sre = re.compile(search)

        ret = []
        for t in self._torrents:
            if sre.match(t.name):
                ret.append(t)

        return ret


    def lookupTorrent(self, hash):
        for t in self._torrents:
            if t.hash == hash:
                return t

        return None
