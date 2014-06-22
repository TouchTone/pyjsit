#!/usr/bin/python

# Helper script to merge PyInstaller dists into one directory 

import sys, os, glob, filecmp, shutil
isfile = os.path.isfile
pj = os.path.join
sep = os.path.sep

import tools

def rec_glob(p, files):
    for d in glob.glob(p):
        if os.path.isfile(d):
            files.append(d)
        rec_glob("%s/*" % d, files)
    

outdir = sys.argv[1]

tools.mkdir_p(outdir)

print "Merging into ", outdir, ":",
sys.stdout.flush()

dfiles = {}
for d in sys.argv[2:]:
    f = []
    rec_glob("%s/*" % d, f)
    print "%s (%d files)" % (d, len(f)),
    dfiles[d] = f

print

for dir,files in dfiles.iteritems():
    for f in files:
        fb = f[len(dir)+1:]
        
        if not isfile(pj(outdir,fb)):
            dd = fb.rsplit(sep, 1)
            
            if len(dd) > 1:
                tools.mkdir_p(pj(outdir,dd[0]))
            
            shutil.copy(f, pj(outdir, fb))
        
        else:
        
            if not filecmp.cmp(pj(outdir, fb), f):
                print "Files %s and %s are different!"% (pj(outdir, fb), f)
            else:
                pass #print "Files %s and %s are the same!"% (pj(outdir, fb), f)

 
print "Done."
            
sys.exit(0)
