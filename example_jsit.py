#!/usr/bin/python

## Simple example for the JSIT module

import time, sys

import jsit

# For debugging, use False to reduce clutter
if False:
    from log import *
    setLogLevel(DEBUG)

if len(sys.argv) < 3:
    print "Call as %s <username> <password>" % sys.argv[0]
    sys.exit(1)

## Establish connection

js = jsit.JSIT(sys.argv[1], sys.argv[2])

print "Established connection to justseed.it. Let's see what you got going on..."

# How many torrent do we have?
print "You're running %s torrents" % len(js)

# How many are finished?
print "Of those %d have already finished." % len([t for t in js if t.hasFinished])

# How much data are we downloading?
print "And they all together have %d bytes of data." % reduce(lambda x,y: x + y.size, js, 0)

# How many trackers do we use?
trackers = set()
for t in js:
    for tr in t.trackers:
        trackers.add(tr.url.split('/')[2])
print "You are using %d different trackers." % len(trackers)


# Add a torrent
print "Now let's do something: Adding new torrent..."
tor = js.addTorrentURL("magnet:?xt=urn:btih:fb87fe0d7d903eec20387fe9616fde7acde766fc&dn=BEST++100+HD++FUNNY+WALLPAPERS&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Ftracker.ccc.de%3A80&tr=udp%3A%2F%2Fopen.demonii.com%3A1337", 
                       maximum_ratio = 0.01)

print "Added torrent has hash %s." % tor.hash

# Wait for it to finish
while not tor.hasFinished:
    print "%s is %s doing %d b/s down and %d b/s up with %d peers (%d seeds)." % (tor.name, tor.status, tor.data_rate_in, tor.data_rate_out, 
                                                                                  len(tor.peers), len([p for p in tor.peers if p.percentage == 100]))
    time.sleep(5)

print "Torrent %s finished!" % tor.name

# Files
print "Torrent %s has %d files." % (tor.name, len(tor.files))

f = tor.files[0]
print "Here is the first one: %s (%d b), download from %s" % (f.path, f.size, f.url)
 
# Labels
print "You've set these labels:", js.labels

# Show label
print "Torrent %s's label: %s" % (tor.name, tor.label)

# Set label
# only if there are labels set
if len(js.labels) > 0:
    tor.label = js.labels[0]

    # Show label
    print "Torrent %s's label now: %s" % (tor.name, tor.label)

    # Remove label
    tor.label = None
    print "Torrent %s's label now: %s" % (tor.name, tor.label)

    
# Stop torrent
tor.stop()

print "Torrent %s status now: %s" % (tor.name, tor.status)

print "Please remove the example torrent by hand, there's no API for that yet..."

print "Done."

