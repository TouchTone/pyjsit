
# Generic tools used in multiple modules

import ctypes, os, platform, sys
import datetime, hashlib, errno
from log import *

import unicodedata, chardet

from bencode import *


# Helper class for enumerations

def enum(*sequential, **named):
    enums = dict()
    if isinstance(sequential[0], tuple):
        enumvals = dict(zip([s[0] for s in sequential], range(len(sequential))), **named)
        reverse = dict((value, key) for key, value in enumvals.iteritems())
        if len(s) == 2:
            enums['attribs'] = dict(zip([s[0] for s in sequential], [s[1] for s in sequential]))
            enums['enum_attribs'] = [s[1] for s in sequential]
        else:
            enums['attribs'] = dict(zip([s[0] for s in sequential], [s[1:] for s in sequential]))
            enums['enum_attribs'] = [s[1:] for s in sequential]
        enums['reverse_attribs'] = dict((value, key) for key, value in enums['attribs'].iteritems())
    else:
        enumvals = dict(zip(sequential, range(len(sequential))), **named)
        reverse = dict((value, key) for key, value in enumvals.iteritems())
    enums['reverse_mapping'] = reverse
    enums['mapping'] = dict((key, value) for key, value in enumvals.iteritems())
    enums['__getitem__'] = lambda i: enums['mapping'][i]
    enums['count'] = len(enums)
    enums['values'] = reverse.values()
    return type('Enum', (), enums)


# Based on http://stackoverflow.com/questions/816285/where-is-pythons-best-ascii-for-this-unicode-database
def unicode_cleanup(s):
   
    # Fix up messy punctuation
    punctuation = { u'\u2018' : u'\u0027', u'\u2019' : u'\u0027',  u'\u201c' : u'\u0022',  u'\u201d' : u'\u0022',
                    u'\u2012' : u'-', u'\u2013' : u'-', u'\u2014' : u'-', u'\u8073' : u'-',
                    u'\xe2\x80\x99' : u'\u0027', u'\xe2\x80\x98' : u'\u0027',  
                    u'\xe2\x80\x9c' : u'\u0022', u'\xe2\x80\x9d' : u'\u0022', 
                    u'\xe2\x80\x9e' : u'\u0022', u'\xe2\x80\x9f' : u'\u0022',
                    u'\xe2\x80\x90' : u'\u002d', u'\xe2\x80\x91' : u'\u002d', 
                    u'\xe2\x80\x92' : u'\u002d', u'\xe2\x80\x93' : u'\u002d', 
                    u'\xe2\x80\x94' : u'\u002d', u'\xe2\x80\x95' : u'\u002d' 
                    }
    
    try:
        for a,b in punctuation.iteritems():
            s = s.replace(a, b)
        
        s = unicodedata.normalize('NFKD', s)
    except UnicodeDecodeError,e:
        pass
    
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


# Map duration string to number of seconds (Ex: "3:12.00" -> 192, "2h" -> 7200, "2d", "3w 2d 10:00")
def mapDuration(dur):
    res = 0
    for p in dur.split(' '):
        if p[-1] == 'w':
            res += float(p[:-1]) * 86400 * 7
            continue
        if p[-1] == 'd':
            res += float(p[:-1]) * 86400
            continue
        if ':' in p:
            pp = p.split(':')
            if len(pp) == 2:
                res += float(pp[0]) * 60 + float(pp[1])
            elif len(pp) == 3:
                res += float(pp[0]) * 3600 + float(pp[1]) * 60 + float(pp[2])
            continue
        res += float(p)

    return res


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

# Based on http://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename-in-python and
# http://stackoverflow.com/questions/1033424/how-to-remove-bad-path-characters-in-python
def clean_pathname(pathname):
    pn = os.path.normpath(pathname)
    pn = u''.join(c for c in pn if not c in u'<>"|?*')
    
    return pn


