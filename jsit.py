#! /usr/bin/python

## Python interface to access justseed.it data to support automation applications


import requests, urllib, time, sys, re, weakref
from copy import copy
from bs4 import BeautifulSoup

from log import *
from tools import *


baseurl="https://justseed.it"
apibaseurl="https://api.justseed.it"

infoValidityLength = 10
dataValidityLength = 120
listValidityLength = 10
fileValidityLength = 3600
trackerValidityLength = 300
peerValidityLength = 30
labelValidityLength = 300
torrentValidityLength = 3600


# Exceptions

class APIError(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


# Helper functions

# Issue API request and check status for success. Return BeautifulSoup handle for content

def issueAPIRequest(jsit, url, params = None, files = None):

    if params is None:
        p = {}
    else:
        p = copy(params)

    p["api_key"] = jsit._api_key

    log(DEBUG2, "issueAPIRequest: Calling %s (params=%s, files=%s)\n"% (apibaseurl + url, p, files))
    
    r = jsit._session.get(apibaseurl + url, params = p, files = files, verify=False)    
    log(DEBUG2, "issueAPIRequest: Got %r\n" % r.content)    
    r.raise_for_status()
    
    bs = BeautifulSoup(r.content, features="xml")
    
    log(DEBUG2, "issueAPIRequest: bs %r\n" % bs)

    status = bs.find("status")
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
                log(ERROR, "can't convert '%s' to float for field %s!\n" % (obj.__dict__[f], f))

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
                log(ERROR, "can't convert '%s' to int for field %s!\n" % (obj.__dict__[f], f))

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
                    log(ERROR, "can't convert '%s' to bool for field %s!\n" % (obj.__dict__[f], f))
            except ValueError:
                log(ERROR, "can't convert '%s' to bool for field %s!\n" % (obj.__dict__[f], f))


# Fill object fields from XML response

def fillFromXML(obj, root, fieldmap, exclude_unquote = []):

    for tag in root.children:
        if tag == "\n":
            continue
        try:
            if tag.string == None:
                obj.__dict__[fieldmap[tag.name]] = None
            elif tag.name in exclude_unquote:
                obj.__dict__[fieldmap[tag.name]] = unicode(tag.string)
            else:
                try:
                    s = unicode_cleanup(urllib.unquote(tag.string)).decode('utf-8')
                    obj.__dict__[fieldmap[tag.name]] = s
                except IOError, UnicodeEncodeError:
                    log(INFO, "fillFromXML: got undecodable response %r, keeping as raw %r.\n" % (s, tag.string))
                    obj.__dict__[fieldmap[tag.name]] = s
        except KeyError:
            pass




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
                                         "torrent_offset", "total_downloaded"], floatfields = ["percentage"])


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



# Base JS.it torrent class

