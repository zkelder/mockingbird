# Worker Lifecycle Boundary Design

## Purpose

Worker and lifecycle design is needed before MockingBird adds background
automation. The current product flow is explicit and review-safe; future
workers must not quietly create evidence, Events, Visits, labels, exports, or
analytics truth outside the user's review path.

## Current State

MockingBird currently uses explicit user-triggered provider actions, not
background automation:

- `external_url` preview, save, and evidence handoff
- `folder_import_future` preview, import, dry-run, and evidence handoff
- `webhook_future` validation and metadata motion evidence creation
- manual media import
- MotionEvidence ignore and promote
- Visit correction
- saved media retention report, dry-run, and low-risk file cleanup

Status and readiness surfaces are read-only unless a user invokes a specific
action.

## Automation Candidates

Future automation candidates include:

- scheduled `external_url` preview fetch
- folder import scan/check
- webhook ingest queue
- retention cleanup dry-run/report
- motion scoring from source media
- model suggestion jobs
- export generation jobs

Each candidate needs a separate phase before implementation.

## Worker Principles

Future workers must be:

- optional
- local-first
- disabled by default initially
- observable
- bounded
- cancellable or safely stoppable
- unable to create silent truth
- unable to cause unbounded media growth
- unable to center the product on one provider

Workers are infrastructure underneath Source, Stream, MotionEvidence, review,
correction, analytics, and export flows.

## Lifecycle States

Future worker status should use product-readable states:

- `disabled`
- `configured`
- `idle`
- `running`
- `paused`
- `failed`
- `backoff`
- `completed`
- `stopped`

These states describe worker lifecycle only. They are not evidence, review
state, or truth.

## Provider Action Boundaries

- `external_url`: no repeated fetch or polling until a later phase explicitly
  scopes scheduling, storage, retention, and privacy behavior.
- `folder_import_future`: no watcher, polling, or background import until a
  later phase explicitly scopes folder scan lifecycle and storage limits.
- `webhook_future`: no async queue until a later phase explicitly scopes
  authentication, delivery, retries, duplicate handling, and observability.
- `manual_media`: no automation; user-selected import remains the boundary.

Current explicit provider actions remain the only active provider behavior.

## Truth Boundary

Worker output cannot:

- create ReviewLabels
- mark Visits reviewed
- become analytics truth
- become export truth
- become classifier or dataset truth

Automated output should become pending MotionEvidence, DetectionProposal, or
SpeciesSuggestion at most. Correction remains truth.

## Storage/Retention Boundary

Future workers must not create unbounded media. Storage estimates, retention
rules, and cleanup behavior must exist before repeated fetch, import, or
generation behavior starts.

Generated media must remain under ignored local data paths. Cleanup must be
explicit and conservative, with dry-run/reporting before destructive behavior.

## Privacy/Ignore Boundary

Privacy zones and ignore zones must block or skip automated evidence creation.
Future automation must prove this in tests before creating evidence from a
worker.

MockingBird should not upload media or evidence to cloud services by default.

## Observability/Status

Future status surfaces should report:

- last run
- next run if scheduled
- last error
- items considered
- items created
- skipped reasons
- storage impact
- no-truth flags

Status routes must have no side effects.

## Configuration Policy

Worker configuration belongs under Source/provider setup or local settings.
There should be no hidden defaults that start background work.

Explicit enablement is required before any worker runs.

## Testing Expectations

Future worker implementation must test:

- disabled by default
- status route has no side effects
- no truth creation
- privacy/ignore skip
- storage limits
- duplicate handling
- errors and backoff are visible
- no dependencies unless explicitly approved
- no live playback claims

## Recommended Future Phases

- Phase 16B: worker status schema/API contract, read-only/no workers.
- Phase 16C: disabled no-op worker registry/status UI.
- Phase 16D: `external_url` scheduled preview dry-run design or implementation.
- Phase 16E: folder scan dry-run worker design.
- Later: live/source automation decision.

## Explicit Non-goals

This phase adds no runtime behavior.

It does not add backend code, frontend code, tests, API endpoints, workers,
schedulers, polling, watchers, queues, provider behavior, media writes,
evidence creation, Event/Visit creation, labels, truth creation, dependencies,
or generated artifacts.
