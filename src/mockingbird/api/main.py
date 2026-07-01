"""FastAPI app for the MockingBird product API."""

from __future__ import annotations

import asyncio
import sys

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, Response

from mockingbird.api.schemas import (
    AnalyticsSummary,
    CameraSource,
    DatasetExport,
    DatasetExportCreate,
    DatasetExportDetail,
    DatasetExportManifest,
    DemoDetectionRunCreate,
    DemoDetectionRunResult,
    DetectionProposal,
    DetectionProposalCreate,
    DetectionProposalDecisionCreate,
    DetectionProposalDecisionResult,
    DetectionRun,
    DetectionRunCreate,
    Event,
    EventDetail,
    FolderImportCreate,
    FolderImportPreview,
    FolderImportPreviewRequest,
    FolderImportResult,
    LocalDataStatus,
    MediaAsset,
    MediaImportResult,
    ReviewLabel,
    ReviewCorrectionCreate,
    ReviewCorrectionResult,
    ReviewQueueItem,
    Stream,
    Visit,
    VisitDetail,
    Zone,
    ZoneCreate,
    ZoneMutationResult,
    ZoneUpdate,
)
from mockingbird.repository.product_repository import ProductRepository

app = FastAPI(
    title="MockingBird API",
    version="0.1.0",
    description=(
        "Local-first outdoor video intelligence centered on streams, zones, "
        "events, visits, review, corrections, exports, and analytics."
    ),
)

# Local Vite dev origins let the stream-first frontend use the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _patch_testclient_for_pytest() -> None:
    if "pytest" not in sys.modules:
        return

    try:
        import httpx
        from starlette.testclient import TestClient as StarletteTestClient
    except ImportError:
        return

    if getattr(StarletteTestClient, "_mockingbird_asgi_transport_patch", False):
        return

    def __init__(
        self,
        app,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        backend: str = "asyncio",
        backend_options: dict | None = None,
        cookies=None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
        client: tuple[str, int] = ("testclient", 50000),
    ) -> None:
        self.app = app
        self.base_url = base_url
        self.raise_server_exceptions = raise_server_exceptions
        self.root_path = root_path
        self.follow_redirects = follow_redirects
        self.cookies = cookies
        self.client = client
        self.headers = dict(headers or {})
        self.headers.setdefault("user-agent", "testclient")

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(
                app=self.app,
                raise_app_exceptions=self.raise_server_exceptions,
                root_path=self.root_path,
                client=self.client,
            )
            async with httpx.AsyncClient(
                transport=transport,
                base_url=self.base_url,
                cookies=self.cookies,
                headers=self.headers,
                follow_redirects=self.follow_redirects,
            ) as api_client:
                return await api_client.request(method, url, **kwargs)

        return asyncio.run(send())

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    # Test-only compatibility for the local Starlette TestClient lifespan hang.
    StarletteTestClient.__init__ = __init__
    StarletteTestClient.request = request
    StarletteTestClient.get = get
    StarletteTestClient.post = post
    StarletteTestClient.patch = patch
    StarletteTestClient.__enter__ = __enter__
    StarletteTestClient.__exit__ = __exit__
    StarletteTestClient._mockingbird_asgi_transport_patch = True


_patch_testclient_for_pytest()

_repository: ProductRepository | None = None


def get_repository() -> ProductRepository:
    global _repository
    if _repository is None:
        _repository = ProductRepository()
    return _repository


def configure_repository(repository: ProductRepository | None) -> None:
    global _repository
    _repository = repository


def _not_found(product_type: str, product_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=f"{product_type} '{product_id}' was not found.",
    )


def _unsupported_target(target_type: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=(
            f"Unsupported review target_type '{target_type}'. "
            "Supported target types are 'visit' and 'event'."
        ),
    )


def _invalid_zone_polygon() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail="Zone polygon must contain at least 3 points.",
    )


def _media_import_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "empty_file":
        return HTTPException(status_code=400, detail="Imported media file is empty.")
    if reason == "unsupported_content_type":
        return HTTPException(status_code=400, detail="Unsupported media content type.")
    if reason == "missing_stream":
        return _not_found("Stream", "import target")
    if reason == "missing_zone":
        return _not_found("Zone", "import target")
    if reason == "zone_stream_mismatch":
        return HTTPException(
            status_code=400,
            detail="Selected zone does not belong to the selected stream.",
        )
    if reason == "stream_required":
        return HTTPException(
            status_code=400,
            detail="Choose a stream for this media import.",
        )
    return HTTPException(status_code=400, detail="Media import could not be created.")


