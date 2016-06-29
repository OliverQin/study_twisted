#!/usr/bin/env python2
#-*- coding: UTF-8 -*-

__all__ = ['OverWallControlProtocol']

from twisted.internet.protocol import Protocol, Factory, ClientFactory
from twisted.protocols.policies import TimeoutMixin
from twisted.internet import reactor, protocol, defer

from se_protocol import SmallEncryptedProtocol
from struct import pack, unpack
import random, hashlib, sys, struct, gc
from securerng import SecureRNG


_OverWallFeedbackInterval = 1.5
_OverWallRetryInterval = 15.0
_OverWallTimeout = 60
_OverWallCloseRetry = 2.0
_OverWallMinPoolSize = 5

ProxyHost, ProxyPort = '23.105.199.44', 8555

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
    
    def objectById(self, idx):
        return self.data[idx].obj
    
    def pop(self, idx):
        if idx in self:
            return self.data.pop(idx)
        else:
            return None
        
    def __getitem__(self, idx):
        return self.data[idx]
        
    def __contains__(self, idx):
        return idx in self.data
    
    def isClearToEndpoint(self, idx):
        return len( self.data[idx].bufs[ self.data[idx].SentToEndpoint ] ) == 0
    
    def clearToEndpoint(self, idx):
        self.data[idx].bufs[ self.data[idx].SentToEndpoint ].clear()


OverWallRNG = SecureRNG()
OverWallConnections = ConnectionManager()
OverWallPool = set()
OverWallFeedbacks = list()
ClientPool = dict()

'''GlobalSwitch = False

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
        a = 4
        
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
    
    reactor.callLater(2.0, randomSend)'''

def collectAllGarbage():
    gc.collect()
    
    if len(OverWallPool) == 0:
        OverWallConnections.data = dict()
        global OverWallFeedbacks
        OverWallFeedbacks = list()
        ClientPool.clear()

def dataToRemoteReceived(idx, seq, data):
    if (idx not in OverWallConnections):
        OverWallFeedbacks.append( idx, seq, 0x3 )
        return #cannot be sent

    nseq = OverWallConnections[idx].seqSentToRemote()
    if (seq >= nseq):
        OverWallFeedbacks.append( (idx, seq, 0) )
    else:
        #TODO: Revise this, make it more reasonable
        OverWallFeedbacks.append( (idx, seq, 1) )
    
    while nseq in OverWallConnections[idx].bufferSentToRemote():
        data = OverWallConnections[idx].dataSentToRemote(nseq)
        #print "{0:#08x}".format(idx), "{0:#02x}".format(nseq), hashlib.md5(data).hexdigest(), 'Rcv'
        
        OverWallConnections.objectById(idx).transport.write(data)
        
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
    collectAllGarbage()
    g = chooseRandomOverWallConnection()
    if g is not None:
        global OverWallFeedbacks
        
        g.sendFeedback( OverWallFeedbacks )
        OverWallFeedbacks = []
    
    reactor.callLater( _OverWallFeedbackInterval, giveFeedBack )

class ToServerClient(protocol.Protocol, TimeoutMixin):
    def __init__(self, idx):
        self.idx = idx
        self.setTimeout(_OverWallTimeout)
        
    def connectionMade(self):       
        chooseRandomOverWallConnection().remoteConnectionDone(self.idx, 0, self)

    def timeoutConnection(self):
        chooseRandomOverWallConnection().remoteConnectionDone(self.idx, 1, self)
    
    def dataReceived(self, data):
        chooseRandomOverWallConnection().sendToEndpoint(self.idx, data)

    def connectionLost(self, reason):
        a = chooseRandomOverWallConnection().requestClose(self.idx)
        if (a != 0):
            reactor.callLater( _OverWallCloseRetry, self.connectionLost, reason )

