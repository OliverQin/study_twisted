#/usr/bin/env python2
# -*- coding: utf-8 -*-


from twisted.internet import reactor, protocol, defer
import random

def fooA(x):
    a = defer.Deferred()
    
    if random.randrange(1) == 0:
        reactor.callLater(2.5, a.callback, x)
    else:
        reactor.callLater(2.5, a.errback, x)
    
    return a

def bar(x):
    print x
    return x**2

def errbar(x):
    print x, 'Failed'
    return -1

@defer.inlineCallbacks
def fooB():
    t = fooA(5)
    
    #print 'before'
    t.addCallback( bar )
    t.addErrback( errbar )
    
    g = yield t
    
    #print g, 'end'
    
    defer.returnValue( 'end')
    
def fooC():
    a =  fooB()
    print a
    print defer.gatherResults([a])

if __name__ == '__main__':
    reactor.callLater( 0.1, fooC)
    reactor.callLater( 5.0, reactor.stop )
    
    reactor.run()
    
    
    
    
