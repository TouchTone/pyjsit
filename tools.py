
# Generic tools used in multiple modules

import datetime, hashlib, errno
from log import *

import unicodedata

from bencode import *


# Helper class for enumerations

def enum(*sequential, **named):
    if isinstance(sequential[0], tuple):
        enums = dict(zip([s[0] for s in sequential], range(len(sequential))), **named)
        reverse = dict((value, key) for key, value in enums.iteritems())
        enums['attribs'] = dict(zip([s[0] for s in sequential], [s[1:] for s in sequential]))
        enums['enum_attribs'] = [s[1:] for s in sequential]
    else:
        enums = dict(zip(sequential, range(len(sequential))), **named)
        reverse = dict((value, key) for key, value in enums.iteritems())
    enums['reverse_mapping'] = reverse
    enums['mapping'] = dict((key, value) for key, value in enums.iteritems())
    enums['__getitem__'] = lambda i: enums['mapping'][i]
    enums['count'] = len(enums)
    enums['values'] = reverse.values()
    return type('Enum', (), enums)


# Based on http://stackoverflow.com/questions/816285/where-is-pythons-best-ascii-for-this-unicode-database
def unicode_cleanup(s):
   
    # Fix up messy punctuation
    punctuation = { u'\u2018' : u'\u0027', u'\u2019' : u'\u0027',  u'\u201c' : u'\u0022',  u'\u201d' : u'\u0022',
                    u'\u2012' : u'-', u'\u2013' : u'-', u'\u2014' : u'-', 
                    u'\xe2\x80\x99' : u'\u0027', u'\xe2\x80\x98' : u'\u0027',  
                    u'\xe2\x80\x9c' : u'\u0022', u'\xe2\x80\x9d' : u'\u0022', 
                    u'\xe2\x80\x9e' : u'\u0022', u'\xe2\x80\x9f' : u'\u0022',
                    u'\xe2\x80\x90' : u'\u002d', u'\xe2\x80\x91' : u'\u002d', 
                    u'\xe2\x80\x92' : u'\u002d', u'\xe2\x80\x93' : u'\u002d', 
                    u'\xe2\x80\x94' : u'\u002d', u'\xe2\x80\x95' : u'\u002d' 
                    }
    
    for a,b in punctuation.iteritems():
        s = s.replace(a, b)
    
    s = unicodedata.normalize('NFKD', s)
    
    return s
 
 

def isoize(val, unit):
    try:
        num=float(val)
    except TypeError:
        return "0 " + unit
        
    sizes = ["", "K", "M", "G", "T"]
    for s in sizes:
        if num < 1024:
            sn = "%.2f %s" % (num, s)
            break
        num /= 1024.0
    return sn + unit

isoize_b = lambda v: isoize(v, "B")
isoize_bps = lambda v: isoize(v, "B/s")


# Based on http://stackoverflow.com/questions/538666/python-format-timedelta-to-string
def printNiceTimeDelta(delta):
    delay = datetime.timedelta(seconds=int(delta))
    out = str(delay)
    #if (delay.days > 1):
    #    out = out.replace(" days, ", ":")
    #if (delay.days > 0):
    #    out = out.replace(" day, ", ":")
    #else:
    #    out = "0:" + out
    #outAr = out.split(':')
    #outAr = ["%02d" % (int(float(x))) for x in outAr]
    #out   = ":".join(outAr)
    return out    
    
# From http://tomayko.com/writings/cleanest-python-find-in-list-function
def find(f, seq):
  """Return first item in sequence where f(item) == True."""
  for item in seq:
    if f(item): 
      return item
 

# From http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise
  
 