# From http://stackoverflow.com/questions/51658/cross-platform-space-remaining-on-volume-using-python
def get_free_space(folder):
    while folder and not os.path.isdir(folder):
        folder = folder.rsplit(os.path.sep, 1)[0]
    
    if not folder:
        return 0
        
    if platform.system() == 'Windows':
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value
    else:
        st = os.statvfs(folder)
        return st.f_bavail * st.f_frsize
        
        
# From http://stackoverflow.com/questions/16261902/python-any-way-to-get-one-process-to-have-a-write-lock-and-others-to-just-read      
import threading

class RWLock:
    '''Non-reentrant write-preferring rwlock.'''
    DEBUG = 1

    def __init__(self):
        self.lock = threading.Lock()

        self.active_writer_lock = threading.Lock()
        # The total number of writers including the active writer and
        # those blocking on active_writer_lock or readers_finished_cond.
        self.writer_count = 0

        # Number of events that are blocking on writers_finished_cond.
        self.waiting_reader_count = 0

        # Number of events currently using the resource.
        self.active_reader_count = 0

        self.readers_finished_cond = threading.Condition(self.lock)
        self.writers_finished_cond = threading.Condition(self.lock)

        class _ReadAccess:
            def __init__(self, rwlock):
                log(DEBUG4)
                self.rwlock = rwlock
            def __enter__(self):
                log(DEBUG4)
                self.rwlock.acquire_read()
                return self.rwlock
            def __exit__(self, type, value, tb):
                log(DEBUG4)
                self.rwlock.release_read()
        # support for the with statement
        self.read_access = _ReadAccess(self)

        class _WriteAccess:
            def __init__(self, rwlock):
                log(DEBUG4)
                self.rwlock = rwlock
            def __enter__(self):
                log(DEBUG4)
                self.rwlock.acquire_write()
                return self.rwlock
            def __exit__(self, type, value, tb):
                log(DEBUG4)
                self.rwlock.release_write()
        # support for the with statement
        self.write_access = _WriteAccess(self)

        if self.DEBUG:
            self.active_readers = set()
            self.active_writer = None

    def acquire_read(self):
        with self.lock:
            if self.DEBUG:
                me = threading.currentThread()
                assert me not in self.active_readers, 'This thread has already acquired read access and this lock isn\'t reader-reentrant!'
                assert me != self.active_writer, 'This thread already has write access, release that before acquiring read access!'
                self.active_readers.add(me)
            if self.writer_count:
                self.waiting_reader_count += 1
                self.writers_finished_cond.wait()
                # Even if the last writer thread notifies us it can happen that a new
                # incoming writer thread acquires the lock earlier than this reader
                # thread so we test for the writer_count after each wait()...
                # We also protect ourselves from spurious wakeups that happen with some POSIX libraries.
                while self.writer_count:
                    self.writers_finished_cond.wait()
                self.waiting_reader_count -= 1
            self.active_reader_count += 1

    def release_read(self):
        with self.lock:
            if self.DEBUG:
                me = threading.currentThread()
                assert me in self.active_readers, 'Trying to release read access when it hasn\'t been acquired by this thread!'
                self.active_readers.remove(me)
            assert self.active_reader_count > 0
            self.active_reader_count -= 1
            if not self.active_reader_count and self.writer_count:
                self.readers_finished_cond.notifyAll()

    def acquire_write(self):
        with self.lock:
            if self.DEBUG:
                me = threading.currentThread()
                assert me not in self.active_readers, 'This thread already has read access - release that before acquiring write access!'
                assert me != self.active_writer, 'This thread already has write access and this lock isn\'t writer-reentrant!'
            self.writer_count += 1
            if self.active_reader_count:
                self.readers_finished_cond.wait()
                while self.active_reader_count:
                    self.readers_finished_cond.wait()

        self.active_writer_lock.acquire()
        if self.DEBUG:
            self.active_writer = me

    def release_write(self):
        if not self.DEBUG:
            self.active_writer_lock.release()
        with self.lock:
            if self.DEBUG:
                me = threading.currentThread()
                assert me == self.active_writer, 'Trying to release write access when it hasn\'t been acquired by this thread!'
                self.active_writer = None
                self.active_writer_lock.release()
            assert self.writer_count > 0
            self.writer_count -= 1
            if not self.writer_count and self.waiting_reader_count:
                self.writers_finished_cond.notifyAll()

    def get_state(self):
        with self.lock:
            return (self.writer_count, self.waiting_reader_count, self.active_reader_count)


