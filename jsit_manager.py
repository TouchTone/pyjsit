#!/usr/bin/python

# Manager class to handle torrents and downloads

import time, re, glob, weakref, shutil, traceback
import threading, Queue

import jsit, aria, PieceDownloader
from log import *
from tools import *
import unpack


# Define WindowsError on non-windows
try: 
    WindowsError 
except NameError: 
    WindowsError = None 


import preferences
pref = preferences.pref
prefDir = preferences.prefDir
makeDir = preferences.makeDir

# Download Modes

DownloadE = enum("No", "Pieces", "Finished")

PriorityE = enum(("Very High", 90), ("High", 70), ("Normal", 50), ("Low", 30), ("Very Low", 10))

# Handler class for single torrents

class Torrent(object):

    def __init__(self, mgr, fname = None, url = None, jsittorrent = None, maximum_ratio = None, basedir = ".", 
                 unquoteNames = True, interpretDirectories = True, addTorrentNameDir = True, downloadMode = "Pieces", 
                 completedDirectory = None, priority = 50):

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
        self.completedDirectory = completedDirectory
        self._priority = priority

        # State vars
        self.percentage = 0.
        self.finishedAt = 0   
        self._label_set = False     
        self._autodownloaded = False     
        self._completion_moved = False     
        self._check_running = False     
        self.checkProgress = 0.
        self.checkPercentage = 0.
        self.checkPieces = None
        self.checkedComplete = False     
        self.unpackProgress = 0.

        self._skipAutostartReject = None


    def __repr__(self):
        if self._torrent:
            return "MTorrent(%r (%r))"% (self.name, self.hash)
        else:
            return "MTorrent(<unnamed> (%r))"% (self.hash)


    def release(self):
        log(DEBUG, "Releasing torrent %s." % self.name)

        self._torrent.release()

        if self._aria != None:
            self._aria.delete()

        if self._pdl != None:
            self._pdl.delete()

    # Forwarded attributes from _torrent or _aria      

    # From jsit.Torrent
    def set_label(self, l):
        self._torrent.label = l

    def set_maximum_ratio(self, r):
        self._torrent.maximum_ratio = r

    def set_priority(self, p):
        self._priority = p
        if self._pdl:
            self._pdl.priority = p


    name            = property(lambda s: s._torrent.name)
    size            = property(lambda s: s._torrent.size)
    tpercentage     = property(lambda s: s._torrent.percentage)
    label           = property(lambda s: s._torrent.label, set_label)

    private         = property(lambda s: s._torrent.private)
    maximum_ratio   = property(lambda s: s._torrent.maximum_ratio, set_maximum_ratio)
    priority        = property(lambda s: s._priority, set_priority)

    # From aria.Download

    # From pdl.Download


    # Other properties

    @property
    def hasFinished(self):
        return ( self.percentage == 100 and not self.isChecking ) or "deleted" in self.status

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
        if self.percentage != 100:
            log(INFO, "Starting download for %s." % self._torrent.name) 
        else:
            log(INFO, "Starting check for %s." % self._torrent.name) 

        base = self.basedir
        if not os.path.isdir(base):
            log(ERROR, "Can't download %s, basedir %s doesn't exist!"% (self._torrent.name, base))
            self.downloadMode = "No"
            return

        if self.addTorrentNameDir: # and len(self._torrent.files) > 1: This fails for stupid torrents with a common-named single file (PICS.rar)
            # See if it only has one file with a similar name as the archive.
            fname = self._torrent.files[0].path.rsplit('.', 1)[0]
            if len(self._torrent.files) > 1 or not fname in self._torrent.name:
                base = os.path.join(base, self._torrent.name.replace('/', '_'))

        log(DEBUG, "To directory %s" % base)

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

        # Do we have enough space? If not, abort.
        free = get_free_space(base)
        if free < self.size - downloadedBytes:
            log(ERROR, "Cannot start downloading %s, free space on %s is %s (< torrent remaining size %s)!" % (self.name, base, isoize(free, "B"), isoize(self.size - downloadedBytes, "B")))
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
                self._pdl = self._mgr()._pdl.download(self._torrent, basedir = base, startPaused = False, downloadedPieces = downloadedPieces, 
                                                      downloadedBytes = downloadedBytes, basePriority = self.fullPriority)
            else:
                self._pdl.start(basedir = base, downloadedPieces = downloadedPieces, downloadedBytes = downloadedBytes, basePriority = self.fullPriority)

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
                if not self.isChecking:
                    self.startDownload()

            if self._aria:    
                self.percentage += self._aria.percentage / 2
            if self._pdl:    
                self.percentage += self._pdl.percentage / 2


        if self.percentage == 100 and not self.finishedAt and not self.isChecking:

            # Recheck/redownload after download?
            if pref("downloads", "recheckAfterDownload", False) and not self.checkedComplete:
                self.downloadMode = "Pieces"
                self.startDownload()
                return

            # Torrent finished downloading!
            self.finishedAt = time.time()
            self._pdl = None
            self._aria = None

            if not self._label_set and pref("downloads", "setCompletedLabel", None):
                self._torrent.label = pref("downloads", "setCompletedLabel")
                self._label_set = True

            if not self._completion_moved and (self.completedDirectory or prefDir("downloads", "completedDirectory", None)):
                base = self.basedir
                if self.addTorrentNameDir and len(self._torrent.files) > 1:
                    tname = self._torrent.name.replace('/', '_')
                else:
                    tname = self._torrent.files[0].path

                base = os.path.normpath(os.path.join(self.basedir, tname))

                if self.completedDirectory:
                    comp = makeDir(self.completedDirectory)
                else:
                    comp = prefDir("downloads", "completedDirectory")

                if base == os.path.join(comp, tname):
                    log(INFO, "Torrent %s downloaded straight to %s, ignoring move!" % (tname, comp))    
                    self._completion_moved = True  
                elif os.path.exists(os.path.join(comp, tname)):
                    log(WARNING, "Just completed torrent %s already exists in %s, ignoring move!" % (tname, comp))    
                    self._completion_moved = True            
                else:
                    archiveexts = ["rar", "RAR", "zip", "ZIP"]

                    if not pref("downloads", "unpackArchives", False) or not base.rsplit('.', 1)[-1] in archiveexts:
                        self._mgr()._completerQ.put(("Move", (self, base, comp)))
                    else:
                        self._mgr()._completerQ.put(("Unpack", (self, base, comp)))
            else:
                log(DEBUG2, "Skip completion move(s): _completion_moved=%s self.completedDirectory=%s prefDir=%s" % (self, self._completion_moved, self.completedDirectory, prefDir("downloads", "completedDirectory", None)))


    def start(self):
        log(DEBUG)

        self._torrent.start()


    def stop(self):
        log(DEBUG)

        self._torrent.stop()

        self.stopDownload()


    def stopDownload(self):
        log(INFO, "Stopping download for %s." % self._torrent.name)

        if self._aria:
            self._aria.stop()

        if self._pdl:
            self._pdl.stop()



