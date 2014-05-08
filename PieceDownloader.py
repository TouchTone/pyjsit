#!/usr/bin/python

# Helper module to download pieces of torrents and assemble them into the result files

import subprocess, requests, random, xmlrpclib, time, urllib, socket
import os, errno, weakref, hashlib
import threading, Queue
import requests

from bencode import *
from log import *
from tools import *

   
# Download set handler class

class Download(object):
    
    def __init__(self, pdl, jtorrent, basedir = u".", startPaused = False):
        
        self._pdl = weakref.ref(pdl)
        self._jtorrent = weakref.ref(jtorrent)
       
        self._basedir = basedir
        self._paused = startPaused
    
        log(DEBUG)
        
        self._files = jtorrent.files
        self._size = jtorrent.size
        self._piece_size = jtorrent.piece_size
        self._npieces = jtorrent.npieces
        
        downloaded, downloadedpieces, downloadedbytes = checkTorrentFiles(basedir, jtorrent.torrent) 
        self._downloadedpieces = self._finishedpieces = downloadedpieces
        self.downloaded = downloadedbytes
        log(DEBUG2, "self.downloadedpieces=%s self.downloaded=%d" % (self._downloadedpieces, self.downloaded))
        
        # Public attributes
        self.downloadSpeed = 0
        
        # Helper attribus for speed calc
        self._lastUpdate = 0.
        self._lastDownloaded = 0
        
        # Build piece->file map       
        self._piecefiles = []
        for p in xrange(self._npieces):
            self._piecefiles.append([])
        
        for f in self._files:
            log(DEBUG2, "File=%s start=%d:%d end=%d:%d"% (f, f.start_piece, f.start_piece_offset, f.end_piece, f.end_piece_offset))
            for p in xrange(f.start_piece, f.end_piece + 1):
                self._piecefiles[p].append(f)
    
        log(DEBUG2, "PF=%s"% self._piecefiles)
        
        # Preallocate files
        #for f in self._files:
        #    fn = os.path.join(self._basedir, f.path)
        #    mkdir_p(fn.rsplit(os.path.sep,1)[0])
        #    fh = open(fn, "r+b")
        #    fh.truncate(f.size)
        #    fh.close()
    
    
    def __repr__(self):
        return "PDL:Download(%r (0x%x))"% (self._basedir, id(self))
    

    def update(self):      
        if self._paused:
            self.downloadSpeed = 0.
            return
        
        # Find newly finished pieces
        lp = self._finishedpieces
        log(DEBUG, "LP=%s" % lp)
        
        for i,e in enumerate(zip(self._finishedpieces, self._jtorrent().bitfield)):
            if self._pdl().stalled():
                break
                
            if e[0] == '0' and e[1] == '1':
                # Mark piece as handled
                lp = self._finishedpieces
                self._finishedpieces = lp[:i] + "1" + lp[i+1:]
                
                # Send piece off to downloader/writer
                self._pdl().pieceFinished(self, self._jtorrent().pieces[i])

        # Update download speed
        
        now = time.time()
        if self._lastUpdate != 0.:
            self.downloadSpeed = (self.downloaded - self._lastDownloaded) / (now - self._lastUpdate)
            
        self._lastUpdate = now
        self._lastDownloaded = self.downloaded
   

    # Piece finished, download it   
    def pieceFinished(self, p):
            
        log(DEBUG, "Piece %d finished (size=%d)." % (p.number, p.size))
        try:
            log(DEBUG3, "url=%s" % p.url)
            r = self._jtorrent()._jsit()._session.get(p.url, params = {"api_key":self._jtorrent()._jsit()._api_key}, verify=False)    
            log(DEBUG3, "Got %r" % r.content)    
            r.raise_for_status()
        except Exception,e :
            log(ERROR, u"Caught exception %s downloading piece %d!" % (e, p.number))
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
    
        self.downloaded += p.size
        dp = self._downloadedpieces
        self._downloadedpieces = dp[:p.number] + "1" + dp[p.number+1:]        
                       
       
    def stop(self):
        self._paused = True
        
     
    def start(self):
        self._paused = False
        
    
    def delete(self):
        self._pdl().deleteTorrent(self)
        
   
    @property
    def hasFinished(self):
        return self.downloaded == self._size
   
    @property
    def percentage(self):
        return self.downloaded / float(self._size) * 100.
       
        
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
        while True:
            tor,piece = self._pieceQ .get()
            log(DEBUG, "Got piece %s:%s" % (tor,piece))
            
            if piece == -1:
                log(DEBUG, "Got suicide signal, returning.")
                return
                
            tor.pieceFinished(piece)   
            
            self._pieceQ.task_done()
       
     
    def writePieceThread(self):
        log(DEBUG)
        while True:
            tor,piece,cont = self._writeQ .get()
            log(DEBUG, "Got piece %s:%s (%d bytes content)" % (tor,piece, len(cont)))
            
            if piece == -1:
                log(DEBUG, "Got suicide signal, returning.")
                return
            
            tor.writePiece(piece, cont)   
            
            self._writeQ.task_done()
    
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
    
    def download(self, torrent, basedir = u".", startPaused = True):
        d = Download(self, torrent, basedir=basedir, startPaused=startPaused)
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
            
            