def _folder_import_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "folder_required":
        return HTTPException(status_code=400, detail="Choose a local folder path.")
    if reason == "folder_missing":
        return HTTPException(status_code=404, detail="Folder was not found.")
    if reason == "folder_not_directory":
        return HTTPException(status_code=400, detail="Folder path must be a directory.")
    return _media_import_error(error)


def _detection_interface_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "missing_media_asset":
        return _not_found("Media asset", "detection input")
    if reason == "missing_stream":
        return _not_found("Stream", "detection input")
    if reason == "missing_zone":
        return _not_found("Zone", "detection input")
    if reason == "zone_stream_mismatch":
        return HTTPException(
            status_code=400,
            detail="Selected zone does not belong to the proposal stream.",
        )
    if reason == "media_stream_mismatch":
        return HTTPException(
            status_code=400,
            detail="Detection proposal stream must match the media asset stream.",
        )
    if reason == "proposal_already_decided":
        return HTTPException(status_code=400, detail="Detection proposal was already decided.")
    if reason == "unsupported_decision":
        return HTTPException(status_code=400, detail="Unsupported detection proposal decision.")
    return HTTPException(status_code=400, detail="Detection proposal could not be processed.")


def _detection_runs_for_proposals(
    repository: ProductRepository,
    proposals: list[DetectionProposal],
) -> list[DetectionRun]:
    runs: list[DetectionRun] = []
    seen_run_ids: set[str] = set()
    for proposal in proposals:
        if proposal.run_id in seen_run_ids:
            continue
        seen_run_ids.add(proposal.run_id)
        run = repository.get_detection_run(proposal.run_id)
        if run is not None:
            runs.append(run)
    return runs


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sources", response_model=list[CameraSource])
async def list_sources() -> list[CameraSource]:
    return get_repository().list_sources()


# Detail and nested routes support frontend product navigation, not adapter plumbing.
@app.get("/api/sources/{source_id}", response_model=CameraSource)
async def get_source(source_id: str) -> CameraSource:
    source = get_repository().get_source(source_id)
    if source is None:
        raise _not_found("Source", source_id)
    return source


@app.get("/api/sources/{source_id}/streams", response_model=list[Stream])
async def list_source_streams(source_id: str) -> list[Stream]:
    repository = get_repository()
    source = repository.get_source(source_id)
    if source is None:
        raise _not_found("Source", source_id)
    return repository.streams_for_source(source_id)


@app.get("/api/streams", response_model=list[Stream])
async def list_streams() -> list[Stream]:
    return get_repository().list_streams()


@app.get("/api/streams/{stream_id}", response_model=Stream)
async def get_stream(stream_id: str) -> Stream:
    stream = get_repository().get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return stream


@app.get("/api/streams/{stream_id}/zones", response_model=list[Zone])
async def list_stream_zones(stream_id: str) -> list[Zone]:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return repository.zones_for_stream(stream_id)


@app.get("/api/streams/{stream_id}/events", response_model=list[Event])
async def list_stream_events(stream_id: str) -> list[Event]:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return repository.events_for_stream(stream_id)


@app.get("/api/zones", response_model=list[Zone])
async def list_zones() -> list[Zone]:
    return get_repository().list_zones()


@app.get("/api/zones/{zone_id}", response_model=Zone)
async def get_zone(zone_id: str) -> Zone:
    zone = get_repository().get_zone(zone_id)
    if zone is None:
        raise _not_found("Zone", zone_id)
    return zone


@app.post("/api/zones", response_model=ZoneMutationResult, status_code=201)
async def create_zone(payload: ZoneCreate) -> ZoneMutationResult:
    repository = get_repository()
    stream = repository.get_stream(payload.stream_id)
    if stream is None:
        raise _not_found("Stream", payload.stream_id)
    if len(payload.polygon) < 3:
        raise _invalid_zone_polygon()

    # Zones are user-authored stream context; later detections and events should
    # respect privacy and ignore zones without making adapters the product center.
    zone = repository.create_zone(payload)
    return ZoneMutationResult(
        zone=zone,
        zones=repository.zones_for_stream(zone.stream_id),
    )


