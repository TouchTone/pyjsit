#!/usr/bin/python

# Manager class to handle torrents and downloads

import time, re, glob, weakref, shutil
import threading, Queue

import jsit, aria, PieceDownloader
from log import *
from tools import *

import preferences
pref = preferences.pref


# Download Modes

DownloadE = enum("No", "Pieces", "Finished")

PriorityE = enum(("Very High", 20), ("High", 10), ("Normal", 0), ("Low", -10), ("Very Low", -20))

# Handler class for single torrents

class Torrent(object):

    def __init__(self, mgr, fname = None, url = None, jsittorrent = None, maximum_ratio = None, basedir = ".", 
                        unquoteNames = True, interpretDirectories = True, addTorrentNameDir = True, downloadMode = "Pieces", priority = 0):
     
        self._mgr = weakref.ref(mgr)
        self._torrent = None
        self._aria = None
        self._pdl = None
        self.hash = None
        
        if jsittorrent:
            self._torrent = jsittorrent            
        elif ( fname == None and url == None ) or ( fname != None and url != None ):
            log(ERROR, "Mgr:Torrent: need to have either filename or url!")
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
        self.priority = priority
        
        # State vars
        self.percentage = 0   
        self.finishedAt = 0   
        self._label_set = False     
        self._completion_moved = False     
        self._check_running = False     
        self.checkProgress = 0
        self.checkPieces = None
        self.checkedComplete = False     
        
        self._skipAutostartReject = False
        
        
    def __repr__(self):
        if self._torrent:
            return "MTorrent(%r (%r))"% (self.name, self.hash)
        else:
            return "MTorrent(<unnamed> (%r))"% (self.hash)
 
 
    def release(self):
        log(INFO, "Releasing torrent %s." % self.name)
        
        self._torrent.release()
        
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
    maximum_ratio   = property(lambda s: s._torrent.maximum_ratio, set_maximum_ratio)
     
    # From aria.Download
     
    # From pdl.Download
    

    # Other properties
    
    @property
    def hasFinished(self):
        return self.percentage == 100 and not self.isChecking
    
    @property
    def isDownloading(self):
        return self._aria != None or (self._pdl != None and self._pdl._paused == False) # TODO: Need to check aria for paused.
     
    @property
    def hasFailed(self):
        return self._pdl != None and self._pdl.hasFailed # TODO: Need to check aria for failed.
   
    @property
    def isChecking(self):
        return self._check_running
    
    @property
    def downloadSpeed(self):
        speed = 0
        if self._aria:
            speed = self._aria.downloadSpeed
        
        elif self._pdl:
            speed = self._pdl.downloadSpeed
            
        return speed
    
    @property
    def status(self):
        s = self._torrent.status
        
        if self.isChecking:
            s += " / check"
            
        elif self.checkedComplete:
            s += " / complete"
            
        elif self._aria:
            s += " / aria "
            if self._aria.percentage == 100:
                s += "done"
            else:
                s += "dl"
                
        elif self._pdl:
            s += " / pieces " + self._pdl.status 
        
        return s
   
    @property
    def downloadPercentage(self):
        if self.checkedComplete:
            return 100
            
        if self._aria:
            return self._aria.percentage
                 
        elif self._pdl:
            return self._pdl.percentage
        
        return 0
     
    @property
    def downloaded(self):
        if self.checkedComplete:
            return self.size
            
        if self._aria:
            return self._aria.downloaded
                 
        elif self._pdl:
            return self._pdl.downloadedBytes
        
        return 0
     
    
    # Estimated time to download
    @property
    def etd(self):
        if self.downloadSpeed == 0 or self.hasFinished:
            return 0
            
        return (self.size - self.downloaded) / self.downloadSpeed
      
    
    # Worker Methods
    
    def start(self):
        log(DEBUG)
        
        self._torrent.start()
 
    
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
    
    
    @property
    def fullPriority(self):
        return self.priority * 100000
    
        
    def startDownload(self):
        log(INFO, "Starting download for %s." % self._torrent.name) 
        
        base = self.basedir
        if self.addTorrentNameDir and len(self._torrent.files) > 1:
            base = os.path.join(base, self._torrent.name.replace('/', '_'))

        log(DEBUG, "To directory %s" % base)
        
        # Do we have enough space? If not, abort.
        free = get_free_space(base)
        if free < self.size:
            log(ERROR, "Cannot start downloading %s, free space on %s is %s (< torrent size %s)!" % (self.name, base, isoize(free, "B"), isoize(self.size, "B")))
            return
        
        # Check which part of torrent exist already
        self._check_running = True
        self.percentage = 0
        self._mgr()._checkQ.put((self.fullPriority, self.hash, base))
        
 
    def startDownloadAftercheck(self, base, downloadedFiles, downloadedPieces, downloadedBytes):
        
        log(DEBUG, "Found %d/%d files, %d/%d pieces, %d/%d bytes in download dir." % (len(downloadedFiles), len(self._torrent.files), downloadedPieces.count('1'), len(downloadedPieces), downloadedBytes, self._torrent.size))

        self._check_running = False
        self.checkProgress = 0
        self.checkPieces = None
        self.checkedComplete =  (downloadedBytes == self._torrent.size)
        
        if self.checkedComplete:
            self.percentage = 100
            return
        
        dm = self.downloadMode
        if dm == "No":
            dm = "Pieces"
 
        if dm == "Finished":
            if not self._torrent.hasFinished:
                log(WARNING, "Can't start download, torrent not finished!")
                return
            if not self._aria:
                self._aria = aria.Download(self._mgr()._aria, [f.url for f in self._torrent.files],  fullsize = self._torrent.size,
                                            basedir = base, unquoteNames = self.unquoteNames, startPaused = False,
                                            interpretDirectories = self.interpretDirectories, torrentdata = self._torrent.torrent,
                                            downloadedFiles = downloadedFiles, downloadedBytes = downloadedBytes)
            else:
                self._aria.start()
                
        elif dm == "Pieces":
            if not self._torrent.hasFinished and self._torrent.status != 'running':
                log(INFO, "Torrent %s has not finished yet, starting it." % self._torrent.name)
                self._torrent.start()
                
            if not self._pdl:
                self._pdl = self._mgr()._pdl.download(self._torrent, basedir = base, startPaused = False, downloadedPieces = downloadedPieces, downloadedBytes = downloadedBytes)
            else:
                self._pdl.start()

        else:
            log(ERROR, "Unknown download mode %s!" % dm)
            
        
    def restartDownload(self):
        if not self._torrent.hasFinished:
            debug(WARNING, "can't restart download, torrent not finished!\n")
            return
 
        log(INFO, "Restarting download for %s." % self.name) 
       
        if self._aria:
            self._aria.delete()
            self._aria = None
        elif self._pdl:
            self._pdl.delete()
            self._pdl = None
        
        self.startDownload()
             
        
    def update(self):
        """To be called in regular intervals to check torrent status and initiate next steps if needed."""
    
        log(DEBUG2)
        
        # Not finished yet?
        if not self.hasFinished:
            try:
                self.percentage = self._torrent.percentage / 2
            except TypeError:
                self.percentage = 0
               
            if (self._torrent.hasFinished and self.downloadMode == "Finished" and not self._aria) or (self.downloadMode == "Pieces" and not self._pdl):
                if not self._check_running:
                    self.startDownload()
    
            if self._aria:    
                self.percentage += self._aria.percentage / 2
            if self._pdl:    
                self.percentage += self._pdl.percentage / 2
        
        if self.percentage == 100 and not self.finishedAt:
        
            # Recheck/redownload after download?
            if pref("downloads", "recheckAfterDownload", False) and not self.checkedComplete:
                self.downloadMode = "Pieces"
                self.startDownload()
                return
            
            
            self.finishedAt = time.time()
            
            if not self._label_set and pref("downloads", "setCompletedLabel", None):
                self._torrent.label = pref("downloads", "setCompletedLabel")
                self._label_set = True

            if not self._completion_moved and pref("downloads", "completedDirectory", None):
                base = self.basedir
                if self.addTorrentNameDir and len(self._torrent.files) > 1:
                    tname =  self._torrent.name.replace('/', '_')
                else:
                    tname = self._torrent.files[0].path
                
                base = os.path.normpath(os.path.join(self.basedir, tname))

                comp = pref("downloads", "completedDirectory")
                
                if os.path.exists(os.path.join(comp, tname)):
                    log(WARNING, "Completed torrent %s already exists in %s, ignoring move!" % (tname, comp))    
                    self._completion_moved = True            
                else:
                    log(INFO, "Moving completed torrent from %s to %s." % (base, comp))
                    mkdir_p(comp)
                    shutil.move(base, comp)
                    self._completion_moved = True
                
    
    def start(self):
        log(DEBUG)
        
        self._torrent.start()
      
     
    def stop(self):
        log(DEBUG)

        self._torrent.stop()
        
        self.stopDownload()

   
    def stopDownload(self):
        log(DEBUG)
        
        if self._aria:
            self._aria.stop()
           
        if self._pdl:
            self._pdl.stop()
         