class Torrent(object):

    def __init__(self, jsit, hash_ = None):
        
        # Set up attributes
        self._jsit = weakref.ref(jsit)
        self._hash = hash_

        # Info data
        self._listValidUntil = 0
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
        self._ratio = 0

        self._infoValidUntil = 0
        self._maximum_ratio = 0
        self._pieces = ""
        self._private = False
        self._elapsed = ""
        self._completed_announced = False
        self._ip_address = ""
        self._ip_port = ""
        self._magnet_link = ""
        self._piece_size = 0
        self._pieces = 0
        self._total_files = 0

        # Files data
        self._filesValidUntil = 0
        self._files = []

        # Trackers data
        self._trackersValidUntil = 0
        self._trackers = []

        # Peers data
        self._peersValidUntil = 0
        self._peers = []

        # Bitfield data
        self._bitfieldValidUntil = 0
        self._bitfield = ""

        # Torrent data
        self._torrentValidUntil = 0
        self._torrent = ""

        log(DEBUG)

    def __repr__(self):
        return "Torrent(%r (%r))"% (self._name, self._hash)


    # Setters

    def set_name(self, name):
        log(DEBUG, "Setting name for %s (%s) to %s\n" % (self._name, self._hash, name))

        if self._name == name:
            return

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/set_name.csp", params = { u"info_hash" : self._hash, u"name": name })

            self._name = name

        except Exception,e :
            log(ERROR, u"Caught exception %s setting name!\n" % (e))


    def set_label(self, label):
        log(DEBUG, "Setting label for %s (%s) from %s to %s\n" % (self._name, self._hash, self._label, label))

        if self._label == label:
            return

        try:
            params = { u"info_hash" : self._hash}
            if label:
                params[u"label"] = label 
                
            bs = issueAPIRequest(self._jsit(), "/torrent/set_label.csp", params=params)

            self._label = label

        except Exception,e :
            log(ERROR, u"Caught exception %s setting label!\n" % (e))


    def set_maximum_ratio(self, ratio):
        log(DEBUG, "Setting maximum ratio for %s (%s) to %s\n" % (self._name, self._hash, ratio))

        if self._maximum_ratio == ratio:
            return

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/set_maximum_ratio.csp", params = { u"info_hash" : self._hash, u"maximum_ratio": ratio })

            self._maximum_ratio = ratio

        except Exception,e :
            log(ERROR, u"Caught exception %s setting maximum ratio!\n" % (e))




    # Set up properties for attributes
    hash                    = property(lambda x: x.getUpdateValue("updateList", "_hash"),                   None)
    name                    = property(lambda x: x.getUpdateValue("updateList", "_name"),                   set_name)
    label                   = property(lambda x: x.getUpdateValue("updateList", "_label"),                  set_label)
    status                  = property(lambda x: x.getUpdateValue("updateList", "_status"),                 None)
    percentage              = property(lambda x: x.getUpdateValue("updateList", "_percentage"),             None)
    size                    = property(lambda x: x.getUpdateValue("updateList", "_size"),                   None)
    downloaded              = property(lambda x: x.getUpdateValue("updateList", "_downloaded"),             None)
    uploaded                = property(lambda x: x.getUpdateValue("updateList", "_uploaded"),               None)
    ratio                   = property(lambda x: x.getUpdateValue("updateList", "_ratio"),                  None)
    data_rate_in            = property(lambda x: x.getUpdateValue("updateList", "_data_rate_in"),           None)
    data_rate_out           = property(lambda x: x.getUpdateValue("updateList", "_data_rate_out"),          None)
    elapsed                 = property(lambda x: x.getUpdateValue("updateList", "_elapsed"),                None)

    ratio                   = property(lambda x: x.getUpdateValue("updateInfo", "_ratio"),                  None)
    maximum_ratio           = property(lambda x: x.getUpdateValue("updateInfo", "_maximum_ratio"),          set_maximum_ratio)
    pieces                  = property(lambda x: x.getUpdateValue("updateInfo", "_pieces"),                 None)
    private                 = property(lambda x: x.getUpdateValue("updateInfo", "_private"),                None)
    elapsed                 = property(lambda x: x.getUpdateValue("updateInfo", "_elapsed"),                None)
    completed_announced     = property(lambda x: x.getUpdateValue("updateInfo", "_completed_announced"),    None)
    ip_address              = property(lambda x: x.getUpdateValue("updateInfo", "_ip_address"),             None)
    ip_port                 = property(lambda x: x.getUpdateValue("updateInfo", "_ip_port"),                None)
    magnet_link             = property(lambda x: x.getUpdateValue("updateInfo", "_magnet_link"),            None)
    piece_size              = property(lambda x: x.getUpdateValue("updateInfo", "_piece_size"),             None)
    pieces                  = property(lambda x: x.getUpdateValue("updateInfo", "_pieces"),                 None)
    total_files             = property(lambda x: x.getUpdateValue("updateInfo", "_total_files"),            None)

    files                   = property(lambda x: x.getUpdateValue("updateFiles","_files"),                  None)
    trackers                = property(lambda x: x.getUpdateValue("updateTrackers","_trackers"),            None)
    peers                   = property(lambda x: x.getUpdateValue("updatePeers","_peers"),                  None)
    bitfield                = property(lambda x: x.getUpdateValue("updateBitfield","_bitfield"),            None)
    torrent                 = property(lambda x: x.getUpdateValue("updateTorrent","_torrent"),              None)

    # Other, indirect properties

    @property
    def hasFinished(self):
        return self.percentage == 100



    # Generic getter

    def getUpdateValue(self, updater, name):
        getattr(self, updater)()
        return self.__dict__[name]


    # Updater methods

    # List elements are set from jsit.updateTorrents and from updateInfo
    # Just forward to updateInfo
    def updateList(self, force = False):
        if time.time() < self._listValidUntil and not force:
            return
        self.updateInfo(force=True)

    def updateInfo(self, force = False):
        if time.time() < self._infoValidUntil and not force:
            return

        log(DEBUG)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/information.csp", params = {"info_hash" : self._hash})

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
                         "ratio_as_decimal" : "_ratio",
                         "maximum_ratio_as_decimal" : "_maximum_ratio",
                         "pieces" : "_pieces",
                         "is_private" : "_private",
                         "elapsed" : "_elapsed",
                         "is_completed_announced" : "_completed_announced",
                         "ip_address" : "_ip_address",
                         "ip_port" : "_ip_port",
                         "magnet_link" : "_magnet_link",
                         "piece_size_as_bytes" : "_piece_size",
                         "pieces" : "_pieces",
                         "total_files" : "_total_files"}

            fillFromXML(self, bs.find("data"), fieldmap)

            self.cleanupFields()

            self._infoValidUntil = time.time() + infoValidityLength
            self._listValidUntil = time.time() + listValidityLength

        except Exception,e :
            log(ERROR, u"Caught exception %s updating info for torrent %s!\n" % (e, self._name))


    def updateFiles(self, force = False):
        if time.time() < self._filesValidUntil and not force:
            return

        log(DEBUG)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/files.csp", params = {"info_hash" : self._hash})

            # Do we have links?
            r1 = bs.find("row")
            if r1 and self.percentage == 100 and r1.find("url").string == None:
                # Triger link gen
                log(DEBUG, u"Generating download links for %s (%s)...\n" % (self._name, self._hash))

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

        except APIError,e :
            log(ERROR, u"Caught exception %s updating files for torrent %s!\n" % (e, self._name))


    def updateTrackers(self, force = False):
        if time.time() < self._trackersValidUntil and not force:
            return

        log(DEBUG)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/trackers.csp", params = {"info_hash" : self._hash})

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

        except IOError,e :
            log(ERROR, u"Caught exception %s updating trackers for torrent %s!\n" % (e, self._name))


    def updatePeers(self, force = False):
        if time.time() < self._peersValidUntil and not force:
            return

        log(DEBUG)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/peers.csp", params = {"info_hash" : self._hash})

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

        except Exception,e :
            log(ERROR, u"Caught exception %s updating peers for torrent %s!\n" % (e, self._name))


    def updateBitfield(self, force = False):
        if time.time() < self._bitfieldValidUntil and not force:
            return

        log(DEBUG)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/bitfield.csp", params = {"info_hash" : self._hash})

            bf = bs.find("bitfield")

            self._bitfield = str(bf.string)

            self._bitfieldValidUntil = time.time() + infoValidityLength

        except Exception,e :
            log(ERROR, u"Caught exception %s updating bitfield for torrent %s!\n" % (e, self._name))


    def updateTorrent(self, force = False):
        if time.time() < self._torrentValidUntil and not force:
            return

        log(DEBUG)

        try:

            r = self._jsit()._session.get(baseurl + "/torrents/torrent_file.csp?info_hash=%s" % self.hash, verify=False)
            r.raise_for_status()

            self._torrent = r.content
 
            self._torrentValidUntil = time.time() + torrentValidityLength

        except Exception,e :
            log(ERROR, u"Caught exception %s updating torrent for torrent %s!\n" % (e, self._name))




    def cleanupFields(self):
        cleanupFields(self, floatfields = ["_percentage", "_ratio", "_maximum_ratio"],
                            intfields = ["_total_files", "_size", "_downloaded", "_uploaded", "_data_rate_in", "_data_rate_out",
                                         "_pieces", "_ip_port", "_piece_size" ],
                            boolfields = ["_private", "_completed_announced"])
        
        # Derived fields
        
        if self._downloaded > 0:
            self._ratio = self._uploaded / float(self._downloaded)
        else:
            self._ratio = 0


    def start(self):
        log(INFO)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/start.csp", params = {"info_hash" : self._hash})

            self._status = "running"

        except Exception,e :
            log(ERROR, u"Caught exception %s starting torrent %s!\n" % (e, self._name))


    def stop(self):
        log(INFO)

        try:
            bs = issueAPIRequest(self._jsit(), "/torrent/stop.csp", params = {"info_hash" : self._hash})

            self._status = "stopped"

        except Exception,e :
            log(ERROR, u"Caught exception %s stopping torrent %s!\n" % (e, self._name))


    def delete(self):
        log(INFO)
        self._jsit().deleteTorrent(self)



