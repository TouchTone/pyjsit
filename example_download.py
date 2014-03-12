#!/usr/bin/python

# Example for using jsit and aria
# Assumes you have the aria executable in your path!

import time
import jsit, aria

if len(sys.argv) < 3:
    print "Call as %s <username> <password>" % sys.argv[0]
    sys.exit(1)

js = jsit.JSIT(sys.argv[1], sys.argv[2])
ar = aria.Aria(cleanupLeftovers = True)

t = js.addTorrentURL("magnet:?xt=urn:btih:fb87fe0d7d903eec20387fe9616fde7acde766fc&dn=BEST++100+HD++FUNNY+WALLPAPERS&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Ftracker.ccc.de%3A80&tr=udp%3A%2F%2Fopen.demonii.com%3A1337", 
                      maximum_ratio = 0.01)
 
while not t.hasFinished:
    print "not done yet... (%.02f%%)" % t.percentage   
    time.sleep(5)
    

durls = [f.url for f in t.files]

print "%d files (%s)" % (len(durls), durls)

d = ar.download(durls,  basedir = "test_download", fullsize = t.size, startPaused = False)    

while not d.hasFinished:
    print ar.status, d.percentage
    time.sleep(5)

print d.statusAll()

print "Done."
    
