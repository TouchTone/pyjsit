#! /usr/bin/python

## Python interface to access justseed.it data to support automation applications


import requests, urllib, time, sys, re, weakref, threading, Queue
from copy import copy
from bs4 import BeautifulSoup

from log import *
from tools import *


baseurl="https://justseed.it"
apibaseurl="https://api.justseed.it"

infoValidityLength = 30
dataValidityLength = 120
listValidityLength = 30
fileValidityLength = 86400
trackerValidityLength = 300
peerValidityLength = 600
labelValidityLength = 300
torrentValidityLength = 86400
piecesValidityLength = 86400


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

# Issue API request and check status for success. Return BeautifulSoup handle for content

def issueAPIRequest(jsit, url, params = None, files = None):

    if params is None:
        p = {}
    else:
        p = copy(params)

    p["api_key"] = jsit._api_key

    log(DEBUG2, "issueAPIRequest: Calling %s (params=%s, files=%s)"% (apibaseurl + url, p, files))
    
    start = time.time()
    try:
        r = jsit._session.get(apibaseurl + url, params = p, files = files, verify=False, timeout = 120)    
        log(DEBUG3, "issueAPIRequest: Got %r" % r.content)
    except requests.exceptions.Timeout, e:
        log(WARNING, "API request '%s' (params = %s, files = %s) timed out!" % (url, params, files))
        raise APIError("%s (params=%s, files=%s) failed: timeout!"% (url, params, files))
        
    end = time.time()
    
    # Keep stats
    try:
        s = apiStats[url]
        ns = (s[0] + 1, s[1] + (end-start))
        apiStats[url] = ns
    except KeyError:
        apiStats[url] = (1, end-start)
        
    r.raise_for_status()
    
    bs = BeautifulSoup(r.content, features="xml")
    
    log(DEBUG3, "issueAPIRequest: bs %r" % bs)

    status = bs.find("status")
    log(DEBUG2, "status=%s" % status)
    
    if not status:
        raise APIError("%s protocol failure!"% url)
        
    if status.text != "SUCCESS":
        m = bs.find("message")
        h = bs.find("info_hash")
        if h and m:
            raise APIError("%s failed: %s (info_hash=%s)!"% (url, unicode(urllib.unquote(m.string)), unicode(urllib.unquote(h.string))))
        elif m:
            raise APIError("%s failed: %s!"% (url, unicode(urllib.unquote(m.string))))
        else:
            raise APIError("%s failed!"% url)

    return bs


# Convert types of given fields from string to desired type

def cleanupFields(obj, floatfields = None, intfields = None, boolfields = None):

    if floatfields:
        for f in floatfields:
            if isinstance(obj.__dict__[f], float) or obj.__dict__[f] is None:
                continue
            if obj.__dict__[f] == "" or obj.__dict__[f] == "unknown":
                obj.__dict__[f] = 0.
                continue
            try:
                obj.__dict__[f] = float(obj.__dict__[f])
            except ValueError:
                log(ERROR, "can't convert '%s' to float for field %s!" % (obj.__dict__[f], f))

    if intfields:
        for f in intfields:
            if isinstance(obj.__dict__[f], int) or obj.__dict__[f] is None:
                continue
            if obj.__dict__[f] == "" or obj.__dict__[f] == "unknown":
                obj.__dict__[f] = 0
                continue
            try:
                obj.__dict__[f] = int(obj.__dict__[f])
            except ValueError:
                log(ERROR, "can't convert '%s' to int for field %s!" % (obj.__dict__[f], f))

    if boolfields:
        for f in boolfields:
            if isinstance(obj.__dict__[f], bool) or obj.__dict__[f] is None:
                continue
            if obj.__dict__[f] == "" or obj.__dict__[f] == "unknown":
                obj.__dict__[f] = None
                continue
            try:
                if obj.__dict__[f] in ["True", "true", "1", "Yes", "yes"]:
                    obj.__dict__[f] = True
                elif obj.__dict__[f] in ["False", "false", "0", "No", "no"]:
                    obj.__dict__[f] = False
                else:
                    log(ERROR, "can't convert '%s' to bool for field %s!" % (obj.__dict__[f], f))
            except ValueError:
                log(ERROR, "can't convert '%s' to bool for field %s!" % (obj.__dict__[f], f))


