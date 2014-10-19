#!/usr/bin/python

import sys, jsit
from tools import printNiceTimeDelta as pntd
js = jsit.JSIT(sys.argv[1], sys.argv[2])

# For debugging, use False to reduce clutter
if False:
    from log import *
    setLogLevel(DEBUG3)

r = []
for t in js:
    print "%s : %s" % (t.name.encode('ascii', 'replace'), pntd(t.retention))
    r.append(t.retention)

print "\nGlobal retention for %d torrents (min,avg,max): %s - %s - %s" % (len(r), pntd(min(r)), pntd(sum(r) / len(r)), pntd(max(r)))

