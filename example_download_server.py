#!/usr/bin/python

# Example for using pyjsit on a server to automatically get some/all torrents from JSIT


import time, sys
import jsit_manager, tools
  
if len(sys.argv) < 3:
    print "Call as %s <username> <password>" % sys.argv[0]
    sys.exit(1)

# Configuration vars

downLabel = "GetMe"         # Only download torrents with this label, if None: get all
gotLabel = "DLDone"         # Set torrents that have finished download to this label, ignore them later.
downloadDir = "downloads"   # Directory to download everything to
downloadMode = "Pieces"     # How to download torrents: Pieces: piece by piece, Finished: at the end using aria


# Already downloaded/ing torrents
downt = set()
working = set()
last = 0

with jsit_manager.Manager(sys.argv[1], sys.argv[2]) as jsm:

    while True:
       
        # Update torrents and running downloads
        jsm.update()
    
        now = time.time()
        
        # Check for new torrents to download?
        if now > last + 20:
            print "%s : Update: Manager has %d torrents." % (time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime()), len(jsm))

            # Check all torrents to see what we need
            for t in jsm:

                # Do we need this torrent?
                if not t in downt and (not gotLabel or t.label != gotLabel) and (downLabel == None or t.label == downLabel):

                    print "Adding %s for download..." % t.name

                    t.downloadMode = downloadMode

                    downt.add(t)
                    working.add(t)

            # Check if any of the working ones finished
            if len(working):
                print "Active:",
                for t in set(working):
                    print "%s at %.02f%% (%s, %s)" % (t.name, t.percentage, tools.isoize(t._torrent.data_rate_in, "b/s"), tools.isoize(t.downloadSpeed, "b/s")),

                    if t.hasFinished:

                        print "Finished!",
                        if gotLabel:
                            t.label = gotLabel

                        working.remove(t)

                print 
            
            last = now
        
        time.sleep(2)

print
print "Done. Check out %' for the results." % downloadDir

