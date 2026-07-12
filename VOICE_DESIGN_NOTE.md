# Voice Design Note (Option C)

This is a design note, not an implementation — the prompt explicitly says "no need to implement it." It covers how this text-based service would evolve to support real-time voice, and where the current design already helps or would need to change.

## 1. What changes fundamentally between text and voice

The current architecture assumes a **request/response** interaction model: the client sends a complete answer, the server processes it, and
returns a result. Voice is fundamentally a **streaming, interruptible** interaction — the user starts talking before they finish their thought,
may pause, restart, or get cut off, and expects the system to feel responsive within a few hundred milliseconds, not after a multi-second LLM call.

This means the conversational state machine (`ConversationSession` / `SessionStore`) stays conceptually valid — you still track "which
question are we on, what's been answered" — but the *unit of work* inside each turn changes from "one HTTP request with a complete text answer" to "a stream of audio chunks that need to be transcribed,
buffered, and turn-detected before we even know the user is done answering."

## 2. Latency

**Where latency comes from today:** essentially all of it is the LLM call itself (typically 1-3 seconds with the current small model). For text, that's acceptable — the user is looking at a screen and a couple
of seconds doesn't break the interaction.

**Why it's different for voice:** natural spoken conversation has turn-taking gaps around 200-300ms. Anything noticeably longer feels like the system is "broken" or "not listening," even if it's just
thinking. A 1-3 second silence after the user stops talking is a bad voice experience.

**What I'd change:**
- **Don't wait for the full inference before responding.** In text mode we call the LLM once per turn and wait for the complete structured output. For voice, the assistant needs to say *something* (even just a brief acknowledgment: "Got it, thanks") within ~300ms of the user finishing, well before the Big Five inference for that answer is done. Inference can happen in the background while a lightweight,  pre-scripted acknowledgment plays.
- **Stream partial transcription, not just partial LLM output.** ASR (speech-to-text) itself has latency; a good voice pipeline starts processing the transcript incrementally rather than waiting for a "final" transcript before doing anything.
- **Keep the LLM call itself fast**, which is part of why this project already defaults to a small model rather than the largest available one — that decision becomes load-bearing, not just a cost optimization, once latency is a hard UX constraint.

## 3. Turn-taking and interruptions

**Current design:** the conversation is strictly sequential — `ConversationStatus.IN_PROGRESS` moves to `COMPLETED` only when all 5 answers are in, and `submit_answer` assumes one complete answer arrives
per call. There's no concept of "the user started answering, then changed their mind mid-sentence" or "the user interrupted the assistant while it was still talking."

**What voice needs:**
- **Voice Activity Detection (VAD)** to know when the user has actually finished speaking (vs. a pause mid-thought), which determines when to stop listening and start processing.
- **Barge-in handling**: if the assistant is speaking (e.g. reading out a question) and the user starts talking, the assistant needs to stop immediately, not finish its sentence. This means the assistant's audio output needs to be cancellable mid-stream, which has no
  equivalent at all in the current text flow.
- **A "revise last answer" affordance**: in text, if you make a typo you just retype before submitting. In voice, users naturally self-correct out loud ("actually, no, I meant—"). The state machine would need a way to let the current in-progress answer be amended before it's considered final, rather than the current model where an answer is submitted atomically and immediately locks in the next question (see `SessionAlreadyCompletedError` — the analogous  "already answered this question" case would need a softer, revisable state instead of a hard lock).

## 4. Imperfect transcription (ASR errors)

**Why this matters specifically for this service:** the entire inference is built on the *exact wording* of the user's answer — the prompt asks the LLM to justify each score with concrete evidence from
the text. If ASR mishears "I love trying new things" as "I love crying new things," that error propagates directly into a wrong (or at least unjustified) personality inference, with no way for the current
pipeline to notice.

**What I'd add:**
- **Surface ASR confidence scores** where the provider exposes them, and treat low-confidence transcripts differently — e.g. asking the user to confirm ("I heard: '...' — is that right?") rather than silently feeding a possibly-wrong transcript into the LLM.
- **Don't over-trust a single-pass transcript for a task this sensitive to wording.** A cheap mitigation: run the Big Five inference on the full transcript at the *end* of the conversation (as today), not question-by-question in real time — this gives the ASR system the most context to disambiguate, and means an isolated ASR glitch on one short utterance has less influence on the final profile than if each answer were scored independently and then combined.
- **Confidence should reflect ASR quality, not just LLM self-assessment.**
  Right now `confidence` is generated purely by the LLM. For voice, I'd combine that with the ASR confidence/quality signal — a perfectly confident LLM output built on a garbled transcript shouldn't report high confidence.

## 5. Text↔voice parity

**The core risk:** if voice and text use different prompts, different processing paths, or different question phrasing, the same person could get a meaningfully different Big Five profile depending on which modality they used — which undermines the validity of the assessment across channels.

**How the current design already helps:**
- The domain layer (`AssessmentService`, `BigFiveProfile`, `QUESTIONNAIRE`) has zero knowledge of how the answer text was produced — typed or transcribed, it's just a `str` by the time it reaches `assess()`. This means a voice channel could reuse the exact same `AssessmentService`, `AssessmentRequest`/`AssessmentResponse` contract, and prompt, as long as it eventually produces plain text answers to feed in. Voice becomes an alternate *front door*, not a parallel implementation.

**What I'd still need to build to guarantee parity:**
- **A parity evaluation suite**: take the same golden-transcript answers from `tests/evaluation/golden_transcripts.py`, run them through both the text path and a simulated voice path (text → synthetic TTS → ASR → text again, to reproduce realistic transcription noise), and assert the resulting scores don't meaningfully diverge. This is a natural extension of the evaluation harness already built for Option C, not a new concept.
- **Careful handling of disfluencies.** Spoken answers naturally include filler words, false starts, and self-corrections ("I'm pretty — well, actually I'm not that organized, I just pretend to be"). The system prompt (`llm/prompts.py`) would likely need tuning specifically for voice-transcribed input, since it currently assumes relatively clean, deliberate written text. This is a case where the *prompt version* mechanism already in place (PROMPT_REGISTRY`,prompt_version` in the response metadata) becomes directly useful: a `"v1-voice"` prompt variant, tracked separately, so the two channels' outputs can be compared and iterated on independently while still sharing the same underlying schema and service code.

## Summary

| Concern | Current (text) design | What voice adds |
|---|---|---|
| Interaction model | Request/response, complete answer per turn | Streaming, incremental, interruptible |
| Latency budget | ~1-3s acceptable | ~200-300ms turn-taking expectation |
| Turn-taking | N/A (client controls pacing) | VAD, barge-in, cancellable output |
| Input fidelity | Exact typed text | ASR errors, disfluencies, confidence scores |
| Parity | N/A (single channel) | Needs a dedicated evaluation suite |

The layered architecture (`api` / `domain` / `llm`) is what makes this tractable rather than a rewrite: `domain/` — the actual Big Five logic, schemas, and service — doesn't need to know anything changed. Voice
support would mean building a new front door (audio ingestion, ASR, VAD, TTS, streaming session handling) that ultimately still calls `AssessmentService.assess()` with plain text, plus the parity evaluation work described above to prove the two front doors actually
agree.