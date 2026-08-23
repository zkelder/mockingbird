# Acoustic test fixtures -- provenance

These `.wav` files themselves are **not committed to git** (see
`.gitignore`) -- this document is, so their provenance and how to
regenerate them survives even though the binary files do not. Mirrors this
product's existing "model/media artifacts stay local, never committed"
convention for MDv5/BioCLIP.

This directory now backs two things: `tests/test_acoustic_ingest_real_model.py`
(the original Acoustic / BirdNET Observation Foundation v1 real-model
acceptance tests) and the Acoustic Runtime & Quality v1 benchmark corpus
(`docs/acoustic-quality-benchmark.md`, `scripts/evaluate_acoustic_quality.py`).
Every fixture below is labeled **real** (an independently recorded,
third-party clip, license/attribution required), **derived** (a mechanical
transform of a real recording -- same underlying license, disclosed as a
transform, not a second independent recording), or **synthetic** (no
third-party content, `ffmpeg`-generated, no license concern). Do not
pretend a derived/synthetic fixture is independently real, and do not train
on any of these -- evaluation/benchmark use only.

## Real, independently recorded

### `northern_cardinal_48k_mono_15s.wav`

A real, positively-identified Northern Cardinal (*Cardinalis cardinalis*)
field recording, trimmed and format-converted from a real-world source:

