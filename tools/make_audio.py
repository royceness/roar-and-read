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
VOICE = "Charlie"

# Words with a picture in the game, then listen-only words (used for "find the word" and as near-miss choices).
WORDS = """cat dog sun bus pig rex van bug hen fox jet bat box cup red ten
rat hat can pan map bag ram cab ant bed net pen web leg gem egg pin lip six kid
log pot cop ox dot nut tub mug hut hug run
dig big sit hop hot top mud fun wet sad mad dad mom zip win yes jam mop rug bun cub pup
mat man pet men peg pit tin hog jog cut gum bad bit""".split()

PHRASES = {
    "find": "Find the word...",
    "which_pic": "Read the word. Which picture is it?",
    "build": "Build the word...",
    "that_says": "That one says...",
    "try_again": "Try again!",
    "lets_go": "Let's read some words! Ready? Go!",
    "mission": "Mission complete!",
    "sticker": "You got a new sticker!",
    "praise_1": "Great job!",
    "praise_2": "Awesome!",
    "praise_3": "You got it!",
    "praise_4": "Roar-some!",
    "praise_5": "Dino-mite!",
    "praise_6": "Blast off!",
    "praise_7": "Super reader!",
    "praise_8": "Yes! That's right!",
    "praise_9": "Wow, nice reading!",
    "praise_10": "You're on fire!",
    "praise_11": "Fantastic!",
    "praise_12": "Out of this world!",
    "praise_13": "High five!",
    "praise_14": "Boom! Nailed it!",
    "praise_15": "Amazing!",
    "praise_16": "Monster truck power!",
    "praise_17": "Zoom zoom! Great reading!",
    "praise_18": "You're a reading rocket!",
    "oops_1": "Oops! Not quite.",
    "oops_2": "Almost!",
    "oops_3": "Good try!",
    "oops_4": "So close!",
}


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
        res = post(TTS, {"text": text, "voice": VOICE, "stability": 0.6, "similarity_boost": 0.8, "speed": 0.92})
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
        todo = [(c, u) for c, u in urls.items() if c.startswith("w_")]
        bad = 0
        with concurrent.futures.ThreadPoolExecutor(6) as ex:
            for cid, text in ex.map(check, todo):
                heard = re.sub(r"[^a-z]", "", text.lower())
                if heard != cid[2:]:
                    bad += 1
                    print("MISMATCH %-8s heard %r" % (cid, text.strip()))
        print("checked", len(todo), "word clips,", bad, "mismatches")


if __name__ == "__main__":
    main()
