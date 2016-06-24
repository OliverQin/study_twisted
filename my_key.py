#/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Created on Mon Jun 20 20:53:36 2016

@author: oliver
"""

SymmetricKey = b'H\x97"sp\x1f-M\xff\xe2\xefi\xbfGp\xa6\xe7\x18\x1f\x07\x17\x1bD\x18\xef\x8c\xd5p\xc6\xca\xa7\x90'
#SymmetricKey = b'abcdefghABCDEFGH'
InitVectorPrefix = b'\xbdR\xa0\xbacE\xf6-'

if __name__ == '__main__':
    print len(SymmetricKey)
    print len(InitVectorPrefix)