# Canonical New/Regular Species v1

Everyday Discovery / Product Experience v2 (Phase E). Reconciles the two
independent "is this species new / is this species regular" implementations
[historical-baseline-maturity-contract.md](historical-baseline-maturity-contract.md)
itself disclosed and deliberately left unmerged, into one canonical
definition consumed by every surface that makes this claim: Today's
dashboard, Bird Log's overview grid, and Bird Log's per-label history.

## The two prior definitions

**Canonical (`mockingbird.analytics.historical_baseline.compute_species_
historical_statuses`, unchanged by this milestone):** wildlife-inclusive
(any confirmed named species, not just birds), coverage-aware ("regular"
requires >= `MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR` (3) distinct days with
>= `USABLE_DAY_MONITORED_SECONDS_THRESHOLD` (2 hours) of durable monitored
exposure, from the `MonitoringExposureIntervalModel` ledger -- never a raw
calendar day), a bounded 366-day trailing window for regularity, and an
unbounded all-time `GROUP BY` aggregate for "is this taxon's first-ever
confirmed record in this period" (immune to row-count truncation). "New" is
only claimed once Place-wide `baseline_maturity == "established"`; a
thinner history gets the softer "first_record" for the identical
underlying fact. Already the sole source of `PlaceActivityReportTaxonEntry.
historical_status` (Today's Place Activity Report / Calm Daily Digest).

**Legacy (`ProductRepository._dashboard_today_summary`'s own `new_today`/
`recent_regulars`, now replaced):** bird-only (`VisitReviewOutcome.
confirmed_bird` specifically -- a confirmed non-bird wildlife taxon could
never be "new" or "regular" here, no matter how novel or recurring),
coverage-blind ("regular" meant >= 3 *raw calendar days* within a fixed
*14-day* trailing window, with no monitored-duration floor at all -- a
handful of 3-minute days counted identically to well-monitored ones), and
"new" meant "absent from a 5000-row-capped scan of earlier reviewed
Visits" -- silently reproducible as a false "new" purely from row-volume
truncation, independent of any real history.

**Partial (`wildlife_journal_overview`/`wildlife_journal_history`, now
fixed):** already wildlife-inclusive and already reused the canonical
module's constants and its `usable_dates` set, and already called
`_historical_place_baseline_and_species_statuses` in the same request --
but discarded its `SpeciesHistoricalStatus` result and recomputed
`is_regular`/`distinct_confirmed_usable_days` a second time from its own
record grouping (self-documented as deliberate at the time: "this
surface's own `baseline_maturity`/`is_regular` ... remain the source of
truth for this response"). A correct-by-construction second computation is
still a second computation -- any future change to the canonical rule
would silently not apply here unless remembered. `is_new_label_in_range`
was the one case with no canonical counterpart at all (see "What stays
deliberately separate" below).

### Confirmed disagreement (not merely theoretical)

Concrete scenarios exist where the legacy and canonical definitions
produced opposite verdicts for the same species on the same day -- for
example, a species confirmed on 3 raw calendar days each with only a few
monitored minutes read "Regular here" on the legacy Dashboard panel while
correctly failing the canonical coverage bar everywhere else; a species
regular by every usable-day measure but with its most recent sighting more
than 14 raw days ago was omitted from the legacy panel entirely; and a
confirmed non-bird wildlife taxon's genuine debut could never register as
"new" on the legacy panel at all. See `tests/
test_canonical_new_regular_species_consistency.py` for these as executable
fixtures, and `historical-baseline-maturity-contract.md`'s own "What
already existed, reused here" section, which named this exact gap and
explicitly chose not to close it at the time.

## The canonical contract

**`compute_species_historical_statuses` is the only place "new" /
"first_record" / "regular" / "seen_before" is decided.** Every consumer
reaches it through `ProductRepository._historical_place_baseline_and_
species_statuses` (never re-implements any part of the decision) and
surfaces the resulting `SpeciesHistoricalStatusValue` under a field named
`historical_status`:

- **Today** (`DashboardTodaySpecies.historical_status`, feeding `new_today`/
  `recent_regulars`): the canonical call uses `period_start_at=day_start,
  period_end_at=day_end` -- the same local-day boundaries `place_activity_
  report`'s own Today integration uses for the identical taxon, so a
  species' status here is always identical to what the Calm Daily Digest
  would show for it. `new_today` keeps only taxa whose status is `"new"`/
  `"first_record"`; `recent_regulars` keeps only `"regular"`, still scoped
  to taxa with a qualifying Visit in the trailing 14 days (an unchanged
  *presentation* bound -- which regulars are recent enough to show -- not a
  second truth definition).
- **Bird Log overview** (`WildlifeJournalLabelSummary.historical_status`)
  **and history** (`WildlifeJournalHistoryResponse.historical_status`):
  the canonical call now uses `period_start_at=` today's local midnight
  (not the full 366-day window) for the identical reason Today does --
  passing the full window would make `is_first_in_period` span an entire
  year, permanently classifying any taxon first confirmed at any point in
  the last year as `"new"`/`"first_record"` and never `"regular"`. Bird Log
  is a live view rather than a fixed report period, so "today" (as of the
  moment of the request) is its equivalent narrow window.
- Both `is_regular`/`distinct_confirmed_usable_days` fields (kept for
  backward compatibility) are now populated *from* the canonical status
  object rather than independently recomputed, with the previous local
  computation retained only as a defensive fallback for the edge case
  where a label's confirmed records fall entirely outside the canonical
  call's own Stream scope (for example, every confirmation is on an
  archived Stream) -- `historical_status` is `None` in that case rather
  than fabricating a verdict; a real confirmed label is still shown, never
  hidden.

## Coverage requirements (unchanged from the canonical module)

- A calendar day counts toward regularity or baseline maturity only with
  >= 2 hours of durable monitored exposure that day
  (`USABLE_DAY_MONITORED_SECONDS_THRESHOLD`).
- "Regular" requires >= 3 distinct usable days within the trailing 366-day
  window, and is structurally impossible while Place-wide baseline
  maturity is `"insufficient"` (fewer than 3 usable days exist at all) --
  asserted in code, not just documented.
- "New" is worded as "new" only once Place-wide baseline maturity reaches
  `"established"` (>= 7 usable days); a genuine first-ever record before
  that reads "first_record" -- the same underlying fact, honestly softer
  wording, never "new" merely because the system (or a Stream) was offline
  before rather than because the species is actually absent.
- Every consumer now recognizes any confirmed wildlife taxon (not just
  birds), matching Bird Log's own pre-existing scope.

### A known, separate, currently-latent gap

Wildlife-inclusiveness at the *query* level does not by itself make a
non-bird species eligible for "new"/"regular": `compute_species_historical_
statuses` (via `place_activity_report._classify`) requires a confirmed
taxon's own taxonomy row to have `is_species=True`, and the shipped seed
taxonomy (`api/demo_data.py`) currently has **no non-bird category with
`is_species=True`** -- every mammal/pet-style seed label ("squirrel", "cat",
...) is a kind-level, not species-level, taxon today. A confirmed squirrel
or deer is now correctly recognized as confirmed wildlife everywhere
(Activity Library, Bird Log, Today), but cannot yet earn a "new"/"regular"
historical-species verdict until a real non-bird *species*-level taxonomy
entry exists. This is a taxonomy-content gap, not a logic gap; `tests/
test_dashboard_today.py::test_today_summary_new_today_is_wildlife_inclusive_
not_bird_only` proves the code path itself is correct by inserting one such
row directly.

## What stays deliberately separate

`WildlifeJournalHistoryResponse.is_new_label_in_range` is **not** replaced
by `historical_status` -- it answers a different, narrower question ("is
this taxon's all-time-first record visible inside the date range I have
currently selected in the UI," including the `all_time` preset, where it
is unconditionally `False`) than `historical_status`'s always-on, filter-
independent "is this taxon new" fact. Both are returned side by side;
callers wanting "is this species new, period" should read
`historical_status`, and callers building the "New to your reviewed
history in this range" callout on a filtered view should keep using
`is_new_label_in_range`.

`place_change_summary`'s "recorded more/less often recently" is a distinct
concept (recent-vs-reference presence-day comparison) and was never a
second New/Regular implementation -- see
[meaningful-change-detection-contract.md](meaningful-change-detection-contract.md).
It explicitly defers the "first ever" case to this module and never emits
`"new"`/`"regular"` itself.

## Tests proving surfaces cannot disagree

`tests/test_canonical_new_regular_species_consistency.py` seeds one shared
fixture per scenario and asserts `ProductRepository.dashboard_summary` and
`ProductRepository.wildlife_journal_overview` produce identical verdicts
for the same taxon on the same day: a genuinely regular species reads
`"regular"` on both; a species confirmed on 3 raw calendar days with zero
recorded monitoring reads *not* regular on both (the exact coverage-blind
disagreement this milestone closes); and a taxon's true debut reads
`"new"`/`"first_record"` identically on both. `tests/test_dashboard_today.py`
and `tests/test_historical_baseline_repository.py` cover each surface's own
remaining behavior (truncation removal, wildlife-inclusiveness, the
period-anchoring fix) individually.
