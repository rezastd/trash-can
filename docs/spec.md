# Trash-can classifier — working spec

**Status:** Final (interview complete; scope contract accepted 2026-09-20).
Sections still labeled "proposed" below were not individually reviewed and
stand as proposals, not acceptances.

## Goal

A simple web app: the user points their phone camera at a piece of trash, and the
app says which trash can it goes in. Built with Jev (TypeSafe System One model)
and LM Studio on this machine.

## Non-goals (proposed, unresolved)

- Multi-city / multi-locale bin rules in v1.
- Native mobile app; web app only.
- User accounts, history sync, or analytics in v1.

## Context (researched facts)

- Repo was empty except the TypeSafe skill install; no prior docs conventions.
- Jev accepts **text only** (string / JSON state). Images, audio, and video are
  not supported. Source: TypeSafe live docs (`concepts/state.md`).
- Jev is consumed via the TypeSafe API. A `JEV_API_KEY` already exists in the
  project's `.env`.
- LM Studio server is not currently running, but vision-capable local models are
  downloaded (`gemma-4-12B-it` with mmproj projector, plus smaller models).
- No decision-lineage marker in repo; decisions recorded here as plain Drafts.

## Decisions

| ID | Decision | Status |
|----|----------|--------|
| D1 | Photo-to-Jev pipeline architecture | Settled (Final) 2026-09-20 — two-stage: LM Studio vision describes, Jev classifies |
| D2 | Item description format (free caption vs structured) | Settled (Final) 2026-09-20 — structured detail list |
| D3 | Bin taxonomy (which cans, whose rules) | Settled (Final) 2026-09-20 — configurable bins with generic default |
| D4 | Web app stack and hosting shape | Settled (Final) 2026-09-20 — Python backend + framework frontend |
| D5 | How the phone reaches this machine (network path) | Settled (Final) 2026-09-20 — same Wi-Fi + automatic HTTPS |
| D6 | Uncertainty behavior (low-confidence handling) | Settled (Final) 2026-09-20 — best guess + confidence + runner-up |

## D1 record (Final, settled 2026-09-20)

- Chosen: two-stage pipeline. The phone photo goes to a local vision model in
  LM Studio, which produces a text description; that text becomes Jev state, and
  a Jev Choice question selects the bin.
