from __future__ import annotations
import time
from collections import defaultdict,deque
from threading import Lock
class SlidingWindowLimiter:
    def __init__(self):self._hits=defaultdict(deque);self._lock=Lock()
    def allow(self,key:str,limit:int,window:float=60.0)->tuple[bool,int]:
        now=time.monotonic();cut=now-window
        with self._lock:
            q=self._hits[key]
            while q and q[0]<cut:q.popleft()
            if len(q)>=limit:return False,max(1,int(window-(now-q[0])))
            q.append(now);return True,0
limiter=SlidingWindowLimiter()
