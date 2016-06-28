#!/usr/bin/env python2
#-*- coding: UTF-8 -*-

__all__ = ['OverWallControlProtocol']

from twisted.internet.protocol import Protocol, Factory, ClientFactory
from se_protocol import SmallEncryptedProtocol
from struct import pack, unpack
import random, hashlib
import sys
from securerng import SecureRNG
from twisted.internet import reactor, protocol, defer

_OverWallFeedbackInterval = 1.5
_OverWallRetryInterval = 15.0

class ConnectionManagerNode:
    SentToRemote = 0
    SentToEndpoint = 1
    
    def __init__(self, obj):
        self.obj = obj
        self.sent = [0, 0]
        self.bufs = [dict(), dict()]
        
    def bufferSentToRemote(self):
        return self.bufs[ self.SentToRemote ]
    
    def bufferSentToEndpoint(self):
        return self.bufs[ self.SentToEndpoint ]
    
    def seqSentToRemote(self):
        return self.sent[ self.SentToRemote ]
    
    def seqSentToEndpoint(self):
        return self.sent[ self.SentToEndpoint ]
    
    def dataSentToRemote(self, seq):
        return self.bufs[ self.SentToRemote ][seq]
    
    def dataSentToEndpoint(self, seq):
        return self.bufs[ self.SentToEndpoint ][seq]
    
    def addSentToRemote(self):
        a = self.sent[ self.SentToRemote ]
        self.sent[ self.SentToRemote ] += 1
        return a
    
    def addSentToEndpoint(self):
        a = self.sent[ self.SentToEndpoint ]
        self.sent[ self.SentToEndpoint ] += 1
        return a

class ConnectionManager:
    def __init__(self):
        self.data = dict()
        
    def add(self, idx, obj):
        self.data[idx] = ConnectionManagerNode(obj)
    
    def pop(self, idx):
        return self.data.pop(idx)
        
    def __getitem__(self, idx):
        return self.data[idx]
        
    def __contains__(self, idx):
        return idx in self.data


OverWallRNG = SecureRNG()
OverWallConnections = ConnectionManager()
OverWallPool = set()
OverWallFeedbacks = []

GlobalSwitch = False

SuperIdxs = []

def establishAll(num):
    for _ in range(num):
        x = OverWallRNG.genUint32()
        g = chooseRandomOverWallConnection()
        g.requestEstablish(x, '127.0.0.1', 555)

def randomSend():
    global SuperIdxs
    a = random.randrange(5)
    g = chooseRandomOverWallConnection()
    if sys.argv[1] != 'server' and len(SuperIdxs) < 3:
        a = 3
        
    if (a < 3):
        data = OverWallRNG.genStr(8888)
        g.sendToEndpoint( random.choice(SuperIdxs), data )
    elif (a == 3):
        idx = random.choice(SuperIdxs)
        g.requestClose(idx)
    else:
        if sys.argv[1] == 'server':
            return
        else:
            x = OverWallRNG.genUint32()
            g.requestEstablish(x, '127.0.0.1', 555)
    
    reactor.callLater(2.0, randomSend)

def remoteDataReceived(idx, seq, data):
    if (idx not in OverWallConnections):
        OverWallFeedbacks.append( idx, seq, 0x3 )

    nseq = OverWallConnections[idx].seqSentToRemote()
    if (seq >= nseq):
        OverWallFeedbacks.append( (idx, seq, 0) )
    else:
        OverWallFeedbacks.append( (idx, seq, 1) )
    
    while nseq in OverWallConnections[idx].bufferSentToRemote():
        #Send
        data = OverWallConnections[idx].dataSentToRemote(nseq)
        print "{0:#08x}".format(idx), "{0:#02x}".format(nseq), hashlib.md5(data).hexdigest(), 'Rcv'
        OverWallConnections[idx].addSentToRemote()
        OverWallConnections[idx].bufferSentToRemote().pop( nseq )
        nseq += 1
    return 

def chooseRandomOverWallConnection():
    if len(OverWallPool) > 0:
        return random.choice( list(OverWallPool) )
    else:
        return None

def giveFeedBack():
    g = chooseRandomOverWallConnection()
    if g is not None:
        global OverWallFeedbacks
        
        g.sendFeedback( OverWallFeedbacks )
        OverWallFeedbacks = []
    
    reactor.callLater( _OverWallFeedbackInterval, giveFeedBack )

