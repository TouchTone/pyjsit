#!/usr/bin/python

# Trivial logger, to be replaced with something nicer later.

import os, sys, inspect


ERROR=1
WARNING=2
INFO=3
PROGRESS=4
DEBUG=5
DEBUG2=6

logLevelNames = [ "NONE", "ERROR", "WARNING", "INFO", "PROGRESS", "DEBUG", "DEBUG2" ]

logLevel = WARNING


lastmsg = None
lastcount = 0

# Number of characters to ignore from filenames
basedirlen = len(inspect.currentframe().f_code.co_filename.rsplit(os.path.sep,1)[0]) + 1


# From http://stackoverflow.com/questions/2203424/python-how-to-retrieve-class-information-from-a-frame-object
def get_class_name(f):
    try:
        class_name = f.f_locals['self'].__class__.__name__
    except KeyError:
        class_name = None

    return class_name
    
def log(level, msg = None):
    if level <= logLevel:
    
        global lastmsg, lastcount
        
        cf = inspect.currentframe().f_back
        co = cf.f_code
        
        args = ""
        self = ""
        vn = co.co_varnames
        for i in xrange(0, co.co_argcount):
            n = vn[i]
            if i == 0 and n == "self":
                self = "%s" % repr(cf.f_locals["self"])
                continue
            args += "%s=%s " % (vn[i], cf.f_locals[vn[i]])
        args = args[:-1]
        
        caller = "%s(%d) %s::%s(%s)" % (co.co_filename[basedirlen:], cf.f_lineno, self, co.co_name, args)
        
        if msg == None:
            msg = "\n"
        
        fullmsg = u"%s (%s): %s" % (logLevelNames[level], caller, msg)

        if fullmsg != lastmsg and lastcount > 1:
            sys.stderr.write("  *** last message repeated %d times\n" % lastcount)
        
        if fullmsg == lastmsg:
            lastcount += 1
            return
            
        sys.stderr.write(fullmsg)
        sys.stderr.flush()
        
        lastmsg = fullmsg
        lastcount = 1


def setLogLevel(level):
    global logLevel
    
    logLevel = level
