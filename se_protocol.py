
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
An example client. Run simpleserv.py first before running this.
"""

__all__ = ['SmallEncryptedProtocol']

from my_key import InitVectorPrefix, SymmetricKey
import time
from struct import pack, unpack
from twisted.internet import reactor, protocol
import Crypto.Cipher.AES as aes
from token_pool import TokenPool
from securerng import SecureRNG

SmallEncryptedIVPool = TokenPool(bit=64, approxSize=2**16)
SmallEncryptedRNG = SecureRNG()

DeltaOfTimestamp = 300

_SEPMaxChunkSize = 262144

class SmallEncryptedProtocol(protocol.Protocol): 
    def __init__(self):
        self.miniBuffer = ''
        
    def chunkReceived(self, data):
        pass
    
    def sendChunk(self, data):
        if len(data) > _SEPMaxChunkSize:
            return #Ignore
        
        iv = SmallEncryptedRNG.genStr(8)
        cipher = aes.new( SymmetricKey, aes.MODE_CFB, InitVectorPrefix + iv )
        hd = pack('<IIH', len(data), int(time.time()), 23333) #magic num
        packed = cipher.encrypt( hd + data )
        
        toSend = iv + packed
        self.transport.write( toSend )

    def dataReceived(self, data):
        data = self.miniBuffer + data
        self.miniBuffer = ''

        while data:
            if len(data) < 18:
                self.miniBuffer = data
                return
        
            (iv_idx, ) = unpack('<Q', data[:8])
            
            if iv_idx in SmallEncryptedIVPool:
                #Suffering from attack!
                self.miniBuffer = ''
                print 'Under attack'
                return #Ignore
            
            cipher = aes.new( SymmetricKey, aes.MODE_CFB, InitVectorPrefix + data[:8] )
            length, timestamp, magic = unpack('<IIH', cipher.decrypt(data[8:18]) )
            
            if magic != 23333:
                self.miniBuffer = ''
                print 'Under attack'
                return #Ignore
            
            lenData = len(data) - 18
            if (length > lenData or abs(timestamp - time.time()) > DeltaOfTimestamp):
                #Probably this is a replay
                self.miniBuffer = data
                return #Ignore

            SmallEncryptedIVPool.add( iv_idx )
            cipher = aes.new( SymmetricKey, aes.MODE_CFB, InitVectorPrefix + data[:8] )
            decryptedData = cipher.decrypt( data[8:18+length] )
            
            self.chunkReceived( decryptedData[10:] )
            
            data = data[18+length:]

def main():
    for _ in xrange(2):
        f = EchoFactory()
    #reactor.connectTCP("127.0.0.1", 8000, f)
        reactor.connectTCP("23.105.199.44", 8000, f)
    reactor.run()

# this only runs if the module was *not* imported
if __name__ == '__main__':
    main()
