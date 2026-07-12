# Wiselook Big Five Assessment Service

A conversational service that infers a Big Five (OCEAN) personality profile from a user's answers, using an LLM with structured output.

**Option delivered: C (complete, includes A and B).** This covers the evaluation layer, production robustness, observability, concurrency handling, and the voice design note required for Option C. See "Assumptions" and "What I'd improve" below for what's consciously left out of scope.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in OPENAI_API_KEY in .env
```

## Usage

```bash
uvicorn app.main:app --reload
```

### Mode A — 5 answers at once

```bash
curl -X POST http://localhost:8000/api/v1/assess \
  -H "Content-Type: application/json" \
  -d '{
    "answers": [
      {"question_id": "q1", "text": "I like trying new things and exploring unconventional ideas."},
      {"question_id": "q2", "text": "I plan my tasks ahead and find it hard to improvise."},
      {"question_id": "q3", "text": "I really enjoy socializing in large groups."},
      {"question_id": "q4", "text": "I would rather yield in a discussion than create conflict."},
      {"question_id": "q5", "text": "I get nervous easily when unexpected things happen."}
    ]
  }'
```

### Mode B — multi-turn conversation

```bash
curl -X POST http://localhost:8000/api/v1/conversation/start

curl -X POST http://localhost:8000/api/v1/conversation/{session_id}/answer \
  -H "Content-Type: application/json" \
  -d '{"text": "I love trying new things."}'