- **Original source**: [xeno-canto recording #75501](https://www.xeno-canto.org/75501),
  mirrored on Wikimedia Commons as
  [`Cardinalis_cardinalis_-_Northern_Cardinal_XC75501.mp3`](https://commons.wikimedia.org/wiki/File:Cardinalis_cardinalis_-_Northern_Cardinal_XC75501.mp3).
- **Recordist**: Jonathon Jongsma.
- **Recorded**: 2011-04-09.
- **License**: CC BY-SA 3.0 (<https://creativecommons.org/licenses/by-sa/3.0>).
- **Derivation**: the original 35.2s stereo 44.1kHz MP3 was trimmed to the
  9.0-24.0s window (several clean, high-confidence call segments) and
  transcoded to 48kHz mono 16-bit PCM WAV (BirdNET's native analysis rate)
  via:

  ```bash
  ffmpeg -i XC75501_original.mp3 -ss 9.0 -t 15.0 -ac 1 -ar 48000 \
      -c:a pcm_s16le northern_cardinal_48k_mono_15s.wav
  ```

- **Real BirdNET verification**: 3/3 merged windows in this trimmed clip
  correctly identified as Northern Cardinal at 0.81-0.999 confidence, using
  the real bundled `BirdNET_GLOBAL_6K_V2.4` model.

### `black_capped_chickadee_48k_mono_12s.wav`

A real, positively-identified Black-capped Chickadee (*Poecile
atricapillus*) field recording, format-converted (not trimmed -- the source
is already a short, focused clip) -- added for Acoustic Runtime & Quality
v1's benchmark corpus, specifically for "multiple species" coverage.

- **Original source**: [xeno-canto recording #77884](https://www.xeno-canto.org/77884),
  mirrored on Wikimedia Commons as
  [`Poecile_atricapillus_-_Black-capped_Chickadee_XC77884.mp3`](https://commons.wikimedia.org/wiki/File:Poecile_atricapillus_-_Black-capped_Chickadee_XC77884.mp3).
- **Recordist**: Jonathon Jongsma (same recordist as the Cardinal fixture above -- coincidental).
- **Recorded**: 2011-05-16, Bear Head Lake State Park, St. Louis County, Minnesota, USA.
- **Description**: "Gargle call from a bird foraging in alder saplings around campsite."
- **License**: CC BY-SA 3.0.
- **Derivation**: transcoded to 48kHz mono 16-bit PCM WAV, otherwise unmodified (11.6s):

  ```bash
  ffmpeg -i XC77884_original.mp3 -ac 1 -ar 48000 -c:a pcm_s16le \
      black_capped_chickadee_48k_mono_12s.wav
  ```

- **Real BirdNET verification**: first window (0-3000ms) correctly
  identified as Black-capped Chickadee at 0.938 confidence. Later windows
  (3000-12000ms, noisier/more distant in the source recording) show real,
  informative same-family confusion -- Mexican/Boreal/Carolina Chickadee at
  0.12-0.47 confidence alongside a correct but lower-confidence Black-capped
  Chickadee call -- genuine BirdNET behavior on a real recording, not
  fabricated, kept in the corpus deliberately as realistic same-genus
  confusor evidence for Phase H.

### `lawnmower_confusor_48k_mono_15s.wav`

A real, clearly-licensed non-bird mechanical/environmental recording --
added specifically for Phase G's "human/mechanical/environmental
confusors" category, and the fixture that directly drove a real,
benchmark-discovered fix (see `docs/acoustic-runtime-quality-v1-contract.md`
"Non-avian soundscape class filtering").

- **Original source**: [`WWS Lawnmower.ogg`](https://commons.wikimedia.org/wiki/File:WWS_Lawnmower.ogg),
  a Work With Sounds / Wikimedia Sverige field recording.
- **Recordist**: Leena Ahonen (Work With Sounds / Werstas).
- **Recorded**: 2015-06-14 (Klippo 12L902 petrol-powered lawn mower).
- **License**: CC BY 4.0 (<https://creativecommons.org/licenses/by/4.0>).
- **Derivation**: the original 68s recording was trimmed to a clean
  10.0-25.0s window and transcoded to 48kHz mono 16-bit PCM WAV:

  ```bash
  ffmpeg -i WWS_Lawnmower_original.ogg -ss 10 -t 15 -ac 1 -ar 48000 \
      -c:a pcm_s16le lawnmower_confusor_48k_mono_15s.wav
  ```

- **Real BirdNET verification**: zero bird species detected at any
  confidence down to a 0.05 floor. BirdNET's own bundled label set includes
  13 explicit non-avian "soundscape" classes (confirmed by direct
  inspection of the installed `BirdNET_GLOBAL_6K_V2.4_Labels.txt`); this
  clip correctly scores `Engine` (0.51-0.69) and `Power tools` (0.29-0.53)
  -- `Engine` alone clears BirdNET's own *default* 0.5 confidence floor,
  which is exactly what exposed the pre-existing gap this milestone fixed
  (nothing filtered these non-avian classes out of candidate admission
  before Acoustic Runtime & Quality v1).

## Derived (mechanical transform of a real recording above -- same license)

### `cardinal_distant_quiet_48k_mono_derived.wav`

A -20dB volume-attenuated copy of `northern_cardinal_48k_mono_15s.wav`,
simulating a distant/quiet vocalization (Phase G's "distant/quiet bird
vocalizations" category) via a standard, disclosed SNR-reduction technique
-- not an independently recorded distant clip. Same license/attribution as
the source (CC BY-SA 3.0, Jonathon Jongsma).

```bash
ffmpeg -i northern_cardinal_48k_mono_15s.wav -af "volume=-20dB" \
    -ac 1 -ar 48000 -c:a pcm_s16le cardinal_distant_quiet_48k_mono_derived.wav
```

### `overlapping_cardinal_chickadee_48k_mono_derived.wav`

An equal-weight mix of `northern_cardinal_48k_mono_15s.wav` and
`black_capped_chickadee_48k_mono_12s.wav`, both real species genuinely
audible simultaneously (Phase G's "overlapping bird sounds" category).
Same license/attribution as both sources (CC BY-SA 3.0, Jonathon Jongsma).

```bash
ffmpeg -i northern_cardinal_48k_mono_15s.wav -i black_capped_chickadee_48k_mono_12s.wav \
    -filter_complex "[0:a][1:a]amix=inputs=2:duration=shortest:dropout_transition=0" \
    -ac 1 -ar 48000 -c:a pcm_s16le overlapping_cardinal_chickadee_48k_mono_derived.wav
```

## Synthetic (no third-party content, no license concern)

### `no_bird_synthetic_noise_48k_mono_10s.wav`

Deterministic synthetic pink noise -- the original negative/no-detection
fixture:

```bash
ffmpeg -f lavfi -i "anoisesrc=d=10:c=pink:a=0.05:seed=42" \
    -ac 1 -ar 48000 -c:a pcm_s16le no_bird_synthetic_noise_48k_mono_10s.wav
```

Real BirdNET verification: 0 detections at both a low (0.1) and realistic
(0.5) confidence floor.

### `wind_like_synthetic_noise_48k_mono_12s.wav`

Deterministic synthetic brown noise (a lower-frequency-weighted spectrum
than the pink noise above, closer to a real wind rumble's character) --
Phase G's "wind/rain-like noise" category:

```bash
ffmpeg -f lavfi -i "anoisesrc=d=12:c=brown:a=0.15:seed=7" \
    -ac 1 -ar 48000 -c:a pcm_s16le wind_like_synthetic_noise_48k_mono_12s.wav
```

### `silence_synthetic_48k_mono_10s.wav`

True digital silence -- Phase G's "silence" category:

```bash
ffmpeg -f lavfi -i "anullsrc=r=48000:cl=mono" -t 10 -c:a pcm_s16le \
    silence_synthetic_48k_mono_10s.wav
```

## Regenerating this directory

`tests/test_acoustic_ingest_real_model.py` and
`scripts/evaluate_acoustic_quality.py` are gated on this directory's
presence (and separately on the optional `classifier-birdnet` extra being
installed) -- both skip/report cleanly, never fail, when either is absent.
To re-enable them locally, recreate every file above with the commands
shown, downloading the two new real sources from the Wikimedia Commons file
pages linked above (each page's "download" link gives the original
MP3/OGG).
