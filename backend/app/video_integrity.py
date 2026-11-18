"""FFprobe validation and timestamp-safe concatenation for Anima Studio.

Never stream-copy heterogeneous segments (e.g. intro/stories/outro).
Stream copy can produce misleading MP4 duration, blank frames and lost audio.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def probe_media(path: Path) -> dict:
    path=Path(path)
    if not path.is_file() or path.stat().st_size<1000:
        raise RuntimeError("Arquivo de vídeo não encontrado ou vazio: "+str(path))
    process=subprocess.run(
        ["ffprobe","-v","error","-show_entries",
         "format=duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate,duration",
         "-of","json",str(path)],
        capture_output=True,text=True,timeout=35,
    )
    if process.returncode:
        raise RuntimeError("FFprobe não consegue ler "+path.name+": "+
                           process.stderr[-400:])
    data=json.loads(process.stdout)
    try: duration=float(data.get("format",{}).get("duration") or 0)
    except (TypeError,ValueError): duration=0
    streams=data.get("streams") or []
    video=next((s for s in streams if s.get("codec_type")=="video"),None)
    audio=next((s for s in streams if s.get("codec_type")=="audio"),None)
    return {"duration":duration,"video":video,"audio":audio,
            "size_bytes":path.stat().st_size}


def validate_video(path:Path, *, require_audio:bool=True,
                   min_seconds:float=0.1,
                   expected_seconds:float|None=None,
                   tolerance_seconds:float=2.0) -> dict:
    info=probe_media(path)
    if not info["video"] or info["duration"]<min_seconds:
        raise RuntimeError("Vídeo incompleto ou sem trilha de vídeo: "+Path(path).name)
    if require_audio and not info["audio"]:
        raise RuntimeError("Arquivo sem áudio: "+Path(path).name)
    if expected_seconds is not None and abs(info["duration"]-expected_seconds)>tolerance_seconds:
        raise RuntimeError(
            f"Duração incorreta em {Path(path).name}: "
            f"{info['duration']:.1f}s (esperado {expected_seconds:.1f}s). "
            "Possível falha na concatenação dos quadros."
        )
    return info


def verify_audible_audio(path:Path, *, segment_seconds:float=20) -> float:
    """Verify decoded output contains audible samples, not only an AAC header."""
    info=validate_video(path,require_audio=True)
    # Sample both the beginning and middle of the program. The second check
    # catches a working intro followed by unexpectedly silent narration.
    length=info["duration"]
    offsets=[0.0,max(0.0,length*.50-segment_seconds*.5)]
    peaks=[]
    for offset in offsets:
        proc=subprocess.run(
            ["ffmpeg","-hide_banner","-nostats","-v","info",
             "-ss",f"{offset:.3f}","-t",str(segment_seconds),
             "-i",str(path),"-vn","-af","volumedetect",
             "-f","null","-"],
            capture_output=True,text=True,timeout=90,
        )
        if proc.returncode:
            raise RuntimeError("Não foi possível decodificar o áudio: "+
                               proc.stderr[-320:])
        match=re.search(r"max_volume:\s*(-?inf|-?[0-9.]+) dB",proc.stderr)
        if match:
            peaks.append(float(match.group(1)))
    if not peaks or max(peaks)<-65:
        raise RuntimeError(
            "O arquivo tem trilha AAC, mas o áudio está mudo ou quase inaudível."
        )
    # The middle of the movie should also contain audible narration or music.
    if len(peaks)>1 and peaks[1]<-65:
        raise RuntimeError("A vinheta tem som, mas o trecho principal está mudo.")
    return peaks[1] if len(peaks)>1 else peaks[0]


def concat_video_only(clips:list[Path],target:Path,fps:int) -> dict:
    """Build CFR video from individually timestamp-reset source clips."""
    if not clips:
        raise ValueError("Não há segmentos de vídeo para montar.")
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    verified=[validate_video(Path(p),require_audio=False) for p in clips]
    expected=sum(i["duration"] for i in verified)
    args=["ffmpeg","-y","-hide_banner","-loglevel","error"]
    for p in clips:
        args += ["-i",str(p)]
    parts=[
        f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps={fps},"
        f"format=yuv420p[v{i}]"
        for i in range(len(clips))
    ]
    parts.append("".join(f"[v{i}]" for i in range(len(clips)))+
                 f"concat=n={len(clips)}:v=1:a=0[v]")
    args += [
        "-filter_complex",";".join(parts),"-map","[v]",
        "-r",str(fps),"-fps_mode","cfr",
        "-c:v","libx264","-preset","ultrafast","-crf","21",
        "-pix_fmt","yuv420p","-an","-movflags","+faststart",
        str(target),
    ]
    result=subprocess.run(args,capture_output=True,text=True,timeout=1800)
    if result.returncode:
        raise RuntimeError("Falha ao unir quadros: "+result.stderr[-1800:])
    return validate_video(target,require_audio=False,
                          expected_seconds=expected,
                          tolerance_seconds=max(1.5,len(clips)/fps+.5))


def concat_with_audio(clips:list[Path],target:Path,*,fps:int=24) -> dict:
    """Concatenate videos with different encoder settings by resetting A/V clocks.

    Each input must contain an audio stream, so narration can never disappear
    without a clear error before the output is marked as done.
    """
    if not clips:
        raise ValueError("Nenhum trecho para montagem do vídeo final.")
    target=Path(target)
    verified=[validate_video(Path(p),require_audio=True) for p in clips]
    expected=sum(i["duration"] for i in verified)
    first=verified[0]["video"]
    width=int(first["width"]);height=int(first["height"])
    args=["ffmpeg","-y","-hide_banner","-loglevel","error"]
    for p in clips:
        args+=["-i",str(p)]
    filters=[]
    for index in range(len(clips)):
        filters.append(
            f"[{index}:v]settb=AVTB,setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:flags=lanczos,setsar=1,"
            f"fps={fps},format=yuv420p[v{index}]"
        )
        filters.append(
            f"[{index}:a]aresample=async=1:first_pts=0,"
            f"asetpts=PTS-STARTPTS,aformat=sample_rates=48000:"
            f"channel_layouts=stereo[a{index}]"
        )
    filters.append(
        "".join(f"[v{index}][a{index}]" for index in range(len(clips)))+
        f"concat=n={len(clips)}:v=1:a=1[v][a]"
    )
    args += [
        "-filter_complex",";".join(filters),
        "-map","[v]","-map","[a]",
        "-c:v","libx264","-preset","veryfast","-crf","21",
        "-pix_fmt","yuv420p","-r",str(fps),"-fps_mode","cfr",
        "-c:a","aac","-b:a","160k","-ar","48000","-ac","2",
        "-movflags","+faststart",str(target),
    ]
    result=subprocess.run(args,capture_output=True,text=True,timeout=1800)
    if result.returncode:
        raise RuntimeError("Falha na montagem com áudio: "+result.stderr[-1800:])
    info=validate_video(target,require_audio=True,
                        expected_seconds=expected,
                        tolerance_seconds=max(1.5,len(clips)/fps+.5))
    verify_audible_audio(target)
    return info
