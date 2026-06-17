# Design: Static GitHub Pages Viewer with Firebase Mirror

**Date:** 2026-06-16
**Status:** Design approved — not yet planned or implemented
**Author:** Brainstorm between Adam and Claude

## Problem

The draft tracker runs locally on Adam's machine so it can host the API listener
and use local JSON files for persistence. To let remote league members view the
draft on their own devices, Adam currently **opens a port on his machine**. He
wants a better way — ideally a free, publicly hosted viewer (GitHub Pages) that
players reach without his home machine being directly exposed.

Three concerns were raised up front: (1) GitHub Pages can't run the API listener,
(2) there's no cloud persistence story, and (3) it would seem to require an auth
layer.

## Usage model (what makes this tractable)

- **Single writer.** Only Adam enters data (nominations, bids, picks). He operates
  the admin/draft UI locally and shares his screen over Zoom during the draft.
- **Read-only viewers.** League members use the read-only team viewer on their own
  devices to browse, *in addition* to watching Adam's shared screen.

Because the write side is single-writer and local, there is no need for a
multi-writer backend, per-user accounts, or a publicly exposed write API. The
problem collapses to: **how do remote read-only viewers get the current draft
state, given Adam is the only one changing it, without slowing down Adam's admin
UI?**

## Hard requirement: admin responsiveness

Adam's admin actions must stay near-instant (they are ~1–5 ms local disk writes
today). Putting a cloud database *on the write critical path* would add hundreds
of ms to seconds — unacceptable. The design must keep admin latency unchanged.

For reference, the current viewer polls the API every **5 seconds**, so a slight
delay on the remote view is acceptable; the bar is "≤5s for viewers, instant for
the admin."

## Decision: A1 — Static viewer on GitHub Pages + Firebase Realtime Database mirror

**Local JSON store stays the source of truth.** A publisher pushes each state
change to Firebase **asynchronously, off the admin critical path**. The static
viewer on GitHub Pages subscribes to Firebase in real time.

### Architecture

```
┌─ Adam's machine (during draft) ─────────┐         ┌─ Firebase RTDB (free) ─┐
│  Admin/draft UI  →  local JSON store     │  async  │  /draft/state  (~31KB) │
│  (source of truth, ~1-5ms, unchanged)    │ ──push─▶│  write: service acct   │
│  + publisher (watches draft_state.json)  │         │  read:  public/token   │
└──────────────────────────────────────────┘         └───────────┬───────────┘
                                                           realtime │ subscribe
┌─ GitHub Pages (free, static) ───────────────────────────────────▼───────────┐
│  team_viewer.html + players.json / player_stats.json / owners.json /         │
│  config.json  (reference data baked in at deploy; draft_state streamed live)  │
└──────────────────────────── players open this URL on their devices ──────────┘
```

### Data flow

1. Admin action → write `data/draft_state.json` locally, exactly as today
   (~1–5 ms, **unchanged**).
2. Publisher detects the change and pushes the new state to Firebase via the
   Admin SDK — fire-and-forget, so Adam never waits for it.
3. Firebase pushes the change to every subscribed viewer in real time.

Expected viewer latency: ~0.1–0.5 s after Adam commits a change locally —
*faster* than today's 5 s polling — while Adam's own latency is unchanged.

| Hop | Latency | On admin critical path? |
|---|---|---|
| Admin → local JSON write | 1–5 ms | yes (unchanged) |
| Local → cloud async push | 50–300 ms | **no** |
| Cloud → viewer (real-time) | 50–200 ms | no |

### Split of data: mutable vs. reference

- **Reference data** (`players.json` ~123 KB, `player_stats.json` ~256 KB,
  `owners.json`, `config.json`) does not change during a draft. It is **baked into
  the GitHub Pages site as static assets** and fetched directly by the viewer —
  served from the Pages CDN, never through Firebase.
- **Mutable data** (`draft_state.json`, ~31 KB) is the only thing that flows
  through Firebase, keeping the realtime payload tiny.

## Components / work breakdown