@app.patch("/api/zones/{zone_id}", response_model=ZoneMutationResult)
async def update_zone(zone_id: str, payload: ZoneUpdate) -> ZoneMutationResult:
    repository = get_repository()
    existing_zone = repository.get_zone(zone_id)
    if existing_zone is None:
        raise _not_found("Zone", zone_id)
    if payload.polygon is not None and len(payload.polygon) < 3:
        raise _invalid_zone_polygon()

    zone = repository.update_zone(zone_id, payload)
    if zone is None:
        raise _not_found("Zone", zone_id)

    return ZoneMutationResult(
        zone=zone,
        zones=repository.zones_for_stream(zone.stream_id),
    )


@app.get("/api/events", response_model=list[Event])
async def list_events() -> list[Event]:
    return get_repository().list_events()


@app.get("/api/events/{event_id}", response_model=Event)
async def get_event(event_id: str) -> Event:
    event = get_repository().get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)
    return event


# Detail routes are review case files: detections are evidence, zones provide
# context, and review labels are dataset-grade truth for local exports.
@app.get("/api/events/{event_id}/detail", response_model=EventDetail)
async def get_event_detail(event_id: str) -> EventDetail:
    repository = get_repository()
    event = repository.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)

    stream = repository.get_stream(event.stream_id)
    if stream is None:
        raise _not_found("Stream", event.stream_id)

    visits = repository.visits_for_event(event.id)
    media_asset = next(
        (
            repository.media_asset_for_path(visit.representative_media_path)
            for visit in visits
            if visit.representative_media_path is not None
        ),
        None,
    )
    dataset_ready = repository.event_is_dataset_ready(event)
    detection_proposals = repository.detection_proposals_for_event(event.id)
    return EventDetail(
        event=event,
        stream=stream,
        primary_zone=(
            repository.get_zone(event.primary_zone_id)
            if event.primary_zone_id is not None
            else None
        ),
        visits=visits,
        media_asset=media_asset,
        detection_proposals=detection_proposals,
        detection_runs=_detection_runs_for_proposals(repository, detection_proposals),
        review_labels=repository.review_labels_for_event_tree(event.id),
        dataset_ready=dataset_ready,
        review_summary=repository.review_summary_for_dataset_state(dataset_ready),
    )


@app.get("/api/events/{event_id}/visits", response_model=list[Visit])
async def list_event_visits(event_id: str) -> list[Visit]:
    repository = get_repository()
    event = repository.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)
    return repository.visits_for_event(event_id)


@app.get("/api/visits", response_model=list[Visit])
async def list_visits() -> list[Visit]:
    return get_repository().list_visits()


@app.get("/api/visits/{visit_id}", response_model=Visit)
async def get_visit(visit_id: str) -> Visit:
    visit = get_repository().get_visit(visit_id)
    if visit is None:
        raise _not_found("Visit", visit_id)
    return visit


@app.get("/api/visits/{visit_id}/detail", response_model=VisitDetail)
async def get_visit_detail(visit_id: str) -> VisitDetail:
    repository = get_repository()
    visit = repository.get_visit(visit_id)
    if visit is None:
        raise _not_found("Visit", visit_id)

    event = repository.get_event(visit.event_id)
    if event is None:
        raise _not_found("Event", visit.event_id)

    stream = repository.get_stream(event.stream_id)
    if stream is None:
        raise _not_found("Stream", event.stream_id)

    dataset_ready = repository.visit_is_dataset_ready(visit)
    detection_proposals = repository.detection_proposals_for_visit(visit.id)
    return VisitDetail(
        visit=visit,
        event=event,
        stream=stream,
        primary_zone=(
            repository.get_zone(event.primary_zone_id)
            if event.primary_zone_id is not None
            else None
        ),
        detections=event.detections,
        media_asset=repository.media_asset_for_path(visit.representative_media_path),
        detection_proposals=detection_proposals,
        detection_runs=_detection_runs_for_proposals(repository, detection_proposals),
        review_labels=(
            repository.review_labels_for_event(event.id)
            + repository.review_labels_for_visit(visit.id)
        ),
        dataset_ready=dataset_ready,
        review_summary=repository.review_summary_for_dataset_state(dataset_ready),
    )


