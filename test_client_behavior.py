#/usr/bin/env python2
# -*- coding: utf-8 -*-


from twisted.internet import reactor, protocol, defer
from twisted.protocols.policies import TimeoutMixin
import random


class ToServerClient(protocol.Protocol, TimeoutMixin):
    def __init__(self):
        self.setTimeout(5)
        self.resetTimeout()
    
    def timeoutConnection(self):
        print 'Timeout'
        #self.transport.loseConnection()
         
    def connectionMade(self):     
        print 'Made'
        self.transport.loseConnection()
    
    def dataReceived(self, data):
        print 'Rec'
    
    def connectionLost(self, reason):
        print 'Lost'
        
        
        
if __name__ == '__main__':
    ft = protocol.ClientFactory()
    ft.protocol = ToServerClient
    
    reactor.connectTCP('www.baidu.com', 80, ft)
    
    reactor.run()