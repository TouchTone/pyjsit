#!/usr/bin/python

# Simple script to gather used preferences from the code and make sure they are present in preferences.json, and/or filter for defaults.json

import re, glob, os, sys
import preferences

print "Loading preferences"

preferences.load("preferences.json")

prefre = re.compile('(?:pref|prefDir)\("([^"]*)", *"([^"]*)"')

found = {}

for f in glob.glob("*.py"):

    lines = open(f,"r").readlines()
    
    for l in lines:
        
        for m in prefre.findall(l):
        
            if m[0] != '':
                mod = m[0]
                val = m[1]
            else:
                mod = m[2]
                val = m[3]
        
        
            if not found.has_key(mod):
                found[mod] = {}
            found[mod][val] = "found"

            if not preferences.hasPref(mod, val):
                print "Found new %s:%s, adding." % (mod, val)
                preferences.setValue(mod, val, "**UNSET**")
                
# Find settings that are in prefs.json but not in code.

print "Finding orphans:"

for m in preferences.allprefs.keys():
    # Skip version info
    if m == "Version":
        continue
        
    if not m in found.keys():
        print "Module %s is orphaned, removed." % m
        del preferences.allprefs[m]
        continue
        
    pv = preferences.allprefs[m]
    cv = found[m]
    
    for n in pv.keys():
        if not n in cv.keys():
            print "Value %s:%s is orphaned, removed." % (m, n)
            del pv[n]
 
# Decide what to do: write defaults or prefs
           
if len(sys.argv) > 1 and sys.argv[1] == "--defaults":
    # Remove personal values
    for m,v in [("jsit","username"), ("jsit","password"), ("yajsis","username"), ("yajsis","password"), ("autoDownload", "types"), ("autoDownload", "giveUpIfNotCompletedAfter")]:
        try:
            del preferences.allprefs[m][v]
        except KeyError:
            pass
            
    # Set log levels to defaults
    preferences.setValue("yajsig", "logLevel", 3)
    preferences.setValue("yajsig", "fileLogLevel", 4)
    preferences.setValue("yajsis", "logLevel", 3)
    preferences.setValue("yajsis", "fileLogLevel", 4)
    preferences.setValue("yajsis", "port", 8282)
    
    # Reset paths to defaults
    preferences.setValue("jsit", "torrentDirectory", "intorrents")
    preferences.setValue("downloads", "basedir", "downloads")
    preferences.setValue("downloads", "completedDirectory", "completed")
    
    # Remove label options
    preferences.setValue("autoDownload", "skipLabels", [])
    preferences.setValue("autoDownload", "checkAutoDownloadPieces", False)
    preferences.setValue("autoDownload", "deleteSkippedAndStopped", False)
    preferences.setValue("autoDownload", "trackers", [])
   
    preferences.setValue("downloads", "setCompletedLabel", None)
    preferences.setValue("downloads", "unpackArchives", False)
    
    print "Updating defaults.json..."
    preferences.save("defaults.json")
    
    # Add some demo options
    preferences.setValue("autoDownload", "types", 
            { "Movies" : { 
                "completedDirectory": "completed/Movies", 
                "matchLabels": [
                  "Movies"
                ], 
                "matchNames": []
              },
              "JohnSteward" : {
                "completedDirectory": "completed/JohnSteward", 
                "matchLabels": [], 
                "matchNames": [ "The\.Daily\.Show" ]
              }
            }
          )
       
    print "Updating example.json..."
    preferences.save("example.json")
      
else:
    preferences.save("preferences.json")
