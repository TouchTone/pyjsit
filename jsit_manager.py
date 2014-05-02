#!/usr/bin/python

# Manager class to handle torrents and downloads

import time, re, glob, weakref

import jsit, aria, PieceDownloader
from log import *
from tools import *

import preferences
pref = preferences.pref


# Download Modes

DownloadE = enum("No", "Pieces", "Finished")

# Handler class for single torrents

class Torrent(object):

    def __init__(self, mgr, fname = None, url = None, jsittorrent = None, maximum_ratio = None, basedir = ".", 
                        unquoteNames = True, interpretDirectories = True, addTorrentNameDir = True, downloadMode = "Pieces"):
     
        self._mgr = weakref.ref(mgr)
        self._torrent = None
        self._aria = None
        self._pdl = None
        self.hash = None
        
        if jsittorrent:
            self._torrent = jsittorrent            
        elif ( fname == None and url == None ) or ( fname != None and url != None ):
            log(ERROR, "Mgr:Torrent: need to have either filename or url!\n")
            raise Exception("Mgr:Torrent: need to have either filename or url!")
        else:
            if fname:
                self._torrent = self._mgr()._jsit.addTorrentFile(fname, maximum_ratio = maximum_ratio)
            elif url:
                self._torrent = self._mgr()._jsit.addTorrentURL(url, maximum_ratio = maximum_ratio)
            else:
                raise Exception("Torrent: need something to base myself on!")
            
            if not self._torrent:
                raise ValueError("Torrent: failed to create JSIT torrent!")
        
        
        self.hash = self._torrent._hash        
        
        # Save download-related options for later
        self.downloadMode = downloadMode
        self.addTorrentNameDir = addTorrentNameDir
        self.basedir = basedir
        self.unquoteNames = unquoteNames
        self.interpretDirectories = interpretDirectories
        
        # State vars
        self.percentage = 0      
        self._label_set = False     
 
    def __repr__(self):
        if self._torrent:
            return "MTorrent(%r (%r))"% (self.name, self.hash)
        else:
            return "MTorrent(<unnamed> (%r))"% (self.hash)
 
    def release(self):
        self._torrent.delete()
        
        if self._aria:
            self._aria.delete()
        
        if self._pdl:
            self._pdl.delete()
   
    # Forwarded attributes from _torrent or _aria      
    
    # From jsit.Torrent
    def set_label(self, l):
        self._torrent.label = l

    def set_maximum_ratio(self, r):
        self._torrent.maximum_ratio = r
        
        
    name            = property(lambda s: s._torrent.name)
    size            = property(lambda s: s._torrent.size)
    label           = property(lambda s: s._torrent.label, set_label)
     
    private         = property(lambda s: s._torrent.private)
    maximum_ratio   = property(lambda x: s._torrent.maximum_ratio, set_maximum_ratio)
     
    # From aria.Download
     
    # From pdl.Download
    

    # Other properties
    
    @property
    def hasFinished(self):
        return self.percentage == 100
    
    @property
    def status(self):
        if not self._aria:
            return self._torrent.status
        
    
    # Worker Methods
    
    def start(self):
        log(DEBUG)
        
        self._torrent.start()
        
        if self._aria:
            self._aria.start()
        if self._pdl:
            self._pdl.start()
  
    
    def stop(self):
        log(DEBUG)
 
        self._torrent.stop()
        
        if self._aria:
            self._aria.stop()
        if self._pdl:
            self._pdl.stop()
 
    
    def delete(self):
        log(DEBUG)
        
        self._mgr().deleteTorrent(self)
    
        
    def startDownload(self):
        log(INFO) 
        
        base = self.basedir
        if self.addTorrentNameDir and len(self._torrent.files) > 1:
            base = os.path.join(self.basedir, self._torrent.name.replace('/', '_'))
        
        dm = self.downloadMode
        if dm == "No":
            dm = "Pieces"
        
        if dm == "Finished":
            if not self._torrent.hasFinished:
                log(WARNING, "can't start download, torrent not finished!\n")
                return
            if not self._aria:
                self._aria = aria.Download(self._mgr()._aria, [f.url for f in self._torrent.files],  fullsize = self._torrent.size,
                                            basedir = base, unquoteNames = self.unquoteNames, startPaused = False,
                                            interpretDirectories = self.interpretDirectories, torrentdata = self._torrent.torrent) 
            else:
                self._aria.start()
        elif dm == "Pieces":
            if not self._pdl:
                self._pdl = self._mgr()._pdl.download(self._torrent, basedir = base, startPaused = False) 
            else:
                self._pdl.start()
        else:
            log(ERROR, "Unknown download mode %s!" % dm)
            
        
    def restartDownload(self):
        if not self._torrent.hasFinished:
            debug(WARNING, "can't restart download, torrent not finished!\n")
            return
 
        log(INFO, "Restarting download for %s.\n" % self.name) 
       
        if self._aria:
            self._aria.delete()
            self._aria = None
        elif self._pdl:
            self._pdl.delete()
            self._pdl = None
        
        self.startDownload()
       
        
    def recheckDownload(self):
        base = self.basedir
        if self.addTorrentNameDir:
            base = os.path.join(self.basedir, self._torrent.name.replace('/', '_'))
        
        dm = self.downloadMode
        if dm == "No":
            dm = "Pieces"
        
        if dm == "Finished":
            if not self._aria:
                self._aria = aria.Download(self._mgr()._aria, [f.url for f in self._torrent.files],  fullsize = self._torrent.size,
                                            basedir = base, unquoteNames = self.unquoteNames, startPaused = True,
                                            interpretDirectories = self.interpretDirectories, torrentdata = self._torrent.torrent) 
            else:
                self._aria.recheckDownload(torrentdata = self._torrent.torrent) 
                
        elif dm == "Pieces":
            if not self._pdl:
                self._pdl = PieceDownloader.Download(self._mgr()._pdl, basedir = base, startPaused = True) 
            else:
                self._pdl.recheckDownload(torrentdata = self._torrent.torrent)
                
        else:
            log(ERROR, "Unknown download mode %s!" % dm)
        
        
    def update(self):
        """To be called in regular intervals to check torrent status and initiate next steps if needed."""
    
        log(DEBUG2)
        
        # Not finished yet?
        self.percentage = self._torrent.percentage / 2
           
        if (self._torrent.hasFinished and self.downloadMode == "Finished" and not self._aria) or (self.downloadMode == "Pieces" and not self._pdl):
            self.startDownload()

        if self._aria:    
            self.percentage += self._aria.percentage / 2
        if self._pdl:    
            self.percentage += self._pdl.percentage / 2
        
        if self.percentage == 100:
            ##self._aria.cleanup() # This gets us into trouble for calculating the percentage later
            
            if not self._label_set and pref("downloads", "setCompletedLabel"):
                self._torrent.label = pref("downloads", "setCompletedLabel")
                self._label_set = True
                
    
    def start(self):
        log(DEBUG)
        
        self._torrent.start()
        
        if self._aria:
            self._aria.start()
        
        if self._pdl:
            self._pdl.start()
       
    
    def stop(self):
        log(DEBUG)

        self._torrent.stop()
        
        if self._aria:
            self._aria.stop()
           
        if self._pdl:
            self._pdl.stop()
         