def checkTorrentFiles(basedir, torrentdata):

    # Get hashes and piece info from torrent
    # Code based on btshowmetainfo.py
    metainfo = bdecode(torrentdata)
    info = metainfo['info']

    piece_length = info['piece length']
    piece_hash = [info['pieces'][x:x+20] for x in xrange(0, len(info['pieces']), 20)]

    tfiles = []
    file_length = 0

    if info.has_key('length'):
        tfiles.append((info['name'], info['length']))
        file_length = info['length']
    else:
        for file in info['files']:
            path = ""
            for item in file['path']:
                if (path != ''):
                   path = path + "/"
                path = path + item
            tfiles.append((path, file['length']))
            file_length += file['length']

    piece_number, last_piece_length = divmod(file_length, piece_length)

    # Let's get checking...
    
    pi = 0
    psize = pleft = piece_length
    hash = hashlib.sha1()

    finished = []
    finishedpieces = ""
    finishedbytes = 0
    unfinished = []
    curpiece = [] # Files completing in current piece

    for fn,fl in tfiles:

        fn = unicode_cleanup(fn.decode('utf-8'))            
        fn = os.path.abspath(os.path.join(basedir, fn))

        # Try/except doesn't work so well, error messages are not uniform between OSs
        if os.path.isfile(fn): 
            st = os.stat(fn)

            #log(DEBUG2, "fn=%r st.st_size=%d fl=%d" % (fn, st.st_size, fl))

            # Size ok?
            if st.st_size == fl:
                f = open(fn, "rb")   
            else:
                f = None
        else:
            f = None
            #log(DEBUG2, "fn=%r not found fl=%d" % (fn,fl))

        fleft = fl
        filefailed = False
        
        while fleft > 0:

            rs = min(fleft, pleft)
            if f:
                buf = f.read(rs)
            else:
                buf = '0' * rs

            #log(DEBUG2, "fleft=%d pleft=%d f=%r" % (fleft, pleft, f))
            
            hash.update(buf)                
            pleft -=rs
            fleft -=rs

            if fleft == 0 and not filefailed:
                curpiece.append(fn)

            if pleft == 0:

                #log(DEBUG2, "fn=%r pi=%d equal=%r hash.digest()=%r piece_hash[pi]=%r" % (fn, pi, hash.digest() == piece_hash[pi], hash.digest(), piece_hash[pi]))
                
                if hash.digest() == piece_hash[pi]:

                    finishedpieces += "1"
                    finished += curpiece  
                    finishedbytes += psize

                else:
                    filefailed = True
                    finishedpieces += "0"

                curpiece = []

                hash = hashlib.sha1()
                pi += 1

                if pi == piece_number:
                    psize = pleft = last_piece_length
                else:
                    psize = pleft = piece_length

    return finished, finishedpieces, finishedbytes


# Some testing torrents that are small but usually have a good number of seeders (some NSFW!)

testtorrents = { "Wallpapers" : "magnet:?xt=urn:btih:fb87fe0d7d903eec20387fe9616fde7acde766fc&dn=BEST++100+HD++FUNNY+WALLPAPERS&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Ftracker.ccc.de%3A80&tr=udp%3A%2F%2Fopen.demonii.com%3A1337",
                 "CobieSmulders" : "magnet:?xt=urn:btih:af464c51de4d85cd2425681dc184491b8d067d6c&dn=Cobie%20Smulders%20%e2%80%93%20Esquire%20Magazine%20%28March%202014%29&tr=udp://open.demonii.com:1337&tr=udp://tracker.ccc.de:80&tr=udp://tracker.istole.it:6969&tr=udp://tracker.justseed.it:1337&tr=udp://tracker.openbittorrent.com:80&tr=udp://tracker.publicbt.com:80", 
                 "Construction" : "magnet:?xt=urn:btih:b0427d648d8354b312b19e2a2f3335da7a652f42&dn=40%20Funny%20Construction%20Mistakes%20%5bPics%5d&tr=udp://open.demonii.com:1337&tr=udp://tracker.ccc.de:80&tr=udp://tracker.istole.it:6969&tr=udp://tracker.justseed.it:1337&tr=udp://tracker.openbittorrent.com:80&tr=udp://tracker.publicbt.com:80", 
                 "JamesBond" : "magnet:?xt=urn:btih:cb1135220f5b6a5dfec2298080b811dae5a07e2b&dn=James%20Bond%20007%20Complete%20Movie%20Posters-Moviejockey.com&tr=udp://open.demonii.com:1337&tr=udp://tracker.ccc.de:80&tr=udp://tracker.istole.it:6969&tr=udp://tracker.justseed.it:1337&tr=udp://tracker.openbittorrent.com:80&tr=udp://tracker.publicbt.com:80", 
                 "KateUpton" : "magnet:?xt=urn:btih:89c6a13f339ee371a2f54a5bff5b2bb482fd14c7&dn=KATE+UPTON+-+2013+SPORTS+ILLUSTRATED+SWIMSUIT+ISSUE+-+45+PHOTOS&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Ftracker.ccc.de%3A80&tr=udp%3A%2F%2Fopen.demonii.com%3A1337" 
               }
