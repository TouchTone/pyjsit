#! /usr/bin/python

## Python interface to access justseed.it data to support automation applications


import requests, urllib, time, sys, re, weakref, threading, Queue, traceback
import platform
from copy import copy
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

import OpenSSL.SSL

from log import *
from tools import *

# Disable urllib3 warnings. Unverified is fine for us. From http://stackoverflow.com/questions/27981545/surpress-insecurerequestwarning-unverified-https-request-is-being-made-in-pytho
requests.packages.urllib3.disable_warnings()

import requests.packages.urllib3.contrib.pyopenssl
requests.packages.urllib3.contrib.pyopenssl.inject_into_urllib3()


baseurl="https://justseed.it"
apibaseurl="https://api.justseed.it"

# If you mess with these don't be surprised if you're banned without warning...
infoValidityLength = 3600
bitfieldValidityLength = 60 
finishedBitfieldValidityLength = 3600 # Once it's finished it's highly unlikely to change
dataValidityLength = 3600
listValidityLength = 300
fileValidityLength = 86400
trackerValidityLength = 3600
peerValidityLength = 600
labelValidityLength = 300
torrentValidityLength = 86400
piecesValidityLength = 86400


## Temporay until the sciencehd flood is reduced

if False:
    infoValidityLength = 15000
    bitfieldValidityLength = 600 
    finishedBitfieldValidityLength = 36000 # Once it's finished it's highly unlikely to change
    dataValidityLength = 3600
    listValidityLength = 15000
    fileValidityLength = 86400
    trackerValidityLength = 15000
    peerValidityLength = 60000
    labelValidityLength = 3600
    torrentValidityLength = 86400
    piecesValidityLength = 86400


retrySleep = 60.
abortAfterAPIFailures = 5
reconnectTime = 20*60

# Exceptions

