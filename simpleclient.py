from twisted.internet import reactor, protocol
from se_protocol import SmallEncryptedProtocol
import random, time, hashlib

from securerng import SecureRNG

csprng = SecureRNG()

rdstr = csprng.genStr #lambda x: ''.join( chr(random.randrange(256)) for _ in xrange(x) )
rdsmall = lambda x: ''.join( random.choice('0123456789') for _ in xrange(x) )
# a client protocol
StartTime = time.time()

GlobalCounter = 0

class EchoClient(SmallEncryptedProtocol):
    def __init__(self):
        SmallEncryptedProtocol.__init__(self)
        self.tag = rdsmall( 5 )
        
    def connectionMade(self):
        self.sendSomeChars()
        
    def sendSomeChars(self):
        self.last = []
        self.lastTime = []
        self.lastHash = []
        
        for i in range(5):
            a = rdstr(261000)
            self.last.append( a )
            self.lastTime.append( time.time() )
            self.lastHash.append( hashlib.md5( a ).digest() )
            
            self.sendChunk( a )
        
    def chunkReceived(self, data):
        flag = False
        
        for idx, i in enumerate( self.lastHash ):
            if (i == data):
                print self.tag, 'Data ' + str(idx+1) + ' OK!', 'Time:', time.time() - self.lastTime[idx]
                
                if (idx + 1 == len(self.last)):
                    global GlobalCounter
                    GlobalCounter += 1
                    rt = len(self.last) * len(self.last[0]) * GlobalCounter / (time.time() - StartTime) / 1024.0
                    print 'Upload rate:', '%.2f KB/s' % rt
                
                    reactor.callLater(random.random() * 0.01, self.sendSomeChars)
                flag = True
                
        if not flag:
            print self.tag, 'Data broken!', 'Time:', time.time() - self.lastTime[0]

    def connectionLost(self, reason):
        print "Connection Lost"

class EchoFactory(protocol.ClientFactory):
    protocol = EchoClient

# this connects the protocol to a server running on port 8000
def main():
    for _ in xrange(2):
        f = EchoFactory()
        reactor.connectTCP("127.0.0.1", 8000, f)
        #reactor.connectTCP("23.105.199.44", 8000, f)
    reactor.run()

# this only runs if the module was *not* imported
if __name__ == '__main__':
    main()