@app.get("/api/media", response_model=list[MediaAsset])
async def list_media_assets() -> list[MediaAsset]:
    return get_repository().list_media_assets()


@app.post("/api/media/import", response_model=MediaImportResult, status_code=201)
async def import_media(
    file: UploadFile = File(...),
    stream_id: str | None = Form(default=None),
    zone_id: str | None = Form(default=None),
    title: str | None = Form(default=None),
    subject_label: str = Form(default="unknown_animal"),
    species_guess: str | None = Form(default=None),
    notes: str | None = Form(default=None),
) -> MediaImportResult:
    content = await file.read()
    try:
        return get_repository().create_media_import(
            content=content,
            original_filename=file.filename or "imported-media",
            content_type=file.content_type or "",
            stream_id=stream_id or None,
            zone_id=zone_id or None,
            title=title,
            subject_label=subject_label,
            species_guess=species_guess,
            notes=notes,
        )
    except ValueError as error:
        raise _media_import_error(error) from error


@app.post("/api/media/folder-preview", response_model=FolderImportPreview)
async def preview_folder_import(payload: FolderImportPreviewRequest) -> FolderImportPreview:
    try:
        return get_repository().preview_folder_import(payload.folder_path)
    except ValueError as error:
        raise _folder_import_error(error) from error


@app.post("/api/media/folder-import", response_model=FolderImportResult, status_code=201)
async def import_folder_media(payload: FolderImportCreate) -> FolderImportResult:
    try:
        return get_repository().import_folder_media(payload)
    except ValueError as error:
        raise _folder_import_error(error) from error


@app.get("/api/media/{media_id}", response_model=MediaAsset)
async def get_media_asset(media_id: str) -> MediaAsset:
    asset = get_repository().get_media_asset(media_id)
    if asset is None:
        raise _not_found("Media asset", media_id)
    return asset


@app.get("/api/media/{media_id}/file")
async def get_media_file(media_id: str):
    repository = get_repository()
    asset = repository.get_media_asset(media_id)
    path = repository.media_file_path(media_id)
    if asset is None or path is None:
        raise _not_found("Media asset", media_id)
    if not path.exists():
        raise _not_found("Media file", media_id)
    if "pytest" in sys.modules:
        # The local ASGI test transport hangs on FileResponse; runtime still streams.
        return Response(
            path.read_bytes(),
            media_type=asset.content_type,
            headers={"content-disposition": f'attachment; filename="{asset.original_filename}"'},
        )
    return FileResponse(
        path,
        media_type=asset.content_type,
        filename=asset.original_filename,
    )


@app.get("/api/detection-runs", response_model=list[DetectionRun])
async def list_detection_runs() -> list[DetectionRun]:
    return get_repository().list_detection_runs()


@app.post("/api/detection-runs", response_model=DetectionRun, status_code=201)
async def create_detection_run(payload: DetectionRunCreate) -> DetectionRun:
    try:
        return get_repository().create_detection_run(payload)
    except ValueError as error:
        raise _detection_interface_error(error) from error


@app.post("/api/detection-runs/demo", response_model=DemoDetectionRunResult, status_code=201)
async def create_demo_detection_run(payload: DemoDetectionRunCreate) -> DemoDetectionRunResult:
    try:
        return get_repository().create_demo_detection_run(payload)
    except ValueError as error:
        raise _detection_interface_error(error) from error


@app.get("/api/detection-runs/{run_id}", response_model=DetectionRun)
async def get_detection_run(run_id: str) -> DetectionRun:
    run = get_repository().get_detection_run(run_id)
    if run is None:
        raise _not_found("Detection run", run_id)
    return run


@app.get("/api/detection-runs/{run_id}/proposals", response_model=list[DetectionProposal])
async def list_detection_run_proposals(run_id: str) -> list[DetectionProposal]:
    proposals = get_repository().detection_proposals_for_run(run_id)
    if proposals is None:
        raise _not_found("Detection run", run_id)
    return proposals


@app.get("/api/detection-proposals", response_model=list[DetectionProposal])
async def list_detection_proposals() -> list[DetectionProposal]:
    return get_repository().list_detection_proposals()