1. **Publisher (local app).** A small module that, after each local
   `draft_state.json` write, pushes it to Firebase via the Admin SDK. Preferred
   form: a **file-watcher on `data/draft_state.json`**, which fully decouples
   publishing from the API endpoint code (no changes to nominate/bid/draft logic)
   and keeps it off the critical path. The service-account secret lives locally
   and is gitignored.
   - Alternative considered: a FastAPI `BackgroundTasks` hook in each mutating
     endpoint. Rejected as the default because it touches more endpoint code; the
     file-watcher is cleaner. Revisit at implementation time if the watcher proves
     awkward.

2. **Static viewer.** Convert `templates/team_viewer.html` to a static page:
   - Replace the single Jinja line `let currentTeamId = {{ selected_team_id }};`
     with a URL query param read in JS (e.g. `?team=1`).
   - Replace the `draft_state` 5 s poll with a Firebase real-time subscription.
   - Point reference-data `fetch()` calls at committed static JSON files instead
     of the API.
   - The read-only API endpoints on `viewer_app` become unused for remote players
     (decide at implementation time whether to keep `viewer_app` for local use or
     retire it).

3. **Firebase setup.** Create a project + Realtime Database. Security rules:
   world-readable (or token-gated), client writes denied — only the Admin SDK
   (service account) can write. ~15 minutes in the console.

4. **Deploy flow.**
   - *Pre-draft:* run `utils/` scripts to refresh `players` / `stats`, commit,
     push → GitHub Pages publishes with current reference data.
   - *During draft:* run the local app as today; the publisher mirrors state to
     Firebase; players open the GitHub Pages URL.

## How the three original concerns resolve

- **API listener** — gone for players; Firebase is their listener. Adam's local
  app keeps its listener for Adam only.
- **Persistence** — local JSON stays authoritative and unchanged; Firebase is a
  disposable async mirror.
- **Auth** — writes are locked to Adam's local service-account secret; reads are
  public or behind a shared token. No user accounts to build.

## Cost / free-tier verification

Firebase **Spark (free) plan**, Realtime Database, verified 2026-06-16:

- **100 simultaneous connections** — usage ~13 (12-person league + publisher).
- **1 GB storage** — `draft_state.json` is ~31 KB.
- **10 GB/month download** — worst case ~370 MB for a full draft (deltas make it
  far less).

Critically, **Spark has no billing attached**: exceeding a limit turns the app
off rather than incurring charges. Worst case is "viewers stop updating, fall
back to Zoom," never a surprise bill.

Sources: <https://firebase.google.com/docs/database/usage/limits>,
<https://firebase.google.com/support/faq>.

## Failure modes (all soft — local truth protects the draft)

- *Firebase down / quota hit* → draft runs normally on local truth; viewers stop
  updating; fall back to Zoom. No data loss, no bill.
- *Publisher crashes* → same; restart it and it re-pushes current state.
- *Stale viewer* → real-time subscription auto-reconnects; worst case a player
  refreshes.

## Alternatives considered

- **A2 — GitHub Pages + Cloudflare Worker + Durable Object.** Same shape but
  Adam owns the relay code and avoids a Google dependency; Durable Objects give a
  real-time websocket + strong consistency on the free tier. More to build than
  A1. Viable fallback if avoiding Google matters.
- **A3 — Commit `draft_state.json` to the repo / a Gist; viewer fetches the raw
  file.** Rejected: GitHub Pages rebuilds on push (10–60 s) and both Pages and
  `raw.githubusercontent` sit behind a CDN cache (minutes) that cache-busting
  query strings don't reliably defeat. Fails the live-auction responsiveness bar.
- **Tunnel (Cloudflare Tunnel / Tailscale Funnel) in front of the existing app.**
  Not GitHub Pages and not static, but kills the open inbound port, gives a stable
  HTTPS URL + optional access control, and changes zero code/data flow. Lowest
  effort and a strict improvement over port-forwarding — noted as the fallback if
  the goal shifts from "static site" to "just stop opening a port."

## Effort estimate

Roughly a half-day. Most of it is the viewer's data-layer swap and Firebase
rules; the publisher is small.

## Open questions for implementation time

1. Read access: fully public, or gated by a shared token / unguessable DB path?
2. Keep `viewer_app` for local use, or retire it once the static viewer exists?
3. Publisher form: file-watcher (preferred) vs. endpoint `BackgroundTasks` hook —
   confirm once looking at the code.
4. How is the static viewer deployed to Pages (which branch / `docs/` folder /
   action), and how does reference-data refresh fit the existing `utils/` flow?