class JSIT(object):

    def __init__(self, username, password):

        log(DEBUG)

        self._session = requests.Session()
        # Adapter to increase retries
        ad = requests.adapters.HTTPAdapter() # Older requests version don't expose the constructor arg :(
        ad.max_retries=5
        self._session.mount('http://',  ad) 
        ad = requests.adapters.HTTPAdapter() # Older requests version don't expose the constructor arg :(
        ad.max_retries=5
        self._session.mount('https://', ad) 
        
        self._connected = False
        self._api_key = None
        
        # Torrents
        self._torrentsValidUntil = 0
        self._torrents = []
        self._dataRemaining = 0

        # General attributes
        self._labelsValidUntil = 0
        self._labels = []

        # Torrent updates
        self._newTorrents = []
        self._deletedTorrents = []

        # Connect already?
        if username and password:     
            self._username = username
            self._password = password
            self.connect()
 
    
    def __repr__(self):
        return "JSIT(0x%x)" % id(self)

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

    def connect(self, username = None, password = None):
        if username:
            self._username = username
        if password:
            self._password = password
            
        log(DEBUG, u"Connecting to JSIT as %s\n" % self._username)
        try:
            params = { u"username" : self._username, u"password" : self._password}
            r = self._session.get(baseurl + "/v_login.csp", params=params, verify=False)
            r.raise_for_status()
            self._connected = True
            
            text = urllib.unquote(r.content)
            if "status:FAILED" in text:
                log(ERROR, u"Login to js.it failed (username/password correct?)!\n")
                raise Exception("Login failed")

            log(DEBUG, u"Connected to JSIT as %s\n" % self._username)

            r = self._session.get(baseurl + "/options/index.csp", verify=False)
            r.raise_for_status()

            text = urllib.unquote(r.content)
            bs = BeautifulSoup(text)

            f = bs.find(id="api_key")

            if not f or f["value"] == "":
                log(ERROR, u"Couldn't find api_key. Please enable API at http://justseed.it/options/index.csp!\n")
                sys.exit(1)

            self._api_key = f["value"]
            log(DEBUG, u"Found API key %s\n" % self._api_key)

        except APIError,e :
            log(ERROR, u"Caught exception %s connecting to js.it!\n" % (e))
            raise e



    def findTorrents(self, search):
        sre = re.compile(search)

        ret = []
        for t in self.torrents:
            if sre.match(t.name):
                ret.append(t)

        return ret


    def lookupTorrent(self, hash):
        for t in self.torrents:
            if t.hash == hash:
                return t

        return None


    def updateTorrents(self, force = False):
        """Update all torrents. More efficient than one by one, also catches new/deleted torrents"""

        if time.time() < self._torrentsValidUntil and not force:
            return

        log(DEBUG, u"Updating torrent list and overview data.\n")

        deleted = [ t._hash for t in self._torrents ]
        new = []
        foundt = []

        try:
            bs = issueAPIRequest(self, "/torrents/list.csp")

            self._dataRemaining = int(bs.find("data_remaining_as_bytes").string)

            fieldmap = { "data_rate_in_as_bytes" : "_data_rate_in",
                         "data_rate_out_as_bytes" : "_data_rate_out",
                         "downloaded_as_bytes" : "_downloaded",
                         "elapsed_as_seconds" : "_elapsed",
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
                            t.__dict__[fieldmap[tag.name]] = unicode_cleanup(urllib.unquote(tag.string)).decode('utf-8')
                    except KeyError:
                        pass
                    except UnicodeEncodeError, e:
                        log(ERROR, "Caught unicode encode error %s trying to decode %rfor %s\n" % (e, tag.string, tag.name))
                        t.__dict__[fieldmap[tag.name]] = "ERROR DECODING"

                t.cleanupFields()

                t._listValidUntil = now + listValidityLength


            for d in deleted:
                t = self.lookupTorrent(d)
                t._hash = None # Mark as deleted
                self._torrents.remove(t)

            if logCheck(DEBUG):
                msg = "New(%d): " % len(new) + ','.join(new) + " Deleted(%d): " % len(deleted) + ','.join(deleted) + \
                      " Kept(%d): " % len(foundt) + ','.join(foundt) + "\n"
                log(DEBUG, msg)

            log(DEBUG2, "Torrent list now: %s\n" % self._torrents)
            
            self._torrentsValidUntil = now + listValidityLength

            self._newTorrents     += new
            self._deletedTorrents += deleted

        except IOError,e :
            log(ERROR, u"Caught exception %s getting torrent list!\n" % (e))
            return None,None



    def resetNewDeleted(self):
    
        log(DEBUG,"jsit::resetNewDeleted: new: %s deleted: %s\n" % (self._newTorrents, self._deletedTorrents))
        
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
        if time.time() < self._labelsValidUntil and not force:
            return

        log(DEBUG, u"Updating label list.\n")

        try:
            bs = issueAPIRequest(self, "/labels/list.csp")

            labels = []

            for tag in bs.find_all("label"):
                l = urllib.unquote(tag.string).decode('utf-8')
                labels.append(l)

            self._labels = labels
            self._labelsValidUntil = time.time() + labelValidityLength

        except Exception,e :
            log(ERROR, u"Caught exception %s getting label list!\n" % (e))



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
                    log(INFO, u"Torrent (files=%s, params=%s!) already running!\n" % (params, files))
                    
                    h = e.msg.find("info_hash=")
                    if h < 0:
                        raise e
                        
                    hash = e.msg[h+10:h+50]
                else:
                    raise e

            log(DEBUG, u"New torrent has hash %s.\n" % hash)

            # Wait for up to 5 seconds for the torrent to show up
            t = self.lookupTorrent(hash)
            now = time.time()
            while not t and time.time() < now + 5:
                time.sleep(0.3)
                self.updateTorrents(force = True)
                t = self.lookupTorrent(hash)

            if t:
                return t

            log(ERROR, u"Torrent failed to upload (files=%s, params=%s)!\n" % (params, files))

        except APIError,e :
            log(ERROR, u"Caught exception %s trying to upload torrent %s/%s!\n" % (e, params, files))

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
            log(ERROR, u"Caught exception %s deleting torrent %s!\n" % (e, tor._name))

