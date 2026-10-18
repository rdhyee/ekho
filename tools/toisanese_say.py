#!/usr/bin/env python3
"""Speak Chinese text in Toisanese (Hoisanwa) with Ekho's Stephen Li clips.

Two engines:
  ekho   (default when ./ekho exists) - the native Ekho binary does the synthesis.
  clips  - pure fallback: look characters up in ekho-data/toisanese_list,
           concatenate the matching .gsm clips with sox. No C++ build needed.

Either way the text is first normalized: the Toisanese list is mostly simplified
characters, so any character with no entry (e.g. traditional 個) is replaced by
its simplified form (个) when that form has an entry. Characters still unknown
are reported on stderr and skipped.

Usage:
  toisanese_say.py "一二三四五六七八九十零"
  toisanese_say.py -o /tmp/out.wav --no-play "你好，我係你個仔"
  toisanese_say.py --engine clips "一二三"
  toisanese_say.py --gap 0.15 --engine clips "一 二 三"   # slower, for teaching

Written 2026-10-18 (arm64 rebuild). Needs: sox (brew), afplay (macOS);
optional: opencc-python-reimplemented (pip) for traditional->simplified fallback.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "ekho-data")
CLIPS = os.path.join(DATA, "toisanese")
LIST = os.path.join(DATA, "toisanese_list")
EKHO = os.path.join(ROOT, "ekho")

PUNCT_PAUSE = set("，。！？；：、,.!?;: \n\t")


def load_list():
    chars, phrases = {}, {}
    with open(LIST, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2 or not parts[0]:
                continue
            key, sym = parts[0], parts[1].strip()
            if key.startswith("(") and key.endswith(")"):
                words = tuple(key[1:-1].split())
                phrases.setdefault(words, sym.split("|"))
            elif len(key) == 1:
                chars.setdefault(key, sym)
    return chars, phrases


def t2s_converter():
    try:
        from opencc import OpenCC
        return OpenCC("t2s").convert
    except ImportError:
        return None


def normalize(text, chars):
    conv = t2s_converter()
    out, swapped, missing = [], [], []
    for c in text:
        if c in chars or c in PUNCT_PAUSE or c.isascii():
            out.append(c)
            continue
        s = conv(c) if conv else c
        if s != c and s in chars:
            out.append(s)
            swapped.append(f"{c}->{s}")
        else:
            out.append(c)
            missing.append(c)
    return "".join(out), swapped, missing


def symbols_for(text, chars, phrases, maxlen=4):
    """Greedy longest-phrase match, then single characters. Yields symbol or None (pause)."""
    i = 0
    while i < len(text):
        c = text[i]
        if c in PUNCT_PAUSE:
            yield None
            i += 1
            continue
        for n in range(maxlen, 1, -1):
            key = tuple(text[i:i + n])
            if len(key) == n and key in phrases:
                yield from phrases[key]
                i += n
                break
        else:
            if c in chars:
                yield chars[c]
            i += 1


def synth_clips(text, chars, phrases, out, gap, pause):
    with tempfile.TemporaryDirectory() as td:
        silence_gap = os.path.join(td, "gap.wav")
        silence_pause = os.path.join(td, "pause.wav")
        for path, dur in ((silence_gap, gap), (silence_pause, pause)):
            subprocess.run(["sox", "-n", "-r", "8000", "-c", "1", "-b", "16", path,
                            "trim", "0", str(max(dur, 0.001))], check=True)
        parts, nosound = [], []
        for sym in symbols_for(text, chars, phrases):
            if sym is None:
                if parts:
                    parts.append(silence_pause)
                continue
            clip = os.path.join(CLIPS, sym + ".gsm")
            if not os.path.exists(clip):
                nosound.append(sym)
                continue
            if parts and gap > 0 and parts[-1] != silence_pause:
                parts.append(silence_gap)
            parts.append(clip)
        if nosound:
            print("no clip file for: " + " ".join(nosound), file=sys.stderr)
        if not parts:
            sys.exit("nothing to say")
        subprocess.run(["sox", *parts, "-r", "8000", "-c", "1", "-b", "16", out], check=True)


def synth_ekho(text, out, speed):
    cmd = [EKHO, "-v", "toisanese", "-o", out]
    if speed:
        cmd += ["-s", str(speed)]
    subprocess.run(cmd + [text], check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text")
    ap.add_argument("-o", "--output", default=os.path.join(tempfile.gettempdir(), "toisanese.wav"))
    ap.add_argument("--engine", choices=["ekho", "clips"],
                    default="ekho" if os.access(EKHO, os.X_OK) else "clips")
    ap.add_argument("--gap", type=float, default=0.0, help="clips engine: seconds of silence between syllables")
    ap.add_argument("--pause", type=float, default=0.3, help="clips engine: seconds of silence at punctuation/spaces")
    ap.add_argument("-s", "--speed", type=int, default=0, help="ekho engine: delta speed -50..300 (percent)")
    ap.add_argument("--no-play", action="store_true")
    a = ap.parse_args()

    chars, phrases = load_list()
    text, swapped, missing = normalize(a.text, chars)
    if swapped:
        print("used simplified form: " + " ".join(swapped), file=sys.stderr)
    if missing:
        print("NO Toisanese entry (skipped): " + " ".join(missing), file=sys.stderr)

    if a.engine == "ekho":
        synth_ekho(text, a.output, a.speed)
    else:
        if not shutil.which("sox"):
            sys.exit("sox not found: brew install sox")
        synth_clips(text, chars, phrases, a.output, a.gap, a.pause)

    dur = subprocess.run(["soxi", "-D", a.output], capture_output=True, text=True).stdout.strip()
    print(f"{a.output}  {dur} s  (engine: {a.engine})", file=sys.stderr)
    if not a.no_play:
        subprocess.run(["afplay", a.output], check=False)


if __name__ == "__main__":
    main()
