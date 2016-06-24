#!/usr/bin/env python2
#-*- coding: UTF-8 -*-

__all__ = ['OverWallControlProtocol']

from se_protocol import SmallEncryptedProtocol
from struct import pack, unpack
import random

class OverWallControlProtocol(SmallEncryptedProtocol):
    def __init__(self):
        SmallEncryptedProtocol.__init__(self)
        
    def establishConnection(self, oldIdx, addr, port):
        #return (status, newIdx)
        pass
    
    def requestEstablish(self, oldIdx, addr, port):
        self.sendChunk( '\x01' + pack('<IH', oldIdx, port) + addr )
        
    def establishDone(self, oldIdx, newIdx, status):
        pass
        
    def gotSendFeedback(self, feedbacks):
        #feedbacks = [ (idx1, seq1, status1), (idx2, seq2, status2), ... ]
        pass
    
    def sendFeedback(self, feedbacks):
        if len(feedbacks) == 0:
            return
        
        res = '\xfd'
        for (idx, seq, status) in feedbacks:
            res += pack( '<IIB', idx, seq, status )
        self.sendChunk( res )
        
    def sendToRemote(self, idx, seq, data):
        #no return, batch response
        pass
    
    def closeRemoteConnection(self, idx):
        #return (status)
        pass
    
    def requestClose(self, idx):
        self.sendChunk( '\x03' + pack('<I', idx) )
    
    def closingRemoteDone(self, idx, status):
        pass
    
    def sendHeartBeat(self):
        self.sendChunk( '\x04' + ''.join( chr(random.randrange(256)) for _ in xrange(9) ) )
    
    def sendToEndpoint(self, idx, seq, data):
        print 'Sending...', idx, seq, len(data)
        n = '\x02' + pack('<II', idx, seq) + data
        self.sendChunk( n )
    
    def chunkReceived(self, data):
        if len(data) == 0:
            return
        
        cmd = data[0]
        if (cmd == '\x01'):
            oldIdx, port = unpack('<IH', data[1:7])
            addr = data[7:]
            
            self.establishConnection(oldIdx, addr, port)
            
            #FIXME: Python 2.7 does not support return after yield
            #status, idx = self.establishConnection(oldIdx, addr, port)
            #self.sendChunk( '\xfe' + pack('<BII', status, oldIdx, idx) )
        
        elif (cmd == '\x02'):
            idx, seq = unpack('<II', data[1:9])
            print 'Received-:', idx, seq, len(data[9:])
            self.sendToRemote( idx, seq, data[9:] )
            
            #no reply directly
            
        elif (cmd == '\x03'):
            (idx, ) = unpack('<I', data[1:5])
            
            status = self.closeRemoteConnection(idx)
            
            self.sendChunk( '\xfc' + data[1:5] + pack('<B', status) )
            
        elif (cmd == '\xfe'):
            status, oldIdx, idx = unpack('<BII', data[1:10])
            self.establishDone( oldIdx, idx, status )
            
        elif (cmd == '\xfd'):
            feedbacks = []
            for i in range(1, len(data), 9):
                feedbacks.append( unpack( '<IIB', data[i:i+9] ) )
            
            self.gotSendFeedback( feedbacks )
        
        elif (cmd == '\xfc'):
            idx, status = unpack( '<IB', data[1:6] )
            
            self.closingRemoteDone( idx, status )
            
            
    