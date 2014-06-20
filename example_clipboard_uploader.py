#!/usr/bin/python

# Watch the clipboard for magnet: or .torrent links and upload them to JSIT

import time, sys
from PySide import QtGui, QtCore

import jsit
from log import *

if len(sys.argv) < 3:
    print "Call as %s <username> <password>" % sys.argv[0]
    sys.exit(1)

js = jsit.JSIT(sys.argv[1], sys.argv[2])

print "Clipboard uploader started..."

qapp = QtGui.QApplication(sys.argv)
qclip = QtGui.QApplication.clipboard()

interval = 0.5

handled = set()

while True:

    for clip in [str(qclip.text(QtGui.QClipboard.Clipboard)), str(qclip.text(QtGui.QClipboard.Selection))]:
    
        if len(clip) == 0 or clip in handled:
            continue
            
        log(DEBUG, "Got clip: %s" % clip)
        
        handled.add(clip)
         
        if clip.startswith("magnet:") or ( clip.startswith("http://") and clip.endswith(".torrent") ): 

            if clip.startswith("magnet:"):
                s = clip.find("dn=") + 3
                e = clip.find("&", s)
            else:
                s = clip.rfind("/") + 1
                e = None
                
            log(WARNING, "Found link for %s, uploading..." % clip[s:e])
            
            js.addTorrentURL(clip)
           
    time.sleep(interval)
    
