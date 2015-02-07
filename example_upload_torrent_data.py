#!/usr/bin/python

## Simple example for uploading a torrent's data to JSIT

import time, sys, os
import xml.etree.ElementTree as ET
import jsit
from log import *
from tools import checkTorrentFiles


# For debugging, use False to reduce clutter
if True:
    setLogLevel(DEBUG3)

if len(sys.argv) < 5:
    print "Call as %s <username> <password> <torrentfile> <datadir>" % sys.argv[0]
    sys.exit(1)

## Establish connection

# Using with enforces cleanup, good idea for small scripts in general
with jsit.JSIT(sys.argv[1], sys.argv[2]) as js:

    torname = sys.argv[3]
    datadir = sys.argv[4]

    # Add torrent to JSIT and stop it to avoid grabbing external data
    tor = js.addTorrentFile(torname)
    tor.stop()

    print "Added torrent '%s' (%s) with %d files." % (tor.name.encode("ascii","xmlcharrefreplace"), tor.hash, len(tor.files))

    # Use this if you want to automatically add the name of the torrent as a header directory for torrents with > 1 files
    #if len(tor.files) > 1:
    #    datadir = os.path.join(datadir, tor.name.replace('/', '_'))

    
    print "Adding data from %s" % datadir.encode("ascii","xmlcharrefreplace")


    def upload(pnum, pind, ffiles, fpieces, fbytes,  buf):

        piece = tor.pieces[pind]
        url = piece.upload_url

        try:
            r = js._session.post(url=url, params={"api_key" : js._api_key}, files={'piece_file' : ("piece_file", buf) } )
            r.raise_for_status()

            bs = ET.fromstring(r.content)

            log(DEBUG3, "issueAPIRequest: node %r" % bs)

            status = bs.find("status")
            log(DEBUG2, "status=%r" % status)

            if status is None:
                raise APIError("%s protocol failure!"% url)

            if status.text != "SUCCESS":
                m = bs.find("message")
                h = bs.find("info_hash")
                if h is not None and m is not None:
                    raise APIError("%s failed: %s (info_hash=%s)!"% (url, unicode(urllib.unquote(m.text)), unicode(urllib.unquote(h.text))))
                elif m is not None:
                    raise APIError("%s failed: %s!"% (url, unicode(urllib.unquote(m.text))))
                else:
                    raise APIError("%s failed!"% url)


        except Exception, e:
            print "Caught %s uploading piece %d, aborting" % (e, pind)

        sys.stdout.write("\rUploaded %.02f%%..." % (pind / float(pnum) * 100.))
        sys.stdout.flush()



    finished, finishedpieces, finishedbytes = checkTorrentFiles(datadir, tor.torrent, callback = upload)
    
    if finishedbytes != tor.size:
        print "%d bytes failed verification, torrent is probably corrupted!"

        if len(tor.files) > len(finished):
            print "The following files did not match the torrent:"
            for f in tor.files:
                if not os.path.join(datadir, f.path) in finished:
                    print f.path.encode("ascii","xmlcharrefreplace")


    print "\nUpload finished."