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

jsit.listValidityLength = 30000
jsit.infoValidityLength = 30000

# Using with enforces cleanup, good idea for small scripts in general
with jsit.JSIT("mlieschen@hotmail.com", "fuck1you") as js:

    print "Established connection to justseed.it. Let's see what you got going on..."

    for t in js:
        print t,t.status        
        
        found = False
        for tr in t.trackers:
             if tr.url == "http://sciencehd.me:34000/2pc3ai4wo5u2nyqvl3hc70lun22s2keh/announce":
                print "found shd tracker, skipping."
                found = True
                break

        if not found:        
            try:
                bs = jsit.issueAPIRequest(js, "/torrent/add_tracker.csp", params = { u"info_hash" : t.hash, u"url": "http://sciencehd.me:34000/2pc3ai4wo5u2nyqvl3hc70lun22s2keh/announce" })

            except Exception,e :
                log(ERROR, u"Caught exception %s adding tracker for torrent %s!" % (e, t))

        time.sleep(60)
