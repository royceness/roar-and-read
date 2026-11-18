# Roar & Read 🦖

A dinosaurs, trucks and rockets game for children who are just starting to read, made for a tablet.

**Play it: https://royceness.github.io/roar-and-read/**

## What it does

The game talks, so the child doesn't need to read instructions. Each mission is six questions with no timer. A dinosaur, truck or rocket moves along a track with every right answer, and finishing a mission earns a sticker.

There are four groups of things to learn:

| Group | What it covers |
|---|---|
| Letter sounds | Hear a word, tap the letter it starts with (25 letters) |
| Short words | Three-letter words like cat, rex and bus (82 words) |
| Digraphs | sh, ch, th, ck, ng, qu, wh, ee, oo, ar, or, ai, oa (59 words) |
| Sight words | Common words like the, said and was (44 words) |

## The Journey

The default mode is a step-by-step path:

- **Letter sounds come first.**
- **A short word unlocks** once every letter in it has been learned.
- **Digraphs arrive one at a time**, after a good number of short words are known.
- **Sight words** are added a few at a time.

New letters, digraphs and sight words are shown and said on an introduction card before they are ever asked. Brand-new items have two choices; later ones have three, with look-alike choices as the child improves.

Any single group can also be picked by hand on the home screen.

## Kinds of question

- **First sound:** hear a word, tap its first letter.
- **Hear it:** hear a word, tap the written word.
- **Read it:** read a written word and tap its picture. Tapping a letter in the word plays its sound.
- **Missing letters:** hear a word and choose the missing digraph.
- **Build it:** see a picture, hear the word and put letter tiles in order.

Every question continues until it is answered correctly. What is tracked is whether the first answer was right. Whatever is tapped is said aloud, so a wrong tap still teaches something.

## For grown-ups

The Grown-ups screen shows every item and how far along it is, plays any recording when tapped, and holds a practice log.

- **Everything stays on the device.** Progress and the log are kept in the browser's local storage. Nothing is sent anywhere, and there are no accounts, ads or analytics.
- **Practice log.** Every question is recorded: what was asked, the choices, each wrong tap, how long it took and how many sounds were tapped for help. Two buttons copy it to the clipboard, with an explanation of the columns at the top, ready to paste into an AI assistant or a spreadsheet.
- **Erasing progress** needs an adult's year of birth and the answer to a sum.

## Putting it on an iPad

Open the link above in Safari, tap Share, then Add to Home Screen. The game then opens full-screen like an app. Always play from that icon so progress stays in one place.

## Running it yourself

There is no build step. Serve the folder and open it:

```bash
python3 -m http.server 8765
```

Then go to `http://localhost:8765`. It needs to be served, not opened as a file, so the recordings can load.

| File | What it is |
|---|---|
| `index.html` | The game |
| `words.js` | The word lists, pictures and spoken phrases |
| `audio/` | The speech recordings |
| `tools/make_audio.py` | Regenerates the recordings |

## Changing the words or the voice

Edit `words.js`, then regenerate any missing recordings. This needs a [fal.ai](https://fal.ai) API key in the `FAL_AI_KEY` environment variable, and `ffmpeg` installed:

```bash
python3 tools/make_audio.py
```

Whole words and phrases are spoken by a text-to-speech voice. Single sounds such as "ch" or "m" can't be spoken cleanly on their own, so the script says a real word and cuts the sound out of it. A few of those cuts were adjusted by hand; the script says which.

The recordings use an American accent. The voice is set at the top of the script.

## License

MIT for the code and word lists. See [LICENSE](LICENSE), and [NOTICE.md](NOTICE.md) for the recordings and icons, which are not covered.
