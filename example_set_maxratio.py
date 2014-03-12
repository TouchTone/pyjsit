#!/usr/bin/python

import jsit

if len(sys.argv) < 3:
    print "Call as %s <username> <password>" % sys.argv[0]
    sys.exit(1)

js = jsit.JSIT(sys.argv[1], sys.argv[2])

for t in js:
    if t.private:
        print u"Setting ratio on %s to unlimited." % t.name
        t.maximum_ratio = 0
    else:
        print u"Setting ratio on %s to 0.01." % t.name
        t.maximum_ratio = 0.01
