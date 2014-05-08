# Trivial preferences manager

import json

from log import *

# Global preferences dicts

allprefs = {}

changedprefs = set()

def setValue(module, name, value):

    if not allprefs.has_key(module):
        allprefs[module] = {}
    
    modprefs = allprefs[module]
    
    modprefs[name] = value
    
    changedprefs.add(module + ":" + name)


def pref(module, name, default = None):
 
    if not allprefs.has_key(module):
        allprefs[module] = {}
    
    modprefs = allprefs[module]
    
    if not modprefs.has_key(name):
        modprefs[name] = default
    
    return modprefs[name]


def hasPref(module, name):
 
    if not allprefs.has_key(module):
        return False
    
    modprefs = allprefs[module]
    
    if not modprefs.has_key(name):
        return False
    
    return True
    
   


def load(file):
    global allprefs
    
    log(INFO)
    
    if isinstance(file, str):
        try:
            file = open(file, "r")
        except KeyError,e:
            allprefs = {}
            return

    try:
        allprefs = json.load(file)
    except ValueError,e :
        log(ERROR, "Error %s loading %s, ignoring!" % (e, file))
        allprefs = {}


def save(file):   
    log(INFO)
    
    if isinstance(file, str):
        file = open(file, "w")
        
    json.dump(allprefs, file, sort_keys=True, indent=2)
    
    changedprefs = set()
    


def changed():
    log(DEBUG, "changed: %s" % changedprefs)
    
    if len(changedprefs) == 0:
        return None
    
    ret = ", ".join(changedprefs)    
    return ret
    

   
    
