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
print "Lookup:", t

if not t:
    t = js.addTorrentURL("magnet:?xt=urn:btih:06591706c10e8aa7371b521db0b594f671a614d2&dn=ShutterStock+7163029+-+Wild+Orchids+and+Pink+Swirls+%28Vector%29&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Ftracker.ccc.de%3A80&tr=udp%3A%2F%2Fopen.demonii.com%3A1337",
                       maximum_ratio = 0.01)        
	
print t.name

print "Waiting for torrent to finish..."

while not t.hasFinished:
    print "Torrent not done yet... (at %.02f%% with %.0f b/s from %d peers)" % (t.percentage, t.data_rate_in, len(t.peers))
    time.sleep(5)
    
print "Torrent done!"

durls = [f.url for f in t.files]
    
print "Got %d files, downloading them." % (len(durls))

d = ar.download(durls,  basedir = "downloads/" + t.name, fullsize = t.size, startPaused = False, torrentdata = t.torrent)    

# Wait for aria to finish
while not d.hasFinished:
    sys.stdout.write("Download {percentage:.02f}% done ({numActive} running at {downloadSpeed:.0f} b/s, {numWaiting} waiting, {numStopped} stopped)\n".format(percentage = d.percentage, **ar.status));
    sys.stdout.flush()
    time.sleep(5)

print
print "Done. Check out 'downloads/' for the results."
    