# Fill object fields from XML response

def fillFromXML(obj, root, fieldmap, exclude_unquote = []):

    for tag in root.children:
        if tag == "\n":
            continue
        try:
            if tag.string == None:
                s = None
            elif tag.name in exclude_unquote:
                s = unicode(tag.string)
            else:
                try:
                    s = unicode_cleanup(urllib.unquote(str(tag.string)).decode('utf-8'))
                except (IOError, UnicodeEncodeError, UnicodeDecodeError), e:
                    log(INFO, "fillFromXML: caught %s decoding response for %s, keeping as raw %r." % (e, tag, tag.string))
                    s = tag.string
            
            obj.__dict__[fieldmap[tag.name]] = s
            
        except KeyError:
            pass


    

# Update methods boiler plate code
def updateBase(jsit, obj, part, url, params = {}, force = False, raw = False, static = False):

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
    if force or not jsit._nthreads > 0 or (jsit._nthreads > 0 and getattr(obj, "_" + part + "ValidUntil") == 0):
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
            bs = None
            
    else:
        if nbs == None:
            setattr(obj, "_" + part + "NewBS", "Pending")
            jsit._updateQ.put((obj, part, url, params, raw))
            log(DEBUG, "Submit update request.")

        return None


    return bs



# Part classes for torrent info

class TFile(object):

    def __init__(self, torrent):

        self._torrent = weakref.ref(torrent)

        self.end_piece = 0
        self.end_piece_offset = 0
        self.path = u""
        self.size = 0
        self.start_piece = 0
        self.start_piece_offset = 0
        self.torrent_offset = 0
        self.total_downloaded = 0
        self.url = None

    def __repr__(self):
        r = "TFile(%r (%r)"% (self.path, self.size)
        if self.url:
            r += "U"
        r += ")"
        return r


    def cleanupFields(self):
        cleanupFields(self, intfields = ["end_piece", "end_piece_offset", "size", "start_piece", "start_piece_offset",
                                         "torrent_offset", "total_downloaded"])


    def write(self, fname, piece, data, size):
        if piece.number == self.start_piece:
            seek = 0
            start = self.start_piece_offset
        else:
            log(DEBUG2, "piece.number=%s(%s) self.start_piece=%s(%s) self._torrent().piece_size=%s(%s) self.start_piece_offset=%s(%s)" %
                    (piece.number, type(piece.number), piece.number, type(piece.number), 
                    self._torrent().piece_size, type(self._torrent().piece_size), self.start_piece_offset, type(self.start_piece_offset)))
                    
            seek = (piece.number - self.start_piece) * self._torrent().piece_size - self.start_piece_offset
            start = 0
        
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
                log(WARNING, "Caught %s"% e)
            
        log(DEBUG2, "PN=%d SP=%d seek=%d start=%d len=%d" % (piece.number, self.start_piece, seek, start, len(data[start:start + size])))

        f.seek(seek)
        f.write(data[start:start + size])
        f.close()
        

class TTracker(object):

    def __init__(self, torrent):

        self._torrent = weakref.ref(torrent)

        self.downloaded = 0
        self.interval = 0
        self.last_announce = u""
        self.leechers = 0
        self.seeders = 0
        self.peers = 0
        self.url = u""
        self.message = None

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
        self.url = ""

        
    def __repr__(self):
        return "TPiece(%r %r (%r))"% (self._torrent, self.number, self.size)


    def cleanupFields(self):
        cleanupFields(self, intfields = ["number", "size"])



# Base JS.it torrent class

