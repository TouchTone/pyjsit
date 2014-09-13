#!/usr/bin/python

# Utility library to use 7z to unpack archives with a little bit of intelligence

import sys, os
import subprocess

from tools import mkdir_p


if sys.platform.startswith('linux'):
    exename = "7z"
elif sys.platform.startswith('win'):
    exename = "7z.exe"

exepath = "."

def set_path(p):
        if not os.path.isfile(os.path.join(p, exename)):
                print "Can't find %s in %s. Please find correct path and retry!" % (exename, exepath)
                return
                
        exepath = p
        

class UnpackError(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)



def run_7z(command, *args):
    try:
        res = subprocess.call([os.path.join(exepath, exename), command] + list(args))
    except Exception as e:
        print "Caught %s trying to execute %s with %s %s" % (e, os.path.join(exepath, exename), command, args)
        raise

    return res


def pipe_7z(command, *args):
    try:
        p = subprocess.Popen([os.path.join(exepath, exename), command] + list(args), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    except Exception as e:
        print "Caught %s trying to start %s with %s %s" % (e, os.path.join(exepath, exename), command, args)
        raise

    return p


def get_file_list(archive):
    p = pipe_7z("l", archive)
    
    files = []
    inlist = False
    for l in p.stdout.readlines():
        #print "l=", l
        l = l.strip()
                    
        if l.startswith('---------'):
            inlist = not inlist
            continue
    
        if inlist:
            files.append(l.split(None, 5))
    
    p.wait()
    if p.returncode != 0:
        raise UnpackError("Caught error in %s, return code %d" % (archive, p.returncode))
    
    return files

    
def has_single_toplevel(archive):
    """Check whether the archive has a top-level directory, i.e. only one file/path at the top level"""
    
    ntop = 0
    for ff in get_file_list(archive):
        if not os.path.sep in ff[5]:
            ntop += 1
    
    return ntop == 1


def unpack(archive, targetdir = None, progress = None):
    
    if progress:
        nfiles = float(len(get_file_list(archive)))
    
    if targetdir:
        if not os.path.isdir(targetdir):
            mkdir_p(targetdir)
            
        p = pipe_7z("x", "-y", "-o%s" % targetdir, archive)
    else:
        p = pipe_7z("x", "-y", archive)
        
    if progress:
        gfiles = 0
        for l in p.stdout.readlines():
            l = l.strip()
            if l.startswith("Extracting"):
                gfiles += 1
            fs = l.split(None, 1)
            if len(fs) > 0:
                name = fs[-1]
            else:
                name = ""
            progress(gfiles / nfiles, name)                
    
    p.wait()
    if p.returncode != 0:
        raise UnpackError("Caught error unpacking %s, return code %d" % (archive, p.returncode))
    
    

def test(archive, progress = None):
   
    if progress:
        nfiles = float(len(get_file_list(archive)))
 
    p = pipe_7z("t", "-y", archive)

    broken = []
    gfiles = 0
    
    for l in p.stdout.readlines():
        l = l.strip()
        ##print "l=",l
        if l.startswith("Testing"):
            gfiles += 1
            name = l.split(None, 1)[-1]
            if l.endswith("CRC Failed"):
                name = name[:-len("CRC Failed")].strip()
                broken.append(name)
                
            if progress:
                progress(gfiles / nfiles, name)
                
    p.wait()
    if p.returncode != 0:
        raise UnpackError("Caught error testing %s, return code %d. Broken files: %s" % (archive, p.returncode, broken))
    

        
    
if __name__ == "__main__":
    
    print "Files=",get_file_list("ff.zip")
    print "ff single? ", has_single_toplevel("ff.zip")
    
    print "Files=",get_file_list("k k.zip")
    print "kk single? ", has_single_toplevel("k k.zip")

    try:
        print "Files=", get_file_list("unpack.py")
        print "Didn't get expected error!"
    except UnpackError as e:
        print "Caught error:", e
    
    
    print "kk.zip", unpack("k k.zip")
    
    
    def prog(part, name):
        print "Prog: part=%f name=%s" % (part, name)
        
    print "ff.zip:", unpack("ff.zip", targetdir="qq/q", progress = prog)
    
    # Try broken archives
    try:
        print "unpack.py", unpack("unpack.py")
        print "Didn't get expected error!"
    except UnpackError as e:
        print "Caught error:", e

    try:
        print "broken.zip", unpack("broken.zip")
        print "Didn't get expected error!"
    except UnpackError as e:
        print "Caught error:", e
        
    # Test 
    print "Test k k.zip:", test("k k.zip")
    
    try:
        print "Test broken.zip:", test("broken.zip")
        print "Didn't get expected error!"
    except UnpackError as e:
        print "Caught error:", e
    
    