
# Generic tools used in multiple modules

from log import *

import unicodedata


# Based on http://stackoverflow.com/questions/816285/where-is-pythons-best-ascii-for-this-unicode-database
def unicode_cleanup(s):
   
    # Fix up messy punctuation
    punctuation = { u'\u2018' : u'\u0027', u'\u2019' : u'\u0027',  u'\u201c' : u'\u0022',  u'\u201d' : u'\u0022',
                    u'\xe2\x80\x99' : u'\u0027', u'\xe2\x80\x98' : u'\u0027',  
                    u'\xe2\x80\x9c' : u'\u0022', u'\xe2\x80\x9d' : u'\u0022', 
                    u'\xe2\x80\x9e' : u'\u0022', u'\xe2\x80\x9f' : u'\u0022',
                    u'\xe2\x80\x90' : u'\u002d', u'\xe2\x80\x91' : u'\u002d', 
                    u'\xe2\x80\x92' : u'\u002d', u'\xe2\x80\x93' : u'\u002d', 
                    u'\xe2\x80\x94' : u'\u002d', u'\xe2\x80\x95' : u'\u002d' 
                    }
    for a,b in punctuation.iteritems():
        s = s.replace(a, b)
    
    s = unicodedata.normalize('NFKD', s)
    
    return s
 
 

def isoize(val, unit):
    try:
        num=float(val)
    except TypeError:
        return "0 " + unit
        
    sizes = ["", "K", "M", "G", "T"]
    for s in sizes:
        if num < 1024:
            sn = "%.2f %s" % (num, s)
            break
        num /= 1024.0
    return sn + unit

isoize_b = lambda v: isoize(v, "B")
isoize_bps = lambda v: isoize(v, "B/s")


# Based on http://stackoverflow.com/questions/538666/python-format-timedelta-to-string
def printNiceTimeDelta(delta):
    delay = datetime.timedelta(seconds=int(delta))
    out = str(delay)
    if (delay.days > 1):
        out = out.replace(" days, ", ":")
    if (delay.days > 0):
        out = out.replace(" day, ", ":")
    else:
        out = "0:" + out
    outAr = out.split(':')
    outAr = ["%02d" % (int(float(x))) for x in outAr]
    out   = ":".join(outAr)
    return out    
    
# From http://tomayko.com/writings/cleanest-python-find-in-list-function
def find(f, seq):
  """Return first item in sequence where f(item) == True."""
  for item in seq:
    if f(item): 
      return item
      