class Torrent(object):

    def __init__(self, jsit, hash_ = None):
        
        # Set up attributes
        self._jsit = weakref.ref(jsit)
        self._hash = hash_

        # Info data
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
        self._retention = 0
        self._ttl = 0
        self._etc = 0
        self._ratio = 0

        self._infoValidUntil = 0
        self._infoNewBS = None
        self._maximum_ratio = 0
        self._private = False
        self._completed_announced = False
        self._ip_address = ""
        self._ip_port = ""
        self._magnet_link = ""
        self._piece_size = 0
        self._npieces = 0
        self._total_files = 0

        # Files data
        self._filesValidUntil = 0
        self._filesNewBS = None
        self._files = []

        # Trackers data
        self._trackersValidUntil = 0
        self._trackersNewBS = None
        self._trackers = []

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

            self._label = label

        except Exception,e :
            log(ERROR, u"Caught exception %s setting label!" % (e))


    def set_maximum_ratio(self, ratio):
        log(DEBUG, "Setting maximum ratio for %s (%s) to %s" % (self._name, self._hash, ratio))

        if self._maximum_ratio == ratio:
            return

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/set_maximum_ratio.csp", params = { u"info_hash" : self._hash, u"maximum_ratio": ratio })

            self._maximum_ratio = ratio

        except Exception,e :
            log(ERROR, u"Caught exception %s setting maximum ratio!" % (e))




    # Set up properties for attributes
    hash                    = property(lambda x: x.getStaticValue ("updateList", "_hash"),                   None)
    name                    = property(lambda x: x.getStaticValue ("updateList", "_name"),                   set_name)
    label                   = property(lambda x: x.getDynamicValue("updateList", "_label"),                  set_label)
    status                  = property(lambda x: x.getDynamicValue("updateList", "_status"),                 None)
    percentage              = property(lambda x: x.getDynamicValue("updateList", "_percentage"),             None)
    size                    = property(lambda x: x.getStaticValue ("updateList", "_size"),                   None)
    downloaded              = property(lambda x: x.getDynamicValue("updateList", "_downloaded"),             None)
    uploaded                = property(lambda x: x.getDynamicValue("updateList", "_uploaded"),               None)
    ratio                   = property(lambda x: x.getDynamicValue("updateList", "_ratio"),                  None)
    data_rate_in            = property(lambda x: x.getDynamicValue("updateList", "_data_rate_in"),           None)
    data_rate_out           = property(lambda x: x.getDynamicValue("updateList", "_data_rate_out"),          None)
    elapsed                 = property(lambda x: x.getDynamicValue("updateList", "_elapsed"),                None)
    retenion                = property(lambda x: x.getDynamicValue("updateList", "_retention"),              None)
    ttl                     = property(lambda x: x.getDynamicValue("updateList", "_ttl"),                    None)
    etc                     = property(lambda x: x.getDynamicValue("updateList", "_etc"),                    None)

    ratio                   = property(lambda x: x.getDynamicValue("updateInfo", "_ratio"),                  None)
    maximum_ratio           = property(lambda x: x.getDynamicValue("updateInfo", "_maximum_ratio"),          set_maximum_ratio)
    npieces                 = property(lambda x: x.getStaticValue ("updateInfo", "_npieces"),                None)
    private                 = property(lambda x: x.getStaticValue ("updateInfo", "_private"),                None)
    completed_announced     = property(lambda x: x.getDynamicValue("updateInfo", "_completed_announced"),    None)
    ip_address              = property(lambda x: x.getStaticValue ("updateInfo", "_ip_address"),             None)
    ip_port                 = property(lambda x: x.getStaticValue ("updateInfo", "_ip_port"),                None)
    magnet_link             = property(lambda x: x.getStaticValue ("updateInfo", "_magnet_link"),            None)
    piece_size              = property(lambda x: x.getStaticValue ("updateInfo", "_piece_size"),             None)
    total_files             = property(lambda x: x.getStaticValue ("updateInfo", "_total_files"),            None)

    files                   = property(lambda x: x.getStaticValue ("updateFiles","_files"),                  None)
    trackers                = property(lambda x: x.getDynamicValue("updateTrackers","_trackers"),            None)
    peers                   = property(lambda x: x.getDynamicValue("updatePeers","_peers"),                  None)
    bitfield                = property(lambda x: x.getDynamicValue("updateBitfield","_bitfield"),            None)
    torrent                 = property(lambda x: x.getStaticValue ("updateTorrent","_torrent"),              None)
    pieces                  = property(lambda x: x.getStaticValue ("updatePieces","_pieces"),                None)

    # Other, indirect properties

    @property
    def hasFinished(self):
        return self.percentage == 100



    # Generic getters

    def getDynamicValue(self, updater, name):        
        getattr(self, updater)(static = False)
        return self.__dict__[name]

    def getStaticValue(self, updater, name):        
        getattr(self, updater)(static = True)
        return self.__dict__[name]


    # Updater methods    

    # List elements are set from jsit.updateTorrents and from updateInfo
    # Just forward to updateInfo
    def updateList(self, force = False, static = False):
        if time.time() < self._listValidUntil and not force:
            return
        self.updateInfo(force, static)


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

        fillFromXML(self, bs.find("data"), fieldmap)

        self.cleanupFields()

        # Derived values
        try:
            if self._percentage == 100:
                self._etc = 0
            else:
                self._etc = (self._size - self._downloaded) / self._data_rate_in
        except Exception,e :
            self._etc = 0
        
        self._infoValidUntil = time.time() + infoValidityLength
        self._listValidUntil = time.time() + listValidityLength



    def updateFiles(self, force = False, static = False):    
        bs = updateBase(self._jsit(), self, "files", "/torrent/files.csp", params = {"info_hash" : self._hash}, force = force, static = static)

        # No update needed or none received yet?
        if bs == None:
             return
             
        # Do we have links?
        r1 = bs.find("row")
        if r1 and self.percentage == 100 and r1.find("url").string == None:
            # Triger link gen
            log(DEBUG, u"Generating download links for %s (%s)..." % (self._name, self._hash))

            params = { u"info_hash" : self._hash, u"reinstate" : "false"}
            r = self._jsit()._session.get(baseurl + "/torrents/v_create_torrent_file_download_links.csp", params = params, verify=False)
            r.raise_for_status()

            # Re-read list
            bs = issueAPIRequest(self._jsit(), "/torrent/files.csp", params = {"info_hash" : self._hash})


        fieldmap = { "end_piece" : "end_piece",
                     "end_piece_offset" : "end_piece_offset",
                     "path" : "path",
                     "percentage_as_decimal" : "percentage",
                     "size_as_bytes" : "size",
                     "start_piece" : "start_piece",
                     "start_piece_offset" : "start_piece_offset",
                     "torrent_offset" : "torrent_offset",
                     "total_downloaded_as_bytes" : "total_downloaded",
                     "url" : "url" }

        self._files = []

        for r in bs.find_all("row"):

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

        self._trackers = []

        for r in bs.find_all("row"):

            t = TTracker(self)
            fillFromXML(t, r, fieldmap)
            t.cleanupFields()

            self._trackers.append(t)

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

        for r in bs.find_all("row"):

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

        bf = bs.find("bitfield")

        self._bitfield = str(bf.string)

        self._bitfieldValidUntil = time.time() + infoValidityLength


    def updateTorrent(self, force = False, static = False):
        data = updateBase(self._jsit(), self, "torrent", "/torrents/torrent_file.csp?info_hash=%s" % self.hash, params = {}, force = force, static = static, raw = True)

        # No update needed or none received yet?
        if data == None:
             return

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
                    "url" : "url"
                    }

        self._pieces = []

        for r in bs.find_all("row"):

            t = TPiece(self)
            fillFromXML(t, r, fieldmap)
            t.cleanupFields()

            self._pieces.append(t)

        self._piecesValidUntil = time.time() + piecesValidityLength



    def cleanupFields(self):
        cleanupFields(self, floatfields = ["_percentage", "_ratio", "_maximum_ratio"],
                            intfields = ["_total_files", "_size", "_downloaded", "_uploaded", "_data_rate_in", "_data_rate_out",
                                         "_npieces", "_ip_port", "_piece_size", "_elapsed", "_retention" ],
                            boolfields = ["_private", "_completed_announced"])
        
        # Derived fields
        
        if self._downloaded > 0:
            self._ratio = self._uploaded / float(self._downloaded)
        else:
            self._ratio = 0
        
        if self._retention == 0:
            self._ttl = 0
        else:
            self._ttl = self._retention - self._elapsed


    def start(self):
        log(DEBUG)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/start.csp", params = {"info_hash" : self._hash})

            self._status = "running"

        except Exception,e :
            log(ERROR, u"Caught exception %s starting torrent %s!" % (e, self._name))


    def stop(self):
        log(INFO)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/stop.csp", params = {"info_hash" : self._hash})

            self._status = "stopped"

        except Exception,e :
            log(ERROR, u"Caught exception %s stopping torrent %s!" % (e, self._name))


    def delete(self):
        log(INFO)
        self._jsit().deleteTorrent(self)


    def release(self):
        log(DEBUG)
        self._jsit().releaseTorrent(self)
        self._hash = None