- Rejected: vision-only (loses Jev's typed judgments, probabilities, and
  confidence handling; discards half the user's stated stack); cloud vision plus
  Jev (adds a second paid API, sends photos off-machine, abandons the local
  setup the user already has).
- Load-bearing assumptions: the local vision model describes well enough for
  Jev to judge accurately; Jev remains text-only; the TypeSafe API is reachable
  from this machine at runtime.

## D2 record (Final, settled 2026-09-20)

- Chosen: structured detail list. The vision step returns named fields (material,
  object type, visible labels, food residue, condition), which become named
  fields in Jev state.
- Rejected: free-form caption (key bin-deciding details may be omitted or
  buried; harder to debug); both caption and fields (richest, but longer
  prompts and more tokens per photo for v1).
- Load-bearing assumptions: the local vision model follows a structured-output
  format reliably enough; field set may grow once real test photos show gaps.

## D3 record (Final, settled 2026-09-20)

- Chosen: configurable bins. Anyone can define their cans (names plus what goes
  in each); the app ships with a generic default set (recycle, compost/organics,
  landfill, hazardous/special). The configured bins become Jev's Choice options
  and criteria text at runtime.
- Rejected: fixed local bins (most accurate for one household, but bakes one
  municipality's rules into the app); generic-only fixed set (simple, but wrong
  wherever local rules differ, with no escape hatch).
- Load-bearing assumptions: bin configuration is simple enough for v1 (a config
  file or minimal settings UI — shape to be decided with the stack); Jev Choice
  options are built dynamically from the configuration.

## D4 record (Final, settled 2026-09-20)

- Chosen: Python backend plus a framework frontend (React/Vue-class). The server
  owns camera-upload intake, the LM Studio vision call, the Jev call, and the
  bin configuration; the frontend owns the camera view, the result display, and
  the bin-settings screen. The Jev API key never leaves the server.
- Rejected: Python backend with plain HTML/JS (simplest, but the configurable
  bins from D3 deserve a real settings UI); JavaScript throughout (single
  language, but the TypeSafe Python SDK is the better-documented client for the
  orchestration core).
- Load-bearing assumptions: exact framework (React vs Vue vs other) and Python
  framework (FastAPI vs Flask-class) still to be picked; a frontend build step
  is accepted as worth it for the settings screen.

## D5 record (Final, settled 2026-09-20)

- Chosen: same Wi-Fi plus automatic HTTPS. The phone joins the Mac's network and
  loads the app over TLS (local-trust certificate or equivalent), satisfying the
  secure-context requirement for camera access. No traffic leaves the home
  network except the server's Jev API call.
- Rejected: quick tunnel (zero cert setup, but adds an outside dependency and
  routes photos through a third party); plain-HTTP file upload (simplest, but
  gives up the point-and-classify camera experience that motivated the app).
- Load-bearing assumptions: phone and Mac share one Wi-Fi network at demo time;
  exact TLS mechanism (mkcert-class local CA, or server-generated cert the phone
  trusts) still to be picked during implementation.

## D6 record (Final, settled 2026-09-20)

- Chosen: show the best guess with its confidence plus the runner-up bin
  (e.g. "Looks like Recycle (72%), could also be Compost"). Both come free from
  the Jev Choice answer's probabilities.
- Rejected: best guess only (a 51/49 call would look as certain as 99/1);
  ask-for-more-evidence below a threshold (more robust, but adds a retry loop
  to v1 — noted as a deferred enhancement).
- Load-bearing assumptions: confidence display thresholds (if any — e.g. when
  to emphasize vs downplay the runner-up) get tuned against the user's real
  test photos, not demo values.

## Constraints (proposed, unresolved)

- Phone camera access requires a secure context (HTTPS or localhost-class host).
- TypeSafe API credentials stay server-side; the browser must not hold the key.
- Keep the pipeline local-first where the user asked for it (LM Studio on this machine).

## Risks (proposed, unresolved)

- Local vision description quality bounds Jev's accuracy: Jev can only judge the
  text it receives.
- Bin rules vary by municipality; a wrong default taxonomy misclassifies by design.
- Phone-to-machine networking (same Wi-Fi, TLS certs) is the most fiddly part of
  a "simple" local demo.

## Validation (proposed, unresolved)

- Representative test photos across every bin, including confusing items.
- End-to-end latency measured on the real phone + machine path.
- Jev confidence thresholds evaluated on the user's own items, not demo values.

## Unresolved questions

- Q1: Pipeline architecture — answered 2026-09-20 (two-stage, D1).
- Q2: Description format — answered 2026-09-20 (structured list, D2).
- Q3: Bin taxonomy — answered 2026-09-20 (configurable, D3).
- Q4: Web app stack — answered 2026-09-20 (Python + framework frontend, D4).
- Q5: Phone-to-machine networking — answered 2026-09-20 (same-Wi-Fi HTTPS, D5).
- Q6: Uncertainty behavior — answered 2026-09-20 (guess + confidence + runner-up, D6).
- Q7: Scope contract acceptance — accepted 2026-09-20 ("yes, accept", chat, 2026-09-20T02:49:34Z).

## Scope contract (proposed — needs explicit user acceptance)

**Artifact-level boundary.** In scope: this spec (`docs/spec.md`); a Python
backend (photo intake, LM Studio vision call, Jev call, bin config, same-Wi-Fi
HTTPS serving); a framework frontend (camera view, result with
confidence/runner-up, bin-settings screen); a bin-configuration file or store
with the generic default set; a short run guide (README section) for starting
LM Studio, the server, and connecting the phone. Out of scope: native mobile
apps, user accounts, history sync, analytics, multi-locale rule packs, automated
tests beyond a manual test-photo checklist, deployment/packaging beyond running
on this machine.

**Done means.** (1) The phone loads the app over HTTPS on shared Wi-Fi and can
open the camera. (2) Pointing at an item returns the configured bin plus
confidence and runner-up. (3) Bins are editable via the settings screen and take
effect on the next classification. (4) A manual checklist of representative test
photos (covering every default bin plus confusing items) passes by the user's
judgment. (5) This spec is marked Final. Nothing outside this checklist is a
completion dependency.

**Deferred (not approved by accepting this record).** Retry/another-angle loop
for low confidence; per-municipality rule packs; exact framework picks (React vs
Vue, FastAPI vs Flask-class) left to implementation within D4's boundary; any
second PR/phase beyond the v1 above returns for its own decisions.

**Acceptance.** Accepted. User's exact words: "yes, accept." Channel: chat.
Time: 2026-09-20T02:49:34Z. (Execution words like "go" authorize only the
boundary above; anything beyond it needs a new explicit approval or a follow-up
issue. No issue tracker exists in this repo, so this record is the
lane-coordination evidence.)
