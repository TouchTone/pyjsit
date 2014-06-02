#!/usr/bin/python

# Helper module to download pieces of torrents and assemble them into the result files

import subprocess, requests, random, xmlrpclib, time, urllib, socket
import os, errno, weakref, hashlib, traceback
import threading, Queue
import requests
from collections import deque

from bencode import *
from log import *
from tools import *

   
# Download set handler class

class Download(object):
    
    def __init__(self, pdl, jtorrent, basedir = u".", startPaused = False, downloadedPieces = None, downloadedBytes = 0):
        
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
            
        self._downloadedPieces = self._finishedPieces = downloadedPieces
        self.downloadedBytes = downloadedBytes
        log(DEBUG2, "self.downloadedPieces=%s self.downloadedBytes=%d" % (self._downloadedPieces, self.downloadedBytes))
        
        # Public attributes
        self.downloadSpeed = 0
        self.etc = 0
        
        # Helper attribus for speed calc
        self._speedQ = deque( maxlen = 5 )  # Keep 5 records for averaging
        self._lastUpdate = 0.
        self._lastDownloaded = 0
        self._nFailures = 0.
        
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
        if self._paused or self.hasFinished or self.hasFailed:
            self.downloadSpeed = 0.
            self.etc = 0
            return
        
        # Find newly finished pieces
        lp = self._finishedPieces
        log(DEBUG3, "LP=%s" % lp)
        
        for i,e in enumerate(zip(self._finishedPieces, self._jtorrent().bitfield)):
            if self._pdl().stalled():
                break
                
            if e[0] == '0' and e[1] == '1':
                # Mark piece as handled
                lp = self._finishedPieces
                self._finishedPieces = lp[:i] + "1" + lp[i+1:]
                
                # Send piece off to downloader/writer
                self._pdl().pieceFinished(self, self._jtorrent().pieces[i])

        # Update download speed
        
        now = time.time()
        if self._lastUpdate != 0.:
            self._speedQ.append( (self.downloadedBytes - self._lastDownloaded) / (now - self._lastUpdate) )
            
            self.downloadSpeed = sum(self._speedQ) / float(len(self._speedQ))

            # Derived values
            try:
                self.etc = time.time() + (self._size - self.downloadedBytes) / self.downloadSpeed
            except Exception,e :
                self.etc = 0
            
        self._lastUpdate = now
        self._lastDownloaded = self.downloadedBytes
   

    # Piece finished, download it   
    def pieceFinished(self, p):
        
        if self.hasFailed:
            log(DEBUG, "has failed, ignoring")
            return
            
        log(DEBUG, "Piece %d finished (size=%d)." % (p.number, p.size))
        try:
            log(DEBUG3, "url=%s" % p.url)
            r = self._jtorrent()._jsit()._session.get(p.url, params = {"api_key":self._jtorrent()._jsit()._api_key}, verify=False)    
            log(DEBUG3, "Got %r" % r.content)    
            r.raise_for_status()
        except Exception,e :
            log(ERROR, u"Caught exception %s downloading piece %d from %s!" % (e, p.number, p.url))
            if not "404 Client Error" in str(e):
                # Put piece back into queue for retry
                self._pdl().pieceFinished(self, p)
            else:
                self._nFailures += 1 # this is not guaranteed to be accurate in MT, but we only need approximate counts
            return
        
        self._pdl().writePiece(self, p, r.content)
                
                
 
    # Write piece to file(s)
    def writePiece(self, p, content):      
        for f in self._piecefiles[p.number]:
            fn = os.path.normpath(os.path.join(self._basedir, f.path))
            mkdir_p(fn.rsplit(os.path.sep,1)[0])
            if p.number == f.end_piece:
                l = f.end_piece_offset
            else:
                l = self._piece_size

            f.write(fn, p, content, l)
    
        self.downloadedBytes += p.size
        dp = self._downloadedPieces
        self._downloadedPieces = dp[:p.number] + "1" + dp[p.number+1:]
                       
       
    def stop(self):
        self._paused = True
        
     
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
        return self._nFailures != 0
   
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
            self._pieceQ = Queue.Queue(maxsize = 50)
            self._writeQ = Queue.Queue(maxsize = 50)
            self._quitting = False
            
            self._writeThread = threading.Thread(target=self.writePieceThread, name="PieceWriter")
            ##self._writeThread.daemon = True # Hack! Somehow the destructor is never called
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
            self._writeQ.put((None, -1, ""))
            for t in xrange(0, self._nthreads):
                self._pieceQ.put((None, -1))
                
            log(DEBUG, "Wait for threads to finish...")
            
            self._writeThread.join()
            log(DEBUG, "WriteThread done.")
            for t in xrange(0, self._nthreads):
                self._pieceThreads[t].join()
                log(DEBUG, "PieceThread %d done." % t)
            log(DEBUG, "All threads done!")
            self._nthreads = 0
            
  
    # (Parallel) Piece handling
    
    def pieceFinished(self, tor, piece):
        log(DEBUG)
        
        if self._nthreads:
            self._pieceQ.put((tor, piece))
            cont = None
        else:
            cont = tor.pieceFinished(piece)
             
        return cont
  
  
    def writePiece(self, tor, piece, cont):
        log(DEBUG)
        if self._nthreads:
            self._writeQ.put((tor, piece, cont))
        else:
            tor.writePiece(piece, cont)
    
    
    def pieceFinishedThread(self):
        log(DEBUG)

        try:
            while not self._quitting:
                piece = -2
                while piece == -2:
                    try:
                        tor,piece = self._pieceQ.get(True, 5)
                    except Queue.Empty:
                        log(DEBUG, "Heartbeat...")

                log(DEBUG, "Got piece %s:%s" % (tor,piece))

                if piece == -1:
                    log(DEBUG, "Got suicide signal, returning.")
                    return

                tor.pieceFinished(piece)   

                self._pieceQ.task_done()
        except Exception, e:
            log(WARNING, "Caught %s" % e)
            
        log(DEBUG, "Ending (%s)" % self._quitting)
     
    def writePieceThread(self):
        log(DEBUG)
        try:
            while not self._quitting:
                piece = -2
                while piece == -2:
                    try:
                        tor,piece,cont = self._writeQ .get(True, 5)
                    except Queue.Empty:
                        log(DEBUG, "Heartbeat...")

                log(DEBUG, "Got piece %s:%s (%d bytes content)" % (tor,piece, len(cont)))

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
    
    def download(self, torrent, basedir = u".", startPaused = True, downloadedPieces = "", downloadedBytes = 0):
        d = Download(self, torrent, basedir=basedir, startPaused=startPaused, downloadedPieces = downloadedPieces, downloadedBytes = downloadedBytes)
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
        for t in self:
            t.update()
            
            
