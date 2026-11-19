"""Original evolving soundtrack for the Anima Studio children's adventures.

Each episode gets a deterministic original theme from the planet, storyline
and episode identifier. Entirely local synthesis, no licensed audio samples.
"""
from __future__ import annotations

import hashlib
import math
import struct
import wave
from pathlib import Path

SCALE=(0,2,4,7,9,12,14,16,19)
PROGRESSIONS=(
    (0,5,7,4),(0,4,7,2),(0,7,5,4),
    (0,2,5,7),(0,5,2,7),(0,4,5,7),
)
PATTERNS=(
    (0,2,4,5,4,2,1,0,3,2,4,6,5,3,2,0),
    (0,3,4,2,5,4,2,1,0,2,6,4,3,2,1,0),
    (0,2,5,4,3,6,4,2,0,1,4,5,6,4,2,1),
    (0,4,2,3,5,7,6,3,1,2,4,6,5,3,2,0),
)
TEMPO=(100,108,112,120,126,132)

def soundtrack_identity(seed_text:str) -> dict:
    """Stable but different musical choices for each original episode."""
    digest=hashlib.sha256(str(seed_text).encode("utf-8")).digest()
    return {
        "theme_id":digest[:6].hex(),
        "tempo_bpm":TEMPO[digest[0]%len(TEMPO)],
        "melody":PATTERNS[digest[1]%len(PATTERNS)],
        "progression":PROGRESSIONS[digest[2]%len(PROGRESSIONS)],
        "root_hz":196.0*2**((digest[3]%9)/12),
        "bright":bool(digest[4]%2),
        "swing":(digest[5]%4)/40,
    }


def create_music(path:Path,seconds:float,seed_text:str) -> Path:
    """Synthesized playful music-box/marimba with soft bass and rhythm.

    The arrangement changes across episodes, while keeping narration in
    focus. This produces no recognizable commercial melody or recording.
    """
    path.parent.mkdir(parents=True,exist_ok=True)
    identity=soundtrack_identity(seed_text)
    rate=12000
    total=max(1,round(seconds*rate))
    chunk=rate*3
    sec_per_beat=60/identity["tempo_bpm"]
    melody=identity["melody"]
    progression=identity["progression"]
    base=identity["root_hz"]
    with wave.open(str(path),"wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        for start in range(0,total,chunk):
            count=min(chunk,total-start)
            pcm=bytearray(count*2)
            for i in range(count):
                t=(start+i)/rate
                beat=int(t/sec_per_beat)
                position=t/sec_per_beat-beat
                degree=melody[beat%len(melody)]%len(SCALE)
                freq=base*2**(SCALE[degree]/12)
                if identity["bright"]:
                    bell=math.sin(2*math.pi*freq*t)+.19*math.sin(2*math.pi*2*freq*t)
                else:
                    bell=.82*math.sin(2*math.pi*freq*t)+.22*math.sin(2*math.pi*3*freq*t)
                sparkle=bell*math.exp(-4.5*position)
                chord=progression[(beat//4)%4]
                bass_freq=base*.5*2**(chord/12)
                bass=math.sin(2*math.pi*bass_freq*t)*(.65+.35*math.sin(math.pi*position))
                # Soft percussive ticking supports a playful mood, never harsh.
                hit=math.exp(-16*position)*math.sin(2*math.pi*120*t)
                off=math.exp(-20*((position-.5)%1))*.12*math.sin(2*math.pi*520*t)
                warm=.12*math.sin(2*math.pi*(base*.75)*t)
                fade=min(1.0,t/1.5,max(0.0,(seconds-t)/1.8))
                value=(.19*sparkle+.07*bass+.016*hit+.009*off+.025*warm)*fade
                value=max(-.9,min(.9,value))
                struct.pack_into("<h",pcm,i*2,int(value*32767))
            wav.writeframesraw(pcm)
    return path
