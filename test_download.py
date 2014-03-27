#!/usr/bin/python

# Example for using jsit and aria
# Assumes you have the aria executable in your path!

import time, sys
import jsit, aria

# Uncomment for debug output
from log import *
setLogLevel(DEBUG)

if len(sys.argv) < 3:
    print "Call as %s <username> <password>" % sys.argv[0]
    sys.exit(1)

js = jsit.JSIT(sys.argv[1], sys.argv[2])
ar = aria.Aria(cleanupLeftovers = True)

t = js.lookupTorrent("78d03cdec2deae4070631ea49944709299449e9f")

print t.name

print "Waiting for torrent to finish..."

while not t.hasFinished:
    print "Torrent not done yet... (at %.02f%% with %.0f b/s from %d peers)" % (t.percentage, t.data_rate_in, len(t.peers))
    time.sleep(5)
    
print "Torrent done!"

durls = [f.url for f in t.files]
    
print "Got %d files, downloading them." % (len(durls))

d = ar.download([durls[5]],  basedir = "downloads/" + t.name, fullsize = t.size, startPaused = False)    

# Wait for aria to finish
while not d.hasFinished:
    sys.stdout.write("Download {percentage:.02f}% done ({numActive} running at {downloadSpeed:.0f} b/s, {numWaiting} waiting, {numStopped} stopped)".format(percentage = d.percentage, **ar.status)
                        + " " * 10 + "\r");
    sys.stdout.flush()
    time.sleep(1)

print
print "Done. Check out 'downloads/FunnyWallpapers' for the results."
    
