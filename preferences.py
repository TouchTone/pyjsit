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


def pref(module, name):
 
    if not allprefs.has_key(module):
        allprefs[module] = {}
    
    modprefs = allprefs[module]
    
    if not modprefs.has_key(name):
        modprefs[name] = None
    
    return modprefs[name]



def prefOrVal(module, name, val):
    v = pref(module, name)
    if v != None:
        return v
    
    return val
    


def load(file):
    global allprefs
    
    log(INFO)
    
    if isinstance(file, str):
        try:
            file = open(file, "r")
        except KeyError,e:
            allprefs = {}
            return

    
    allprefs = json.load(file)


def save(file):   
    log(INFO)
    
    if isinstance(file, str):
        file = open(file, "w")
        
    json.dump(allprefs, file)
    
    changedprefs = set()
    


def changed():
    log(DEBUG, "changed: %s\n" % changedprefs)
    
    if len(changedprefs) == 0:
        return None
    
    ret = ", ".join(changedprefs)    
    return ret
    

   
    
