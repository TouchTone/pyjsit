#!/usr/bin/python

# Trivial logger, to be replaced with something nicer later.

import sys


ERROR=1
WARNING=2
INFO=3
PROGRESS=4
DEBUG=5

logLevelNames = [ "NONE", "ERROR", "WARNING", "INFO", "PROGRESS", "DEBUG" ]

logLevel = WARNING

def log(level, msg):
    if level <= logLevel:
        sys.stderr.write(u"%s: %s" % (logLevelNames[level], msg) )
        sys.stderr.flush()

def setLogLevel(level):
    global logLevel
    
    logLevel = level
