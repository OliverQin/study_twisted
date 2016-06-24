import numpy as np

__all__ = ['TokenPool']

class TokenPool:
    def __init__(self, bit=32, approxSize=2**17):
        self.bucketSize = 64 
        self.bucketNum = approxSize // self.bucketSize
        
        self.pt = np.zeros( self.bucketNum, dtype=np.uint32 )
        if bit == 32:
            mtype = np.uint32
        elif bit == 64:
            mtype = np.uint64
        elif bit == 16:
            mtype = np.uint16
        else:
            raise Exception('Bit should be 16, 32 or 64!')
        
        self.buckets = np.zeros( (self.bucketNum, self.bucketSize), dtype=mtype )
    
    def __contains__(self, num):
        if (num == 0):
            return True
        
        idx = num % self.bucketNum
        
        return (self.buckets[idx] == num).sum() > 0
    
    def add(self, num):
        idx = num % self.bucketNum
        
        self.buckets[ idx, self.pt[idx] ] = num
        self.pt[idx] = (self.pt[idx] + 1) % self.bucketSize
            
if __name__ == '__main__':
    import random, time, gc
    
    a = set(random.randrange(2**1, 2**32) for _ in range(65536))

    bt = time.time()
    p = TokenPool()
    
    for i in a:
        #print i
        assert (i not in p)
        p.add(i)
    
    for i in a:
        assert (i in p)
    
    et = time.time()
    print et- bt
    
    del a
    gc.collect()
    time.sleep(5)