# The 5th answer returns the final profile instead of the next question.
```

See [`EXAMPLE_TRANSCRIPT.json`](./EXAMPLE_TRANSCRIPT.json) for a full example conversation.

Every response includes an `X-Request-ID` header, useful for correlating a single HTTP call across logs (see "Observability" below).

## Tests

```bash
pytest -v
```

18 tests run by default (schema validation, the `/assess` endpoint, the full conversational flow including edge cases, and a concurrency test — see "Concurrency" below). The evaluation suite (3 more tests) is excluded by default because it calls the real LLM provider:

```bash
pytest -m evaluation -v
```

## Architecture
app/
├── main.py                    # FastAPI entrypoint + request-ID middleware
├── api/
│   ├── routes.py              # HTTP endpoints (thin layer, maps exceptions to status codes)
│   └── dependencies.py        # Dependency wiring (allows mocking in tests)
├── domain/
│   ├── schemas.py             # Pydantic contract (request/response, mode A and B)
│   ├── questions.py           # Fixed 5-question questionnaire (one per dimension)
│   ├── conversation.py        # Conversation state + in-memory session store
│   └── assessment_service.py  # Orchestration: requests inference, validates output
├── llm/
│   ├── client.py              # Async OpenAI SDK wrapper (retries, timeout, latency logging)
│   └── prompts.py             # Versioned prompt + tool schema
└── core/
├── config.py                  # Settings via environment variables
├── exceptions.py              # Custom exceptions (decouples API from SDK)
└── logging_config.py          # JSON formatter supporting extra fields (session_id, etc.)
tests/
├── test_schemas.py            # Schema validation
├── test_endpoint.py           # /assess endpoint, LLM mocked
├── test_conversation.py       # Multi-turn flow, LLM mocked
├── test_concurrency.py        # 10 concurrent conversations, no state leak
└── evaluation/
├── golden_transcripts.py    # Unambiguous-answer cases with expected score ranges
└── test_golden_transcripts.py # Runs against the REAL provider (pytest -m evaluation)

Split into 3 layers: `api` (HTTP) → `domain` (orchestration, state, rules) → `llm` (provider). The domain layer doesn't know the OpenAI SDK directly, so switching providers only touches `llm/client.py`. It didn't require any change to `domain/`, `api/`, or the tests, which is the practical proof this separation holds up, not just a design claim on paper.

## Evaluation layer

`tests/evaluation/` is a small golden-transcript harness. Each case pairs answers that unambiguously lean toward one pole of a dimension with a *score range* (not an exact score — LLM output has legitimate call-to-call variance). What it checks:

- **Schema**: already guaranteed by Pydantic validation before a result can even reach the test assertion — a malformed response never gets this far, it's rejected earlier as `LLMMalformedResponseError`.
- **Ranges**: the core of the harness — each golden case asserts the score for an unambiguous dimension falls within a defensible range (e.g. an answer that explicitly describes loving novelty and exploration should score openness 4-5, not exactly one fixed value).

This isn't meant to validate psychometric accuracy, which is out of scope and has no ground truth for open-ended text anyway; it's meant to catch drift — e.g. a prompt change that makes the model start scoring everything near the middle regardless of input would fail these cases even though the output still passes schema validation.

**Note on running this harness:** `pytest -m evaluation` requires a funded OpenAI account, since it makes real API calls. During development, the free trial credit ran out mid-testing — the retry/backoff logic can be seen handling this gracefully in the logs (3 attempts with exponential backoff per call, each one logged, then a clean `LLMError` raised instead of a crash or an unhandled exception), which is itself a live demonstration of the retry behavior described under "Robustness" below, not a bug in the harness or the client.

**LLM-as-judge:** not implemented. The prompt lists golden transcripts "and/or" LLM-as-judge, so the golden-transcript harness alone satisfies the requirement. I chose not to add a judge on top given the time available, but it's a natural next layer: a second LLM call reviewing `(answer, assigned score, rationale)` and flagging cases where the rationale doesn't actually support the score — useful specifically for catching *plausible-looking but unjustified* outputs that a fixed range check can't, since a score can sit inside a "reasonable" range while its rationale is still weak or unrelated to the answer. Listed under "What I'd improve."

**Consistency checks:** also not implemented. The natural version of this would be running the same golden case multiple times and asserting the score doesn't vary wildly between runs — a signal of prompt instability distinct from "is the score in the right range." Left out given the time budget; listed under "What I'd improve."

## Robustness

- Input validation via Pydantic (answer length, exact count, blank-text rejection) at the API boundary, before any LLM call is made.
- Timeouts (`LLM_TIMEOUT_SECONDS`) and retries with exponential backoff (`LLM_MAX_RETRIES`) on transient provider errors (timeout, rate limit, 5xx). 4xx errors (e.g. invalid API key) fail fast, no retry.
- Malformed LLM responses (missing tool call, schema mismatch) are caught and mapped to a 502, never a raw 500 or an unhandled exception.

## Observability

- **Structured JSON logs** (`core/logging_config.py`): every log line is a JSON object; `extra={...}` fields (`session_id`, `question_number`, `attempt`, `latency_ms`) are included automatically and let you filter logs for one conversation or one LLM call attempt.
- **Per-call latency**: `llm/client.py` logs `latency_ms` for every successful LLM call, tagged with the attempt number and model used.
- **Request correlation ("basic traces")**: `RequestIDMiddleware` (`main.py`) assigns a UUID to every HTTP request, returned in the `X-Request-ID` response header — the primitive needed to trace one HTTP call end-to-end, as opposed to `session_id`, which correlates logs across an entire multi-turn conversation. This is log-based correlation, not distributed tracing spans (no OpenTelemetry) — noted honestly under "What I'd improve" rather than overstated here.

## Concurrency

`tests/test_concurrency.py` runs 10 full conversations (start + 5 answers each) concurrently against the app and asserts each session's stored answers exactly match what was submitted to it — i.e. no state leaks between concurrent sessions through the shared `SessionStore`.

**Strategy:** FastAPI/Starlette run async endpoints on a single event loop; `await`ing I/O (the LLM call) yields control instead of blocking other requests. The one shared mutable resource is `SessionStore`, guarded by an `asyncio.Lock` around every read/write — cheap to hold since operations on it are just dict access, not I/O. This means the service handles many concurrent I/O-bound requests well, which is the actual bottleneck here (waiting on the LLM API).

**Limits:** a single Python process has one event loop — this design doesn't scale across multiple processes/replicas, since `SessionStore` is in-memory per-process. Running multiple replicas behind a load balancer today would silently break sessions (a request could land on a replica that never saw the `/start` call for that session). See "What I'd improve" for the Redis-backed alternative that would fix this.

## Voice design note

**What changes fundamentally:** the current design is request/response (client sends a complete answer, server processes it). Voice is streaming and interruptible — the user starts talking before finishing a thought, may self-correct, and expects turn-taking gaps around 200-300ms, not the 1-3 seconds an LLM call currently takes.

**Latency:** today, latency is almost entirely the LLM call itself, which is fine for text. For voice, the assistant would need to acknowledge within ~300ms of the user finishing — well before the Big Five inference completes — with inference happening in the background. Partial ASR transcription should also be processed incrementally rather than waiting for a final transcript. Keeping the LLM call itself fast matters more for voice than for text — one reason this service already defaults to a small, cheap model (`gpt-4.1-mini`) rather than the largest available one: for a structured classification task over a
small amount of text, a bigger model isn't needed, and the lower latency becomes directly load-bearing for a voice UX rather than just a cost optimization.

**Turn-taking and interruptions:** the conversation is currently strictly sequential (one complete answer locks in the next question). Voice needs Voice Activity Detection to know when the user actually finished speaking, barge-in handling (cancel the assistant's audio output if the user starts talking mid-sentence), and a way to revise an in-progress answer before it's final — today's `SessionAlreadyCompletedError` is a hard lock with no equivalent "still editable" state, which spoken self-correction needs.

**Imperfect transcription (ASR):** the inference relies on exact wording — the prompt asks the LLM to justify each score with concrete evidence from the text, so an ASR error propagates directly into a wrong or unjustified inference, with no way for the pipeline to notice today. I'd surface ASR confidence scores and ask the user to confirm low-confidence transcripts, and keep scoring the full transcript at the end of the conversation (as now) rather than per question — this gives ASR the most context to disambiguate and limits the impact of one bad utterance on the final profile. I'd also combine ASR confidence with the LLM's own self-reported `confidence` (currently generated purely by the LLM, see "Assumptions" below) — a confidently-produced score built on a garbled transcript shouldn't report high confidence.

**Text↔voice parity:** the domain layer (`AssessmentService`, `BigFiveProfile`, `QUESTIONNAIRE`) already has zero knowledge of whether the answer text was typed or transcribed — voice would be an alternate front door reusing the exact same service, contract, and prompt, not a parallel implementation. To actually *guarantee* parity, though, I'd extend the evaluation harness (`tests/evaluation/`) with a parity suite: run the same golden-transcript answers through both the text path and a simulated voice path (text → TTS → ASR → text, to reproduce realistic transcription noise) and assert the resulting scores don't meaningfully diverge. I'd also expect the system prompt to need a voice-specific variant tuned for disfluencies and filler words — the prompt-versioning mechanism already in place (`PROMPT_REGISTRY`, `prompt_version` in the response metadata) is what would let a `"v1-voice"` variant be tracked and compared against the text version independently.

## Orchestration (LangGraph) — considered and skipped

The prompt lists this as optional "if it adds value." It doesn't here: this service makes a single structured call per assessment — there's no multi-step reasoning, no branching between tools, no agent making sequential decisions that would benefit from a graph-based orchestrator. Introducing LangGraph would add a dependency and an abstraction layer around what is, honestly, one `chat.completions.create` call wrapped in a retry loop. It would become relevant if the service grew to need, say, a step that decides whether to ask a clarifying follow-up question before scoring, or coordinates multiple specialized sub-agents — neither of which this scope calls for.

## Design decisions

- **Structured output via function calling, not free-text parsing.**
  The LLM is forced to fill in a concrete JSON schema (via OpenAI function calling) instead of being asked for JSON in the prompt and having the response parsed as text. Free-text JSON parsing is fragile — models can wrap output in markdown fences or produce near-valid JSON. Even so, the output is validated a second time with Pydantic in `assessment_service.py`, so a model returning an out-of-range score or missing field is still caught, not trusted blindly.
- **3-layer architecture (api → domain → llm), validated by a real migration.** `api/` only knows HTTP; `domain/` only knows business rules; `llm/` only knows how to talk to the provider. This is what let the actual Anthropic→OpenAI migration touch only `llm/client.py` and `llm/prompts.py` — zero changes to `domain/`, `api/`, or any test.
- **Custom exceptions** (`LLMError`, `LLMTimeoutError`, `LLMMalformedResponseError`) so the API layer doesn't import or catch SDK-specific exception types directly, and can map to meaningful status codes (504 timeout, 502 malformed/other) in exactly one place.
- **Backoff only on transient errors, fail-fast on 4xx.** Retrying an invalid API key wastes time on an error that won't resolve itself; retrying a timeout or rate limit often does resolve on its own. Exponential backoff (1s, 2s, 4s) reduces the chance of hammering an already-struggling endpoint.
- **In-memory session store**, a plain dict guarded by an `asyncio.Lock` — matches the actual scope of this test (a single-process demo service). Explicitly documented as a limitation, not an oversight, under "What I'd improve."
- **Prompt versioned as code** (`PROMPT_REGISTRY`, keyed by `prompt_version`). Every response carries `metadata.prompt_version`, so any output can be traced back to the exact prompt text that generated it — useful once the prompt changes during iteration.
- **Tests mock at the service boundary, not the SDK.** `test_endpoint.py` and `test_conversation.py` override the `AssessmentService` dependency with a fake, rather than patching `openai.AsyncOpenAI` directly. Mocking at the SDK level means tests know SDK internals and break on provider changes — exactly what would have happened during the Anthropic→OpenAI migration if tests were written that way. None of the 17 non-evaluation tests needed changes during that migration.
- **Custom JSON log formatter instead of adding `structlog`.** The actual need was narrow — dump `extra={...}` fields (`session_id`, `latency_ms`, etc.) as JSON. Python's standard `logging` already supports arbitrary `extra` fields; the missing piece was about 20 lines of formatter code, which didn't justify a new dependency.
- **Small/cheap default model (`gpt-4.1-mini`).** This is a structured classification task over a small amount of input text — it doesn't need frontier-model reasoning. Faster and cheaper, and the model name is a config value (`LLM_MODEL`), so swapping to a larger model is a one-line change if ever needed for a quality comparison.

## Assumptions

- The conversational mode's questionnaire is fixed (5 questions, one per dimension) — no dynamic follow-up question generation.
- No authentication on the endpoints; in production this would sit behind an API gateway, out of scope here.
- `confidence` is generated by the LLM itself (explicitly requested in the prompt) instead of a separate heuristic.
- The in-memory `SessionStore` assumes a single process/replica. There's no session expiration (in production I'd add a TTL).
- The evaluation harness checks score *ranges* on hand-picked unambiguous cases, not a statistically validated psychometric benchmark — appropriate given the prompt explicitly scopes psychometric validity as a minor concern, not the focus.
- LangGraph/agent orchestration deliberately skipped — see the dedicated section above.

## What I'd improve with more time

- **LLM-as-judge** as a second evaluation signal alongside the golden transcripts, to catch plausible-but-unjustified rationales that a range check alone can't.
- **Consistency checks**: run each golden case multiple times and assert scores don't vary wildly between runs, as a signal of prompt instability.
- **Session persistence** (Redis or a DB) instead of in-memory, with a TTL, to support multiple replicas and survive restarts.
- **Real distributed tracing** (OpenTelemetry spans) instead of correlation via log fields and a request-ID header alone.
- **A more objective `confidence` signal**, not purely LLM self-assessment — e.g. run the profile twice and measure variance across dimensions, or combine it with ASR confidence in a voice scenario.
- **The parity evaluation suite for text vs. voice** described above — natural next step once a voice front door exists, reusing the same golden-transcript cases.
