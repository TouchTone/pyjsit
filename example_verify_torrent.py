#!/usr/bin/python

## Simple example for verifying a torrent's data

import time, sys, os
from tools import checkTorrentFiles

import jsit

# For debugging, use False to reduce clutter
if False:
    from log import *
    setLogLevel(DEBUG3)

if len(sys.argv) < 4:
    print "Call as %s <username> <password> <torrent hash or name> [<downdir>]" % sys.argv[0]
    sys.exit(1)

## Establish connection

# Using with enforces cleanup, good idea for small scripts in general
with jsit.JSIT(sys.argv[1], sys.argv[2]) as js:

    # Find torrent on JSIT
    
    name = sys.argv[3]
    # Hash?
    t = js.lookupTorrent(name)
    
    if not t:
        t = js.findTorrents(name)
        
        if not t:
            log(ERROR, "Can't find any torrent matching '%s'!" % name)
            sys.exit(1)
            
        if len(t) > 1:
            log(ERROR, "Found %s torrents matching '%s', can't proceeed." % (len(t), name))
        
        t = t[0]
    
    print "Found torrent '%s' (%s) with %d files." % (t.name.encode("ascii","xmlcharrefreplace"), t.hash, len(t.files))
    
    
    # Look for data
    if len(sys.argv) == 5:
        datadir = sys.argv[4]

    else:  
        datadir = '.' 
              
    if len(t.files) > 1:
        datadir = os.path.join(datadir, t.name.replace('/', '_'))
    
    print "Checking data in %s" % datadir.encode("ascii","xmlcharrefreplace")
 
    
    def progress(pnum, pind, ffiles, fpieces, fbytes,  buf):
        sys.stdout.write("\rChecked %.02f%%..." % (pind / float(pnum) * 100.))
        sys.stdout.flush()
    
    finished, finishedpieces, finishedbytes = checkTorrentFiles(datadir, t.torrent, callback = progress)
    
    print 
   
    print "Found %d of %d bytes (%.02f%%)." % (finishedbytes, t.size, finishedbytes / float(t.size) * 100)
    
    if len(t.files) > len(finished):
        print "The following files are unfinished:"
        for f in t.files:
            if not os.path.join(datadir, f.path) in finished:
                print f.path.encode("ascii","xmlcharrefreplace")
             
