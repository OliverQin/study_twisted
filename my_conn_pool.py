#!/usr/bin/env python2
#-*- coding: UTF-8 -*-

__all__ = ['MyConnectionPool']

from cachedict import CacheDict

class MyConnectionPool():
    def __init__(self, size=1000):
        self.dicts = CacheDict( size )
        
    def reg(self, idx, obj):
        self.dicts[idx] = (obj, [0, 0])
        
    def unreg(self, idx):
        return self.dicts.pop(idx)[0]
        
    def getUploadSeq(self, idx):
        return self.dicts[idx][1][0]
    
    def getDownloadSeq(self, idx):
        return self.dicts[idx][1][1]
    
    def getObject(self, idx):
        return self.dicts[idx][0]
    
    def __contains__(self, idx):
        return idx in self.dicts
    
    def uploadOne(self, idx):
        self.dicts[idx][1][0] += 1
        return self.dicts[idx][1][0] - 1
    
    def downloadOne(self, idx):
        self.dicts[idx][1][1] += 1
        return self.dicts[idx][1][1] - 1
        
    def pop(self, idx):
        return self.dicts.pop(idx)
    
    
        
    