# Manager class for all torrents

class Manager(object):

    def __init__(self, username, password, torrentdir = "intorrents"):
        
        self._jsit = jsit.JSIT(username, password, nthreads = pref("jsit", "nthreads", False))
        self._aria = aria.Aria(cleanupLeftovers = True)
        self._pdl = PieceDownloader.PieceDownloader(self._jsit, nthreads = pref("downloads", "nPieceThreads", 4))
      
        self._quitPending = False
        
        self._torrents = []
 
        time.sleep(0.3)     # Little break to avoid interrupted system calls
        
        self.syncTorrents()
        
        # Behavior Vars
        
        self._watchClipboard = pref("jsit_manager", "watchClipboard", False)
        self._handledClips = set()
        
        self._watchDirectory = pref("jsit_manager", "watchDirectory", False)
        if torrentdir:
            self._torrentDirectory = torrentdir
        else:
            self._torrentDirectory = "intorrents"
        self._torrentRename = True

        # Start check threads
        self._checkQ      = Queue.PriorityQueue(maxsize = 200)
        self._checkDoneQ  = Queue.PriorityQueue(maxsize = 200)
        
        self._checkThreads = []
        
        for i in xrange(1, pref("jsit_manager", "nCheckThreads", 1) + 1):
            t = threading.Thread(target=self.checkThread, name="Checker-%d" % i)
            t.start()
            self._checkThreads.append(t)
        
    
    # Cleanup methods...
    
    def __del__(self):
        if self._jsit:
            self.release()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, value, traceback):
        self.release()
    
      
    def release(self):
        try:
            self._quitPending = True
            
            for t in self._checkThreads:
                self._checkQ.put((0, None, None))
                
            for t in self._checkThreads:
                t.join()
            
            self._jsit.release()            
            self._aria.release()            
            self._pdl.release()  
            self._jsit = None
            self._aria = None
            self._pdl = None
            
        except AttributeError:
            pass # Can happen if inits fail          
              
        
        
    def __repr__(self):
        return "Manager(0x%x)"% id(self)
 
    # Iterator access to torrent list
    def __iter__(self):
         return self._torrents.__iter__()

    def __getitem__(self, index):
        return self._torrents[index]

    def __len__(self):
        return len(self._torrents)

    
    def setcheckProgress(self, tor, npieces, piecesChecked, downloadedFiles, downloadedPieces, downloadedBytes):
        log(DEBUG3)
        tor.checkProgress = piecesChecked / float(npieces)
        tor.checkPieces = downloadedPieces
        
        return self._quitPending
    
    
    def checkThread(self):
        log(DEBUG)
        while not self._quitPending:
            prio, hash, base = self._checkQ .get()
            log(DEBUG, "Got hash %s for base %s" % (hash, base))
            
            if hash == None:
                log(DEBUG, "Got suicide signal, returning.")
                return
            
            tor = self.lookupTorrent(hash)
            
            if tor:
                downloadedFiles, downloadedPieces, downloadedBytes = checkTorrentFiles(base, tor._torrent.torrent, lambda a,b,c,d,e, t=tor, s=self: s.setcheckProgress(t, a, b, c, d, e) )

                # Not in download dir. Completed already?
                if downloadedBytes == 0 and pref("downloads", "completedDirectory", None):

                    comp = pref("downloads", "completedDirectory")
                    if tor.addTorrentNameDir and len(tor._torrent.files) > 1:
                        comp = os.path.join(comp, tor._torrent.name.replace('/', '_'))

                    downloadedFiles, downloadedPieces, downloadedBytes = checkTorrentFiles(comp, tor._torrent.torrent, lambda a,b,c,d,e, t=tor, s=self: s.setcheckProgress(t, a, b, c, d, e) ) 
                    log(DEBUG, "Found %d/%d files, %d/%d pieces, %d/%d bytes in completed dir." % (len(downloadedFiles), len(tor._torrent.files), downloadedPieces.count('1'), len(downloadedPieces), downloadedBytes, tor._torrent.size))

                    # Found something, move into continuing it
                    if downloadedBytes > 0:
                        base = comp

                self._checkDoneQ.put((prio, hash, base, downloadedFiles, downloadedPieces, downloadedBytes))
            else:
                log(INFO, "Torrent %s doesn't exist any more for check, ignored." % hash)
            
            self._checkQ.task_done()


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
            self.addTorrentFile(t, basedir = pref("downloads","basedir", "downloads"), maximum_ratio = pref("jsit","maximumRatioPublic", 1.5), downloadMode = pref("downloads","directoryDownloadMode", "No"))
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

                log(WARNING, "Found link for %s, uploading..." % clip[s:e])

                self.addTorrentURL(clip, basedir = pref("downloads","basedir", "doenloads"), maximum_ratio = pref("jsit","maximumRatioPublic", 1.5), downloadMode = pref("downloads","clipboardDownloadMode", "No"))
         
  
    def checkAutoDownloads(self):
        log(DEBUG)
        
        labels   = pref("autoDownload", "getLabels", [])
        trackers = pref("autoDownload", "getTrackers", [])
        names    = pref("autoDownload", "getNames", [])
        perc     = pref("autoDownload", "minPercentage", 0)
        skips    = pref("autoDownload", "skipLabels", [])
       
        for t in self:
            if t.isDownloading or t.isChecking or t.hasFinished:
                continue
            
            get = False
            reason = ""
            
            # Known label?
            if not get and len(labels):
                if t._torrent.label in labels:
                    reason = "label"
                    get = True
            
            # Known tracker?
            if not get and len(trackers):
                for tt in t._torrent.trackers:
                    for dt in trackers:
                        if re.search(dt, tt.url):
                            reason = "tracker"
                            get=True
            
            # Known name?
            if not get and len(names):
                n = t.name
                for r in names:
                    if re.search(r, n):
                        reason = "name"
                        get=True
            
            
            if get:
                if t._torrent.percentage < perc:
                    get = False
                    reason = "percentage"
                
                if get and len(skips) and t._torrent.label in skips:
                    get = False
                    reason = "label"
                
                if get:
                    log(INFO, "Auto-starting download for torrent %s because of %s." % (t.name, reason))
                    t.startDownload()
                elif not t._skipAutostartReject:
                    log(INFO, "Download for torrent %s not auto-started because of %s." % (t.name, reason))           
                    t._skipAutostartReject = True
                    
                    

    def syncTorrents(self, force = False, downloadMode = "No"):       
        '''Synchronize local list with data from JSIT server: add new, remove deleted ones'''
        
        log(DEBUG)
        
        self._jsit.updateTorrents(force = force)
        
        new, deleted = self._jsit.resetNewDeleted()
        
        for d in deleted:
            t = self.lookupTorrent(d)
            if t:
                # Don't do delete, as it's already gone from JSIT
                self._torrents.remove(t)
                t.release()
        
        for n in new:
            # Do we have this one already?
            t = self.lookupTorrent(n)
            if not t:
                t = self._jsit.lookupTorrent(n)
                self._torrents.append(Torrent(self, jsittorrent = t, downloadMode = downloadMode, basedir = pref("downloads", "basedir", "downloads")))
        
        return new, deleted


    def update(self, force = False, clip = None):
        log(DEBUG)
        
        if self._watchDirectory:
            self.checkTorrentDirectory()
          
        if self._watchClipboard and clip:
            self.checkClipboard(clip)
      
        new, deleted = self.syncTorrents(force = force)
        
        self.checkAutoDownloads()
        
        self._pdl.update()

        for t in sorted(self._torrents, key=lambda t: t.fullPriority):
            t.update()
        
        # Any checks finished?
        try:
            while True:
                prio, hash, base, downloadedFiles, downloadedPieces, downloadedBytes = self._checkDoneQ.get(False)
                
                tor = self.lookupTorrent(hash)
                
                if tor:
                    tor.startDownloadAftercheck(base, downloadedFiles, downloadedPieces, downloadedBytes)
                else:
                    log(DEBUG, "Torrent %s not found after check, ignored." % hash)
                    
        except Queue.Empty:
            pass
            
        return new, deleted

   
    @property
    def allFinished(self):     
        af = True
        for t in self:
            t.update()
            if not t.hasFinished:
                af = False
        
        return af
        

    def postAddTorrent(self, t):

        if find(lambda tt: tt.hash == t.hash, self._torrents):
            log(INFO, "Torrent already running, ignored.")
        else:
            self._torrents.append(t)
    
        # Set ratio for given tracker (if just one)
        tr = t._torrent.trackers
        
        if len(tr) == 1:
            
            url = tr[0].url
            for n,r in pref("jsit", "trackerRatios").iteritems():
                if n in url:
                    log(INFO, "Setting max ratio for %s to %f based on trackerRatios prefs." % (t.name, r))
                    t.maximum_ratio = r
    
    
            
    def addTorrentFile(self, fname, maximum_ratio = None, basedir='.', unquoteNames = True, 
                        interpretDirectories = True,  downloadMode = "No"):
    
        log(INFO, "addTorrentFile(%s)" % fname)
        
        try:
            t = Torrent(self, fname = fname, maximum_ratio = maximum_ratio, basedir = basedir, unquoteNames = unquoteNames, interpretDirectories = interpretDirectories, downloadMode = downloadMode) 

            self.postAddTorrent(t)
            
        except ValueError, e:
            log(ERROR, "%r::addTorrentFile: Caught '%s', aborting." % (self, e))
            t = None
            
        return t
        
        
    def addTorrentURL(self, url, maximum_ratio = None, basedir='.', unquoteNames = True, 
                        interpretDirectories = True, downloadMode = "No"):
    
        log(INFO, "addTorrentURL(%s)" % (url))
         
        try:
            t = Torrent(self, url = url, maximum_ratio = maximum_ratio, basedir = basedir, unquoteNames = unquoteNames, interpretDirectories = interpretDirectories, downloadMode = downloadMode) 

            self.postAddTorrent(t)
                 
        except ValueError, e:
            log(ERROR, "%r::addTorrentURL: Caught '%s', aborting." % (self, e))
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
            
        log(INFO, u"Deleting torrent %s..." % (tor.hash))
        
        self._jsit.deleteTorrent(tor._torrent)
        tor.release()
        self._torrents.remove(tor)
  
  
    def startAll(self): 
        for t in self._torrents:
            t.start()
  
  
    def stopAll(self): 
        for t in self._torrents:
            t.stop()
            
