#!/usr/bin/python

# Utility library to use 7z/unrar to unpack archives with a little bit of intelligence

import sys, os, string
from distutils import spawn
import subprocess
from log import *

from tools import mkdir_p


if sys.platform.startswith('linux'):
    exename_7z = "7z"
    exename_unrar = "unrar"
elif sys.platform.startswith('win'):
    exename_7z = "7z.exe"
    exename_unrar = "unrar.exe"


def set_path(p):
        if not os.path.isfile(os.path.join(p, exename_7z)):
                print "Can't find %s in %s. Please find correct path and retry!" % (exename_7z, exepath_7z)
                return
                
        exepath_7z = os.path.join(p, exename_7z)


def archive_type(archive):
    atype = string.lower(archive.rsplit('.', 1)[-1])
    
    return atype
    
        

class UnpackError(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)



def run_7z(command, *args):
    try:
        res = subprocess.call([exepath_7z, command] + list(args))
    except Exception as e:
        print "Caught %s trying to execute %s with %s %s" % (e, exepath_7z, command, args)
        raise

    return res


def pipe_7z(command, *args):
    try:
        p = subprocess.Popen([exepath_7z, command] + list(args), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    except Exception as e:
        print "Caught %s trying to start %s with %s %s" % (e, exepath_7z, command, args)
        raise

    return p


def run_unrar(command, *args):
    try:
        res = subprocess.call([exepath_unrar, command] + list(args))
    except Exception as e:
        print "Caught %s trying to execute %s with %s %s" % (e, exepath_unrar, command, args)
        raise

    return res


def pipe_unrar(command, *args):
    try:
        p = subprocess.Popen([exepath_unrar, command] + list(args), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    except Exception as e:
        print "Caught %s trying to start %s with %s %s" % (e, exepath_unrar, command, args)
        raise

    return p



# Return list of name, size, compsize, date, time tuples
def get_file_list(archive):

    # Archive type?
    atype = archive_type(archive)

    # RAR?
    if atype == "rar":
        p = pipe_unrar("l", archive)

        files = []
        inlist = False
        for l in p.stdout.readlines():
            #print "l=", l
            l = l.strip()

            if l.startswith('---------'):
                inlist = not inlist
                continue

            if inlist:
                s = l.split(None, 6)
                files.append((s[0], s[1], s[2], s[4], s[5]))

        p.wait()
        if p.returncode != 0:
            raise UnpackError("Caught error in %s, return code %d" % (archive, p.returncode))
        

    # Other, try 7z
    else:
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
                s = l.split(None, 5)
                files.append((s[5], s[3], s[4], s[0], s[1]))

        p.wait()
        if p.returncode != 0:
            raise UnpackError("Caught error in %s, return code %d" % (archive, p.returncode))
    
    return files


    
def has_single_toplevel(archive):
    """Check whether the archive has a top-level directory, i.e. only one file/path at the top level"""
    
    ntop = 0
    for ff in get_file_list(archive):
        if not os.path.sep in ff[0]:
            ntop += 1
    
    return ntop == 1



def unpack(archive, targetdir = None, progress = None):

    # Archive type?
    atype = archive_type(archive)
    
    if progress:
        nfiles = float(len(get_file_list(archive)))
    
    if targetdir:
        if not os.path.isdir(targetdir):
            mkdir_p(targetdir)
        
        if atype == "rar":
            p = pipe_unrar("x", "-y", archive, targetdir)
        else:
            p = pipe_7z("x", "-y", "-o%s" % targetdir, archive)
    else:        
        if atype == "rar":
            p = pipe_unrar("x", "-y", archive)
        else:
            p = pipe_7z("x", "-y", archive)
        
    if progress:
        gfiles = 0
        name = ""
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

    # Archive type?
    atype = archive_type(archive)
   
   
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
    
    
# Try to find 7z executable

try:

    exepath_7z = spawn.find_executable("7z")
    log(DEBUG, "Found 7z in %s" % exepath_7z)
    
except Exception, e:
    log(WARNING, "Couldn't find 7z executable, auto-unpack will fail unless manually set! (%s)" % e)
    exepath_7z = None

    
# Try to find unrar executable

try:

    exepath_unrar = spawn.find_executable("unrar")
    log(DEBUG, "Found unrar in %s" % exepath_unrar)
    
except Exception, e:
    log(WARNING, "Couldn't find unrar executable, auto-unpack will fail unless manually set! (%s)" % e)
    exepath_unrar = None



if __name__ == "__main__":

    print "Test", len(get_file_list("hegre.rar"))
    print "Test2"

    def prog(a,b):
        print a,b

    unpack("hegre.rar", progress=prog)

    sys.exit(1)

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
    
    
