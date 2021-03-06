#!/usr/bin/python

## Simple example for the JSIT module

import time, sys
from tools import testtorrents, isoize_b, isoize_bps

import jsit

# For debugging, use False to reduce clutter
if False:
    from log import *
    setLogLevel(DEBUG)

if len(sys.argv) < 3:
    print "Call as %s <username> <password>" % sys.argv[0]
    sys.exit(1)

## Establish connection

# Using with enforces cleanup, good idea for small scripts in general
with jsit.JSIT(sys.argv[1], sys.argv[2]) as js:

    print "Established connection to justseed.it. Let's see what you got going on..."

    # How many torrent do we have?
    print "You're running %s torrents and you have %s remaining." % (len(js), isoize_b(js.dataRemaining))

    # How many are finished?
    print "Of those %d have already finished." % len([t for t in js if t.hasFinished])

    # How much data are we downloading?
    print "And they all together have %s of data." % isoize_b(reduce(lambda x,y: x + y.size, js, 0))

    # How many trackers do we use?
    trackers = set()
    for t in js:
        for tr in t.trackers:
            trackers.add(tr.url.split('/')[2])
    print "You are using %d different trackers." % len(trackers)


    # Add a torrent
    print "Now let's do something: Adding new torrent..."
    tor = js.addTorrentURL(testtorrents["CreativeIdeas"], maximum_ratio = 0.01)

    print "Added torrent has hash %s." % tor.hash

    # Wait for it to finish
    while not tor.hasFinished:
        print "%s is at %.02f%% %s doing %s down and %s up with %d peers (%d seeds)." % (tor.name, tor.percentage, 
                tor.status, isoize_bps(tor.data_rate_in), isoize_bps(tor.data_rate_out), 
                len(tor.peers), len([p for p in tor.peers if p.percentage == 100]))
        time.sleep(10)

    print "Torrent %s finished!" % tor.name

    # Peers
    print "Currently with %d peers." % len(tor.peers)
    
    # Files
    print "Torrent %s has %d files." % (tor.name, len(tor.files))

    f = tor.files[0]
    print "Here is the first one: %s (%d b), download from %s" % (f.path, f.size, f.url)

    # Bitfield
    print "Torrent bitfield is %s." % tor.bitfield
    
    # Torrent data
    print "Raw torrent data starts with %s." % tor.torrent[0:10]
    
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

    # Delete torrent

    print "Deleting torrent %s." % (tor.name)

    h = tor.hash
    tor.delete()

    print "Torrent with hash %s: %s" % (h, js.lookupTorrent(h))

    print "Done."

