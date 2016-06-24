
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet import reactor, protocol
from se_protocol import SmallEncryptedProtocol
import hashlib

class Echo(SmallEncryptedProtocol):
    def chunkReceived(self, data):
        #print len(data), hashlib.md5( data ).hexdigest()
        self.sendChunk ( hashlib.md5( data ).digest() )

def main():
    """This runs the protocol on port 8000"""
    factory = protocol.ServerFactory()
    factory.protocol = Echo
    reactor.listenTCP(8000, factory)
    reactor.run()

# this only runs if the module was *not* imported
if __name__ == '__main__':
    main()
