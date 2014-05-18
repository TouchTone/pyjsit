#!/usr/bin/python

# Trivial logger, to be replaced with something nicer later.

import os, sys, inspect, time, threading, gzip, glob
import repr as reprlib

ERROR=1
WARNING=2
INFO=3
PROGRESS=4
DEBUG=5
DEBUG2=6
DEBUG3=7
DEBUG4=8

logLevelNames = [ "NONE", "ERROR", "WARNING", "INFO", "PROGRESS", "DEBUG", "DEBUG2", "DEBUG3", "DEBUG4" ]

# Runtime configuration
logLevel = WARNING
fileLogLevel = PROGRESS

logCallbacks = []

ignoreModules = set()   # Ignore these modules
onlyModules = None     # Only show these modules
logFile = None
logFileName = None
stacklevels = 5

lastmsg = None
lastcount = 0

# Number of characters to ignore from filenames
basedirlen = len(inspect.currentframe().f_code.co_filename.rsplit(os.path.sep,1)[0]) + 1

starttime = time.time()

# Custom repr to shorten output

primitives = (int, str, bool, float, list, dict)
has_op = lambda obj, op: callable(getattr(obj, op, None))

class MyRepr(reprlib.Repr):
    def repr(self, obj):
        # Use for classes that don't have a personal repr
        if not isinstance(obj, primitives) and not obj is None:
            if has_op(obj, "__repr__"):
                try:
                    return obj.__repr__()
                except TypeError, e:
                    return type.__repr__(obj)
            else:
                return "%s(0x%x)" % (obj.__class__.__name__, id(obj))
        else:
            # Hack: repr is old-style class, call method directly
            return reprlib.Repr.repr(self, obj)
 
aRepr = MyRepr()


# From http://stackoverflow.com/questions/2203424/python-how-to-retrieve-class-information-from-a-frame-object
def get_class_name(f):
    try:
        class_name = f.f_locals['self'].__class__.__name__
    except KeyError:
        class_name = None

    return class_name


def logCheck(level):
    return  level <= logLevel or level <= fileLogLevel  
     
    
def log(level, msg = None):
    if level <= logLevel or level <= fileLogLevel:
    
        global lastmsg, lastcount, ignoreModules, onlyModules
        
        cf = inspect.currentframe().f_back
        co = cf.f_code
        
        mod = co.co_filename[basedirlen:]
        modn = mod[:-3]
        
        if onlyModules and modn not in onlyModules:
            return
        
        if modn in ignoreModules:
            return
        
        if mod == "":
            mod = "<Top>"
        
        caller = ""
        scf = cf
        
        for bt in xrange(0, stacklevels):
            
            if caller:
                caller = " > " + caller
                
            caller = "%s:%d" % (scf.f_code.co_filename[basedirlen:], scf.f_lineno) + caller
            
            scf = scf.f_back
            
            if scf == None:
                break
 
         
        args = ""
        self = ""
        vn = co.co_varnames
        for i in xrange(0, co.co_argcount):
            n = vn[i]
            if i == 0 and n == "self":
                self = aRepr.repr(cf.f_locals["self"])
                continue

            v = aRepr.repr(cf.f_locals[vn[i]])
            
            args += "%s=%s " % (vn[i], v)
        args = args[:-1]
        
        caller += " %s::%s(%s)" % (self, co.co_name, args)
        
        if msg == None:
            msg = " called"
        
        now = time.time()
        ct = threading.current_thread()
        
        fullmsg = u"%s %0.3f %s (%s): %s\n" % (ct.name, now - starttime, logLevelNames[level], caller, msg)
        
        for cb in logCallbacks:
            cb(fullmsg = fullmsg, threadName = ct.name, ltime = now - starttime, level = level, levelName = logLevelNames[level], caller = caller, msg = msg)
            
            
        if fullmsg == lastmsg:
            lastcount += 1
            return
        elif lastcount > 1:
            lastmsg = fullmsg
            lastcount = 1
            fullmsg = "  *** last message repeated %d times\n" % lastcount
            
        
        if level <= logLevel:
            sys.stderr.write(fullmsg)
            sys.stderr.flush()
        
        if logFile != None and level <= fileLogLevel:
            logFile.write(fullmsg.encode("utf-8"))
            logFile.flush()


def setLogLevel(level):
    global logLevel
    
    logLevel = level


def setFileLog(filename, level):
    global fileLogLevel, logFile
    
    log(WARNING)
    
    # Log rotation
    if os.path.isfile(filename):
        st = os.stat(filename)
        try:
            base,ext = filename.rsplit('.', 1)
            out = base + '.' + time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime(st.st_mtime)) + '.' + ext + ".gz"
            logglob = base + '.*.' + ext + ".gz"
        except IOError:            
            out = filename + '.' + time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime(st.st_mtime)) + ".gz"
            logglob = filename + '.*.' + ".gz"
           
        
        log(WARNING, "Found old log file, compressing to %s." % out)
        
        f_in = open(filename, 'rb')
        f_out = gzip.open(out, 'wb')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()
        
        logs = glob.glob(logglob)
        
        nl = 10 # Number of log files to keep
        if len(logs) > nl:
            logs.sort()
            for l in logs[:-nl]:
                log(WARNING, "Removing %s to keep nLogs <= %d." % (l, nl))
                os.remove(l)
        

    try:
        logFile = open(filename, "w")
    except Exception,e:
        log(ERROR, "Caught %s trying to open %s as log file!" % (e, filename))
        return
    
    logFileName = filename
    
    fileLogLevel = level


def addOnlyModule(mod):
    global onlyModules
    if not onlyModules:
        onlyModules = set()
    
    onlyModules.add(mod)


def subOnlyModule(mod):
    global onlyModules
    if not onlyModules:
        return
    
    onlyModules.discard(mod)
    
    if not len(onlyModules):
        onlyModules = None


def addIgnoreModule(mod):
    global ignoreModules
    if not ignoreModules:
        ignoreModules = set()
    
    ignoreModules.add(mod)


def subIgnoreModule(mod):
    global ignoreModules
    if not ignoreModules:
        return
    
    ignoreModules.discard(mod)
    
    if not len(ignoreModules):
        ignoreModules = None
    
    
def addLogCallback(cb):
    logCallbacks.append(cb)

def subLogCallback(cb):
    logCallbacks.remofe(cb)
    
 
    
