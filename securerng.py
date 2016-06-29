#/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Created on Mon Jun 20 20:00:30 2016

@author: oliver
"""

__all__ = ['SecureRNG']

import random, time, struct
import Crypto.Cipher.AES as aes

class SecureRNG:
    def __init__(self):
        f = lambda x: ''.join( chr(random.SystemRandom().randrange(256)) for _ in range(x) )
        self.key = f(32)
        self.iv  = f(16)
        
        self.StateLen = 4096
        
        self.pointer = 0
        self.state = ''.join( chr(random.randrange(256)) for _ in range(self.StateLen) )
        
        self.cipher = aes.new( self.key, aes.MODE_CFB, self.iv )
        for _ in range(16):
            self.refreshState()
        
    def refreshState(self):
        self.pointer = 0
        self.state = self.cipher.encrypt( self.state )
    
    def genStr(self, length):
        res = ''
        while length > 0:
            if self.pointer == self.StateLen:
                self.refreshState()
                
            minLength = min(length, self.StateLen - self.pointer)
            res += self.state[self.pointer:self.pointer+minLength]
            
            self.pointer += minLength
            length -= minLength
        return res
    
    def genInt32(self):
        return struct.unpack( '!i', self.genStr(4) )[0]
    
    def genInt64(self):
        return struct.unpack( '!q', self.genStr(8) )[0]
    
    def genUint32(self):
        return struct.unpack( '!I', self.genStr(4) )[0]
    
    def genUint64(self):
        return struct.unpack( '!Q', self.genStr(8) )[0]
    

if __name__ == '__main__':
    a = SecureRNG()
    #print a.genInt32()
    #print a.genInt64()
    #for i in range(1, 100):
        #print a.genStr(i+10)
    #print a.state, len(a.state)
    
    #print 'P6'
    #print '1024 1024'
    #print '255'
    #print a.genStr(1024 * 1024 * 3)

