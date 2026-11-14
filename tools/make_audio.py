#!/usr/bin/env python3
"""Generate the spoken-audio library for Roar & Read with fal.ai text-to-speech.

Usage:  python3 tools/make_audio.py            # make any missing clips
        python3 tools/make_audio.py --check    # also transcribe the word clips and report mismatches
        python3 tools/make_audio.py --redo cat dog   # regenerate specific clips
        python3 tools/make_audio.py --fix hat pan    # re-record mispronounced words until they transcribe correctly

The API key is read from the FAL_AI_KEY (or FAL_KEY) environment variable, or from ~/.env.
Clips are written to audio/<id>.mp3. Existing files are skipped.
"""
import concurrent.futures, json, os, re, subprocess, sys, tempfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "audio")
TTS = "https://fal.run/fal-ai/elevenlabs/tts/multilingual-v2"
STT = "https://fal.run/fal-ai/wizper"
VOICE = "Liam"

def data():
    """The word lists live in words.js (shared with the game)."""
    text = open(os.path.join(ROOT, "words.js"), encoding="utf-8").read()
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


R = data()
WORDS = []
for w in (list(R["cvc"]) + R["cvcExtra"] + list(R["dig"]) + R["sight"] + [w for ex in R["letters"].values() for w in ex]):
    if w.lower() not in WORDS:
        WORDS.append(w.lower())
PHRASES = dict(R["say"])
for i, (_shown, spoken) in enumerate(R["praise"], 1):
    PHRASES["praise_%d" % i] = spoken


def key():
    for name in ("FAL_AI_KEY", "FAL_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    try:
        for line in open(os.path.expanduser("~/.env")):
            m = re.match(r"\s*(?:export\s+)?(FAL_AI_KEY|FAL_KEY)\s*=\s*(.+)", line)
            if m:
                return m.group(2).strip().strip("'\"")
    except OSError:
        pass
    sys.exit("No fal.ai key found (set FAL_AI_KEY).")


KEY = key()


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Authorization": "Key " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def make(item):
    cid, text, force = item
    path = os.path.join(OUT, cid + ".mp3")
    if os.path.exists(path) and not force:
        return cid, None, "kept"
    try:
        body = {"text": text, "voice": VOICE, "stability": 0.6, "similarity_boost": 0.8, "speed": 0.95}
        if cid.startswith("w_"):      # context stops single words being read as another language
            body["previous_text"] = CONTEXT
        elif cid.startswith("d_"):
            body["previous_text"] = "We are practising phonics. The sound these letters make is:"
        res = post(TTS, body)
        url = res["audio"]["url"]
        with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
        return cid, url, "made"
    except Exception as e:  # noqa: BLE001
        return cid, None, "FAILED: %s" % e


def check(item):
    cid, url = item
    try:
        text = post(STT, {"audio_url": url, "task": "transcribe", "language": "en"}).get("text", "")
    except Exception as e:  # noqa: BLE001
        text = "ERROR %s" % e
    return cid, text


# Consonant sounds like "ch", "ck" or "ng" can't be spoken on their own without an added vowel ("chuh"),
# so they are cut out of a real word instead: say the carrier word slowly with per-letter timings, then
# keep only the part where those letters are spoken.  mode "end" keeps from the letters to the end of the
# word (rich -> ch); mode "start" keeps from the start of the word to the end of the letters (quick -> qu).
def make_cut(cid, spec, force):
    path = os.path.join(OUT, cid + ".mp3")
    if os.path.exists(path) and not force:
        return
    text, letters, mode = spec[:3]
    if mode == "manual":   # cut by hand from the carrier word after looking at its waveform; not reproducible automatically
        print("%-6s is hand-cut from %r and its file is missing - it needs cutting again by hand" % (cid, text))
        return
    lead = spec[3] if len(spec) > 3 else 0.0       # optional nudge (seconds) to the cut point
    res = post(TTS, {"text": text, "voice": VOICE, "stability": 0.7, "similarity_boost": 0.8, "speed": 0.8,
                     "timestamps": True, "previous_text": CONTEXT})
    ts = res["timestamps"][0]
    chars = "".join(ts["characters"]).lower()
    st, en = ts["character_start_times_seconds"], ts["character_end_times_seconds"]
    if mode == "end":
        i = chars.rindex(letters)
        a, b = st[i] + lead, en[chars.rindex(".")] if "." in chars else en[-1]
    else:
        i = chars.index(letters)
        a, b = max(0.0, st[i] - 0.02), en[i + len(letters) - 1] + lead
    with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
        with urllib.request.urlopen(res["audio"]["url"], timeout=120) as r:
            tmp.write(r.read())
        tmp.flush()
        flt = "atrim=start=%.3f:end=%.3f,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.012,afade=t=out:st=%.3f:d=0.04,volume=1.8,alimiter" % (a, b, max(0.0, b - a - 0.04))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp.name, "-af", flt, "-codec:a", "libmp3lame", "-q:a", "3", path], check=True)
    print("%-6s cut from %-8s %.2fs-%.2fs (%d ms)   letter timings: %s" % (cid, text, a, b, (b - a) * 1000,
          " ".join("%s@%.2f" % (c, t) for c, t in zip(ts["characters"], st) if c.strip())))


