#!/usr/bin/python

# Example for using jsit and the PieceDownloader

import time, sys
import jsit, PieceDownloader, tools

# Uncomment for debug output
from log import *
if True:
    ##setLogLevel(DEBUG)
    setFileLog("log.txt", DEBUG2)
    ##addOnlyModule("PieceDownloader")
    
if len(sys.argv) < 3:
    print "Call as %s <username> <password>" % sys.argv[0]
    sys.exit(1)

with jsit.JSIT(sys.argv[1], sys.argv[2]) as js, PieceDownloader.PieceDownloader(js, nthreads = 6) as pd:

    t = js.addTorrentURL(tools.testtorrents["JamesBond"], maximum_ratio = 0.01)


    # Don't need to wait for torrent to finish, let's just get going

    print "Let's download whatever is done."

    d = pd.download(t,  basedir = os.path.join("downloads", tools.unicode_cleanup(t.name)), startPaused = False)    

    # Wait for PieceDownloader to finish
    while not d.hasFinished:
        pd.update() # Need to call to check new pieces
        sys.stdout.write("Download {percentage:.02f}% done at {downloadSpeed:.0f} b/s".format(percentage = d.percentage, downloadSpeed=d.downloadSpeed)
                            + " " * 10 + "\r");
        sys.stdout.flush()
        time.sleep(1)

print
print "Done. Check out 'downloads/' for the results."

