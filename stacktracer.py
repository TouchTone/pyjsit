"""Stack tracer for multi-threaded applications.


Usage:

import stacktracer
stacktracer.start_trace("trace.html",interval=5,auto=True) # Set auto flag to always update file!
....
stacktracer.stop_trace()
"""



import sys
import traceback
from collections import defaultdict

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter


# From http://www.pythoncentral.io/how-to-check-if-a-string-is-a-number-in-python-including-unicode/
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass

    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass

    return False
    
 # Taken from http://bzimmer.ziclix.com/2008/12/17/python-thread-dumps/
 
def stacktraces():
    # Build ap from thread id to name
    tname = {}
    tgroups = defaultdict(list)
    
    for t in threading.enumerate():
        tname[t.ident] = t.getName()
        
        g = t.getName().rsplit('-',1)    
        if len(g) == 2 and is_number(g[1]):
            group = g[0]
        else:
            group = "default"
            
        tgroups[group].append(t.ident)
    
    # Build threads dict
    threads = {}
    for threadId, stack in sys._current_frames().items():
        threads[threadId] = stack
        
    code = []
    for gn in sorted(tgroups.keys()):
        gt = tgroups[gn]
        code.append("\n#\n# Thread Group %s\n#" % gn)
        
        for threadId in sorted(gt):
            try:
                code.append("\n# Thread: %s (%s)" % (tname[threadId], threadId))
                for filename, lineno, name, line in traceback.extract_stack(threads[threadId]):
                    code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
                    if line:
                        code.append("  %s" % (line.strip()))
            except KeyError,e:
                pass
 
    return highlight("\n".join(code), PythonLexer(), HtmlFormatter(
      full=False,
      # style="native",
      noclasses=True,
    ))


# This part was made by nagylzs
import os
import time
import threading

class TraceDumper(threading.Thread):
    """Dump stack traces into a given file periodically."""
    def __init__(self,fpath,interval,auto):
        """
        @param fpath: File path to output HTML (stack trace file)
        @param auto: Set flag (True) to update trace continuously.
            Clear flag (False) to update only if file not exists.
            (Then delete the file to force update.)
        @param interval: In seconds: how often to update the trace file.
        """
        assert(interval>0.1)
        self.auto = auto
        self.interval = interval
        self.fpath = os.path.abspath(fpath)
        self.stop_requested = threading.Event()
        threading.Thread.__init__(self, name="StackTracer")
    
    def run(self):
        while not self.stop_requested.isSet():
            time.sleep(self.interval)
            if self.auto or not os.path.isfile(self.fpath):
                self.stacktraces()
    
    def stop(self):
        self.stop_requested.set()
        self.join()
        try:
            if os.path.isfile(self.fpath):
                os.unlink(self.fpath)
        except:
            pass
    
    def stacktraces(self):
        fout = file(self.fpath,"wb+")
        try:
            fout.write(stacktraces())
        finally:
            fout.close()


_tracer = None
def trace_start(fpath,interval=5,auto=True):
    """Start tracing into the given file."""
    global _tracer
    if _tracer is None:
        _tracer = TraceDumper(fpath,interval,auto)
        _tracer.setDaemon(True)
        _tracer.start()
    else:
        raise Exception("Already tracing to %s"%_tracer.fpath)

def trace_stop():
    """Stop tracing."""
    global _tracer
    if _tracer is None:
        raise Exception("Not tracing, cannot stop.")
    else:
        _tracer.stop()
        _tracer = None