class APIError(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


# Helper functions

# Keep some stats about API calls...
# 0: number of calls, 1: time for calls
apiStats = {}
apiStatsLock = RWLock()
apiNFailures = 0   # Number of failed requests after last successful one

def apiFailed(jsit, msg = None):
    global apiNFailures
    apiNFailures += 1
    if apiNFailures >= abortAfterAPIFailures and jsit.connected():
        log(ERROR, "Got %s consecutive API failures, disconnecting (%s)." % (apiNFailures, msg))
        jsit.disconnect()
        sys.exit(1)
    else:
        log(DEBUG, "Got api failure (%s), already disconnected" % msg)


def apiSucceeded(jsit):
    global apiNFailures
    apiNFailures = 0
    
    

# Issue API request and check status for success. Return BeautifulSoup handle for content

def issueAPIRequest(jsit, url, params = None, files = None):

    if jsit._session is None:
        log(ERROR, "No JSIT session, API request skipped.")
        raise APIError("%s (params=%s, files=%s) failed: No session!"% (url, params, files))
        
    if params is None:
        p = {}
    else:
        p = copy(params)

    p["api_key"] = jsit._api_key

    log(DEBUG2, "issueAPIRequest: Calling %s (params=%s, files=%s)"% (apibaseurl + url, p, files))
    
    retries = 4
    
    while retries > 0:
        start = time.time()
        try:
            r = jsit._session.get(apibaseurl + url, params = p, files = files, verify=False, timeout = 20)            
            r.raise_for_status()
            log(DEBUG3, "issueAPIRequest: Got %r" % r.content)
            end = time.time()
	    if len(r.content) == 0:
	    	log(INFO, "API request '%s' (params = %s, files = %s) got empty response, retrying!" % (url, params, files))
		retries -= 1
                time.sleep(retrySleep)
		continue
            break
        except (requests.exceptions.Timeout, OpenSSL.SSL.SysCallError), e:
            log(DEBUG, "API request '%s' (params = %s, files = %s) timed out, retrying!" % (url, params, files))
            retries -= 1
            apiFailed(jsit, e)
            time.sleep(retrySleep)
        except requests.ConnectionError, e:
            apiFailed(jsit, str(e))
            if "target machine actively refused it" in str(e):
                log(ERROR, "JSIT refused conncetion, probably down. Disconnecting!")
                jsit.disconnect()
                raise APIError("%s (params=%s, files=%s) failed: JSIT down!"% (url, params, files))
            elif "Connection aborted" in str(e) or "EOF occurred in violation of protocol" in str(e):
                log(DEBUG, "API request '%s' (params = %s, files = %s) timed out, retrying!" % (url, params, files))
                retries -= 1
                time.sleep(retrySleep)               
            else:
                log(ERROR, "Got Connection error, sleeping before throwing!")
                time.sleep(retrySleep)
                raise e
        except Exception, e:
            apiFailed(jsit, e)
            if "account is out of data" in str(e):
                log(ERROR, "Your account is out of data! Disconnecting!")
                jsit.disconnect()
                raise APIError("%s (params=%s, files=%s) failed: Account out of data!"% (url, params, files))
            elif "EOF occurred" in str(e) or "Connection aborted" in str(e):
                log(DEBUG, "API request '%s' (params = %s, files = %s) timed out, retrying!" % (url, params, files))
                retries -= 1
                time.sleep(retrySleep)
            elif "object has no attribute 'get'" in str(e):
                log(DEBUG, "Caught get error, probably already closed connection. Ignoring.")
                raise APIError("Ran into closed conection, ignoring.")
            else:
                log(ERROR, "Got unknown exception %s, sleeping before throwing!" % e)
                time.sleep(retrySleep)
                raise e

    
    if retries == 0:
        apiFailed(jsit)
        log(WARNING, "API request '%s' (params = %s, files = %s) ran out of retries!" % (url, params, files))
        raise APIError("%s (params=%s, files=%s) failed: ran out of retries!" % (url, params, files))        
    
    apiSucceeded(jsit)    
        
    # Keep stats
    with apiStatsLock.write_access:
        try:
            s = apiStats[url]
            ns = (s[0] + 1, s[1] + (end-start))
            apiStats[url] = ns
        except KeyError:
            apiStats[url] = (1, end-start)
    
    bs = ET.fromstring(r.content)
    
    log(DEBUG3, "issueAPIRequest: node %r" % bs)

    status = bs.find("status")
    log(DEBUG2, "status=%r" % status)
    
    if status is None:
        raise APIError("%s protocol failure!"% url)
        
    if status.text != "SUCCESS":
        m = bs.find("message")
        h = bs.find("info_hash")
        
        if m is not None and "Your account is not accessible" in unicode(urllib.unquote(m.text)):
            log(ERROR, "Your account is not accessible! Disconnecting!")
            jsit.disconnect()
            
        if h is not None and m is not None:
            raise APIError("%s failed: %s (info_hash=%s)!"% (url, unicode(urllib.unquote(m.text)), unicode(urllib.unquote(h.text))))
        elif m is not None:
            raise APIError("%s failed: %s!"% (url, unicode(urllib.unquote(m.text))))
        else:
            raise APIError("%s failed!"% url)

    return bs


# Convert types of given fields from string to desired type

def cleanupFields(obj, floatfields = None, intfields = None, boolfields = None):

    if floatfields:
        for f in floatfields:
            if isinstance(getattr(obj, f), float) or getattr(obj, f) is None:
                continue
            if getattr(obj, f) == "" or getattr(obj, f) == "unknown":
                setattr(obj, f,  0.)
                continue
            try:
                setattr(obj, f,  float(getattr(obj, f)))
            except ValueError:
                log(ERROR, "can't convert '%s' to float for field %s!" % (getattr(obj, f), f))

    if intfields:
        for f in intfields:
            if isinstance(getattr(obj, f), int) or getattr(obj, f) is None:
                continue
            if getattr(obj, f) == "" or getattr(obj, f) == "unknown":
                setattr(obj, f,  0)
                continue
            try:
                setattr(obj, f,  int(getattr(obj, f)))
            except ValueError:
                log(ERROR, "can't convert '%s' to int for field %s!" % (getattr(obj, f), f))

    if boolfields:
        for f in boolfields:
            if isinstance(getattr(obj, f), bool) or getattr(obj, f) is None:
                continue
            if getattr(obj, f) == "" or getattr(obj, f) == "unknown":
                setattr(obj, f,  None)
                continue
            try:
                if getattr(obj, f) in ["True", "true", "1", "Yes", "yes"]:
                    setattr(obj, f,  True)
                elif getattr(obj, f) in ["False", "false", "0", "No", "no"]:
                    setattr(obj, f,  False)
                else:
                    log(ERROR, "can't convert '%s' to bool for field %s!" % (getattr(obj, f), f))
            except ValueError:
                log(ERROR, "can't convert '%s' to bool for field %s!" % (getattr(obj, f), f))


# Fill object fields from XML response

def fillFromXML(obj, root, fieldmap, exclude_unquote = []):

    for n in root:
        try:
            if n.tag == None:
                s = None
            elif n.tag in exclude_unquote:
                s = unicode(n.text)
            else:
                try:
                    nt = urllib.unquote(str(n.text))
                    nt = decodeString(nt)
                    s = unicode_cleanup(nt)
                except (IOError, UnicodeEncodeError, UnicodeDecodeError, LookupError), e:
                    log(INFO, "fillFromXML: caught %s decoding response for %s, keeping as raw %r." % (e, n, n.text))
                    s = n.text
            
            setattr(obj, fieldmap[n.tag], s)
            
        except KeyError:
            pass


    

# Update methods boiler plate code
def updateBase(jsit, obj, part, url, params = {}, force = False, raw = False, static = False):

    with obj._lock.read_access:

        # Did we get a new update from update thread? Use it!
        nbs = getattr(obj, "_" + part + "NewBS")
        if nbs != None and nbs != "Pending":
            setattr(obj, "_" + part + "NewBS", None)
            return nbs

        # Updating already set static var?
        if static and getattr(obj, "_" + part + "ValidUntil") != 0:
            return

        # Do we need a new update?
        if (time.time() < getattr(obj, "_" + part + "ValidUntil") or nbs == "Pending") and not force:
            return None

        ##log(DEBUG, "force=%s jsit._asyncUpdates=%s validuntil=%s" % (force, jsit._asyncUpdates, getattr(obj, "_" + part + "ValidUntil")))

        # Forced or first call?
        if force or jsit._nthreads == 0 or (jsit._nthreads > 0 and getattr(obj, "_" + part + "ValidUntil") == 0):
            log(DEBUG, "Need to update data.")
            try:
                if not raw:
                    bs = issueAPIRequest(jsit, url, params = params)
                else:
                    r = jsit._session.get(baseurl + url, verify=False)
                    r.raise_for_status()
                    bs = r.content

            except Exception,e :
                log(ERROR, u"Caught exception %s updating %s for torrent %s!" % (e, part, obj._name))
                time.sleep(10)
                bs = None

        else:
            if nbs == None:
                obj._lock.release_read()
                obj._lock.acquire_write()
                setattr(obj, "_" + part + "NewBS", "Pending")
                jsit._updateQ.put((obj, part, url, params, raw))
                log(DEBUG, "Submit update request.")

                obj._lock.release_write()
                obj._lock.acquire_read()

            return None


        return bs



# Part classes for torrent info

class TFile(object):

    def __init__(self, torrent):

        self._torrent = weakref.ref(torrent)

        self.end_piece = 0
        self.end_piece_offset = 0
        self.path = u""
        self.percentage = 0
        self.required = 1
        self.size = 0
        self.start_piece = 0
        self.start_piece_offset = 0
        self.torrent_name = 0
        self.torrent_offset = 0
        self.total_downloaded = 0
        self.url = None

    def __repr__(self):
        r = "TFile(%r (%r)"% (self.path, self.size)
        if self.url:
            r += " U"
        if self.required:
            r += " R"
        r += ")"
        return r


    def cleanupFields(self):
        cleanupFields(self, intfields = ["end_piece", "end_piece_offset", "size", "start_piece", "start_piece_offset",
                                         "torrent_offset", "total_downloaded", "required"],
                            floatfields = ["percentage"])


    def write(self, fname, piece, data, size):
        if piece.number == self.start_piece:
            seek = 0
            start = self.start_piece_offset
        else:                    
            seek = (piece.number - self.start_piece) * self._torrent().piece_size - self.start_piece_offset
            start = 0
        
        if platform.system() == "Windows" and len(fname) > 250:
            fname = u"\\\\?\\" + fname
            
        if not os.path.isfile(fname):
            mkdir_p(fname.rsplit(os.path.sep,1)[0])
            f = open(fname, "wb")
        else:
            try:
                s = os.stat(fname)

                if s.st_size < seek:
                    f = open(fname, "r+b")
                    f.truncate(seek)
                else:
                    f = open(fname, "r+b")
                    
            except IOError,e :
                f.close()
                log(WARNING, "Caught %s"% e)
                raise
            
        log(DEBUG2, "PN=%d SP=%d seek=%d start=%d len=%d" % (piece.number, self.start_piece, seek, start, len(data[start:start + size])))

        try:
            f.seek(seek)
            f.write(data[start:start + size])
        finally:
            f.close()
        

class TTracker(object):

    def __init__(self, torrent):

        self._torrent = weakref.ref(torrent)

        self.downloaded = 0
        self.interval = 0
        self.last_announce = u""
        self.leechers = 0
        self.message = None
        self.peers = 0
        self.seeders = 0
        self.url = u""

    def __repr__(self):
        r = "TTracker(%r (S:%r L:%r)"% (self.url, self.seeders, self.leechers)
        if self.url:
            r += "U"
        r += ")"
        return r


    def cleanupFields(self):
        cleanupFields(self, intfields = ["downloaded", "interval", "leechers", "seeders", "peers"])


class TPeer(object):

    def __init__(self, torrent):

        self._torrent = weakref.ref(torrent)

        self.direction = ""
        self.ip_address = ""
        self.peer_id = ""
        self.percentage = 0
        self.port = 0

    def __repr__(self):
        return "TPeer(%r (%r, %r))"% (self.ip_address, self.direction, self.percentage)


    def cleanupFields(self):
        cleanupFields(self, intfields = ["port"], floatfields = ["percentage"])

        
class TPiece(object):

    def __init__(self, torrent):

        self._torrent = weakref.ref(torrent)

        self.hash = ""
        self.number = 0
        self.size = 0
        self.upload_url = ""
        self.url = ""

        
    def __repr__(self):
        return "TPiece(%r (%r))"% (self.number, self.size)


    def cleanupFields(self):
        cleanupFields(self, intfields = ["number", "size"])



# Base JS.it torrent class

class Torrent(object):

    def __init__(self, jsit, hash_ = None):
        
        # Lock for parallel access
        self._lock = RWLock()
        
        # Set up attributes
        self._jsit = weakref.ref(jsit)
        self._hash = hash_

        # List data
        self._listValidUntil = 0
        self._listNewBS = None
        self._name = u""
        self._label = u""
        self._status = ""
        self._percentage = 0
        self._size = 0
        self._downloaded = 0
        self._uploaded = 0
        self._ratio = 0
        self._data_rate_in = 0
        self._data_rate_out = 0
        self._elapsed = 0
        self._start_time = 0  # Derived from elapsed on updates, used to update elapsed without API calls
        self._ttl = 0
        self._etc = 0
        self._maximum_ratio = 0
        self._auto_download_pieces = False
        self._auto_generate_links = False
        self._auto_generate_tar_links = False
        self._completion = 0

        # Info data
        self._infoValidUntil = 0
        self._infoNewBS = None
        self._private = False
        self._completed_announced = False
        self._ip_address = ""
        self._ip_port = ""
        self._magnet_link = ""
        self._piece_size = 0
        self._npieces = 0
        self._total_files = 0
        self._retention = 0

        # Files data
        self._filesValidUntil = 0
        self._filesNewBS = None
        self._files = []

        # Trackers data
        self._trackersValidUntil = 0
        self._trackersNewBS = None
        self._trackers    = []
        self._trackerurls = []

        # Peers data
        self._peersValidUntil = 0
        self._peersNewBS = None
        self._peers = []

        # Bitfield data
        self._bitfieldValidUntil = 0
        self._bitfieldNewBS = None
        self._bitfield = ""

        # Torrent data
        self._torrentValidUntil = 0
        self._torrentNewBS = None
        self._torrent = ""

        # Pieces data
        self._piecesValidUntil = 0
        self._piecesNewBS = None
        self._pieces = []

        log(DEBUG)

    def __repr__(self):
        return "Torrent(%r (%r))"% (self._name, self._hash)


    # Setters

    def set_name(self, name):
        log(DEBUG, "Setting name for %s (%s) to %s" % (self._name, self._hash, name))

        if self._name == name:
            return

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/set_name.csp", params = { u"info_hash" : self._hash, u"name": name })

            with self._lock.write_access:
                self._name = name

        except Exception,e :
            log(ERROR, u"Caught exception %s setting name!" % (e))


    def set_label(self, label):
        log(DEBUG, "Setting label for %s (%s) from %s to %s" % (self._name, self._hash, self._label, label))

        if self._label == label:
            return

        try:
            params = { u"info_hash" : self._hash}
            if label:
                params[u"label"] = label 
                
            bs = issueAPIRequest(self._jsit(), "/torrent/set_label.csp", params=params)

            with self._lock.write_access:
                self._label = label

        except Exception,e :
            log(ERROR, u"Caught exception %s setting label!" % (e))


    def set_status(self, status):
        log(DEBUG, "Setting status for %s (%s) from %s to %s" % (self._name, self._hash, self._status, status))

        self._status = status


    def set_maximum_ratio(self, ratio):
        log(DEBUG, "Setting maximum ratio for %s (%s) to %s" % (self._name, self._hash, ratio))

        if self._maximum_ratio == ratio:
            return

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/set_maximum_ratio.csp", params = { u"info_hash" : self._hash, u"maximum_ratio": ratio })

            with self._lock.write_access:
                self._maximum_ratio = ratio

        except Exception,e :
            log(ERROR, u"Caught exception %s setting maximum ratio!" % (e))




    # Set up properties for attributes
    hash                    = property(lambda x: x.getStaticValue ("updateList", "_hash"),                   None)
    name                    = property(lambda x: x.getDynamicValue("updateList", "_name"),                   set_name)
    label                   = property(lambda x: x.getDynamicValue("updateList", "_label"),                  set_label)
    status                  = property(lambda x: x.getDynamicValue("updateList", "_status"),                 set_status)
    percentage              = property(lambda x: x.getDynamicValue("updateList", "_percentage"),             None)
    size                    = property(lambda x: x.getStaticValue ("updateList", "_size"),                   None)
    downloaded              = property(lambda x: x.getDynamicValue("updateList", "_downloaded"),             None)
    uploaded                = property(lambda x: x.getDynamicValue("updateList", "_uploaded"),               None)
    ratio                   = property(lambda x: x.getDynamicValue("updateList", "_ratio"),                  None)
    data_rate_in            = property(lambda x: x.getDynamicValue("updateList", "_data_rate_in"),           None)
    data_rate_out           = property(lambda x: x.getDynamicValue("updateList", "_data_rate_out"),          None)
    # Handled below elapsed = property(lambda x: x.getDynamicValue("updateList", "_elapsed"),                None)
    ttl                     = property(lambda x: x.getDynamicValue("updateList", "_ttl"),                    None)
    etc                     = property(lambda x: x.getDynamicValue("updateList", "_etc"),                    None)
    maximum_ratio           = property(lambda x: x.getDynamicValue("updateList", "_maximum_ratio"),          set_maximum_ratio)
    auto_generate_links     = property(lambda x: x.getDynamicValue("updateList", "_auto_generate_links"),    None)
    auto_generate_tar_links = property(lambda x: x.getDynamicValue("updateList", "_auto_generate_tar_links"),None)
    auto_download_pieces    = property(lambda x: x.getDynamicValue("updateList", "_auto_download_pieces"),   None)
    completion              = property(lambda x: x.getDynamicValue("updateList", "_completion"),             None)

    npieces                 = property(lambda x: x.getStaticValue ("updateInfo", "_npieces"),                None)
    private                 = property(lambda x: x.getStaticValue ("updateInfo", "_private"),                None)
    completed_announced     = property(lambda x: x.getDynamicValue("updateInfo", "_completed_announced"),    None)
    ip_address              = property(lambda x: x.getStaticValue ("updateInfo", "_ip_address"),             None)
    ip_port                 = property(lambda x: x.getStaticValue ("updateInfo", "_ip_port"),                None)
    magnet_link             = property(lambda x: x.getStaticValue ("updateInfo", "_magnet_link"),            None)
    piece_size              = property(lambda x: x.getStaticValue ("updateInfo", "_piece_size"),             None)
    retention               = property(lambda x: x.getDynamicValue("updateInfo", "_retention"),              None)
    total_files             = property(lambda x: x.getStaticValue ("updateInfo", "_total_files"),            None)

    files                   = property(lambda x: x.getStaticValue ("updateFiles","_files"),                  None)
    trackers                = property(lambda x: x.getDynamicValue("updateTrackers","_trackers"),            None)
    trackerurls             = property(lambda x: x.getStaticValue ("updateTrackers","_trackerurls"),         None)
    peers                   = property(lambda x: x.getDynamicValue("updatePeers","_peers"),                  None)
    bitfield                = property(lambda x: x.getDynamicValue("updateBitfield","_bitfield"),            None)
    torrent                 = property(lambda x: x.getStaticValue ("updateTorrent","_torrent"),              None)
    pieces                  = property(lambda x: x.getStaticValue ("updatePieces","_pieces"),                None)

    # Other, indirect properties

    @property
    def hasFinished(self):
        return self.percentage == 100

    @property
    def elapsed(self):
        if self._start_time == 0:
            return 0
        return time.time() - self._start_time


    # Generic getters

    def getDynamicValue(self, updater, name):        
        getattr(self, updater)(static = False)
        with self._lock.read_access:
            return self.__dict__[name]

    def getStaticValue(self, updater, name):        
        getattr(self, updater)(static = True)
        with self._lock.read_access:
            return self.__dict__[name]


    # Updater methods    

    # Try to get list elements from /torrents/list.csp
    def updateList(self, force = False, static = False):
        if not self._jsit:
            return
        if time.time() < self._listValidUntil and not force:
            return
        if static and self._listValidUntil != 0:
            return
        self._jsit().updateTorrents(force)


    def updateInfo(self, force = False, static = False):
    
        bs = updateBase(self._jsit(), self, "info", "/torrent/information.csp", params = {"info_hash" : self._hash}, force = force, static = static)

        # No update needed or none received yet?
        if bs == None:
             return

        fieldmap = { "name" : "_name",
                     "label" : "_label",
                     "status" : "_status",
                     "percentage_as_decimal" : "_percentage",
                     "size_as_bytes" : "_size",
                     "downloaded_as_bytes" : "_downloaded",
                     "uploaded_as_bytes" : "_uploaded",
                     "data_rate_in_as_bytes" : "_data_rate_in",
                     "data_rate_out_as_bytes" : "_data_rate_out",
                     "elapsed_as_seconds" : "_elapsed",
                     "server_retention_as_seconds" : "_retention",
                     "ratio_as_decimal" : "_ratio",
                     "maximum_ratio_as_decimal" : "_maximum_ratio",
                     "pieces" : "_npieces",
                     "is_private" : "_private",
                     "is_completed_announced" : "_completed_announced",
                     "ip_address" : "_ip_address",
                     "ip_port" : "_ip_port",
                     "magnet_link" : "_magnet_link",
                     "piece_size_as_bytes" : "_piece_size",
                     "total_files" : "_total_files"}

        with self._lock.write_access:
            fillFromXML(self, bs.find("data"), fieldmap)

            self.cleanupFields()

            self._infoValidUntil = time.time() + infoValidityLength
            self._listValidUntil = time.time() + listValidityLength


    def updateFiles(self, force = False, static = False):    
        bs = updateBase(self._jsit(), self, "files", "/torrent/files.csp", params = {"info_hash" : self._hash}, force = force, static = static)

        # No update needed or none received yet?
        if bs == None:
             return
             
        # Do we have links?
        r1 = bs.find("row")
        if r1 and self.percentage == 100 and r1.find("url").text == None:
            # Triger link gen
            log(DEBUG, u"Generating download links for %s (%s)..." % (self._name, self._hash))

            bs = issueAPIRequest(self._jsit(), "/links/create.csp", params = {"info_hash" : self._hash, "force" : 0})
            
            # Re-read list
            bs = issueAPIRequest(self._jsit(), "/torrent/files.csp", params = {"info_hash" : self._hash})


        fieldmap = { "end_piece" : "end_piece",
                     "end_piece_offset" : "end_piece_offset",
                     "path" : "path",
                     "percentage_as_decimal" : "percentage",
                     "size_as_bytes" : "size",
                     "required" : "required",
                     "start_piece" : "start_piece",
                     "start_piece_offset" : "start_piece_offset",
                     "torrent_name" : "torrent_name",
                     "torrent_offset" : "torrent_offset",
                     "total_downloaded_as_bytes" : "total_downloaded",
                     "url" : "url" }

        with self._lock.write_access:
            self._files = []

            for r in bs.find("data").findall("row"):

                t = TFile(self)
                fillFromXML(t, r, fieldmap)
                t.cleanupFields()

                self._files.append(t)

            self._filesValidUntil = time.time() + fileValidityLength


    def updateTrackers(self, force = False, static = False):
        bs = updateBase(self._jsit(), self, "trackers", "/torrent/trackers.csp", params = {"info_hash" : self._hash}, force = force, static = static)

        # No update needed or none received yet?
        if bs == None:
             return

        fieldmap = { "downloaded": "downloaded",
                     "interval": "interval",
                     "last_announce": "last_announce",
                     "leechers": "leechers",
                     "seeders": "seeders",
                     "peers": "peers",
                     "url": "url",
                     "message": "message" }

        with self._lock.write_access:
            self._trackers     = []
            self._trackerurls = []

            for r in bs.find("data").findall("row"):

                t = TTracker(self)
                fillFromXML(t, r, fieldmap)
                t.cleanupFields()

                self._trackers.append(t)
                self._trackerurls.append(t.url)

            self._trackersValidUntil = time.time() + trackerValidityLength


    def updatePeers(self, force = False, static = False):
        bs = updateBase(self._jsit(), self, "peers", "/torrent/peers.csp", params = {"info_hash" : self._hash}, force = force, static = static)

        # No update needed or none received yet?
        if bs == None:
             return

        fieldmap = {"direction" : "direction",
                    "ip_address" : "ip_address",
                    "peer_id" : "peer_id",
                    "percentage_as_decimal" : "percentage",
                    "port" : "port"
                    }

        self._peers = []

        with self._lock.write_access:
            for r in bs.find("data").findall("row"):

                t = TPeer(self)
                fillFromXML(t, r, fieldmap)
                t.cleanupFields()

                self._peers.append(t)

            self._peersValidUntil = time.time() + peerValidityLength


    def updateBitfield(self, force = False, static = False):
        bs = updateBase(self._jsit(), self, "bitfield", "/torrent/bitfield.csp", params = {"info_hash" : self._hash}, force = force, static = static)

        # No update needed or none received yet?
        if bs == None:
             return

        with self._lock.write_access:
            bf = bs.find("bitfield")

            self._bitfield = str(bf.text)

            if '0' in self._bitfield:
                self._bitfieldValidUntil = time.time() + bitfieldValidityLength
            else:
                self._bitfieldValidUntil = time.time() + finishedBitfieldValidityLength


    def updateTorrent(self, force = False, static = False):
        data = updateBase(self._jsit(), self, "torrent", "/torrents/torrent_file.csp?info_hash=%s" % self.hash, params = {}, force = force, static = static, raw = True)

        # No update needed or none received yet?
        if data == None:
             return

        with self._lock.write_access:
            self._torrent = data

            self._torrentValidUntil = time.time() + torrentValidityLength



    def updatePieces(self, force = False, static = False):
        bs = updateBase(self._jsit(), self, "pieces", "/torrent/pieces.csp", params = {"info_hash" : self._hash}, force = force, static = static)

        # No update needed or none received yet?
        if bs == None:
             return

        fieldmap = {"hash" : "hash",
                    "number" : "number",
                    "size" : "size",
                    "url" : "url",
                    "upload_url" : "upload_url"
                    }

        with self._lock.write_access:
            self._pieces = []

            for r in bs.find("data").findall("row"):

                t = TPiece(self)
                fillFromXML(t, r, fieldmap)
                t.cleanupFields()

                self._pieces.append(t)

            self._piecesValidUntil = time.time() + piecesValidityLength

            
    # Check if files valid, if not trigger update
    # TODO: It would be nice to have a generic version of this for every attribute
    def checkFiles(self):
        if self._filesValidUntil == 0:            
            # Not running async? Just go ahead and wait...
            if self._jsit()._nthreads == 0:
                return True

            # Got new data, but not parsed yet? Accept!
            nbs = getattr(self, "_" + "files" + "NewBS")
            if nbs != None and nbs != "Pending":
                return True
            
            # No request sent yet? Send one.
            if nbs != "Pending":
                self._lock.acquire_write()
                setattr(self, "_" + "files" + "NewBS", "Pending")
                self._jsit()._updateQ.put((self, "files", "/torrent/files.csp", {"info_hash" : self._hash}, False))
                log(DEBUG, "Submit files update request.")
                self._lock.release_write()
                
            return False
        
        return True


    def cleanupFields(self):
        cleanupFields(self, floatfields = ["_percentage", "_maximum_ratio"],
                            intfields = ["_total_files", "_size", "_downloaded", "_uploaded", "_data_rate_in", "_data_rate_out",
                                         "_npieces", "_ip_port", "_piece_size", "_elapsed", "_retention", "_completion" ],
                            boolfields = ["_private", "_completed_announced","_auto_generate_links","_auto_generate_tar_links",
                                          "_auto_download_pieces"])
        
        if len(self._label) == 0:
            self._label = ""
            
        # Derived fields
        if self._downloaded > 0:
            self._ratio = self._uploaded / float(self._downloaded)
        else:
            self._ratio = 0
        
        if self._start_time == 0 and self._elapsed != 0:
            self._start_time = time.time() - self._elapsed        
        
        if self._retention == 0:
            self._ttl = 0
        else:
            self._ttl = self._retention - self._elapsed

        try:
            if self._percentage == 100:
                self._etc = 0
            else:
                self._etc = (self._size - self._downloaded) / self._data_rate_in
        except Exception,e :
            self._etc = 0



    def start(self):
        log(DEBUG)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/start.csp", params = {"info_hash" : self._hash})

            self._status = "running"

        except Exception,e :
            log(ERROR, u"Caught exception %s starting torrent %s!" % (e, self._name))


    def stop(self):
        log(DEBUG)

        self._status = "stopped"
        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/stop.csp", params = {"info_hash" : self._hash})
        except Exception,e :
            log(ERROR, u"Caught exception %s stopping torrent %s!" % (e, self._name))
            
            if "Please specify a valid Info Hash" in str(e):
                self._status = "deleted"


    def delete(self):
        log(INFO)
        self._jsit().deleteTorrent(self)


    def release(self):
        log(DEBUG)
        self._jsit().releaseTorrent(self)
        self._hash = None


    def removeDownloadLinks(self):
        log(INFO)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/links/delete.csp", params = {"info_hash" : self._hash})

        except Exception,e :
            log(ERROR, u"Caught exception %s removing download links for torrent %s!" % (e, self._name))

        



class JSIT(object):

    def __init__(self, username=None, password=None, apikey=None, nthreads = 0):

        
        self._name = "JSIT(%s)"% username
        self._lock = RWLock()
        
        self._connected = False
        self._disconnectTime = 0
        self._api_key = None
        
        # Torrents
        self._torrentsValidUntil = 0
        self._torrentsNewBS = None
        self._torrents = []
        self._dataRemaining = 0

        # General attributes
        self._labelsValidUntil = 0
        self._labelsNewBS = None
        self._labels = []

        # Torrent updates
        self._newTorrents = []
        self._deletedTorrents = []

        # Connect already?
        if username and password:     
            self._username = username
            self._password = password
            self.connect()
        elif apikey:
            self._api_key = apikey
            self.connect()            
        else:
            log(INFO, "Don't have username and password, not connecting.")
            
        # Async update thread
        self._nthreads = nthreads
        
        if self._nthreads > 0:
            log(DEBUG, "Starting Update threads.")
            
            self._updateQ = Queue.Queue( maxsize = 400) 
            self._quitEvent = threading.Event()
            self._newDelLock = threading.Lock()
            
            self._updateThreads = []
            
            for t in xrange(0, self._nthreads):
                    t = threading.Thread(target=self.updateThread, name="JSIT-Updater-%d" % t)
                    t.daemon = True
                    t.start()
                    self._updateThreads.append(t)        

    
    def __repr__(self):
        return "JSIT(0x%x)" % id(self)


    def __enter__(self):
        return self
         
    def __exit__(self, type, value, traceback):
        self.release()
   
   
    def release(self):
        log(DEBUG)
        # Kill updater thread
        if self._nthreads > 0:
            log(DEBUG, "Waiting for update threads...")
            self._quitEvent.set()
            for t in xrange(0, self._nthreads):
                self._updateQ.put((0,0,0,0,0))
                
            for t in xrange(0, self._nthreads):
                self._updateThreads[t].join()
                
            log(DEBUG, "Got update threads.")

        # Analyze stats
        l = []
        nc = 0
        tc = 0
        for k,v in apiStats.iteritems():
            l.append([k, v[0], v[1]])
            nc += v[0]
            tc += v[1]
        
        log(DEBUG, "API stats: called API %d times, taking %.02f secs" % (nc,tc))
        
        log(DEBUG, "Most used:")
        l.sort(key = lambda e: -e[1])
        for i in xrange(0, min(len(l), 20)):
            c = l[i]
            log(DEBUG, "   %s:\t%d calls" % (c[0], c[1]))
        
        log(DEBUG, "Most time:")
        l.sort(key = lambda e: -e[2])
        for i in xrange(0, min(len(l), 20)):
            c = l[i]
            log(DEBUG, "   %s:\t%.02f s in %d calls" % (c[0], c[2], c[1]))
        
        log(DEBUG, "Most expensive:")
        l.sort(key = lambda e: -e[2]/e[1])
        for i in xrange(0, min(len(l), 20)):
            c = l[i]
            log(DEBUG, "   %s:\t%.02f s/c in %d calls" % (c[0], c[2]/c[1], c[1]))


    def connected(self):
        return not self._session is None


    # Properties
    torrents        = property(lambda x: x.getUpdateValue("updateTorrents","_torrents"), None)
    dataRemaining   = property(lambda x: x.getUpdateValue("updateTorrents","_dataRemaining"), None)
    labels          = property(lambda x: x.getUpdateValue("updateLabels","_labels"), None)


    # Generic getter
    def getUpdateValue(self, updater, name):
        getattr(self, updater)()
        with self._lock.read_access:
            return self.__dict__[name]


    # Iterator access to torrent list
    def __iter__(self):
        self.updateTorrents()
        with self._lock.read_access:
            return self._torrents.__iter__()

    def __getitem__(self, index):
        self.updateTorrents()
        with self._lock.read_access:
            return self._torrents[index]

    def __len__(self):
        self.updateTorrents()
        with self._lock.read_access:
            return len(self._torrents)


    # Worker methods

    # Run async updates
    def updateThread(self):
        log(DEBUG, "Starting.")
        while not self._connected:
            log(DEBUG, "Waiting for connection...")
            time.sleep(0.5)

        # Run update queue
        while True:
            (tor, part, url, params, raw) = self._updateQ.get()

            if self._quitEvent.is_set():
                break

            if (isinstance(tor, Torrent) and not tor._hash) or not self.connected():
                continue # Torrent already destroyed or not connected, don't try to update

            log(DEBUG, "Updating %s for %s" % (part, tor))
            
            try:
                if not raw:
                    bs = issueAPIRequest(self, url, params = params)
                else:
                    r = self._jsit()._session.get(baseurl + url, verify=False)
                    r.raise_for_status()
                    bs = r.content

            except Exception,e :
                log(ERROR, u"Caught exception %s updating %s for torrent %s!" % (e, part, tor._name))
                log(ERROR, traceback.format_exc())
                bs = None
                 
            with self._lock.write_access:
                setattr(tor, "_" + part + "NewBS", bs)
            log(DEBUG2, "Got new data for %s of %s" % (part, tor))
        
        log(DEBUG, "Finished.")



    def connect(self, username = None, password = None, apikey = None):
        if username:
            self._username = username
        if password:
            self._password = password

        # Set up session

        self._session = requests.Session()
        # Adapter to increase retries
        ad = requests.adapters.HTTPAdapter() # Older requests version don't expose the constructor arg :(
        ad.max_retries=5
        self._session.mount('http://',  ad) 
        ad = requests.adapters.HTTPAdapter()
        ad.max_retries=5
        self._session.mount('https://', ad) 
        
        if self._api_key == None:
            log(DEBUG, u"Connecting to JSIT as %s" % self._username)
            try:
                params = { u"username" : self._username, u"password" : self._password}

                retries = 5
                while retries > 0:
                    try:
                        r = self._session.get(baseurl + "/v_login.csp", params=params, verify=False)
                        r.raise_for_status()
                        retries = -1
                    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError), e:
                        log(INFO, "Login failed due to %s, retrying..." % e)
                        time.sleep(retrySleep)
                        retries -= 1

                if retries == 0:
                    log(ERROR, "Couldn't connect to JSIT, aborting!")
                    sys.exit(1)

                self._connected = True

                text = urllib.unquote(r.content)
                if "status:FAILED" in text:
                    log(ERROR, u"Login to js.it failed (username/password correct?) (reason: %s)!" % text)
                    raise APIError("Login failed (%s)" % text.replace('\n', ' '))

                log(DEBUG, u"Connected to JSIT as %s" % self._username)

                r = self._session.get(baseurl + "/options/index.csp", verify=False)
                r.raise_for_status()

                text = urllib.unquote(r.content)
                bs = BeautifulSoup(text)

                f = bs.find(id="api_key")

                if not f or f["value"] == "":
                    log(ERROR, u"Couldn't find api_key. Please enable API at http://justseed.it/options/index.csp!")
                    sys.exit(1)

                self._api_key = f["value"]
                log(DEBUG, u"Found API key %s" % self._api_key)

            except APIError,e :
                log(ERROR, u"Caught exception %s connecting to js.it!" % (e))
                raise e

        self._connected = True
        self._disconnectTime = 0
        apiSucceeded(self)

            
    def disconnect(self):
        if self._session is None:
            log(INFO, "Already closed connection.")
            return
        log(WARNING, "Disconnecting from JSIT.")
        self._session.close()
        self._session = None
        self._disconnectTime = time.time()
        self._connected = False
   
    def isConnected(self):
        return self._connected

    def tryReconnect(self):
        now = time.time()
        if self._disconnectTime + reconnectTime > now:
           log(DEBUG, "%.0f secs to reconnect..." % (self._disconnectTime + reconnectTime - now))
           return True

        self.connect()
        return False


    def findTorrents(self, search):
        sre = re.compile(search)

        ret = []
        for t in self.torrents:
            if sre.search(t.name):
                ret.append(t)

        return ret


    def lookupTorrent(self, hash):
        for t in self.torrents:
            if t.hash == hash:
                return t

        return None


    def updateTorrents(self, force = False):
        """Update all torrents. More efficient than one by one, also catches new/deleted torrents"""

        if not self.connected():
            log(DEBUG, "Not connected, skipping.")
            return
    
        bs = updateBase(self, self, "torrents", "/torrents/list.csp", force = force)

        # No update needed or none received yet?
        if bs == None:
            return

        with self._lock.write_access:

            deleted = [ t._hash for t in self._torrents if t._hash != None ]
            new = []
            foundt = []

            self._dataRemaining = int(bs.find("data_remaining_as_bytes").text)

            fieldmap = { "auto_download_pieces" : "_auto_download_pieces",
                         "auto_generate_links" : "_auto_generate_links",
                         "auto_generate_tar_links" : "_auto_generate_tar_links",
                         "data_rate_in_as_bytes" : "_data_rate_in",
                         "data_rate_out_as_bytes" : "_data_rate_out",
                         "downloaded_as_bytes" : "_downloaded",
                         "elapsed_as_seconds" : "_elapsed",
                         "label" : "_label",
                         "maximum_ratio_as_decimal" : "_maximum_ratio",
                         "name" : "_name",
                         "percentage_as_decimal" : "_percentage",
                         "size_as_bytes" : "_size",
                         "status" : "_status",
                         "uploaded_as_bytes" : "_uploaded",
                         "completion_as_seconds" : "_completion"
            }

            now = time.time()            

            for r in bs.iter("row"):

                hash_ = unicode(r.find("info_hash").text)

                # Can't use lookupTorrent here, infinite loop
                found = None
                for t in self._torrents:
                    if t._hash == hash_:
                        found = t
                        break
                
                if not found:
                    t = Torrent(self, hash_ = hash_)
                    self._torrents.append(t)
                    new.append(hash_)
                else:
                    deleted.remove(hash_)
                    foundt.append(hash_)
                    t = found


                fillFromXML(t, r, fieldmap)
                t.cleanupFields()

                t._listValidUntil = now + listValidityLength


            for d in deleted:
                for t in self._torrents:
                    if t.hash == d:
                        break
                t._hash = None # Mark as deleted
                t._status = "deleted"
                ## self._torrents.remove(t) # Keep them in list for status display

            log(DEBUG2, "Torrent list now: %s" % self._torrents)

            self._torrentsValidUntil = now + listValidityLength

            self._newTorrents     += new
            self._deletedTorrents += deleted


            if logCheck(DEBUG): 
                log(DEBUG, "QQQ: New=%s Deleted=%s Foundt=%s" % (new, deleted, foundt));
                msg = ""
                if self._nthreads > 0:
                    msg += "UpdateQ:%d " % (self._updateQ.qsize())

                msg += "New(%d): " % len(new) + ','.join(new) + " Deleted(%d): " % len(deleted) + ','.join(deleted) + \
                      " Kept(%d): " % len(foundt) + ','.join(foundt)
                log(DEBUG, msg)



    def resetNewDeleted(self):
    
        log(DEBUG,"jsit::resetNewDeleted: new: %s deleted: %s" % (self._newTorrents, self._deletedTorrents))

        with self._lock.write_access:

            n = self._newTorrents
            d = self._deletedTorrents

            # Remove torrents from new that have already been deleted
            for t in d:
                if t in n:
                    n.remove(t)

            self._newTorrents = []
            self._deletedTorrents = []

            return n,d



    def updateLabels(self, force = False):
    
        bs = updateBase(self, self, "labels", "/labels/list.csp", force = force)

        # No update needed or none received yet?
        if bs == None:
             return

        labels = []

        for n in bs.find("data").findall("row"):
            l = urllib.unquote(str(n[0].text)).decode('utf-8')
            labels.append(l)

        with self._lock.write_access:

            self._labels = labels
            self._labelsValidUntil = time.time() + labelValidityLength



    # Torrent adding

    def _doAddTorrent(self, files, params, maximum_ratio):
        try:
            if params is None:
                params = {}

            if maximum_ratio != None:
                params["maximum_ratio"] = maximum_ratio

            try:
                bs = issueAPIRequest(self, "/torrent/add.csp", files = files, params = params)
                hash = unicode(bs.find("info_hash").text)
            except APIError, e:
                if "You're already running a torrent for this info hash" in e.msg:
                    log(INFO, u"Torrent (files=%s, params=%s!) already running!" % (files, params))
                    
                    h = e.msg.find("info_hash=")
                    if h < 0:
                        raise e
                        
                    hash = e.msg[h+10:h+50]
                else:
                    log(DEBUG, u"Caught response %s, raising." % e)
                    raise e

            log(DEBUG, u"New torrent has hash %s." % hash)

            # Wait for up to 20 seconds for the torrent to show up
            t = self.lookupTorrent(hash)
            now = time.time()
            w = 0.3
            while not t and time.time() < now + 20:
                time.sleep(w)
                w += 1
                self.updateTorrents(force = True)
                t = self.lookupTorrent(hash)

            if t:
                return t

            log(ERROR, u"Torrent failed to upload (files=%s, params=%s)!" % (files, params))

        except APIError,e :
            log(ERROR, u"Caught exception %s trying to upload torrent %s/%s!" % (e, params, files))

        return None



    def addTorrentFile(self, fname, maximum_ratio = None):
        log(DEBUG)

        files = { u"torrent_file" : open(fname, "rb") }

        return self._doAddTorrent(files, None, maximum_ratio)


    def addTorrentURL(self, url, maximum_ratio = None):
        log(DEBUG)

        params = { u"url" : url }

        return self._doAddTorrent(None, params, maximum_ratio)


    def deleteTorrent(self, tor):
        if isinstance(tor, str):
            tor = self.lookupTorrent(tor)
            
        log(DEBUG)

        with self._lock.write_access:

            try:
                bs = issueAPIRequest(self, "/torrent/delete.csp", params = {"info_hash" : tor._hash})

                self._deletedTorrents.append(tor._hash)

                for i,t in enumerate(self._torrents):
                    if t._hash == tor._hash:
                        t.status = "deleted"
                        #self._torrents.pop(i)
                        break

            except Exception,e :
                log(ERROR, u"Caught exception %s deleting torrent %s!" % (e, tor._name))


    def releaseTorrent(self, tor):
        if isinstance(tor, str):
            tor = self.lookupTorrent(tor)
            
        log(DEBUG)

        with self._lock.write_access:

            for i,t in enumerate(self._torrents):
                if t._hash == tor._hash:
                    t.status = "deleted"
                    #self._torrents.pop(i)
                    break