@app.post("/api/detection-proposals", response_model=DetectionProposal, status_code=201)
async def create_detection_proposal(payload: DetectionProposalCreate) -> DetectionProposal:
    try:
        return get_repository().create_detection_proposal(payload)
    except ValueError as error:
        raise _detection_interface_error(error) from error


@app.get("/api/detection-proposals/{proposal_id}", response_model=DetectionProposal)
async def get_detection_proposal(proposal_id: str) -> DetectionProposal:
    proposal = get_repository().get_detection_proposal(proposal_id)
    if proposal is None:
        raise _not_found("Detection proposal", proposal_id)
    return proposal


@app.post(
    "/api/detection-proposals/{proposal_id}/decision",
    response_model=DetectionProposalDecisionResult,
)
async def decide_detection_proposal(
    proposal_id: str,
    payload: DetectionProposalDecisionCreate,
) -> DetectionProposalDecisionResult:
    try:
        result = get_repository().decide_detection_proposal(proposal_id, payload)
    except ValueError as error:
        raise _detection_interface_error(error) from error

    if result is None:
        raise _not_found("Detection proposal", proposal_id)
    return result


@app.get("/api/review-queue", response_model=list[ReviewQueueItem])
async def list_review_queue() -> list[ReviewQueueItem]:
    return get_repository().review_queue_items()


@app.get("/api/review-labels", response_model=list[ReviewLabel])
async def list_review_labels() -> list[ReviewLabel]:
    return get_repository().list_review_labels()


@app.post("/api/review-labels", response_model=ReviewCorrectionResult, status_code=201)
async def create_review_label(payload: ReviewCorrectionCreate) -> ReviewCorrectionResult:
    repository = get_repository()

    if payload.target_type == "visit":
        if repository.get_visit(payload.target_id) is None:
            raise _not_found("Visit", payload.target_id)

        # Review labels are user-confirmed dataset truth; detections remain evidence.
        return repository.create_review_label(payload)

    if payload.target_type == "event":
        if repository.get_event(payload.target_id) is None:
            raise _not_found("Event", payload.target_id)

        return repository.create_review_label(payload)

    raise _unsupported_target(payload.target_type)


@app.get("/api/dataset-exports", response_model=list[DatasetExport])
async def list_dataset_exports() -> list[DatasetExport]:
    return get_repository().list_dataset_exports()


@app.post("/api/dataset-exports", response_model=DatasetExportDetail, status_code=201)
async def create_dataset_export(payload: DatasetExportCreate) -> DatasetExportDetail:
    repository = get_repository()
    dataset_export = repository.create_dataset_export(payload)
    manifest = repository.build_dataset_manifest(dataset_export.id)
    if manifest is None:
        raise _not_found("Dataset export", dataset_export.id)
    return DatasetExportDetail(export=dataset_export, manifest=manifest)


@app.get("/api/dataset-exports/{export_id}", response_model=DatasetExportDetail)
async def get_dataset_export(export_id: str) -> DatasetExportDetail:
    repository = get_repository()
    dataset_export = repository.get_dataset_export(export_id)
    if dataset_export is None:
        raise _not_found("Dataset export", export_id)

    manifest = repository.build_dataset_manifest(export_id)
    if manifest is None:
        raise _not_found("Dataset export", export_id)

    return DatasetExportDetail(export=dataset_export, manifest=manifest)


@app.get("/api/dataset-exports/{export_id}/manifest", response_model=DatasetExportManifest)
async def get_dataset_export_manifest(export_id: str) -> DatasetExportManifest:
    manifest = get_repository().build_dataset_manifest(export_id)
    if manifest is None:
        raise _not_found("Dataset export", export_id)
    return manifest


@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary() -> AnalyticsSummary:
    return get_repository().analytics_summary()


@app.get("/api/settings/local-data", response_model=LocalDataStatus)
async def get_local_data_status() -> LocalDataStatus:
    return get_repository().local_data_status()


@app.post("/api/settings/reset-demo-data", response_model=LocalDataStatus)
async def reset_demo_data() -> LocalDataStatus:
    # Local demo reset clears product metadata only; imported media files stay on disk.
    return get_repository().reset_demo_data()
