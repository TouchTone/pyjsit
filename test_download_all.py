#!/usr/bin/python

# Download all finished torrents that do not have label dllabel (if set)
# Assumes you have the aria2c executable in your path!

import time, sys, os
import jsit, aria

# Uncomment for debug output
from log import *
#setLogLevel(DEBUG)

if len(sys.argv) < 3:
    print "Call as %s <username> <password> [<label>]" % sys.argv[0]
    sys.exit(1)

# Establish connections
js = jsit.JSIT(sys.argv[1], sys.argv[2])
ar = aria.Aria(cleanupLeftovers = True)

if len(sys.argv) > 3:
    dllabel = sys.argv[3]
else:
    dllabel = None

# Iterate torrents, find finished ones (without dllabel)
dls = []
for t in js:
    
    if t.hasFinished and (dllabel == None or t.label == dllabel):
        print "Adding %s to download queue..." % t.name
        durls = [f.url for f in t.files]
        dls.append(ar.download(durls,  basedir = os.path.join("downloads", t.name), fullsize = t.size, startPaused = False, torrentdata = t.torrent))
        
        #if dllabel:
        #    t.label = dllabel

# Wait for aria to finish
while not ar.hasFinished:
    sys.stdout.write("{numActive} running at {downloadSpeed:.0f} b/s. {numWaiting} waiting, {numStopped} stopped.".format(**ar.status)
                        + " " * 10 + "\r");
    sys.stdout.flush()
    time.sleep(1)

print 
print "Done."
    
