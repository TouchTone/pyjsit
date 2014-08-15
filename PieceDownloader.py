#!/usr/bin/python

# Helper module to download pieces of torrents and assemble them into the result files

import subprocess, requests, random, xmlrpclib, time, urllib, socket, math
import os, errno, weakref, hashlib, traceback
import threading, Queue
import requests
from collections import deque
from dpqueue import DPQueue

from bencode import *
from log import *
from tools import *


maxFailures = 5
failureResetTime = 120
maxQueueSize = 500

# Download set handler class

class Download(object):
    
    def __init__(self, pdl, jtorrent, basedir = u".", startPaused = False, downloadedPieces = None, downloadedBytes = 0,
                    basePriority = 0):
        
        self._pdl = weakref.ref(pdl)
        self._jtorrent = weakref.ref(jtorrent)
       
        self._basedir = basedir
        self._paused = startPaused
    
        log(DEBUG)
        
        self._files = jtorrent.files
        self._size = jtorrent.size
        self._piece_size = jtorrent.piece_size
        self._npieces = jtorrent.npieces
        
        if downloadedPieces == None:
            downloadedPieces = "0" * self._npieces
        
        self._nPendingPieces = 0
        self._downloadedPieces = self._finishedPieces = downloadedPieces
        self.downloadedBytes = downloadedBytes
        log(DEBUG2, "self.downloadedPieces=%s self.downloadedBytes=%d" % (self._downloadedPieces, self.downloadedBytes))
        
        # Public attributes
        self.downloadSpeed = 0
        self.etc = 0
        self.priority = basePriority
        
        # Helper attribus for speed calc
        self._speedQ = deque( maxlen = 5 )  # Keep 5 records for averaging
        self._lastUpdate = 0.
        self._lastDownloaded = 0
        self._nFailures = 0
        self._lastFailure = 0
        
        # Build piece->file map       
        self._piecefiles = []
        for p in xrange(self._npieces):
            self._piecefiles.append([])
        for f in self._files:
            log(DEBUG2, "File=%s start=%d:%d end=%d:%d"% (f, f.start_piece, f.start_piece_offset, f.end_piece, f.end_piece_offset))
            for p in xrange(f.start_piece, f.end_piece + 1):
                self._piecefiles[p].append(f)
    
        log(DEBUG2, "PF=%s"% self._piecefiles)
   
    
    def __repr__(self):
        return "PDL:Download(%r (0x%x))"% (self._basedir, id(self))
    

    def update(self): 
        log(DEBUG2)    
        if self._paused or self.hasFinished or self.hasFailed:
            self.downloadSpeed = 0.
            self.etc = 0
            return
        
        # Find newly finished pieces
        lp = self._finishedPieces
        nadd = 0
        log(DEBUG3, "LP=%s" % lp)
        
        for i,e in enumerate(zip(self._finishedPieces, self._jtorrent().bitfield)):
            if self._pdl().stalled() or self._nPendingPieces >= maxQueueSize * 0.1:
                break
                
            if e[0] == '0' and e[1] == '1':
                # Mark piece as handled
                lp = self._finishedPieces
                self._finishedPieces = lp[:i] + "1" + lp[i+1:]
                
                # Send piece off to downloader/writer
                self._pdl().pieceFinished(self, self._jtorrent().pieces[i])
                
                self._nPendingPieces += 1
 
 
        # Update download speed
        
        now = time.time()
        log(DEBUG3, "%s: _lastUpdate=%s now=%s speedQ=%s" % (self._jtorrent().name, self._lastUpdate, now, self._speedQ))
        if self._lastUpdate != 0. and self._lastUpdate != now:
            sp = (self.downloadedBytes - self._lastDownloaded) / (now - self._lastUpdate)
            self._speedQ.append( sp )   
            
            self.downloadSpeed = sum(self._speedQ) / float(len(self._speedQ))
            ##self.downloadSpeed = sp

            # Derived values
            try:
                self.etc = time.time() + (self._size - self.downloadedBytes) / self.downloadSpeed
            except Exception,e :
                self.etc = 0
            
        self._lastUpdate = now
        self._lastDownloaded = self.downloadedBytes
   
    # How important is this piece?
    def piecePriority(self, p):
        prio = self.priority + (1. / math.log10(self._size - self.downloadedBytes + 10)) * 1000
        log(DEBUG2, "%s (%s) self._size=%d self.downloadedBytes=%d prio=%f" % (self._jtorrent().name, p, self._size, self.downloadedBytes, prio))
        return prio

    # Piece finished, download it   
    def pieceFinished(self, p):
        
        if self.hasFailed:
            log(DEBUG, "has failed, ignoring")
            return
            
        log(DEBUG, "Piece %d finished (size=%d)." % (p.number, p.size))
        try:
            log(DEBUG3, "url=%s" % p.url)
            r = requests.get(p.url, params = {"api_key":self._jtorrent()._jsit()._api_key}, verify=False, timeout=20)    
            log(DEBUG3, "Got %r" % r.content)    
            r.raise_for_status()
        except Exception,e :
            log(ERROR, u"Caught exception %s downloading piece %d from %s!" % (e, p.number, p.url))
            log(ERROR, traceback.format_exc())
            
            if time.time() > self._lastFailure + failureResetTime:
                self._nFailures = 1 # reset when time since last failure long enough
            else:
                self._nFailures += 1 # this is not guaranteed to be accurate in MT, but we only need approximate counts
                
            if self._nFailures == maxFailures:
                log(ERROR, "Stopping torrent %s because of failures!" % self._jtorrent().name)
                self.stop()
                
            if "404 Client Error" in str(e):
                # Abort on 404s or get banned quickly...
                self.stop()
            else:
                # Put piece back into queue for retry
                self._pdl().pieceFinished(self, p)
                
            return
        
        self._pdl().writePiece(self, p, r.content)
                
 
    # Write piece to file(s)
    def writePiece(self, p, content):      
        for f in self._piecefiles[p.number]:
            fn = os.path.normpath(os.path.join(self._basedir, f.path))
            mkdir_p(fn.rsplit(os.path.sep,1)[0])
            if p.number == f.end_piece and p.number == f.start_piece:
                l = f.end_piece_offset - f.start_piece_offset
            elif p.number == f.end_piece:
                l = f.end_piece_offset
            else:
                l = self._piece_size

            try:
                f.write(fn, p, content, l)
            except Exception,e:
                log(ERROR, "Caught %s trying to write piece %d for file %s!" % (e, p.number, fn))
                return
    
        self.downloadedBytes += p.size
        dp = self._downloadedPieces
        self._downloadedPieces = dp[:p.number] + "1" + dp[p.number+1:]
        self._nPendingPieces -= 1
                       
       
    def stop(self):
        self._paused = True
        self._nPendingPieces = 0
        
     
    def start(self):
        self._paused = False
        self._nFailures = 0
        
    
    def delete(self):
        self._pdl().deleteTorrent(self)
        
   
    @property
    def hasFinished(self):
        return self.downloadedBytes == self._size
   
    @property
    def hasFailed(self):
        return self._nFailures >= maxFailures
   
    @property
    def percentage(self):
        return self.downloadedBytes / float(self._size) * 100.
   
    @property
    def status(self):
        s = ""
        if self._paused:
            s += "paused "
        else:
            s += "dl "
        if self.hasFinished:
            s += "done "
        if self.hasFailed:
            s += "failed "
       
        return s
        
