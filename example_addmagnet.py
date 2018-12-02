#!/usr/bin/python

## Simple example for the JSIT module

import time, sys
from tools import testtorrents, isoize_b, isoize_bps

import jsit
from log import *

# For debugging, use False to reduce clutter
if True:
    setLogLevel(DEBUG)

## Establish connection

# Using with enforces cleanup, good idea for small scripts in general
with jsit.JSIT("mlieschen@hotmail.com", "fuck1you") as js:

    print "Established connection to justseed.it. Let's see what you got going on..."

    f = open(sys.argv[1])

    for h in f.readlines():
        h = h.strip()
        print "Adding %s" % h
        
        try:
            bs = jsit.issueAPIRequest(js, "/torrent/add.csp", params = { u"info_hash" : h })
            thash = unicode(bs.find("info_hash").text)
            bs = jsit.issueAPIRequest(js, "/torrent/add_tracker.csp", params = { u"info_hash" : thash, u"url": "http://sciencehd.me:34000/2pc3ai4wo5u2nyqvl3hc70lun22s2keh/announce" })
            bs = jsit.issueAPIRequest(js, "/torrent/set_label.csp", params = { u"info_hash" : thash, u"label": "Documentary" })

        except Exception,e :
            log(ERROR, u"Caught exception %s adding torrent %s!" % (e, h))

        time.sleep(10)
