#!/usr/bin/env python3
"""Generate the spoken-audio library for Roar & Read with fal.ai text-to-speech.

Usage:  python3 tools/make_audio.py            # make any missing clips
        python3 tools/make_audio.py --check    # also transcribe the word clips and report mismatches
        python3 tools/make_audio.py --redo cat dog   # regenerate specific clips

The API key is read from the FAL_AI_KEY (or FAL_KEY) environment variable, or from ~/.env.
Clips are written to audio/<id>.mp3. Existing files are skipped.
"""
import concurrent.futures, json, os, re, sys, urllib.request

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
        res = post(TTS, {"text": text, "voice": VOICE, "stability": 0.6, "similarity_boost": 0.8, "speed": 0.95})
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


def main():
    args = sys.argv[1:]
    redo = set(args[args.index("--redo") + 1:]) if "--redo" in args else set()
    os.makedirs(OUT, exist_ok=True)
    items = [("w_" + w, w.capitalize() + ".", w in redo or "w_" + w in redo) for w in WORDS]
    items += [(cid, text, cid in redo) for cid, text in PHRASES.items()]
    urls = {}
    with concurrent.futures.ThreadPoolExecutor(6) as ex:
        for cid, url, status in ex.map(make, items):
            if status != "kept":
                print(cid, status)
            if url:
                urls[cid] = url
    print("clips on disk:", len([f for f in os.listdir(OUT) if f.endswith(".mp3")]), "of", len(items))
    if "--check" in args and urls:
        todo = list(urls.items())
        bad = 0
        with concurrent.futures.ThreadPoolExecutor(6) as ex:
            for cid, text in ex.map(check, todo):
                heard = re.sub(r"[^a-z0-9]", "", text.lower())
                want = cid[2:] if cid.startswith("w_") else re.sub(r"[^a-z0-9]", "", PHRASES[cid].lower())
                if heard != want:
                    bad += 1
                    print("MISMATCH %-12s heard %r" % (cid, text.strip()))
        print("checked", len(todo), "clips,", bad, "mismatches")


if __name__ == "__main__":
    main()