class OverWallControlProtocol(SmallEncryptedProtocol):
    def __init__(self):
        SmallEncryptedProtocol.__init__(self)
        OverWallPool.add(self)
    
    def establishConnection(self, idx, addr, port):
        print "{0:#08x}".format(idx), 'Req'
        
        if (idx in OverWallConnections):
            self.sendChunk( '\xfe\x02' + pack('<I', idx) )
        else:
            OverWallConnections.add( idx, None )
            SuperIdxs.append(idx)
            self.sendChunk( '\xfe\x00' + pack('<I', idx) )
            
        global GlobalSwitch
        if (GlobalSwitch == False):
            GlobalSwitch = True
            reactor.callLater(7.0, randomSend)
        
    def requestEstablish(self, idx, addr, port):
        self.sendChunk( '\x01' + pack('<IH', idx, port) + addr )
        
    def establishDone(self, idx, status):
        OverWallConnections.add(idx, None)
        SuperIdxs.append(idx)
        print "{0:#08x}".format(idx), 'Est', len(SuperIdxs), len(OverWallConnections.data)
        pass
        
    def gotSendFeedback(self, feedbacks):
        #feedbacks = [ (idx1, seq1, status1), (idx2, seq2, status2), ... ]
        for idx, seq, status in feedbacks:
            if (status == 0x0 or status == 0x1) and (idx in OverWallConnections):
                if seq in OverWallConnections[idx].bufferSentToEndpoint():
                    print "{0:#08x}".format(idx), "{0:#02x}".format(seq), 'SucSnt'
                    OverWallConnections[idx].bufferSentToEndpoint().pop(seq)
    
    def sendFeedback(self, feedbacks):
        if len(feedbacks) == 0:
            return
        
        res = '\xfd'
        for (idx, seq, status) in feedbacks:
            res += pack( '<IIB', idx, seq, status )
        self.sendChunk( res )
        
    def sendToRemote(self, idx, seq, data):
        OverWallConnections[idx].bufferSentToRemote()[seq] = data
        remoteDataReceived(idx, seq, data)
        pass
    
    def closeRemoteConnection(self, idx):
        OverWallConnections.pop(idx)
        SuperIdxs.remove(idx)
        return 0

    def requestClose(self, idx):
        print "{0:#08x}".format(idx), 'Cls'
        SuperIdxs.remove(idx)
        self.sendChunk( '\x03' + pack('<I', idx) )
    
    def closingRemoteDone(self, idx, status):
        OverWallConnections.pop(idx)
        print "{0:#08x}".format(idx), 'Cld'
    
    def sendHeartBeat(self):
        self.sendChunk( '\x04' + ''.join( chr(random.randrange(256)) for _ in xrange(9) ) )
    
    def sendToEndpoint(self, idx, data, seq=None):
        #print 'sendto endpoint', hex(idx), hashlib.md5(data).hexdigest(), seq
        if seq is None:
            seq = OverWallConnections[idx].addSentToEndpoint()
        else:
            if idx not in OverWallConnections or \
                seq not in OverWallConnections[idx].bufferSentToEndpoint():
                return #Success
            
        OverWallConnections[idx].bufferSentToEndpoint()[seq] = data
        print "{0:#08x}".format(idx), "{0:#02x}".format(seq), hashlib.md5(data).hexdigest(), 'Snt'
        
        n = '\x02' + pack('<II', idx, seq) + data
        self.sendChunk( n )
        
        reactor.callLater(_OverWallRetryInterval, self.sendToEndpoint, idx, data, seq)
    
    def chunkReceived(self, data):
        if len(data) == 0:
            return
        
        cmd = data[0]
        if (cmd == '\x01'):
            idx, port = unpack('<IH', data[1:7])
            addr = data[7:]
            
            self.establishConnection(idx, addr, port)
            
            #FIXME: Python 2.7 does not support return after yield
            #status, idx = self.establishConnection(idx, addr, port)
            #self.sendChunk( '\xfe' + pack('<BII', status, idx) )
        
        elif (cmd == '\x02'):
            idx, seq = unpack('<II', data[1:9])
            #print 'Received-:', idx, seq, len(data[9:])
            self.sendToRemote( idx, seq, data[9:] )
            
            #no reply directly
            
        elif (cmd == '\x03'):
            (idx, ) = unpack('<I', data[1:5])
            
            status = self.closeRemoteConnection(idx)
            
            self.sendChunk( '\xfc' + data[1:5] + pack('<B', status) )
            
        elif (cmd == '\xfe'):
            status, idx = unpack('<BI', data[1:6])
            self.establishDone( idx, status )
            
        elif (cmd == '\xfd'):
            feedbacks = []
            for i in range(1, len(data), 9):
                feedbacks.append( unpack( '<IIB', data[i:i+9] ) )
            
            self.gotSendFeedback( feedbacks )
        
        elif (cmd == '\xfc'):
            idx, status = unpack( '<IB', data[1:6] )
            
            self.closingRemoteDone( idx, status )
        
    def connectionLost(self, reason):
        OverWallPool.remove( self )

def testServer():
    f = Factory()
    f.protocol = OverWallControlProtocol
    reactor.listenTCP(8555, f)
    
    reactor.callLater(0.0, giveFeedBack)
    reactor.run()

def testClient():
    for _ in range(10):
        f = ClientFactory()
        f.protocol = OverWallControlProtocol
            
        #reactor.connectTCP('23.105.199.44', 8555, f)
        reactor.connectTCP('127.0.0.1', 8555, f)
    
    reactor.callLater( 1.0, establishAll, 5 )
    reactor.callLater( 2.0, randomSend )
    
    reactor.callLater(0.0, giveFeedBack)
    reactor.run()

if __name__ == '__main__':
    
    if sys.argv[1] == 'server':
        testServer()
    else:
        testClient()
    