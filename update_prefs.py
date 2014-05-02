#!/usr/bin/python

# Simple script to gather used preferences from the code and make sure they are present in preferences.json


import re, glob, os
import preferences

preferences.load("preferences.json")

prefre = re.compile('pref\("([^"]*)", *"([^"]*)"\)')

for f in glob.glob("*.py"):

    lines = open(f,"r").readlines()
    
    for l in lines:
        
        for m in prefre.findall(l):
        
            if not preferences.hasPref(m[0], m[1]):
                print "Found new %s:%s, adding." % (m[0], m[1])
                preferences.setValue(m[0], m[1], "**UNSET**")

          
preferences.save("preferences.json")
