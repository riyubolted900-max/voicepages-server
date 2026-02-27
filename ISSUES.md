# VoicePages Server — Issue Tracker

Issues identified from code review. Each item maps to a GitHub issue to be created.

---

## Bugs

### CRITICAL

#### S1 — kokoro_generator.py: text written to .wav instead of .txt
**File:** `pipeline/kokoro_generator.py`
Input text is written into a temp file with suffix `.wav`, then passed to Kokoro as an input file.
Kokoro expects a text file. This breaks **all** audio generation.
**Fix:** Use `.txt` suffix for the input temp file; keep a separate `.wav` path for output.

---

### HIGH

#### S2 — Character name key inconsistency: "Narrator" vs "narrator"
**Files:** `pipeline/character_detector.py`, `pipeline/voice_assigner.py`
`character_detector.py` adds `"Narrator"` (title-case) but `voice_assigner.py` checks
`char_name.lower() == "narrator"` and stores the result back as `"Narrator"`. The mismatch
can produce duplicate narrator entries when LLM and heuristic paths both add a narrator.
**Fix:** Normalize narrator key to lowercase `"narrator"` everywhere; let the API layer
capitalise for display.

#### S3 — Dialogue detection regex drops lines with double-spaces / contractions
**File:** `pipeline/audio_generator.py`
The dialogue regex requires exactly one space before a speech verb; `"John  said"` (double
space) or `"She'd"` mid-sentence confuses the pattern and drops attribution.
**Fix:** Replace `\s+` for multi-space; add contraction handling.

---

### MEDIUM

#### S4 — LLM character-detection timeout (60 s) blocks upload endpoint
**File:** `pipeline/character_detector.py`
The `httpx` call to Ollama uses `timeout=60.0`. A slow LLM hangs the entire upload
request for up to a minute.
**Fix:** Reduce to `timeout=15.0`; already falls back to heuristics on failure.

#### S5 — CORS_ORIGINS whitespace not stripped
**File:** `config.py`
`"host1, host2".split(",")` produces `[" host2"]` with a leading space, breaking CORS
matching. Was fixed in security patch; documented here for tracking.
**Fix:** `[o.strip() for o in ...]`

#### S6 — WAV concatenation assumes mono 16-bit; multi-channel audio corrupts output
**File:** `pipeline/audio_generator.py`
`np.frombuffer(segment[44:], dtype=np.int16)` assumes mono/16-bit but does not
validate the WAV header channels or bit-depth fields.
**Fix:** Read channels + bit-depth from the WAV header before concatenating.

---

### LOW

#### S7 — Dead code: `_generate_placeholder_audio` never called
**File:** `pipeline/audio_generator.py`
The method generates a sine-wave placeholder. It was replaced by Kokoro-only logic
but was never removed.
**Fix:** Delete the method.

---

## Enhancements

#### S8 — Add rate limiting to expensive endpoints
Endpoints `/api/books/{id}/chapters/{id}/audio` (POST) and `/api/tts/generate` (POST)
are CPU-bound; a single client can saturate the machine. Add `slowapi` or a semaphore.

#### S9 — Batch chapter audio pre-generation endpoint
Add `POST /api/books/{id}/audio/generate-all` that triggers background generation
of all ungenerated chapters.

#### S10 — API request timeout in frontend (see also W7 in voicepages-web)
All `fetch()` calls in the frontend have no timeout, causing requests to hang forever
if the server is unreachable.

#### S11 — Implement ElevenLabs TTS backend
`config.py` defines `ELEVENLABS_API_KEY` and `TTS_BACKEND`; no ElevenLabs code exists.

#### S12 — Audio streaming (chunked response) for large chapters
Currently the entire chapter audio is generated and buffered in memory before returning.
Streaming would allow playback to start earlier.
