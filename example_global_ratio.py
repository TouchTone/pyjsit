#!/usr/bin/python

import sys, jsit
js = jsit.JSIT(sys.argv[1], sys.argv[2])

r = []
for t in js:
	if True: # use t.private: to only check private torrents. Much slower!
		print "%s : %.3f" % (t.name.encode('ascii', 'replace'), t.ratio)
		r.append(t.ratio)

print "Global ratio for %d torrents: %.3f" % (len(r), sum(r) / len(r))