class JSIT(object):

    def __init__(self, username, password, nthreads = 0):

        log(DEBUG)

        self._session = requests.Session()
        # Adapter to increase retries
        ad = requests.adapters.HTTPAdapter() # Older requests version don't expose the constructor arg :(
        ad.max_retries=5
        self._session.mount('http://',  ad) 
        ad = requests.adapters.HTTPAdapter()
        ad.max_retries=5
        self._session.mount('https://', ad) 
        
        self._connected = False
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


    # Properties
    torrents        = property(lambda x: x.getUpdateValue("updateTorrents","_torrents"), None)
    dataRemaining   = property(lambda x: x.getUpdateValue("updateTorrents","_dataRemaining"), None)
    labels          = property(lambda x: x.getUpdateValue("updateLabels","_labels"), None)


    # Generic getter
    def getUpdateValue(self, updater, name):
        getattr(self, updater)()
        return self.__dict__[name]


    # Iterator access to torrent list
    def __iter__(self):
        self.updateTorrents()
        return self._torrents.__iter__()

    def __getitem__(self, index):
        self.updateTorrents()
        return self._torrents[index]

    def __len__(self):
        self.updateTorrents()
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

            if isinstance(tor, Torrent) and not tor._hash:
                continue # Torrent already destroyed, don't try to update

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
                bs = None

            setattr(tor, "_" + part + "NewBS", bs)
        
        log(DEBUG, "Finished.")



    def connect(self, username = None, password = None):
        if username:
            self._username = username
        if password:
            self._password = password
            
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
                    retries -= 1
            
            if retries == 0:
                log(ERROR, "Couldn't connect to JSIT, aborting!")
                sys.exit(1)
                
            self._connected = True
            
            text = urllib.unquote(r.content)
            if "status:FAILED" in text:
                log(ERROR, u"Login to js.it failed (username/password correct?)!")
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
    
        bs = updateBase(self, self, "torrents", "/torrents/list.csp", force = force)

        # No update needed or none received yet?
        if bs == None:
            return

        deleted = [ t._hash for t in self._torrents ]
        new = []
        foundt = []

        self._dataRemaining = int(bs.find("data_remaining_as_bytes").string)

        fieldmap = { "data_rate_in_as_bytes" : "_data_rate_in",
                     "data_rate_out_as_bytes" : "_data_rate_out",
                     "downloaded_as_bytes" : "_downloaded",
                     "elapsed_as_seconds" : "_elapsed",
                     "server_retention_as_seconds" : "_retention",
                     "label" : "_label",
                     "name" : "_name",
                     "percentage_as_decimal" : "_percentage",
                     "size_as_bytes" : "_size",
                     "status" : "_status",
                     "uploaded_as_bytes" : "_uploaded"   }

        now = time.time()            

        for r in bs.find_all("row"):

            hash_ = unicode(r.find("info_hash").string)

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

            for tag in r.children:

                if tag == "\n":
                    continue

                try:
                    if tag.string == None:
                        t.__dict__[fieldmap[tag.name]] = ""
                    else:
                        s = str(tag.string) # Can't turn into unicode here, or unquote().decode() will mess up
                        t.__dict__[fieldmap[tag.name]] = unicode_cleanup(urllib.unquote(s).decode('utf-8'))
                except KeyError:
                    pass
                except IOError,e: ##UnicodeEncodeError, e:
                    log(ERROR, "Caught unicode encode error %s trying to decode %r for %s" % (e, tag.string, tag.name))
                    t.__dict__[fieldmap[tag.name]] = "ERROR DECODING"

            t.cleanupFields()

            t._listValidUntil = now + listValidityLength
            
            if self._nthreads > 0:
                # Queue an update request for info, we will most likely need it anyway           
                self._updateQ.put((t, "info", "/torrent/information.csp", { "info_hash" : hash_ }, False))
 

        for d in deleted:
            for t in self._torrents:
                if t.hash == d:
                    break
            t._hash = None # Mark as deleted
            self._torrents.remove(t)

        if logCheck(DEBUG): 
            msg = ""
            if self._nthreads > 0:
                msg += "UpdateQ:%d " % (self._updateQ.qsize())
                
            msg += "New(%d): " % len(new) + ','.join(new) + " Deleted(%d): " % len(deleted) + ','.join(deleted) + \
                  " Kept(%d): " % len(foundt) + ','.join(foundt)
            log(DEBUG, msg)

        log(DEBUG2, "Torrent list now: %s" % self._torrents)

        self._torrentsValidUntil = now + listValidityLength

        if self._nthreads > 0:
            self._newDelLock.acquire()

        self._newTorrents     += new
        self._deletedTorrents += deleted

        if self._nthreads > 0:
            self._newDelLock.release()



    def resetNewDeleted(self):
    
        log(DEBUG,"jsit::resetNewDeleted: new: %s deleted: %s" % (self._newTorrents, self._deletedTorrents))

        if self._nthreads > 0:
            self._newDelLock.acquire()

        n = self._newTorrents
        d = self._deletedTorrents
        
        # Remove torrents from new that have already been deleted
        for t in d:
            if t in n:
                n.remove(t)
        
        self._newTorrents = []
        self._deletedTorrents = []

        if self._nthreads > 0:
            self._newDelLock.release()

        return n,d



    def updateLabels(self, force = False):
    
        bs = updateBase(self, self, "labels", "/labels/list.csp", force = force)

        # No update needed or none received yet?
        if bs == None:
             return

        labels = []

        for tag in bs.find_all("label"):
            l = urllib.unquote(str(tag.string)).decode('utf-8')
            labels.append(l)

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
                hash = unicode(bs.find("info_hash").string)
            except APIError, e:
                if "You're already running a torrent for this info hash" in e.msg:
                    log(INFO, u"Torrent (files=%s, params=%s!) already running!" % (params, files))
                    
                    h = e.msg.find("info_hash=")
                    if h < 0:
                        raise e
                        
                    hash = e.msg[h+10:h+50]
                else:
                    raise e

            log(DEBUG, u"New torrent has hash %s." % hash)

            # Wait for up to 5 seconds for the torrent to show up
            t = self.lookupTorrent(hash)
            now = time.time()
            while not t and time.time() < now + 5:
                time.sleep(0.3)
                self.updateTorrents(force = True)
                t = self.lookupTorrent(hash)

            if t:
                return t

            log(ERROR, u"Torrent failed to upload (files=%s, params=%s)!" % (params, files))

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
            
        log(INFO)

        try:
            bs = issueAPIRequest(self, "/torrent/delete.csp", params = {"info_hash" : tor._hash})

            self._deletedTorrents.append(tor._hash)
            
            for i,t in enumerate(self._torrents):
                if t._hash == tor._hash:
                    self._torrents.pop(i)
                    break

        except Exception,e :
            log(ERROR, u"Caught exception %s deleting torrent %s!" % (e, tor._name))


    def releaseTorrent(self, tor):
        if isinstance(tor, str):
            tor = self.lookupTorrent(tor)
            
        log(DEBUG)

        for i,t in enumerate(self._torrents):
            if t._hash == tor._hash:
                self._torrents.pop(i)
                break