# Manager class for all torrents

class Manager(object):

    def __init__(self, username, password, torrentdir = "intorrents"):

        self._jsit = jsit.JSIT(username, password, nthreads = pref("jsit", "nthreads", False))
        # Aria is giving problems, use PieceDownloader instead
        ##self._aria = aria.Aria(cleanupLeftovers = True)
        self._pdl = PieceDownloader.PieceDownloader(self._jsit, nthreads = pref("downloads", "nPieceThreads", 4))

        self._quitPending = False

        self._torrents = []

        self.downloadSpeed = 0
        self.leftToDownload = 0
        
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
        self._checkQ      = Queue.PriorityQueue()
        self._checkDoneQ  = Queue.PriorityQueue()

        self._checkThreads = []

        for i in xrange(1, pref("jsit_manager", "nCheckThreads", 1) + 1):
            t = threading.Thread(target=self.checkThread, name="Checker-%d" % i)
            t.start()
            self._checkThreads.append(t)

        # Completer thread and queue
        self._completerQ      = Queue.Queue()
        self._completerThread = threading.Thread(target=self.completerThread, name="Completer")
        self._completerThread.start()


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

            self._completerQ.put(("Quit", None))
            self._completerThread.join()

            self._jsit.release()            
            ##self._aria.release()            
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
        tor.checkPercentage = downloadedBytes / float(tor.size)

        return self._quitPending


    def checkThread(self):
        log(DEBUG)
        while not self._quitPending:
            hash = -2
            while hash == -2:
                try:
                    prio, hash, base = self._checkQ .get(True, 300)
                except Queue.Empty:
                    log(DEBUG3, "Heartbeat...")
            log(DEBUG, "Got hash %s for base %s" % (hash, base))

            if hash == None:
                log(DEBUG, "Got suicide signal, returning.")
                return

            tor = self.lookupTorrent(hash)

            if tor:
                try:
                    downloadedFiles, downloadedPieces, downloadedBytes = checkTorrentFiles(base, tor._torrent.torrent, lambda a,b,c,d,e,f, t=tor, s=self: s.setcheckProgress(t, a, b, c, d, e) )

                    # Not in download dir. Completed already?
                    if downloadedBytes == 0 and (tor.completedDirectory or pref("downloads", "completedDirectory", None)):

                        if tor.completedDirectory:
                            comp = makeDir(tor.completedDirectory)
                        else:
                            comp = pref("downloads", "completedDirectory")

                        if tor.addTorrentNameDir and len(tor._torrent.files) > 1:
                            comp = os.path.join(comp, tor._torrent.name.replace('/', '_'))

                        downloadedFiles, downloadedPieces, downloadedBytes = checkTorrentFiles(comp, tor._torrent.torrent, lambda a,b,c,d,e,f, t=tor, s=self: s.    setcheckProgress(t, a, b, c, d, e) ) 
                        log(DEBUG, "Found %d/%d files, %d/%d pieces, %d/%d bytes in completed dir." % (len(downloadedFiles), len(tor._torrent.files), downloadedPieces.count('1'), len(downloadedPieces), downloadedBytes, tor._torrent.size))

                        # Found something, move into continuing it
                        if downloadedBytes > 0:
                            base = comp

                    self._checkDoneQ.put((prio, hash, base, downloadedFiles, downloadedPieces, downloadedBytes))
                except Exception,e:
                    log(ERROR, "Caught %s trying to check and start torrent %s!" % (e, tor.name))
                    log(ERROR, traceback.format_exc())
                    tor._check_running = False
            else:
                log(INFO, "Torrent %s doesn't exist any more for check, ignored." % hash)

            self._checkQ.task_done()


    def completerThread(self):
        log(DEBUG)
        while not self._quitPending:
            com, args = self._completerQ .get()
            log(DEBUG, "Got %s (%s)." % (com, args))

            try:
                if com == "Quit":
                    break

                elif com == "Move":
                    tor, base, comp = args

                    log(INFO, "Moving completed torrent from %s to %s." % (base, comp))
                    try:
                        skip = False
                        try:
                            bstat = os.stat(base)
                            cstat = os.stat(comp)
                            skip = False
                            if bstat.st_dev != cstat.st_dev:
                                f = get_free_space(comp)
                                if f < tor.size:
                                    log(ERROR, "Free space for %s = %s (< torrent size %s), skipping completion move!" % (comp, isoize(f, "B"), isoize(tor.size, "B")))
                                    skip = True
                        except Exception,e:
                            pass

                        if not skip:
                            mkdir_p(comp)
                            try:
                                os.rename(base, os.path.join(comp, base.rsplit(os.sep,1)[-1]))
                            except OSError,e:
                                shutil.move(base, comp)

                    except WindowsError, e:
                        log(ERROR, "Completion move raised error %s! Old data may be left behind!" % e)

                    tor._completion_moved = True

                elif com == "Unpack":
                    tor, base, comp = args

                    try:
                        skip = False

                        if not unpack.has_single_toplevel(base):
                            fname = base.rsplit(os.path.sep, 1)[-1]
                            comp = os.path.join(comp, fname.rsplit('.', 1)[0])

                            if os.path.isdir(comp):
                                log(WARNING, "Unpack torrent: %s exists, %s not unpacked." % (comp, base))
                                skip = True

                        if not skip:
                            log(INFO, "Unpack torrent from %s to %s." % (base, comp))

                            unpack.unpack(base, targetdir = comp, progress = lambda part, name, tor = tor: setattr(tor, "unpackProgress", part))

                            log(INFO, "Removing %s" % base)
                            os.remove(base)

                    except Exception, e:
                        log(ERROR, "Unpack raised error %s! Old data may be left behind!" % e)

                    tor._completion_moved = True
            
            except Exception,e:
                log(ERROR, "completer thread caught unhandled exception %s for %s %s" % (e, com, args))
                
            self._completerQ.task_done()

        log(DEBUG, "Done")



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
            self.addTorrentFile(t, basedir = pref("downloads","basedir", "downloads"))
            if self._torrentRename:
                os.rename(t, t + ".uploaded")


    def checkClipboard(self, clips):
        log(DEBUG)

        for clip in clips: 

            if not clip or clip in self._handledClips:
                return

            self._handledClips.add(clip)

            clip = unicode_cleanup(clip).encode("ascii", 'replace')

            if clip.startswith("magnet:") or ( clip.startswith("http://") and clip.endswith(".torrent") ): 

                if clip.startswith("magnet:"):
                    s = clip.find("dn=") + 3
                    e = clip.find("&", s)
                else:
                    s = clip.rfind("/") + 1
                    e = None

                log(WARNING, "Found link for %s, uploading..." % clip[s:e])

                self.addTorrentURL(clip, basedir = prefDir("downloads", "basedir", "downloads"))


    # Auto-download/skip related methods

    def getNonSkipped(self):
        out = []

        perc     = pref("autoDownload", "minPercentage", 0)
        skips    = pref("autoDownload", "skipLabels", [])

        for t in self:
            if t.isDownloading or t.isChecking or t.hasFinished:
                continue

            if t._torrent.percentage < perc:
                continue

            if len(skips) and t._torrent.label in skips:
                continue

            out.append(t)

        return out


    def checkAutoDownloads(self):
        log(DEBUG)

        types       = pref("autoDownload", "types", {})
        trackers    = pref("autoDownload", "trackers", {})
        perc        = pref("autoDownload", "minPercentage", 0)
        skips       = pref("autoDownload", "skipLabels", [])
        autoPieces  = pref("autoDownload", "checkAutoDownloadPieces", True)
        skipdelete  = pref("autoDownload", "deleteSkippedAndStopped", False)
        lifetime    = pref("autoDownload", "giveUpIfNotCompletedAfter", None)
        nothingtime = pref("autoDownload", "giveUpIfNothingAfter", None)

        mlifetime    = mapDuration(lifetime)
        mnothingtime = mapDuration(nothingtime)

        deletes = []
   
        for t in self:
            # Ignore deleted torrents here.
            if "deleted" in t.status:
                    continue

            # Check auto-delete
            if skipdelete and "stopped" in t.status and len(skips) and t._torrent.label in skips:
                reason = "stopped with label %s" % t._torrent.label
                deletes.append((t, reason))
                continue

            if not lifetime is None and t._torrent.elapsed > mlifetime and not "deleted" in t.status:
                reason = "exceeded global lifetime %s" % lifetime
                deletes.append((t, reason))
                continue

            if not nothingtime is None and t._torrent.elapsed > mnothingtime and not "deleted" in t.status and \
                            t._torrent.percentage == 0:
                reason = "no data received after %s" % lifetime
                deletes.append((t, reason))
                continue

            # Is downloading or checking? Skip!
            if t.isDownloading or t.isChecking:
                continue

            reason = ""


            # Check trackers

            for trn,tr in trackers.iteritems():

                if tr.has_key("stopAfterSeeding"):
                    stopAfter = tr["stopAfterSeeding"]
                    sstopAfter = mapDuration(tr["stopAfterSeeding"])
                else:
                    stopAfter = "never"
                    sstopAfter = 1000000

                for ttr in t._torrent.trackerurls:
                    if trn in ttr:
                        if t._torrent.completion > sstopAfter:
                            reason = "exceeded seedtime %s for tracker %s" % (lifetime, trn)
                            deletes.append((t, reason))
                            break


            # Check types

            for tn in sorted(types.keys()):

                log(DEBUG3, "TN: %s"% tn)

                td = types[tn]

                # Check auto-stop
                if td.has_key("stopAfterSeeding") and mapDuration(td["stopAfterSeeding"]) > t._torrent.completion:
                    reason = "type %s stop after seeding %s" % (tn, td["stopAfterSeeding"])
                    deletes.append((t, reason))
                    continue


                # Already tried downloading? Skip trying it again
                if t._autodownloaded:
                    continue
                
                labelMatch = False
                nameMatch = False

                # Label match?
                if td.has_key("matchLabels") and len(td["matchLabels"]):
                    if t._torrent.label in td["matchLabels"]:
                        reason = "label %s" % tn
                        labelMatch = True
                else:
                    labelMatch = True

                # Name match?
                if td.has_key("matchNames") and len(td["matchNames"]):
                    n = t.name
                    for r in td["matchNames"]:
                        if re.search(r, n):
                            reason = "name %s" % tn
                            nameMatch = True
                else:
                    nameMatch = True


                get = labelMatch and nameMatch

                if get:
                    if (not td.has_key('checkAutoDownloadPieces') and autoPieces and not t._torrent.auto_download_pieces) or (td.has_key('checkAutoDownloadPieces') and 
                                                                                                                              td['checkAutoDownloadPieces'] and not t._torrent.auto_download_pieces):
                        get = False
                        reason = "autoPieces %s" % tn

                    if t._torrent.percentage < perc:
                        get = False
                        reason = "percentage"

                    if get and len(skips) and t._torrent.label in skips:
                        get = False
                        reason = "label"

                    if get:						
                        # Trigger updating files if not set yet, wait until they're done to actually start downloading
                        if t._torrent.checkFiles():
                            log(INFO, "Auto-starting download for torrent %s because of %s." % (t.name, reason))

                            if td.has_key("completedDirectory"):    
                                t.completedDirectory = td["completedDirectory"]   

                            if td.has_key("priority"):    
                                t.priority = td["priority"]  

                            t._autodownloaded = True
                            t.startDownload()

                        else:
                            t._skipAutostartReject = "files"

                        break

                    elif t._skipAutostartReject != reason:
                        log(DEBUG, "Download for torrent %s not auto-started because of %s." % (t.name, reason)) 
                        t._skipAutostartReject = reason
                        break

        if len(deletes):
            for t,r in deletes:
                self.deleteTorrent(t, reason = r)


    def syncTorrents(self, force = False, downloadMode = "No"):       
        '''Synchronize local list with data from JSIT server: add new, remove deleted ones'''

        log(DEBUG)

        if self._jsit is None:
            log(DEBUG, "self._jsit is None, skipping.")
            return None, None
            
        self._jsit.updateTorrents(force = force)

        new, deleted = self._jsit.resetNewDeleted()

        for d in deleted:
            t = self.lookupTorrent(d)
            if t:
                # Don't do delete, as it's already gone from JSIT
                # Keep deleted around for listing them as finished...
                #self._torrents.remove(t)
                #t.release()
                pass

        for n in new:
            # Do we have this one already?
            t = self.lookupTorrent(n)
            if not t:
                t = self._jsit.lookupTorrent(n)
                self._torrents.append(Torrent(self, jsittorrent = t, downloadMode = downloadMode, basedir = prefDir("downloads", "basedir", "downloads")))

        return new, deleted


    def update(self, force = False, clip = None):
        log(DEBUG)

        if not self._jsit.connected():
            if self._jsit.tryReconnect():
                log(DEBUG, "Not connected, skipping.")
                return

        if self._watchDirectory:
            self.checkTorrentDirectory()

        if self._watchClipboard and clip:
            self.checkClipboard(clip)

        new, deleted = self.syncTorrents(force = force)

        self.checkAutoDownloads()

        if self._pdl is not None:
            self._pdl.update()

        downspeed = 0
        downsize = 0
        
        for t in sorted(self._torrents, key=lambda t: -t.fullPriority):
            t.update()
            if t.isDownloading and not t.hasFailed and not t.hasFinished:
                downspeed += t.downloadSpeed
                downsize += t.size - t.downloaded
        
        self.downloadSpeed = downspeed
        self.leftToDownload = downsize

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

    @property    
    def labels(self):
        return self._jsit.labels


    def postAddTorrent(self, t):
        if find(lambda tt: tt.hash == t.hash, self._torrents):
            log(INFO, "Torrent already running, ignored.")
        else:
            self._torrents.append(t)



    def addTorrentFile(self, fname, maximum_ratio = None, basedir='.', unquoteNames = True, 
                       interpretDirectories = True,  downloadMode = "No"):   
        log(INFO, "Adding torrent from %s..." % fname)

        try:
            t = Torrent(self, fname = fname, maximum_ratio = maximum_ratio, basedir = basedir, unquoteNames = unquoteNames, interpretDirectories = interpretDirectories, downloadMode = downloadMode) 

            self.postAddTorrent(t)

        except ValueError, e:
            log(ERROR, "%r::addTorrentFile: Caught '%s', aborting." % (self, e))
            t = None

        return t


    def addTorrentURL(self, url, maximum_ratio = None, basedir='.', unquoteNames = True, 
                      interpretDirectories = True, downloadMode = "No"):   
        log(INFO, "Adding torrent from %s..." % url)

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


    def deleteTorrent(self, tor, reason = None):
        if isinstance(tor, str):
            tor = self.lookupTorrent(tor)

        if reason is None:
            log(INFO, u"Deleting torrent %s..." % (tor.name))
        else:
            log(INFO, u"Deleting torrent %s because of %s" % (tor.name, reason))

        if True:
            tor._torrent._status = "deleted"
            self._jsit.deleteTorrent(tor._torrent)
            ##tor._torrent = None
        else:
            self._jsit.deleteTorrent(tor._torrent)
            tor.release()
            self._torrents.remove(tor)


    def startAll(self): 
        for t in self._torrents:
            t.start()


    def stopAll(self): 
        for t in self._torrents:
            t.stop()


    def downloadAll(self): 
        for t in self._torrents:
            t.startDownload()


    def reloadList(self): 
        log(INFO, u"Forcing list reload!")
        self._jsit.updateTorrents(force = True)    
