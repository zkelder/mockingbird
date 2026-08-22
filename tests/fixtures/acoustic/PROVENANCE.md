# Acoustic test fixtures -- provenance

These `.wav` files themselves are **not committed to git** (see
`.gitignore`) -- this document is, so their provenance and how to
regenerate them survives even though the binary files do not. Mirrors this
product's existing "model/media artifacts stay local, never committed"
convention for MDv5/BioCLIP.

## `northern_cardinal_48k_mono_15s.wav`

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

- **Real BirdNET verification** (see docs/acoustic-birdnet-observation-
  foundation-v1-contract.md "BirdNET runtime decision"): 3/3 merged windows
  in this trimmed clip correctly identified as Northern Cardinal at
  0.81-0.999 confidence, using the real bundled `BirdNET_GLOBAL_6K_V2.4`
  model.

Redistribution of this file requires the same CC BY-SA 3.0 attribution
above; that is why it is not committed to a public-adjacent git history --
regenerate it locally from the source above if needed.

## `no_bird_synthetic_noise_48k_mono_10s.wav`

Deterministic synthetic pink noise (no bird content, no third-party
provenance) -- the negative/no-detection fixture:

```bash
ffmpeg -f lavfi -i "anoisesrc=d=10:c=pink:a=0.05:seed=42" \
    -ac 1 -ar 48000 -c:a pcm_s16le no_bird_synthetic_noise_48k_mono_10s.wav
```

Real BirdNET verification: 0 detections at both a low (0.1) and realistic
(0.5) confidence floor.

## Regenerating this directory

`tests/test_acoustic_ingest_real_model.py`'s real-model tests are
`skipif`-gated on this directory's presence (and separately on the
optional `classifier-birdnet` extra being installed) -- they skip cleanly,
never fail, when either is absent. To re-enable them locally, recreate both
files above with the commands shown.
