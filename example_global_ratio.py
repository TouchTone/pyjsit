#!/usr/bin/python

import sys, jsit
js = jsit.JSIT(sys.argv[1], sys.argv[2])

r = []
for t in js:
	if t.private:
		print "%s : %.3f" % (t.name, t.ratio)
		r.append(t.ratio)

print "Global ratio: %.3f" % (sum(r) / len(r))

