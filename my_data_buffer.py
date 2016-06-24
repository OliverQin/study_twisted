#!/usr/bin/env python2
#-*- coding: UTF-8 -*-

#from collections import defaultdict

class MyDataBuffer():
    def __init__(self):
        self.bf = dict( )
        
    def __contains__(self, tag):
        if isinstance(tag, int):
            return tag in self.bf
        else: #tuple
            if len(tag) == 1:
                return tag[0] in self.bf
            else:
                idx, seq = tag
                return idx in self.bf and seq in self.bf[idx]
    
    def add(self, idx):
        self.bf[idx] = dict()
        
    def setValue(self, idx, seq, data):
        self.bf[idx][seq] = data
        
    def pop(self, idx):
        #if idx in self.bf:
        return self.bf.pop(idx)
        #return None
    
    def popValue(self, idx, seq):
        if idx in self.bf and seq in self.bf[idx]:
            return self.bf[idx].pop(seq)
        return None
    
    def __getitem__(self, tup):
        idx, seq = tup
        return self.bf[idx][seq]
    
    def __iter__(self):
        for i in self.bf:
            for j in self.bf[i]:
                yield (i, j)
        return 
    
    def getSeqsByIndex(self, idx):
        return [i for i in self.bf[idx]]
    
    def getLengthByIndex(self, idx):
        if idx in self.bf:
            return len(self.bf[idx])
        return 0

if __name__ == '__main__':
    a = MyDataBuffer()
    
    print 1 in a
    
    a.setValue(1, 20, 'afe')
    print 1 in a
    
    print a.bf