class OverWallControlProtocol(SmallEncryptedProtocol):
    def __init__(self):
        SmallEncryptedProtocol.__init__(self)
        OverWallPool.add(self)
    
    def remoteConnectionDone(self, idx, status, obj):
        self.sendChunk( '\xfe' + pack('<BI', status, idx) )
        
        if status == 0:
            OverWallConnections.add(idx, obj)

    def establishConnection(self, idx, addr, port):
        #print "{0:#08x}".format(idx), 'Req'
        
        if (idx in OverWallConnections):
            self.sendChunk( '\xfe\x02' + pack('<I', idx) ) #already used idx
        else:
            ct = lambda: ToServerClient( idx )
            ft = protocol.ClientFactory()
            ft.protocol = ct
            
            reactor.connectTCP( addr, port, ft )
        
    def requestEstablish(self, idx, addr, port):
        self.sendChunk( '\x01' + pack('<IH', idx, port) + addr )
        
    def establishDone(self, idx, status):
        if (idx in ClientPool):
            j = ClientPool.pop(idx)
            if (status == 0):
                OverWallConnections.add(idx, j)
                j.serverConnectionMade('127.0.0.1', 666, 0)
            else:
                j.serverConnectionMade('127.0.0.1', 666, status)
        else:
            pass
            #print idx, '?', idx in OverWallConnections
            
    def gotSendFeedback(self, feedbacks):
        'From endpoint'
        for idx, seq, status in feedbacks:
            if (status == 0x0 or status == 0x1) and (idx in OverWallConnections):
                if seq in OverWallConnections[idx].bufferSentToEndpoint():
                    #print "{0:#08x}".format(idx), "{0:#02x}".format(seq), 'SucSnt'
                    OverWallConnections[idx].bufferSentToEndpoint().pop(seq)
            elif (status == 0x3) and idx in OverWallConnections:
                #OverWallConnections[idx].clearToEndpoint()
                OverWallConnections.pop(idx)
                
    def sendFeedback(self, feedbacks):
        if len(feedbacks) == 0:
            return
        
        res = '\xfd'
        for (idx, seq, status) in feedbacks:
            res += pack( '<IIB', idx, seq, status )
        self.sendChunk( res )
        
    def sendToRemote(self, idx, seq, data):
        if idx in OverWallConnections:
            OverWallConnections[idx].bufferSentToRemote()[seq] = data
            dataToRemoteReceived(idx, seq, data) 
    
    def closeRemoteConnection(self, idx):
        OverWallConnections.pop(idx)
        return 0

    def requestClose(self, idx):
        if idx not in OverWallConnections or OverWallConnections.isClearToEndpoint(idx):
            self.sendChunk( '\x03' + pack('<I', idx) )
            return 0
        else:
            return -1
    
    def closingRemoteDone(self, idx, status):
        OverWallConnections.pop(idx)
        #print "{0:#08x}".format(idx), 'Cld'
    
    def sendHeartBeat(self):
        self.sendChunk( '\x04' + ''.join( chr(random.randrange(256)) for _ in xrange(9) ) )
    
    def sendToEndpoint(self, idx, data, seq=None):
        if idx not in OverWallConnections:
            return
        
        if seq is None:
            seq = OverWallConnections[idx].addSentToEndpoint()
        else:
            if idx not in OverWallConnections or \
                seq not in OverWallConnections[idx].bufferSentToEndpoint():
                return #Success
            
        OverWallConnections[idx].bufferSentToEndpoint()[seq] = data
        #print "{0:#08x}".format(idx), "{0:#02x}".format(seq), hashlib.md5(data).hexdigest(), 'Snt'
        
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

class LightSocks5Server(Protocol):
    WaitingHandshake = 1
    WaitingRequest = 2
    Transferring = 3
    
    def __init__(self):
        self.connectionStage = self.WaitingHandshake
        self.idx = OverWallRNG.genUint32()
        
        self.tag = random.randrange(2**31+1, 2**32)
        
    def serverConnectionMade(self, addr, port, status):
        if status == 0:
            reply = b"\x05\x00\x00\x03" #OK
        elif status == 2:
            reply = b'\x05\x01\x00\x03' #same idx = general error
        else:
            reply = b'\x05\x04\x00\x03' #unreachable
        reply += chr(len(addr)) + addr + struct.pack("!H", int(port))
        
        self.transport.write(reply)
        
    def dataReceived(self, data):
        if len(OverWallPool) < _OverWallMinPoolSize:
            g = protocol.ClientFactory()
            g.protocol = OverWallControlProtocol
            reactor.connectTCP(ProxyHost, ProxyPort, g)
            reactor.callLater( 0.02, self.dataReceived, data)
            return
                    
        if self.connectionStage == self.WaitingHandshake:
            reply = b'\x05\x00'
            self.connectionStage = self.WaitingRequest
            self.transport.write(reply)

        elif self.connectionStage == self.WaitingRequest:
            mode, addrtype = ord(data[1]), ord(data[3])
            data = data[4:]

            if addrtype == 1:       # IPv4
                addr = socket.inet_ntoa(data[0:4])
                data = data[4:]
            elif addrtype == 3:     # Domain name
                datalen = ord(data[0])
                addr = data[1:datalen+1]
                data = data[datalen+1:]
            else:
                #print 'Not supported IP class'
                reply = b'\x05\x07\x00\x01' # Command not supported
                self.transport.write(reply)
                self.transport.loseConnection()
                return
            
            port = struct.unpack('!H', data[0:2])[0]

            if mode == 1:
                print '[xx] Connecting to: (%s, %d)' % (str(addr), port)

                ClientPool[self.idx] = self

                chooseRandomOverWallConnection().requestEstablish( self.idx, addr, port )
                
                self.connectionStage = self.Transferring
            else: 
                print 'Not supported command'
                reply = b'\x05\x07\x00\x01' # Command not supported
                self.transport.close()
        else: #Transferring
            chooseRandomOverWallConnection().sendToEndpoint( self.idx, data )

    def connectionLost(self, reason):
        a = chooseRandomOverWallConnection().requestClose(self.idx)
        if (a != 0):
            reactor.callLater( _OverWallCloseRetry, self.connectionLost, reason )


def testServer():
    f = Factory()
    f.protocol = OverWallControlProtocol
    reactor.listenTCP(ProxyPort, f)
    
    reactor.callLater(0.0, giveFeedBack)
    reactor.run()

def testClient():
    """for _ in range(10):
        f = ClientFactory()
        f.protocol = OverWallControlProtocol
            
        #reactor.connectTCP('23.105.199.44', 8555, f)
        reactor.connectTCP('127.0.0.1', 8555, f)
    
    reactor.callLater( 1.0, establishAll, 5 )
    reactor.callLater( 2.0, randomSend )
    
    reactor.callLater(0.0, giveFeedBack)
    reactor.run()"""
    
    f = Factory()
    f.protocol = LightSocks5Server
        
    reactor.listenTCP(1081, f)
    
    reactor.callLater(0.0, giveFeedBack)
    reactor.run()

if __name__ == '__main__':
    
    if sys.argv[1] == 'server':
        testServer()
    else:
        testClient()
    