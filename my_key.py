#/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Created on Mon Jun 20 20:53:36 2016

@author: oliver
"""

SymmetricKey = b'abcdefghABCDEFGH'
InitVectorPrefix = b"77889922"

if __name__ == '__main__':
    assert len(SymmetricKey) in [16, 24, 32]
    assert len(InitVectorPrefix) == 8