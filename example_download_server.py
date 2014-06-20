#!/usr/bin/python

# Example for using pyjsit on a server to automatically get some/all torrents from JSIT


import time, sys
import jsit_manager, tools, preferences
  
if len(sys.argv) < 3:
    print "Call as %s <username> <password>" % sys.argv[0]
    sys.exit(1)

# Configuration is done in preferences
preferences.load("preferences.json")

with jsit_manager.Manager(sys.argv[1], sys.argv[2]) as jsm:

    while not jsm.allFinished:
       
        # Update torrents, running downloads and start new automatic downloads
        jsm.update()
        
        # Put a little sleep to avoid overhead
        time.sleep(2)

print
print "Done. Check out %s for the results." % prefs("downloads", "basedir", "downloads")

