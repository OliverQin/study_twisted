#!/usr/bin/env python2
#-*- coding: UTF-8 -*-

from twisted.internet.protocol import Protocol, Factory, ClientFactory
from over_wall import OverWallControlProtocol
from twisted.internet import reactor, protocol, defer
import random, struct
from my_conn_pool import MyConnectionPool
from twisted.protocols.policies import TimeoutMixin
from cachedict import CacheDict
from my_data_buffer import MyDataBuffer
from securerng import SecureRNG

ClientProtocolConnectionPool = set() #Contain protocols
ClientProtocolRNG = SecureRNG()
ClientProtocolIdxPool = MyConnectionPool(1000)
ClientFeedbackBuffer = [] #(idx, seq, status)

ClientOldConnections = dict()

ClientToClientBuffer = MyDataBuffer()
ClientToServerBuffer = MyDataBuffer()

_ClientSideTimeout = 60
_ClientSideFeedbackInterval = 5.0
_ClientSideCloseRetry = 2.0

_ClientSideOldIdxCounter = 0
_ClientMinPoolSize = 15

ProxyHost, ProxyPort = '127.0.0.1', 8555

def chooseRandomProxyConnection():
    if len(ClientProtocolConnectionPool) > 0:
        return random.choice( list(ClientProtocolConnectionPool) )
    else:
        return None
    
def giveFeedBack():
    g = chooseRandomProxyConnection()
    if g is not None:
        global ClientFeedbackBuffer
        
        g.sendFeedback( ClientFeedbackBuffer )
        ClientFeedbackBuffer = []
    
    reactor.callLater( _ClientSideFeedbackInterval, giveFeedBack )
    
class ProxyClientProtocol(OverWallControlProtocol):
    def connectionMade(self):
        ClientProtocolConnectionPool.add( self )
           
    def sendToRemote(self, idx, seq, data):
        if idx not in ClientProtocolIdxPool:
            print idx, 'error'
            ClientFeedbackBuffer.append( (idx, seq, 0x3) ) #no idx
            return
        
        ClientToClientBuffer.setValue(idx, seq, data)
        nseq = ClientProtocolIdxPool.getDownloadSeq(idx)

        if (seq == nseq):
            obj = ClientProtocolIdxPool.getObject(idx)
                        
            while True:
                nseq = ClientProtocolIdxPool.getDownloadSeq(idx)
                if (idx, nseq) in ClientToClientBuffer:
                    ndata = ClientToClientBuffer[ idx, nseq ]
                    obj.transport.write( ndata )
                    ClientProtocolIdxPool.downloadOne(idx)
                    
                    ClientFeedbackBuffer.append( (idx, nseq, 0x0) )
                    ClientToClientBuffer.popValue( idx, nseq )
                else:
                    break
            
            return

        elif (seq > nseq):
            ClientFeedbackBuffer.append( (idx, nseq, 0x2) ) #We need this
        
        else: 
            ClientFeedbackBuffer.append( (idx, seq, 0x1) ) #Already have

    def closeRemoteConnection(self, idx):
        #return status
        if (idx not in ClientProtocolIdxPool):
            return 1 #already closed
        else:
            obj = ClientProtocolIdxPool.getObject(idx)
            obj.transport.loseConnection()
            
            g = [(i, seq) for (i, seq) in ClientToClientBuffer if i == idx]
            
            if len(g) > 0:
                print idx, 'Not cleaned'
                for i, j in g:
                    ClientToClientBuffer.popValue(i, j)
            
            return 0
        
    def gotSendFeedback(self, feedbacks):
        #print feedbacks
        for idx, seq, status in feedbacks:
            if (status == 0x0 or status == 0x1) and (idx, seq) in ClientToServerBuffer:
                seqs = [i for i in ClientToServerBuffer.getSeqsByIndex(idx) if i <= idx]
                for i in seqs:
                    ClientToServerBuffer.popValue( idx, i )
                
            if status == 0x2 and (idx, seq) in ClientToServerBuffer:
                self.sendToEndpoint( idx, seq, ClientToServerBuffer[idx, seq] )
            
            if status == 0x3:
                print 'error'
                for i in ClientToServerBuffer.getSeqsByIndex(idx):
                    ClientToServerBuffer.popValue( idx, i )
    
    def closingRemoteDone(self, idx, status):
        pass #Ignore
    
    def connectionLost(self, reason):
        ClientProtocolConnectionPool.remove( self )
        
    def establishDone(self, oldIdx, newIdx, status):
        print 'ed', oldIdx, newIdx, status
        if status != 0: #failed
            ClientOldConnections[oldIdx].transport.loseConnection()
            ClientOldConnections.pop(oldIdx)
        
        else: #success
            obj = ClientOldConnections.pop(oldIdx)
            ClientProtocolIdxPool.reg( newIdx, obj )
            ClientToClientBuffer.add( newIdx )
            ClientToServerBuffer.add( newIdx )
            obj.idx = newIdx
            
            obj.serverConnectionMade( '127.0.0.1', 55555 )

class LightSocks5Server(Protocol):
    WaitingHandshake = 1
    WaitingRequest = 2
    Transferring = 3
    
    def __init__(self):
        self.connectionStage = self.WaitingHandshake
        self.idx = None
        
        self.tag = random.randrange(2**31+1, 2**32)
        
        global _ClientSideOldIdxCounter
        _ClientSideOldIdxCounter = (_ClientSideOldIdxCounter+1) & 0xFfFfFfFf
        self.oldIdx = _ClientSideOldIdxCounter
        
    def serverConnectionMade(self, addr, port):
        reply = b"\x05\x00\x00\x03"
        reply += chr(len(addr)) + addr + struct.pack("!H", int(port))
        
        self.transport.write(reply)
        
    def dataReceived(self, data):
        if len(ClientProtocolConnectionPool) < _ClientMinPoolSize:
            g = protocol.ClientFactory()
            g.protocol = ProxyClientProtocol
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

                ClientOldConnections[self.oldIdx] = self
                
                proxyConn = chooseRandomProxyConnection()
                proxyConn.requestEstablish( self.oldIdx, addr, port )
                
                self.connectionStage = self.Transferring
            else: 
                print 'Not supported command'
                reply = b'\x05\x07\x00\x01' # Command not supported
                self.transport.close()
        else: #Transferring
            if self.idx is not None:
                idx = self.idx
                proxyConn = chooseRandomProxyConnection()
                
                seq = ClientProtocolIdxPool.uploadOne(idx)
                ClientToServerBuffer.setValue( idx, seq, data )
                
                proxyConn.sendToEndpoint( self.idx, seq, data )

    def connectionLost(self, reason):
        if self.idx in ClientProtocolIdxPool:
            if ClientToServerBuffer.getLengthByIndex(self.idx) == 0 and \
                ClientToClientBuffer.getLengthByIndex(self.idx) == 0:
                    
                ClientToServerBuffer.pop(self.idx)
                ClientToClientBuffer.pop(self.idx)
                
                ClientProtocolIdxPool.unreg(self.idx)
                
                proxyConn = chooseRandomProxyConnection()
                if proxyConn:
                    proxyConn.requestClose( self.idx )
                else:
                    print 'No conn?'
                    pass
                            
                print self.idx, 'Successfully closed'
            else:
                reactor.callLater( _ClientSideCloseRetry, self.connectionLost, reason )

def main():
    f = Factory()
    f.protocol = LightSocks5Server
        
    reactor.listenTCP(8000, f)
    
    reactor.callLater(0.0, giveFeedBack)
    reactor.run()

if __name__ == '__main__':
    main()
 