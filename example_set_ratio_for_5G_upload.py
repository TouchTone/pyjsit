#!/usr/bin/python

import sys, jsit

js = jsit.JSIT(sys.argv[1], sys.argv[2])

for t in js:
    r = 5*1024*1024*1024 / t.size
    if r != t.maximum_ratio:
        print u"Setting ratio on %s to %.02f." % (t.name, r)
        t.maximum_ratio = r