# Manager class for all torrents

class Manager(object):

    def __init__(self, username, password, torrentdir = "intorrents"):
        
        self._jsit = jsit.JSIT(username, password, async_updates = pref("jsit", "asyncUpdates"))
        self._aria = aria.Aria(cleanupLeftovers = True)
        self._pdl = PieceDownloader.PieceDownloader(self._jsit, nthreads = pref("downloads", "nPieceThreads"))
      
        self._torrents = []
 
        time.sleep(0.3) # Little break to avoid interrupted system calls
        
        self.syncTorrents()
        
        # Behavior Vars
        
        self._watchClipboard = False
        self._handledClips = set()
        
        self._watchDirectory = False
        if torrentdir:
            self._torrentDirectory = torrentdir
        else:
            self._torrentDirectory = "intorrents"
        self._torrentRename = True

    
    # Cleanup methods...
    
    def __del__(self):
        self.release()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, value, traceback):
        self.release()
    
      
    def release(self):   
        self._jsit.release()            
        self._aria.release()            
        self._pdl.release()            
              
        
        
    def __repr__(self):
        return "Manager(0x%x)"% id(self)
 
    # Iterator access to torrent list
    def __iter__(self):
         return self._torrents.__iter__()

    def __getitem__(self, index):
        return self._torrents[index]

    def __len__(self):
        return len(self._torrents)


    def watchClipboard(self, value = True):
        self._watchClipboard = bool(value)

    def watchDirectory(self, value = True):
        self._watchDirectory = bool(value)


    def setTorrentDirectory(self, value):
        self._torrentDirectory = value


    def checkTorrentDirectory(self):
        log(DEBUG)
        torrents = glob.glob(os.path.join(self._torrentDirectory, "*.torrent"))
        
        for t in torrents:
            self.addTorrentFile(t, basedir = pref("downloads","basedir"), maximum_ratio = pref("jsit","maximumRatioPublic"), downloadMode = pref("downloads","directoryDownloadMode"))
            if self._torrentRename:
                os.rename(t, t + ".uploaded")
        
 
    def checkClipboard(self, clips):
        log(DEBUG)
        
        for clip in clips: 
            if not clip or clip in self._handledClips:
                return

            self._handledClips.add(clip)

            if clip.startswith("magnet:") or ( clip.startswith("http://") and clip.endswith(".torrent") ): 

                if clip.startswith("magnet:"):
                    s = clip.find("dn=") + 3
                    e = clip.find("&", s)
                else:
                    s = clip.rfind("/") + 1
                    e = None

                log(WARNING, "Found link for %s, uploading...\n" % clip[s:e])

                self.addTorrentURL(clip, basedir = pref("downloads","basedir"), maximum_ratio = pref("jsit","maximumRatioPublic"), downloadMode = pref("downloads","clipboardDownloadMode"))
         
 
    def syncTorrents(self, force = False, downloadMode = "No"):       
        '''Synchronize local list with data from JSIT server: add new, remove deleted ones'''
        
        log(DEBUG)
        
        self._jsit.updateTorrents(force = force)
        
        new, deleted = self._jsit.resetNewDeleted()
        
        for d in deleted:
            t = self.lookupTorrent(d)
            if t:
                t.delete()
        
        for n in new:
            # Do we have this one already?
            t = self.lookupTorrent(n)
            if not t:
                t = self._jsit.lookupTorrent(n)
                self._torrents.append(Torrent(self, jsittorrent = t, downloadMode = downloadMode, basedir = "downloads"))
        
        return new, deleted


    def update(self, force = False, clip = None):
        log(DEBUG)
        
        if self._watchDirectory:
            self.checkTorrentDirectory()
          
        if self._watchClipboard and clip:
            self.checkClipboard(clip)
      
        new, deleted = self.syncTorrents(force = force)
        
        self._pdl.update()

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
        
       
    def addTorrentFile(self, fname, maximum_ratio = None, basedir=None, unquoteNames = True, 
                        interpretDirectories = True,  downloadMode = "No"):
    
        log(DEBUG, "%r:addTorrentFile(%s)\n" % (self, fname))
        
        try:
            t = Torrent(self, fname = fname, maximum_ratio = maximum_ratio, basedir = basedir, unquoteNames = unquoteNames, interpretDirectories = interpretDirectories, downloadMode = downloadMode) 
            
            if find(lambda tt: tt.hash == t.hash, self._torrents):
                log(INFO, "Torrent already running, ignored.\n")
            else:
                self._torrents.append(t)

        except ValueError, e:
            log(ERROR, "%r::addTorrentFile: Caught '%s', aborting.\n" % (self, e))
            t = None
            
        return t
        
        
    def addTorrentURL(self, url, maximum_ratio = None, basedir=None, unquoteNames = True, 
                        interpretDirectories = True, downloadMode = "No"):
    
        log(INFO, "addTorrentURL(%s)\n" % (url))
         
        try:
            t = Torrent(self, url = url, maximum_ratio = maximum_ratio, basedir = basedir, unquoteNames = unquoteNames, interpretDirectories = interpretDirectories, downloadMode = downloadMode) 
            
            if find(lambda tt: tt.hash == t.hash, self._torrents):
                log(INFO, "Torrent already running, ignored.\n")
            else:
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


    def deleteTorrent(self, tor):
        if isinstance(tor, str):
            tor = self.lookupTorrent(tor)
            
        log(INFO, u"Deleting torrent %s...\n" % (tor.hash))
        
        tor.release()
        self._torrents.remove(tor)
  
  
    def startAll(self): 
        for t in self._torrents:
            t.start()
  
  
    def stopAll(self): 
        for t in self._torrents:
            t.stop()
            
