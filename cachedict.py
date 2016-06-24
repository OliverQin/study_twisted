#/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Created on Mon Jun 20 19:21:58 2016

@author: oliver
"""

import gc

class CacheDict:
    def __init__(self, maxSize):
        self.dicts = [dict(), dict()]
        self.maxSize = max( maxSize, 1 )
    
    def __getitem__(self, name):
        for i in [0, 1]: 
            if name in self.dicts[i]:
                return self.dicts[i][name]
        raise KeyError(name)
        
    def __setitem__(self, name, value):
        if name in self.dicts[1]:
            self.dicts[1].pop(name)
        self.dicts[0][name] = value
        if len(self.dicts[0]) >= self.maxSize:
            self.dicts = [ dict(), self.dicts[0] ]
            gc.collect()
            
    def pop(self, name):
        for i in [0, 1]:
            if name in self.dicts[i]:
                return self.dicts[i].pop( name )
        raise KeyError(name)

    def __len__(self):
        return len(self.dicts[0]) + len(self.dicts[1])
    
    def __contains__(self, term):
        return (term in self.dicts[0]) or (term in self.dicts[1])
    
    def __iter__(self):
        for i in [0, 1]:
            for j in self.dicts[i]:
                yield j
        return
    
if __name__ == '__main__':
    import random, time
    
    a = CacheDict(2)
    for i in range(65536 * 4 - 1):
        a[ random.randrange(2**31, 2**32) ] = int( time.time() )
    
    print 'Sleeping...'
    time.sleep(5.0)
    