def decodeString(s):
    sout = None
    
    encoding = chardet.detect(s)
    # For short strings, chardet sometimes messes up. But it knows it...
    # Try chinese GB18030 for those and use it if it works
    if encoding["confidence"] < 0.7:
        try:
            sout = s.decode("GB18030")
        except UnicodeDecodeError,e:
            # Didn't work, ignore.
            pass
        
    if not sout:
        try:
            sout = s.decode(encoding["encoding"])
        except UnicodeDecodeError,e:
            if encoding["encoding"] == "GB2312":
                try:
                    sout = s.decode("GB18030")
                except UnicodeDecodeError,e:
                    log(ERROR, "Can't decode path %r, keeping as raw." % s)
                    sout = s
            else:
                log(ERROR, "Can't decode path %r, keeping as raw." % s)
                sout = s
    return sout


def getTorrentInfo(torrentdata):
    # Get hashes and piece info from torrent
    # Code based on btshowmetainfo.py
    metainfo = bdecode(torrentdata)
    info = metainfo['info']

    piece_length = info['piece length']
    piece_hash = [info['pieces'][x:x+20] for x in xrange(0, len(info['pieces']), 20)]

    tfiles = []
    file_length = 0

    if info.has_key('length'):
        tfiles.append((decodeString(info["name"]), info['length']))
        file_length = info['length']
    else:
        for file in info['files']:
            path = ""
            for item in file['path']:
                if (path != ''):
                    path = path + "/"
                path = path + item
            
            pname = decodeString(path)
            tfiles.append((pname, file['length']))
            file_length += file['length']

    piece_number, last_piece_length = divmod(file_length, piece_length)
    
    return tfiles, piece_length, piece_hash, piece_number, last_piece_length



def checkTorrentFiles(basedir, torrentdata, callback = None):
    
    tfiles, piece_length, piece_hash, piece_number, last_piece_length = getTorrentInfo(torrentdata)
    
    # Does base dir exist? If not there is nothing to check...
    if not os.path.isdir(basedir):
        return [], '0' * (piece_number + 1), 0

    # Let's get checking...
    
    pi = 0
    psize = pleft = piece_length
    buf = ""
    
    f = None
    finished = []
    finishedpieces = ""
    finishedbytes = 0
    unfinished = []
    curpiece = [] # Files completing in current piece

    for fname,fl in tfiles:
                
        fname = unicode_cleanup(fname)            
        fname = os.path.abspath(os.path.join(basedir, fname))

        if platform.system() == "Windows" and len(fname) > 250:
            fname = u"\\\\?\\" + fname
       
        # Try/except doesn't work so well, error messages are not uniform between OSs
        if os.path.isfile(fname): 
            st = os.stat(fname)

            log(DEBUG3, "fname=%r st.st_size=%d fl=%d" % (fname, st.st_size, fl))

            if f != None:
                f.close()
                
            # Size ok?
            if st.st_size == fl:
                f = open(fname, "rb")   
            else:
                f = None
        else:
            f = None
            log(DEBUG3, "fname=%r not found fl=%d" % (fname,fl))

        fleft = fl
        filefailed = False
        
        while fleft > 0:

            rs = min(fleft, pleft)
            if f:
                b = f.read(rs)
                if len(b) != rs:
                    log(DEBUG3, "tried to read %d bytes, but got %d from f=%r" % (rs, len(b), f))
                    filefailed = True
                    b = "0" * rs
                buf += b
                  

            log(DEBUG3, "fleft=%d pleft=%d f=%r" % (fleft, pleft, f))
            
            pleft -=rs
            fleft -=rs

            if fleft == 0 and not filefailed:
                curpiece.append(fname)

            if pleft == 0:

                hash = hashlib.sha1(buf)
                
                log(DEBUG3, "fname=%r pi=%d equal=%r hash.digest()=%r piece_hash[pi]=%r" % (fname, pi, hash.digest() == piece_hash[pi], hash.digest(), piece_hash[pi]))
                
                if hash.digest() == piece_hash[pi]:

                    finishedpieces += "1"
                    finished += curpiece  
                    finishedbytes += psize

                else:
                    filefailed = True
                    finishedpieces += "0"


                if callback:
                    callback(piece_number + 1, pi, finished, finishedpieces + '0' * (piece_number + 1 - len(finishedpieces)), finishedbytes, buf)

                curpiece = []

                buf = ""
                pi += 1

                if pi == piece_number:
                    psize = pleft = last_piece_length
                else:
                    psize = pleft = piece_length

    if f != None:
        f.close()

    return finished, finishedpieces, finishedbytes