# Single short words are sometimes read as if they were another language ("pan", "zebra", "I").
# --fix tries stronger hints that the word is English and keeps the first take that transcribes back correctly.
TURBO = "https://fal.run/fal-ai/elevenlabs/tts/turbo-v2.5"
CONTEXT = "We are practising reading simple English words. The next word is:"
STRATEGIES = [
    (TTS, {"previous_text": CONTEXT}),
    (TURBO, {"language_code": "en", "previous_text": CONTEXT}),
    (TURBO, {"language_code": "en"}),
    (TTS, {"previous_text": CONTEXT, "stability": 0.8}),
    (TURBO, {"language_code": "en", "previous_text": CONTEXT, "stability": 0.8}),
]


def fix(words):
    for w in words:
        w = w.lower()
        done = False
        for n, (url, extra) in enumerate(STRATEGIES * 2):
            body = {"text": w.capitalize() + ".", "voice": VOICE, "stability": 0.6, "similarity_boost": 0.8, "speed": 0.95}
            body.update(extra)
            try:
                audio = post(url, body)["audio"]["url"]
                heard = re.sub(r"[^a-z0-9]", "", check(("w_" + w, audio))[1].lower())
            except Exception as e:  # noqa: BLE001
                print(w, "attempt", n + 1, "error", e)
                continue
            print("%-6s attempt %d (%s%s) heard %r" % (w, n + 1, "turbo" if url == TURBO else "multilingual", ", context" if "previous_text" in extra else "", heard))
            if heard == w:
                with urllib.request.urlopen(audio, timeout=120) as r, open(os.path.join(OUT, "w_" + w + ".mp3"), "wb") as f:
                    f.write(r.read())
                done = True
                break
        print(w, "REPLACED" if done else "NOT FIXED - left as it was")


def main():
    if "--fix" in sys.argv:
        return fix(sys.argv[sys.argv.index("--fix") + 1:])

    args = sys.argv[1:]
    redo = set(args[args.index("--redo") + 1:]) if "--redo" in args else set()
    os.makedirs(OUT, exist_ok=True)
    items = [("w_" + w, w.capitalize() + ".", w in redo or "w_" + w in redo) for w in WORDS]
    items += [(cid, text, cid in redo) for cid, text in PHRASES.items()]
    items += [("d_" + dg, text, dg in redo or "d_" + dg in redo) for dg, text in R.get("digraphSounds", {}).items()]
    urls = {}
    with concurrent.futures.ThreadPoolExecutor(6) as ex:
        for cid, url, status in ex.map(make, items):
            if status != "kept":
                print(cid, status)
            if url:
                urls[cid] = url
    for dg, spec in R.get("digraphCuts", {}).items():
        make_cut("d_" + dg, spec, dg in redo or "d_" + dg in redo)
    print("clips on disk:", len([f for f in os.listdir(OUT) if f.endswith(".mp3")]), "of", len(items))
    if "--check" in args and urls:
        todo = list(urls.items())
        bad = 0
        with concurrent.futures.ThreadPoolExecutor(6) as ex:
            for cid, text in ex.map(check, todo):
                heard = re.sub(r"[^a-z0-9]", "", text.lower())
                if cid.startswith("d_"):   # letter sounds can't be checked by transcription; just show what was heard
                    print("SOUND    %-12s heard %r" % (cid, text.strip()))
                    continue
                want = cid[2:] if cid.startswith("w_") else re.sub(r"[^a-z0-9]", "", PHRASES[cid].lower())
                if heard != want:
                    bad += 1
                    print("MISMATCH %-12s heard %r" % (cid, text.strip()))
        print("checked", len(todo), "clips,", bad, "mismatches")


if __name__ == "__main__":
    main()