# Main class providing piece downloader management

class PieceDownloader(object):
    
    def __init__(self, jsit, nthreads = 0):
        
        log(DEBUG)
        
        self._jsit = jsit
        
        # Currently running downloads
        self._downloads = []
        
        # Parallel? Create queues, start threads
        self._nthreads = nthreads
        if nthreads:
            self._pieceQ = DPQueue(maxsize = maxQueueSize, prio = lambda e: e[0] == None or -e[0].piecePriority(e[1]))
            self._writeQ = Queue.PriorityQueue(maxsize = maxQueueSize)
            self._quitting = False
            
            self._writeThread = threading.Thread(target=self.writePieceThread, name="PieceWriter")
            self._writeThread.start()
            
            self._pieceThreads = []
            
            for t in xrange(0, nthreads):
                    t = threading.Thread(target=self.pieceFinishedThread, name="PieceDown-%d" % t)
                    ##t.daemon = True
                    t.start()
                    self._pieceThreads.append(t)
            
    
    def __repr__(self):
        return "PieceDownloader(0x%x)"% id(self)
        
    
    # Cleanup methods...
    
    def __del__(self):
        self.release()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, value, traceback):
        self.release()
    
      
    def release(self):        
        if self._nthreads:
            log(DEBUG, "Send suicide signals...")
            self._quitting = True
            self._writeQ.put((0, None, -1, ""))
            for t in xrange(0, self._nthreads):
                self._pieceQ.put((None, -1))
                
            log(DEBUG, "Wait for threads to finish...")
            
            self._writeThread.join()
            log(DEBUG, "WriteThread done.")
            for t in xrange(0, self._nthreads):
                self._pieceThreads[t].join(5)
                if self._pieceThreads[t].isAlive():
                    log(DEBUG, "PieceThread %d not responding!" % t)                    
                else:
                    log(DEBUG, "PieceThread %d done." % t)
            log(DEBUG, "All threads done!")
            self._nthreads = 0
            
  
    # (Parallel) Piece handling
    
    def pieceFinished(self, tor, piece):
        log(DEBUG)
        
        if self._nthreads:
            log(DEBUG, "Put piece %s:%s (prio=%d)" % (tor, piece, tor.piecePriority(piece)))
            self._pieceQ.put((tor, piece))
            cont = None
        else:
            cont = tor.pieceFinished(piece)
             
        return cont
  
  
    def writePiece(self, tor, piece, cont):
        log(DEBUG)
        if self._nthreads:
            prio = tor.piecePriority(piece)
            log(DEBUG, "Put piece %s:%s (prio=%d)" % (tor, piece, prio))
            self._writeQ.put((-prio, tor, piece, cont))
        else:
            tor.writePiece(piece, cont)
    
    
    def pieceFinishedThread(self):
        log(DEBUG)

        try:
            while not self._quitting:
                piece = -2
                while piece == -2:
                    try:
                        tor,piece = self._pieceQ.get(True, 300)
                    except Queue.Empty:
                        log(DEBUG, "Heartbeat...")

                log(DEBUG, "Got piece %s:%s" % (tor, piece))

                if piece == -1:
                    log(DEBUG, "Got suicide signal, returning.")
                    return

                tor.pieceFinished(piece)   

                self._pieceQ.task_done()
        except Exception, e:
            log(WARNING, "Caught %s" % e)
            log(WARNING, traceback.format_exc())
            
        log(DEBUG, "Ending (%s)" % self._quitting)
     
    def writePieceThread(self):
        log(DEBUG)
        try:
            while not self._quitting:
                piece = -2
                while piece == -2:
                    try:
                        prio,tor,piece,cont = self._writeQ .get(True, 30)
                    except Queue.Empty:
                        log(DEBUG, "Heartbeat...")

                log(DEBUG, "Got piece %s:%s (%d bytes content, prio=%d)" % (tor,piece, len(cont), prio))

                if piece == -1:
                    log(DEBUG, "Got suicide signal, returning.")
                    return

                tor.writePiece(piece, cont)   

                self._writeQ.task_done()
        except Exception, e:
            log(WARNING, "Caught %s" % e)
            log(WARNING, traceback.format_exc())
            
        log(DEBUG, "Ending (%s)" % self._quitting)
    
    
    def stalled(self):
        if not self._nthreads:
            return False
        
        return self._pieceQ.full() or self._writeQ.full()
            
        
    # Iterator access to downloads list 
           
    def __iter__(self):
        return iter(self._downloads)

    # Status 

    @property
    def hasFinished(self):
        flag = True
        for t in self:
            flag &= t.hasFinished
        return flag
        
        
    # Control
    
    def download(self, torrent, basedir = u".", startPaused = True, downloadedPieces = "", downloadedBytes = 0, basePriority = 0):
        d = Download(self, torrent, basedir=basedir, startPaused=startPaused, downloadedPieces = downloadedPieces, 
                        downloadedBytes = downloadedBytes, basePriority = basePriority)
        self._downloads.append(d)
        return d
   
    def pauseAll(self):
        pass
    
    def unpauseAll(self):
        pass
        

    def deleteTorrent(self, tor):
        tor.stop()
        self._downloads.remove(tor)
    
    def update(self):
        if self._nthreads:
            log(DEBUG, "Got %d downloads (%d pieces pending, %d writes pending)." % (len(self._downloads), self._pieceQ.qsize(), self._writeQ.qsize()))
        else:
            log(DEBUG, "Got %d downloads." % len(self._downloads))
        
        self._pieceQ.reprioritize()
        
        for t in sorted(self._downloads, key=lambda t: -t.priority):
            t.update()
            
            