# Some testing torrents that are small but usually have a good number of seeders (some NSFW!)

testtorrents = { "Wallpapers" : "magnet:?xt=urn:btih:fb87fe0d7d903eec20387fe9616fde7acde766fc&dn=BEST++100+HD++FUNNY+WALLPAPERS&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Ftracker.ccc.de%3A80&tr=udp%3A%2F%2Fopen.demonii.com%3A1337",
                 "CobieSmulders" : "magnet:?xt=urn:btih:af464c51de4d85cd2425681dc184491b8d067d6c&dn=Cobie%20Smulders%20%e2%80%93%20Esquire%20Magazine%20%28March%202014%29&tr=udp://open.demonii.com:1337&tr=udp://tracker.ccc.de:80&tr=udp://tracker.istole.it:6969&tr=udp://tracker.justseed.it:1337&tr=udp://tracker.openbittorrent.com:80&tr=udp://tracker.publicbt.com:80", 
                 "Construction" : "magnet:?xt=urn:btih:b0427d648d8354b312b19e2a2f3335da7a652f42&dn=40%20Funny%20Construction%20Mistakes%20%5bPics%5d&tr=udp://open.demonii.com:1337&tr=udp://tracker.ccc.de:80&tr=udp://tracker.istole.it:6969&tr=udp://tracker.justseed.it:1337&tr=udp://tracker.openbittorrent.com:80&tr=udp://tracker.publicbt.com:80", 
                 "JamesBond" : "magnet:?xt=urn:btih:cb1135220f5b6a5dfec2298080b811dae5a07e2b&dn=James%20Bond%20007%20Complete%20Movie%20Posters-Moviejockey.com&tr=udp://open.demonii.com:1337&tr=udp://tracker.ccc.de:80&tr=udp://tracker.istole.it:6969&tr=udp://tracker.justseed.it:1337&tr=udp://tracker.openbittorrent.com:80&tr=udp://tracker.publicbt.com:80", 
                 "CreativeIdeas" : "magnet:?xt=urn:btih:a307f2758e4f4d2bd94c33e29cc34e6c40e9e648&dn=70%20Creative%20Ideas%20For%20Everyday%20Life%20%5bPics%5d&tr=udp://open.demonii.com:1337&tr=udp://tracker.istole.it:6969&tr=udp://tracker.justseed.it:1337&tr=udp://tracker.openbittorrent.com:80&tr=udp://tracker.publicbt.com:80",                  
                 "KateUpton" : "magnet:?xt=urn:btih:89c6a13f339ee371a2f54a5bff5b2bb482fd14c7&dn=KATE+UPTON+-+2013+SPORTS+ILLUSTRATED+SWIMSUIT+ISSUE+-+45+PHOTOS&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Ftracker.ccc.de%3A80&tr=udp%3A%2F%2Fopen.demonii.com%3A1337" 
               }
