#!/bin/python

# Priority queue that allows updating priorities

# Todo: don't do busy waiting...


import time
from heapq import * # Basic heap implementation
import Queue # Need to pull in exceptions
from tools import * # For RWLock


class DPQueue(object):
    """Thread-safe Priority queue that can update priorities"""
    
    def __init__(self, maxsize = 0, prio = lambda e: e.id):

        # Queue parameters
        
        self.maxsize = maxsize
        self.prio = prio
        
        # Internals
        self._data = []
        self._lock = RWLock()
        self._pendingtasks = 0
        
        
    def qsize(self):
        with self._lock.read_access:
            return len(self._data)


    def empty(self):
        return self.qsize() == 0


    def full(self):
        return self.maxsize != 0 and self.qsize() == self.maxsize
 
 
    def put(self, item, block = True, timeout = None):
        
        self._lock.acquire_write()
        
        if self.maxsize == 0 or len(self._data) < self.maxsize:
            p = self.prio(item)
            heappush(self._data, (p, item))
            self._pendingtasks += 1
            self._lock.release_write()
            return
        else:
            if not block:
                self._lock.release_write()
                raise Queue.Full
            
            if timeout > 0:
                deadline = time.time() + timeout
            else:
                deadline = 0
                
            self._lock.release_write()
            
            while deadline == 0 or time.time() < deadline:
                self._lock.acquire_write()
                if len(self._data) < self.maxsize:
                    p = self.prio(item)
                    heappush(self._data, (p, item))  
                    self._pendingtasks += 1
                    self._lock.release_write()
                    return
                self._lock.release_write()
                
                time.sleep(0.01)
            
            if time.time() >= deadline:
                raise Queue.Full
                        
        
    def put_nowait(self, item):
        self.put(item, False)
    
    
    def get(self, block = True, timeout = None):
        self._lock.acquire_write()
        
        if len(self._data) > 0:
            p,item = heappop(self._data)
            self._lock.release_write()
            return item
        else:
            if not block:
                self._lock.release_write()
                raise Queue.Empty
            
            if timeout > 0:
                deadline = time.time() + timeout
            else:
                deadline = 0
                
            self._lock.release_write()
            
            while deadline == 0 or time.time() < deadline:
                self._lock.acquire_write()
                if len(self._data) > 0:
                    p,item = heappop(self._data)
                    self._lock.release_write()
                    return item
                
                self._lock.release_write()
                
                time.sleep(0.01)
            
            if time.time() >= deadline:
                raise Queue.Empty
        

        
    def get_nowait(self):
        return self.get(False)
   
   
    def task_done(self):
        with self._lock.write_access:
            if self._pendingtasks == 0:
                raise ValueError
            self._pendingtasks -= 1
            
            
    def join(self): 
        self._lock.acquire_read()
        
        while self._pendingtasks > 0:
            self._lock.release_read()
            time.sleep(0.01)
            self._lock.acquire_read()
    
        self._lock.release_read()
    
    
    def reprioritize(self):
        with self._lock.write_access:
            for i in xrange(len(self._data)):
                p,item = self._data[i]
                p = self.prio(item)
                self._data[i] = (p,item)
            
            heapify(self._data)


if __name__ == "__main__":
    # Test...
    
    print "Creating..."
    dpq = DPQueue(maxsize = 5, prio = lambda e: e)
    
    print "Empty:", dpq.empty()
    
    print "Putting..."
    dpq.put(1)
    print "Empty:", dpq.empty()
    dpq.put(5)
    dpq.put(3)
    dpq.put(2)
    print "Full:", dpq.full()
    dpq.put(4)
    
    print "Full:", dpq.full()
    
    print "Reprioritize..."
    dpq.prio = lambda e: -e
    dpq.reprioritize()
    
    print "Getting..."
    
    e = dpq.get()
    print "Got:", e   
    dpq.task_done()
    print "Full:", dpq.full()
    e = dpq.get()
    print "Got:", e    
    dpq.task_done()
    e = dpq.get()
    print "Got:", e
    dpq.task_done()
    e = dpq.get()
    print "Got:", e
    dpq.task_done()
    print "Empty:", dpq.empty()
    e = dpq.get()
    print "Got:", e
    dpq.task_done()
    print "Empty:", dpq.empty()
    
    print "Join..."
    dpq.join()