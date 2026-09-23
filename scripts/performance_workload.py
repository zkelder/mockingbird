"""Realistic v0.1 load-profile generation for release performance measurement.

Performance / Scale / Stability Closure v1.

This module builds *credible v0.1* observation histories -- not enterprise
or multi-site scale -- so that release performance claims rest on measured
behaviour at data volumes a real MockingBird owner can actually reach.

Why these sizes and not others
------------------------------
Every profile's Visit count is derived from this repository's own accepted
field evidence, not invented:

- *Real Field Acceptance v1* (2026-08-16) admitted 5 Visits in a ~97.5
  minute representative daylight session.
- *End-to-End Bird Encounter Recall Closure v1* (2026-08-19) counted 22
  genuine bird encounters in 92.2 minutes at 68.2% recall -- i.e. ~15
  admitted Visits/hour during genuinely busy feeder activity.
- *Whole-Product UI / Accessibility / Performance Closure v1* (2026-08-27)
  measured its endpoints against a 371-Visit / 89-item-backlog dataset,
  which is the largest previously-measured MockingBird library.

Wildlife activity is strongly bimodal across a day: a couple of busy
feeding periods and long quiet stretches. Taking ~2 busy hours/day at the
measured ~15/hour rate, plus a sparse tail, lands at roughly 30-35 admitted
Visits/day for an established backyard feeder -- which is what Profiles B
and D below are built from. Media volume per Visit follows the repository's
own accepted `_DEFAULT_MAX_EVIDENCE_ITEMS_PER_CANDIDATE = 4`.

Fidelity and its limits
-----------------------
Rows are written through the real ORM models with the same column values
the real Observation path produces, so query planning, index use, join
cost, and response-serialization cost are all genuinely exercised. Two
deliberate, disclosed departures keep generation tractable:

- media *bytes* are small synthetic JPEGs, not real camera frames, so this
  module measures database/API behaviour rather than image decode cost;
  `--media-bytes` exists for the storage-growth measurement that does care.
- no detector/classifier inference runs; `SpeciesSuggestionModel` rows are
  written directly with plausible values, exactly as a real BioCLIP run
  would leave behind.

Neither affects the query shapes, row counts, or response sizes this
milestone measures.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import random
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_ROOT / "src"))

from mockingbird.repository.product_repository import (  # noqa: E402
    DetectionProposalModel,
    DetectionRunModel,
    ProductRepository,
    SourceProviderConfigurationModel,
    SpeciesSuggestionModel,
)
from mockingbird.storage.models import (  # noqa: E402
    CameraSourceModel,
    DetectionModel,
    EventModel,
    MediaAssetModel,
    ReviewLabelModel,
    StreamModel,
    VisitEvidenceLinkModel,
    VisitModel,
    ZoneModel,
)


# A smallest-possible real JPEG. Enough for the media layer to treat the
# file as present and non-empty; `--media-bytes` pads it when storage
# growth (rather than row count) is what is being measured.
_TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300"
    + "08" * 64
    + "ffc0000b080001000101011100ffc40014000100000000000000000000000000000009"
    "ffda0008010100003f00d2cf20ffd9"
)

# Species mix modelled on an ordinary North American backyard feeder: a
# few dominant regulars, a long tail of occasional visitors, and a
# non-bird share that the detector legitimately admits.
_BIRD_SPECIES: tuple[tuple[str, float], ...] = (
    ("Northern Cardinal", 0.16),
    ("House Finch", 0.14),
    ("American Goldfinch", 0.12),
    ("Tufted Titmouse", 0.10),
    ("Carolina Chickadee", 0.10),
    ("Blue Jay", 0.08),
    ("Mourning Dove", 0.07),
    ("Downy Woodpecker", 0.06),
    ("White-breasted Nuthatch", 0.05),
    ("Red-bellied Woodpecker", 0.04),
    ("Carolina Wren", 0.03),
    ("Song Sparrow", 0.02),
    ("Brown-headed Cowbird", 0.015),
    ("Pine Siskin", 0.01),
    ("Rose-breasted Grosbeak", 0.005),
)
_OTHER_SUBJECTS: tuple[str, ...] = ("Eastern Gray Squirrel", "Eastern Chipmunk", "White-tailed Deer")

# Real `mockingbird.api.schemas.ZoneType` members, not invented strings.
_ZONE_NAMES: tuple[tuple[str, str], ...] = (
    ("Feeder", "feeder"),
    ("Bird bath", "birdbath"),
    ("Ground", "ground"),
)


@dataclass(frozen=True)
class WorkloadProfile:
    """One credible v0.1 workload, with the reasoning that justifies it."""

    key: str
    title: str
    rationale: str
    days: int
    streams: int
    visits_per_day: float
    reviewed_fraction: float
    evidence_per_visit: int = 4
    # A burst day multiplies one day's activity, modelling genuine bursty
    # wildlife behaviour rather than a uniform arrival rate.
    burst_days: int = 0
    burst_multiplier: float = 1.0

    @property
    def total_visits(self) -> int:
        ordinary = (self.days - self.burst_days) * self.visits_per_day
        bursty = self.burst_days * self.visits_per_day * self.burst_multiplier
        return int(round(ordinary + bursty))


PROFILES: dict[str, WorkloadProfile] = {
    "a": WorkloadProfile(
        key="a",
        title="Profile A -- fresh / small install",
        rationale=(
            "The first days of use: one Place, one Camera Node, a handful of "
            "observations. Sized at 4 days x ~13 Visits/day, below the "
            "established-feeder rate because a newly-aimed camera and an "
            "un-habituated yard both produce less than a settled install."
        ),
        days=4,
        streams=1,
        visits_per_day=13,
        reviewed_fraction=0.35,
    ),
    "b": WorkloadProfile(
        key="b",
        title="Profile B -- established home install",
        rationale=(
            "Three months of ordinary use at the rate this repository's own "
            "field evidence measured (~2 busy hours/day at ~15 admitted "
            "Visits/hour, plus a sparse tail => ~30/day), across two Streams, "
            "with a realistic mixed review backlog. ~2,700 Visits -- roughly "
            "7x the largest previously-measured MockingBird library."
        ),
        days=90,
        streams=2,
        visits_per_day=30,
        reviewed_fraction=0.62,
    ),
    "c": WorkloadProfile(
        key="c",
        title="Profile C -- busy period",
        rationale=(
            "Profile B's library plus genuine burst pressure: 6 of the 90 "
            "days carry 4x normal activity (a migration push, a cold snap "
            "driving heavy feeder use), producing clustered events, a larger "
            "review backlog, and the queue pressure a real owner sees in a "
            "busy week rather than a synthetic flood."
        ),
        days=90,
        streams=2,
        visits_per_day=30,
        reviewed_fraction=0.38,
        burst_days=6,
        burst_multiplier=4.0,
    ),
    "d": WorkloadProfile(
        key="d",
        title="Profile D -- large v0.1 library",
        rationale=(
            "A serious early adopter: a full year of continuous use across "
            "three Streams at the same measured daily rate. ~11,000 Visits "
            "and ~44,000 media assets -- deliberately beyond what an ordinary "
            "owner reaches in v0.1's lifetime, which is exactly what makes it "
            "able to expose unbounded queries, linear scans and pathological "
            "rendering before a real user does."
        ),
        days=365,
        streams=3,
        visits_per_day=30,
        reviewed_fraction=0.55,
    ),
}


@dataclass
class SeedResult:
    profile: str
    visits: int
    events: int
    media_assets: int
    evidence_links: int
    review_labels: int
    species_suggestions: int
    detections: int
    streams: int
    zones: int
    database_bytes: int
    media_bytes: int
    seconds: float
    extra: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "visits": self.visits,
            "events": self.events,
            "media_assets": self.media_assets,
            "evidence_links": self.evidence_links,
            "review_labels": self.review_labels,
            "species_suggestions": self.species_suggestions,
            "detections": self.detections,
            "streams": self.streams,
            "zones": self.zones,
            "database_bytes": self.database_bytes,
            "media_bytes": self.media_bytes,
            "seconds": round(self.seconds, 2),
            **self.extra,
        }


def _weighted_species(rng: random.Random) -> str:
    roll = rng.random()
    cumulative = 0.0
    for name, weight in _BIRD_SPECIES:
        cumulative += weight
        if roll <= cumulative:
            return name
    return _BIRD_SPECIES[0][0]


def _activity_weight(hour: int) -> float:
    """Relative wildlife activity by hour -- dawn and late-afternoon peaks."""

    if hour < 6 or hour > 19:
        return 0.0
    if 6 <= hour <= 9:
        return 3.0
    if 15 <= hour <= 18:
        return 2.5
    return 1.0


def _pick_hour(rng: random.Random) -> int:
    hours = list(range(24))
    weights = [_activity_weight(hour) for hour in hours]
    return rng.choices(hours, weights=weights, k=1)[0]


def build_workload(
    repository: ProductRepository,
    profile: WorkloadProfile,
    *,
    media_bytes: int = 0,
    seed: int = 20260922,
    write_media_files: bool = True,
    now: datetime | None = None,
    progress: bool = False,
    id_prefix: str = "perf",
) -> SeedResult:
    """Populate `repository` with `profile`'s worth of realistic history.

    `id_prefix` keeps successive calls against the same repository from
    colliding, so a soak can append fresh activity to a library it has
    already seeded instead of trying to recreate the same Source.
    """

    import time as _time

    started = _time.perf_counter()
    rng = random.Random(seed)
    now = now or datetime.now(UTC)
    media_root = Path(repository.media_root)
    media_root.mkdir(parents=True, exist_ok=True)

    payload = _TINY_JPEG
    if media_bytes > len(_TINY_JPEG):
        # Pad after the EOI marker: still a decodable JPEG, but with the
        # on-disk footprint a real evidence frame has.
        payload = _TINY_JPEG + os.urandom(media_bytes - len(_TINY_JPEG))

    counts = {
        "events": 0,
        "visits": 0,
        "media": 0,
        "links": 0,
        "labels": 0,
        "suggestions": 0,
        "detections": 0,
    }
    media_written = 0

    with repository.session_factory() as session:
        with session.begin():
            stream_ids: list[str] = []
            zones_by_stream: dict[str, list[str]] = {}
            for stream_index in range(profile.streams):
                source_id = f"{id_prefix}-source-{stream_index}"
                stream_id = f"{id_prefix}-stream-{stream_index}"
                if session.get(CameraSourceModel, source_id) is not None:
                    # Appending to a library this prefix already seeded.
                    stream_ids.append(stream_id)
                    zones_by_stream[stream_id] = [
                        f"{id_prefix}-zone-{stream_index}-{zone_index}"
                        for zone_index in range(len(_ZONE_NAMES))
                    ]
                    continue
                session.add(
                    CameraSourceModel(
                        id=source_id,
                        name=f"Backyard camera {stream_index + 1}",
                        # A real, non-demo `SourceKind` -- an RTSP camera is
                        # exactly what a paired Camera Node presents as.
                        kind="rtsp",
                        status="connected",
                        description="Performance workload camera.",
                    )
                )
                # A real, recognised provider key, so nothing this workload
                # produces is treated as demo history.
                session.add(
                    SourceProviderConfigurationModel(
                        source_id=source_id,
                        provider_key="camera_node",
                        config_json="{}",
                        updated_at=now,
                    )
                )
                session.add(
                    StreamModel(
                        id=stream_id,
                        source_id=source_id,
                        name=f"Feeder view {stream_index + 1}",
                        description="Performance workload stream.",
                        is_live=True,
                    )
                )
                stream_ids.append(stream_id)
                zone_ids: list[str] = []
                for zone_index, (zone_name, zone_type) in enumerate(_ZONE_NAMES):
                    zone_id = f"{id_prefix}-zone-{stream_index}-{zone_index}"
                    session.add(
                        ZoneModel(
                            id=zone_id,
                            stream_id=stream_id,
                            name=f"{zone_name} {stream_index + 1}",
                            zone_type=zone_type,
                            polygon_json=json.dumps(
                                [
                                    {"x": 0.1, "y": 0.1},
                                    {"x": 0.9, "y": 0.1},
                                    {"x": 0.9, "y": 0.9},
                                    {"x": 0.1, "y": 0.9},
                                ]
                            ),
                            is_active=True,
                            monitoring_policy_json=None,
                        )
                    )
                    zone_ids.append(zone_id)
                zones_by_stream[stream_id] = zone_ids

        burst_days = set(
            rng.sample(range(profile.days), profile.burst_days) if profile.burst_days else []
        )

        pending = 0
        for day_offset in range(profile.days):
            day_start = (now - timedelta(days=profile.days - day_offset - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            rate = profile.visits_per_day
            if day_offset in burst_days:
                rate *= profile.burst_multiplier
            # Poisson-ish daily variation around the profile's mean rate.
            day_visits = max(0, int(round(rng.gauss(rate, rate * 0.35))))

            for _ in range(day_visits):
                stream_id = stream_ids[rng.randrange(len(stream_ids))]
                zone_id = zones_by_stream[stream_id][rng.randrange(len(_ZONE_NAMES))]
                started_at = day_start + timedelta(
                    hours=_pick_hour(rng), minutes=rng.randrange(60), seconds=rng.randrange(60)
                )
                ended_at = started_at + timedelta(seconds=rng.randrange(12, 180))

                is_bird = rng.random() > 0.12
                subject = _weighted_species(rng) if is_bird else rng.choice(_OTHER_SUBJECTS)
                reviewed = rng.random() < profile.reviewed_fraction

                event_id = f"{id_prefix}-event-{counts['events']}"
                visit_id = f"{id_prefix}-visit-{counts['visits']}"
                counts["events"] += 1
                counts["visits"] += 1

                session.add(
                    EventModel(
                        id=event_id,
                        stream_id=stream_id,
                        title=f"{subject} at the feeder",
                        event_type="wildlife_visit",
                        started_at=started_at,
                        ended_at=ended_at,
                        primary_zone_id=zone_id,
                        review_status="reviewed" if reviewed else "needs_review",
                    )
                )
                session.add(
                    DetectionModel(
                        id=f"{id_prefix}-detection-{counts['detections']}",
                        event_id=event_id,
                        label="animal",
                        confidence=round(rng.uniform(0.35, 0.98), 3),
                        zone_id=zone_id,
                        bbox_json=json.dumps({"x": 0.3, "y": 0.3, "width": 0.2, "height": 0.2}),
                    )
                )
                counts["detections"] += 1

                confidence = round(rng.uniform(0.28, 0.96), 3)
                asset_ids: list[str] = []
                for frame_index in range(profile.evidence_per_visit):
                    asset_id = f"{id_prefix}-media-{counts['media']}"
                    counts["media"] += 1
                    relative = f"{id_prefix}/{asset_id}.jpg"
                    if write_media_files:
                        target = media_root / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(payload)
                        media_written += len(payload)
                    captured = started_at + timedelta(seconds=frame_index * 2)
                    session.add(
                        MediaAssetModel(
                            id=asset_id,
                            source_id=stream_id.replace("-stream-", "-source-"),
                            stream_id=stream_id,
                            filename=f"{asset_id}.jpg",
                            content_type="image/jpeg",
                            media_type="image",
                            local_path=relative,
                            original_filename=f"{asset_id}.jpg",
                            file_size_bytes=len(payload),
                            created_at=captured,
                            evidence_role=(
                                "classifier_same_frame" if frame_index == 0 else "monitoring_frame"
                            ),
                            image_width=1920,
                            image_height=1080,
                            captured_at=captured,
                            trigger_started_at=started_at,
                            capture_requested_at=started_at,
                            alignment_status="aligned",
                            normalized_track_box_json=json.dumps(
                                {"x": 0.3, "y": 0.3, "width": 0.2, "height": 0.2}
                            ),
                        )
                    )
                    asset_ids.append(asset_id)

                for sort_order, asset_id in enumerate(asset_ids):
                    session.add(
                        VisitEvidenceLinkModel(
                            id=f"{id_prefix}-link-{counts['links']}",
                            visit_id=visit_id,
                            media_asset_id=asset_id,
                            captured_at=started_at + timedelta(seconds=sort_order * 2),
                            frame_sequence=sort_order,
                            sort_order=sort_order,
                            is_primary=sort_order == 0,
                            evidence_role=(
                                "classifier_same_frame" if sort_order == 0 else "monitoring_frame"
                            ),
                            created_at=started_at,
                        )
                    )
                    counts["links"] += 1

                session.add(
                    VisitModel(
                        id=visit_id,
                        event_id=event_id,
                        subject_label="bird" if is_bird else "animal",
                        species_guess=subject if is_bird else None,
                        confidence=confidence if is_bird else None,
                        reviewed_label=subject if reviewed else None,
                        review_status="reviewed" if reviewed else "needs_review",
                        representative_media_path=f"{id_prefix}/{asset_ids[0]}.jpg",
                        zone_id=zone_id,
                        is_superseded=False,
                    )
                )

                if is_bird:
                    session.add(
                        SpeciesSuggestionModel(
                            id=f"{id_prefix}-suggestion-{counts['suggestions']}",
                            stream_id=stream_id,
                            event_id=event_id,
                            visit_id=visit_id,
                            media_asset_id=asset_ids[0],
                            adapter_id="bioclip_v2",
                            adapter_name="BioCLIP-2",
                            suggested_label=subject,
                            suggested_common_name=subject,
                            confidence=confidence,
                            rank=1,
                            alternatives_json=json.dumps(
                                [
                                    {
                                        "label": _weighted_species(rng),
                                        "confidence": round(confidence * 0.6, 3),
                                    }
                                ]
                            ),
                            status="pending",
                            created_at=ended_at,
                        )
                    )
                    counts["suggestions"] += 1

                # One DetectionRun per detected frame, matching the real
                # per-media-asset shape of `DetectionRunModel`.
                run_id = f"{id_prefix}-run-{counts['visits']}"
                session.add(
                    DetectionRunModel(
                        id=run_id,
                        media_asset_id=asset_ids[0],
                        source="future_model",
                        summary=None,
                        status="completed",
                        created_at=started_at,
                        completed_at=started_at + timedelta(seconds=1),
                    )
                )
                session.add(
                    DetectionProposalModel(
                        id=f"{id_prefix}-proposal-{counts['detections']}",
                        run_id=run_id,
                        media_asset_id=asset_ids[0],
                        stream_id=stream_id,
                        zone_id=zone_id,
                        event_id=event_id,
                        visit_id=visit_id,
                        label="animal",
                        confidence=confidence,
                        bbox_json=json.dumps({"x": 0.3, "y": 0.3, "width": 0.2, "height": 0.2}),
                        suggested_event_type="wildlife_visit",
                        suggested_subject_label="bird" if is_bird else "animal",
                        suggested_species=subject if is_bird else None,
                        status="accepted",
                        notes=None,
                        created_at=started_at,
                        decided_at=ended_at,
                    )
                )

                if reviewed:
                    session.add(
                        ReviewLabelModel(
                            id=f"{id_prefix}-label-{counts['labels']}",
                            target_type="visit",
                            target_id=visit_id,
                            label=subject,
                            notes=None,
                            created_at=ended_at + timedelta(hours=rng.randrange(1, 72)),
                            review_origin="human",
                            reviewer_identity="Performance workload owner",
                            review_action="confirm",
                        )
                    )
                    counts["labels"] += 1

                pending += 1
                if pending >= 400:
                    session.commit()
                    pending = 0
                    if progress:
                        print(
                            f"  ... {counts['visits']} Visits, {counts['media']} media assets",
                            file=sys.stderr,
                        )
            if pending:
                session.commit()
                pending = 0
        session.commit()

    db_path = Path(repository.db_url.replace("sqlite:///", ""))
    return SeedResult(
        profile=profile.key,
        visits=counts["visits"],
        events=counts["events"],
        media_assets=counts["media"],
        evidence_links=counts["links"],
        review_labels=counts["labels"],
        species_suggestions=counts["suggestions"],
        detections=counts["detections"],
        streams=profile.streams,
        zones=profile.streams * len(_ZONE_NAMES),
        database_bytes=db_path.stat().st_size if db_path.exists() else 0,
        media_bytes=media_written,
        seconds=_time.perf_counter() - started,
    )


def open_repository(root: Path) -> ProductRepository:
    """Open (creating if needed) an isolated repository under `root`."""

    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MOCKINGBIRD_BACKUP_ROOT", str(root / "backups"))
    return ProductRepository(
        db_url=f"sqlite:///{root / 'mockingbird.sqlite3'}",
        media_root=root / "media",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--media-bytes", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--no-media-files", action="store_true")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--id-prefix", default="perf")
    args = parser.parse_args(argv)

    profile = PROFILES[args.profile]
    print(f"{profile.title}\n{profile.rationale}", file=sys.stderr)
    print(f"target ~{profile.total_visits} Visits over {profile.days} days", file=sys.stderr)

    repository = open_repository(args.root)
    try:
        result = build_workload(
            repository,
            profile,
            media_bytes=args.media_bytes,
            seed=args.seed,
            write_media_files=not args.no_media_files,
            progress=True,
            id_prefix=args.id_prefix,
        )
    finally:
        repository.close()

    text = json.dumps(result.as_dict(), indent=2)
    print(text)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
