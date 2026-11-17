"""Original gentle children’s background music, generated locally without APIs.

This synthesizes a simple original pentatonic instrumental accompaniment.
No copyrighted recordings, external downloads, or subscriptions.
"""
from __future__ import annotations

import hashlib
import math
import struct
import wave
from pathlib import Path

def create_music(path: Path, seconds: float, seed_text: str) -> Path:
    """Render a soft bell/music-box bed. Safe for mixing underneath narrator."""
    path.parent.mkdir(parents=True,exist_ok=True)
    rate=12000
    notes=[0,2,4,7,9,12,9,7,4,2,0,7,9,4,2,0]
    base=220 * 2**((int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:2],'big')%5)/12)
    total=max(1,int(seconds*rate))
    chunk=rate*4
    with wave.open(str(path),'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        for start in range(0,total,chunk):
            length=min(chunk,total-start)
            samples=bytearray(length*2)
            for i in range(length):
                t=(start+i)/rate
                beat=int(t/0.58)
                note=notes[beat%len(notes)]
                freq=base*2**(note/12)
                envelope=math.exp(-2.5*(t%0.58))
                bell=(math.sin(2*math.pi*freq*t)
                      +0.23*math.sin(2*math.pi*freq*2*t))
                bass_freq=base/2*2**([0,5,7,0][int(t/4.64)%4]/12)
                bass=0.20*math.sin(2*math.pi*bass_freq*t)
                volume=(0.22*bell*envelope + bass)*0.19
                struct.pack_into('<h',samples,i*2,max(-32767,min(32767,int(volume*32767))))
            output.writeframesraw(samples)
    return path
