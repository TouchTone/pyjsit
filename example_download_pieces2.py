#!/usr/bin/python

## Simple example for verifying a torrent's data

import time, sys, os
from tools import checkTorrentFiles

import jsit, PieceDownloader
from log import *
# For debugging, use False to reduce clutter
if True:
    setLogLevel(DEBUG3)

if len(sys.argv) < 4:
    print "Call as %s <username> <password> <torrent hash or name> [<downdir>]" % sys.argv[0]
    sys.exit(1)

## Establish connection

# Using with enforces cleanup, good idea for small scripts in general
with jsit.JSIT(sys.argv[1], sys.argv[2]) as js, PieceDownloader.PieceDownloader(js, nthreads = 6) as pd:

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
    
    print "Downloading to %s" % datadir.encode("ascii","xmlcharrefreplace")
 
    d = pd.download(t,  basedir = datadir, startPaused = False)    

    # Wait for PieceDownloader to finish
    while not d.hasFinished:
        pd.update() # Need to call to check new pieces
        sys.stdout.write("Download {percentage:.02f}% done at {downloadSpeed:.0f} b/s".format(percentage = d.percentage, downloadSpeed=d.downloadSpeed)
                            + " " * 10 + "\r");
        sys.stdout.flush()
        time.sleep(5)

print
print "Done. Check out '%s' for the results." % (datadir)

