#!/usr/bin/env python2
#-*- coding: UTF-8 -*-

from twisted.internet.protocol import Protocol, Factory, ClientFactory
from over_wall import OverWallControlProtocol
from twisted.internet import reactor, protocol, defer
import random
from struct import pack, unpack
from my_conn_pool import MyConnectionPool
from twisted.protocols.policies import TimeoutMixin
from cachedict import CacheDict
from my_data_buffer import MyDataBuffer
from securerng import SecureRNG

ServerProtocolConnectionPool = set() #Contain protocols
ServerProtocolRNG = SecureRNG()
ServerProtocolIdxPool = MyConnectionPool(1000)
ServerFeedbackBuffer = [] #(idx, seq, status)

ServerToServerBuffer = MyDataBuffer()
ServerToClientBuffer = MyDataBuffer()

_ServerSideTimeout = 60
_ServerSideFeedbackInterval = 5.0
_ServerSideCloseRetry = 2.0

def chooseRandomProxyConnection():
    if len(ServerProtocolConnectionPool) > 0:
        return random.choice( list(ServerProtocolConnectionPool) )
    else:
        return None
    
def giveFeedBack():
    g = chooseRandomProxyConnection()
    if g is not None:
        global ServerFeedbackBuffer
        
        g.sendFeedback( ServerFeedbackBuffer )
        ServerFeedbackBuffer = []
    
    reactor.callLater( _ServerSideFeedbackInterval, giveFeedBack )

class ToServerClient(protocol.Protocol, TimeoutMixin):
    def __init__(self, idx, connDefer):
        self.idx = idx
        self.connectionMadeDefer = connDefer
        
        self.setTimeout(_ServerSideTimeout)
        
    def connectionMade(self):        
        self.connectionMadeDefer.callback( (0, self) ) #success
        self.setTimeout(None)

    def timeoutConnection(self):
        self.connectionMadeDefer.callback( (1, None) ) #time out
    
    def dataReceived(self, data):
        idx = self.idx
        seq = ServerProtocolIdxPool.downloadOne(idx)
        
        ServerToClientBuffer.setValue( idx, seq, data )
        g = chooseRandomProxyConnection()
        
        if (g is not None):
            g.sendToEndpoint(idx, seq, data)
        #proxyConn = random.choice( list(GlobalPCConnections) )
        #proxyConn.serverDataReceived(self.idx, data)
    
    def connectionLost(self, reason):
        if ServerToClientBuffer.getLengthByIndex(self.idx) == 0 and \
            ServerToServerBuffer.getLengthByIndex(self.idx) == 0:
            ServerToClientBuffer.pop(self.idx)
            ServerToServerBuffer.pop(self.idx)
            
            ServerProtocolIdxPool.unreg(self.idx)
            proxyConn = chooseRandomProxyConnection()
            if proxyConn:
                proxyConn.requestClose( self.idx )
            else:
                print 'No conn?'
                pass
                           
            
            print self.idx, 'Successfully closed'
        else:
            reactor.callLater( _ServerSideCloseRetry, self.connectionLost, reason )
        #pass
        #proxyConn = random.choice( list(GlobalPCConnections) )
        #proxyConn.serverConnectionLost(self.idx, reason)

class ProxyServerProtocol(OverWallControlProtocol):
    def connectionMade(self):
        ServerProtocolConnectionPool.add( self )
    
    @defer.inlineCallbacks
    def establishConnection(self, oldIdx, addr, port):
        #return (status, newIdx)
        idx = ServerProtocolRNG.genUint32()
        while idx in ServerProtocolIdxPool:
            idx = ServerProtocolRNG.genUint32()
        
        a = defer.Deferred()
        a.addCallback( lambda x: x )
        
        ct = lambda: ToServerClient( idx, a )
        ft = protocol.ClientFactory()
        ft.protocol = ct
        
        reactor.connectTCP( addr, port, ft )
        
        status, obj = yield a
        
        if (status == 0): #success
            ServerProtocolIdxPool.reg(idx, obj)
            ServerToClientBuffer.add( idx )
            ServerToServerBuffer.add( idx )

            self.sendChunk( '\xfe' + pack('<BII', status, oldIdx, idx) )
        else:
            self.sendChunk( '\xfe' + pack('<BII', status, oldIdx, 0xFFFFFFFF) )
        
        return
        
    def sendToRemote(self, idx, seq, data):
        if idx not in ServerProtocolIdxPool:
            ServerFeedbackBuffer.append( (idx, seq, 0x3) ) #no idx
            return
        
        ServerToServerBuffer.setValue(idx, seq, data)
        nseq = ServerProtocolIdxPool.getUploadSeq(idx)

        if (seq == nseq):
            obj = ServerProtocolIdxPool.getObject(idx)
                        
            while True:
                nseq = ServerProtocolIdxPool.getUploadSeq(idx)
                if (idx, nseq) in ServerToServerBuffer:
                    ndata = ServerToServerBuffer[ idx, nseq ]
                    obj.transport.write( ndata )
                    ServerProtocolIdxPool.uploadOne(idx)
                    
                    ServerFeedbackBuffer.append( (idx, nseq, 0x0) )
                    ServerToServerBuffer.popValue( idx, nseq )
                else:
                    break
            
            return

        elif (seq > nseq):
            ServerFeedbackBuffer.append( (idx, nseq, 0x2) ) #We need this
        
        else: 
            ServerFeedbackBuffer.append( (idx, seq, 0x1) ) #Already have

    def closeRemoteConnection(self, idx):
        #return status
        if (idx not in ServerProtocolIdxPool):
            return 1 #already closed
        else:
            obj = ServerProtocolIdxPool.getObject(idx)
            obj.transport.loseConnection()
            
            g = [(i, seq) for (i, seq) in ServerToServerBuffer if i == idx]
            
            if len(g) > 0:
                print idx, 'Not cleaned'
                for i, j in g:
                    ServerToServerBuffer.popValue(i, j)
                    
            return 0
        
    def gotSendFeedback(self, feedbacks):
        for idx, seq, status in feedbacks:
            if (status == 0x0 or status == 0x1) and (idx, seq) in ServerToClientBuffer:
                seqs = [i for i in ServerToClientBuffer.getSeqsByIndex(idx) if i <= idx]
                for i in seqs:
                    ServerToClientBuffer.popValue( idx, i )
                
            if status == 0x2 and (idx, seq) in ServerToClientBuffer:
                self.sendToEndpoint( idx, seq, ServerToClientBuffer[idx, seq] )
            
            if status == 0x3:
                print 'error'
                for i in ServerToClientBuffer.getSeqsByIndex(idx):
                    ServerToClientBuffer.popValue( idx, i )
    
    def closingRemoteDone(self, idx, status):
        pass #Ignore
    
    def connectionLost(self, reason):
        ServerProtocolConnectionPool.remove( self )

def main():
    f = Factory()
    f.protocol = ProxyServerProtocol
    reactor.listenTCP(8555, f)
    
    reactor.callLater(0.0, giveFeedBack)
    reactor.run()

if __name__ == '__main__':
    main()
