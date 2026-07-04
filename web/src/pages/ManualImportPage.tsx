import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  DemoDetectionRunCreate,
  DemoDetectionRunResult,
  DetectionProposalDecisionResult,
  MediaAsset,
  MediaImportResult,
  SourceSetupReviewResponse,
  Stream,
  Zone,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatLabel } from "../utils";

interface ManualImportPageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenStream: (streamId: string) => void;
  onOpenStreams: () => void;
  onOpenFolderImport: () => void;
  onOpenDetectionProposals: () => void;
  onOpenReview: () => void;
  onImportComplete: () => Promise<void>;
}

interface LastImportContext {
  title: string;
  subjectLabel: string;
  speciesGuess: string;
  zoneId: string | null;
}

export function ManualImportPage({
  streams,
  sources,
  onOpenEvent,
  onOpenVisit,
  onOpenStream,
  onOpenStreams,
  onOpenFolderImport,
  onOpenDetectionProposals,
  onOpenReview,
  onImportComplete,
}: ManualImportPageProps) {
  const [selectedStreamId, setSelectedStreamId] = useState(streams[0]?.id ?? "");
  const [zones, setZones] = useState<Zone[]>([]);
  const [selectedZoneId, setSelectedZoneId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [title, setTitle] = useState("Imported outdoor observation");
  const [subjectLabel, setSubjectLabel] = useState("unknown_bird");
  const [speciesGuess, setSpeciesGuess] = useState("");
  const [notes, setNotes] = useState("");
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [setupReviews, setSetupReviews] = useState<Record<string, SourceSetupReviewResponse>>({});
  const [result, setResult] = useState<MediaImportResult | null>(null);
  const [lastImportContext, setLastImportContext] = useState<LastImportContext | null>(null);
  const [demoResult, setDemoResult] = useState<DemoDetectionRunResult | null>(null);
  const [demoDecisionResult, setDemoDecisionResult] =
    useState<DetectionProposalDecisionResult | null>(null);
  const [isLoadingMedia, setIsLoadingMedia] = useState(true);
  const [isLoadingZones, setIsLoadingZones] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCreatingDemoProposal, setIsCreatingDemoProposal] = useState(false);
  const [isConvertingDemoProposal, setIsConvertingDemoProposal] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [demoMessage, setDemoMessage] = useState<string | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);

  const sourceNames = useMemo(
    () => new Map(sources.map((source) => [source.id, source.name])),
    [sources],
  );
  const selectedStream = streams.find((stream) => stream.id === selectedStreamId) ?? null;
  const selectedSource = selectedStream
    ? sources.find((source) => source.id === selectedStream.source_id) ?? null
    : null;
  const selectedZone = zones.find((zone) => zone.id === selectedZoneId) ?? null;
  const selectedSetupReview = selectedSource ? setupReviews[selectedSource.id] ?? null : null;
  const isManualMediaReady =
    selectedSetupReview?.provider_key === "manual_media" &&
    selectedSetupReview.readiness_level === "metadata_ready";
  const demoSubjectLabel =
    lastImportContext?.subjectLabel ||
    result?.visit?.subject_label ||
    subjectLabel.trim() ||
    "unknown_bird";
  const demoSpeciesGuess =
    lastImportContext?.speciesGuess ||
    result?.visit?.species_guess ||
    speciesGuess.trim() ||
    "unknown_bird";
  const demoEventTitle =
    lastImportContext?.title ||
    result?.event.title ||
    (result ? `Local smoke import: ${result.media_asset.original_filename}` : "Local smoke import");
  const demoZoneId =
    lastImportContext?.zoneId || result?.event.primary_zone_id || selectedZoneId || undefined;
  const firstDemoProposal = demoResult?.proposals[0] ?? null;

  useEffect(() => {
    setSelectedStreamId((current) =>
      current && streams.some((stream) => stream.id === current) ? current : streams[0]?.id ?? "",
    );
  }, [streams]);

  useEffect(() => {
    let isMounted = true;

    async function loadSetupReviews() {
      if (sources.length === 0) {
        setSetupReviews({});
        return;
      }

      try {
        const entries = await Promise.all(
          sources.map(async (source) => [
            source.id,
            await apiClient.getSourceSetupReview(source.id),
          ] as const),
        );
        if (isMounted) {
          setSetupReviews(Object.fromEntries(entries));
        }
      } catch {
        if (isMounted) {
          setSetupReviews({});
        }
      }
    }

    void loadSetupReviews();

    return () => {
      isMounted = false;
    };
  }, [sources]);

  useEffect(() => {
    let isMounted = true;

    async function loadZones() {
      if (!selectedStreamId) {
        setZones([]);
        setSelectedZoneId("");
        return;
      }

      setIsLoadingZones(true);
      try {
        const nextZones = await apiClient.getStreamZones(selectedStreamId);
        if (isMounted) {
          setZones(nextZones);
          setSelectedZoneId((current) =>
            current && nextZones.some((zone) => zone.id === current) ? current : "",
          );
        }
      } catch (caught) {
        if (isMounted) {
          setZones([]);
          setSelectedZoneId("");
          setError(caught instanceof Error ? caught.message : "Could not load stream zones.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingZones(false);
        }
      }
    }

    void loadZones();

    return () => {
      isMounted = false;
    };
  }, [selectedStreamId]);

  async function loadMedia(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoadingMedia(true);
    }
    setError(null);
    try {
      setMediaAssets(await apiClient.getMediaAssets());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load imported media.");
    } finally {
      if (showLoading) {
        setIsLoadingMedia(false);
      }
    }
  }

  useEffect(() => {
    void loadMedia();
  }, []);

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose an image or video file before creating a review event.");
      return;
    }
    if (!selectedStreamId) {
      setError("Choose a stream for this media import.");
      return;
    }

    const payload = new FormData();
    payload.append("file", file);
    payload.append("stream_id", selectedStreamId);
    if (selectedZoneId) {
      payload.append("zone_id", selectedZoneId);
    }
    if (title.trim()) {
      payload.append("title", title.trim());
    }
    payload.append("subject_label", subjectLabel.trim() || "unknown_bird");
    if (speciesGuess.trim()) {
      payload.append("species_guess", speciesGuess.trim());
    }
    if (notes.trim()) {
      payload.append("notes", notes.trim());
    }

    const nextImportContext = {
      title: title.trim() || `Local smoke import: ${file.name}`,
      subjectLabel: subjectLabel.trim() || "unknown_bird",
      speciesGuess: speciesGuess.trim() || "unknown_bird",
      zoneId: selectedZoneId || null,
    };

    setIsSubmitting(true);
    setError(null);
    setMessage(null);
    setDemoMessage(null);
    setDemoError(null);
    try {
      const nextResult = await apiClient.importMedia(payload);
      setResult(nextResult);
      setLastImportContext(nextImportContext);
      setDemoResult(null);
      setDemoDecisionResult(null);
      setMessage("Imported media created a reviewable event and visit.");
      setFile(null);
      setFileInputKey((current) => current + 1);
      setSpeciesGuess("");
      setNotes("");
      await loadMedia({ showLoading: false });
      await onImportComplete();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Media import could not be created.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function buildDemoProposalPayload(): DemoDetectionRunCreate | null {
    if (!result) {
      return null;
    }

    return {
      media_asset_id: result.media_asset.id,
      zone_id: demoZoneId,
      label: "bird",
      confidence: 0.72,
      suggested_subject_label: demoSubjectLabel,
      suggested_species: demoSpeciesGuess,
      notes:
        "Browser local smoke path demo detector evidence only. No model inspected the media " +
        "and no reviewed truth was created.",
    };
  }

  async function createDemoProposal() {
    const payload = buildDemoProposalPayload();
    if (!payload) {
      setDemoError("Import local media before creating demo proposal evidence.");
      return null;
    }

    setIsCreatingDemoProposal(true);
    setDemoError(null);
    setDemoMessage(null);
    setDemoDecisionResult(null);
    try {
      const nextDemoResult = await apiClient.createDemoDetectionRun(payload);
      setDemoResult(nextDemoResult);
      setDemoMessage(
        nextDemoResult.proposals.length > 0
          ? "Synthetic proposal evidence was created. Review correction still creates truth."
          : "Demo run completed without proposal evidence.",
      );
      await onImportComplete();
      return nextDemoResult;
    } catch (caught) {
      setDemoError(caught instanceof Error ? caught.message : "Demo proposal could not be created.");
      return null;
    } finally {
      setIsCreatingDemoProposal(false);
    }
  }

  async function convertDemoProposal(sourceResult: DemoDetectionRunResult | null = demoResult) {
    const proposal = sourceResult?.proposals[0] ?? null;
    if (!proposal) {
      setDemoError("Create demo proposal evidence before converting it to Event/Visit context.");
      return null;
    }

    setIsConvertingDemoProposal(true);
    setDemoError(null);
    setDemoMessage(null);
    try {
      const nextDecisionResult = await apiClient.decideDetectionProposal(proposal.id, {
        decision: "convert_to_event",
        event_title: demoEventTitle,
        subject_label: demoSubjectLabel,
        species_guess: demoSpeciesGuess,
        notes: "Converted from explicit browser smoke action; still needs review/correction.",
      });
      setDemoDecisionResult(nextDecisionResult);
      setDemoMessage(
        "Converted proposal into needs-review Event/Visit context. No ReviewLabel truth was created.",
      );
      await onImportComplete();
      return nextDecisionResult;
    } catch (caught) {
      setDemoError(caught instanceof Error ? caught.message : "Demo proposal could not be converted.");
      return null;
    } finally {
      setIsConvertingDemoProposal(false);
    }
  }

  async function createAndConvertDemoProposal() {
    setIsConvertingDemoProposal(true);
    const nextDemoResult = await createDemoProposal();
    if (nextDemoResult) {
      await convertDemoProposal(nextDemoResult);
    }
    setIsConvertingDemoProposal(false);
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Local-first media input"
        title="Import Media"
        description="Create a reviewable outdoor event from local media. Media stays local; review and correct imported observations before export."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenFolderImport}>
              Import Folder
            </button>
            <button className="secondary-action" onClick={onOpenDetectionProposals}>
              Detection Proposals
            </button>
            {selectedStream ? (
              <button className="secondary-action" onClick={() => onOpenStream(selectedStream.id)}>
                Open stream context
              </button>
            ) : null}
          </>
        }
      />

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}
      <section className="notice-panel onboarding-provider-note">
        <strong>Explicit local ingest</strong>
        <span>Import creates review work. Corrections create truth.</span>
      </section>

      {selectedStream && selectedSource ? (
        <section className="panel import-context-panel">
          <div className="section-heading">
            <div>
              <h2>Import context</h2>
              <span className="meta-text">
                Source and Stream context for reviewable Events/Visits
              </span>
            </div>
            {selectedSetupReview ? (
              <StatusPill label={formatLabel(selectedSetupReview.readiness_level)} tone="quiet" />
            ) : null}
          </div>
          <div className="import-context-grid">
            <div>
              <span>Source</span>
              <strong>{selectedSource.name}</strong>
            </div>
            <div>
              <span>Stream</span>
              <strong>{selectedStream.name}</strong>
            </div>
            <div>
              <span>Zone</span>
              <strong>{selectedZone ? selectedZone.name : "Unzoned"}</strong>
            </div>
            <div>
              <span>Provider</span>
              <strong>
                {selectedSetupReview
                  ? selectedSetupReview.provider_display_name
                  : formatLabel(selectedSource.kind)}
              </strong>
            </div>
          </div>
          <div className="import-context-copy">
            {isManualMediaReady ? (
              <p>Next: choose local media for this Source/Stream.</p>
            ) : selectedSetupReview?.provider_key === "manual_media" ? (
              <p>{selectedSetupReview.next_step}</p>
            ) : (
              <p>
                Manual import can still be used as an explicit local ingest path for the selected
                Stream. Live playback is not implied.
              </p>
            )}
            <p>Imported media stays local and needs review.</p>
          </div>
          <div className="detail-actions">
            <button className="secondary-action" onClick={onOpenStreams} type="button">
              Source setup
            </button>
            <button className="secondary-action" onClick={() => onOpenStream(selectedStream.id)}>
              Open stream context
            </button>
          </div>
        </section>
      ) : null}

      {result ? (
        <section className="panel import-result-panel">
          <div>
            <span className="meta-text">Review and correct imported observations before export.</span>
            <h2>{result.event.title}</h2>
            <p>
              {result.media_asset.original_filename} is now local evidence for a needs-review visit.
            </p>
          </div>
          <div className="detail-actions">
            <button className="primary-action" onClick={() => onOpenEvent(result.event.id)}>
              Event detail
            </button>
            {result.visit ? (
              <button className="secondary-action" onClick={() => onOpenVisit(result.visit!.id)}>
                Visit detail
              </button>
            ) : null}
            <button className="secondary-action" onClick={onOpenReview}>
              Review Queue
            </button>
            <StatusPill label={`${result.review_queue_count} needs review`} tone="review" />
          </div>
          <MediaAssetPreview asset={result.media_asset} compact />
          <div className="import-smoke-panel">
            <div className="section-heading">
              <div>
                <span className="meta-text">Browser local smoke path</span>
                <h3>Create review evidence</h3>
              </div>
              <StatusPill label="Synthetic evidence" tone="quiet" />
            </div>
            <p>
              Create synthetic demo proposal evidence for local smoke testing. No model inspects the media and
              no reviewed truth is created.
            </p>
            <div className="import-flow-strip">
              <span>MediaAsset</span>
              <span>DetectionProposal evidence</span>
              <span>Needs-review Event/Visit</span>
              <span>Review correction truth</span>
            </div>
            {demoMessage ? <div className="notice-panel compact-notice">{demoMessage}</div> : null}
            {demoError ? <div className="error-panel compact-error">{demoError}</div> : null}
            <div className="detail-actions">
              <button
                className="primary-action"
                disabled={isCreatingDemoProposal || isConvertingDemoProposal}
                onClick={() => void createDemoProposal()}
                type="button"
              >
                {isCreatingDemoProposal && !isConvertingDemoProposal ? "Creating..." : "Create demo proposal"}
              </button>
              <button
                className="secondary-action"
                disabled={isCreatingDemoProposal || isConvertingDemoProposal}
                onClick={() => void createAndConvertDemoProposal()}
                type="button"
              >
                {isConvertingDemoProposal ? "Creating..." : "Create and convert to Event/Visit"}
              </button>
              {firstDemoProposal && !demoDecisionResult ? (
                <button
                  className="secondary-action"
                  disabled={isConvertingDemoProposal}
                  onClick={() => void convertDemoProposal()}
                  type="button"
                >
                  {isConvertingDemoProposal ? "Converting..." : "Convert first proposal to Event/Visit"}
                </button>
              ) : null}
              <button className="secondary-action" onClick={onOpenReview} type="button">
                Open Review Queue
              </button>
              <button className="secondary-action" onClick={onOpenDetectionProposals} type="button">
                Open Detection Proposals
              </button>
            </div>
            {demoResult ? (
              <div className="import-smoke-result-grid">
                <div className="data-row">
                  <span>DetectionRun ID</span>
                  <strong>{demoResult.detection_run.id}</strong>
                </div>
                <div className="data-row">
                  <span>Proposal IDs</span>
                  <strong>
                    {demoResult.proposals.length > 0
                      ? demoResult.proposals.map((proposal) => proposal.id).join(", ")
                      : "none"}
                  </strong>
                </div>
                <div className="data-row">
                  <span>Review Queue</span>
                  <strong>{demoResult.review_queue_count} needs review</strong>
                </div>
              </div>
            ) : null}
            {demoDecisionResult ? (
              <div className="import-smoke-result-grid">
                <div className="data-row">
                  <span>Converted proposal</span>
                  <strong>{demoDecisionResult.proposal.id}</strong>
                </div>
                <div className="data-row">
                  <span>Event</span>
                  {demoDecisionResult.event ? (
                    <button
                      className="inline-link-button"
                      onClick={() => onOpenEvent(demoDecisionResult.event!.id)}
                      type="button"
                    >
                      {demoDecisionResult.event.id}
                    </button>
                  ) : (
                    <strong>not created</strong>
                  )}
                </div>
                <div className="data-row">
                  <span>Visit</span>
                  {demoDecisionResult.visit ? (
                    <button
                      className="inline-link-button"
                      onClick={() => onOpenVisit(demoDecisionResult.visit!.id)}
                      type="button"
                    >
                      {demoDecisionResult.visit.id}
                    </button>
                  ) : (
                    <strong>not created</strong>
                  )}
                </div>
              </div>
            ) : null}
            <div className="notice-panel compact-notice import-smoke-boundary">
              <strong>Truth boundary</strong>
              <ul>
                <li>Demo proposal is synthetic evidence.</li>
                <li>No model inspected the media.</li>
                <li>No ReviewLabel truth was created.</li>
                <li>
                  Event/Visit still requires explicit review/correction before exports, analytics, or classifier
                  truth.
                </li>
              </ul>
            </div>
          </div>
        </section>
      ) : null}

      <section className="manual-import-layout">
        <form className="panel manual-import-form" onSubmit={submitImport}>
          <div className="section-heading">
            <h2>Create review event</h2>
            <StatusPill label="Media stays local" tone="quiet" />
          </div>
          <div className="import-flow-strip">
            <span>Local media</span>
            <span>Stream context</span>
            <span>Needs review</span>
            <span>Export-ready after correction</span>
          </div>
          <label>
            Image or video file
            <input
              accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime"
              key={fileInputKey}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              type="file"
            />
          </label>
          {file ? (
            <div className="selected-file-row">
              <span>Selected file</span>
              <strong>{file.name}</strong>
            </div>
          ) : null}
          <label>
            Stream
            <select
              disabled={streams.length === 0}
              value={selectedStreamId}
              onChange={(event) => setSelectedStreamId(event.target.value)}
            >
              {streams.map((stream) => (
                <option key={stream.id} value={stream.id}>
                  {stream.name} - {sourceNames.get(stream.source_id) ?? stream.source_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Zone
            <select
              disabled={!selectedStreamId || isLoadingZones}
              value={selectedZoneId}
              onChange={(event) => setSelectedZoneId(event.target.value)}
            >
              <option value="">Unzoned</option>
              {zones.map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.name} - {formatLabel(zone.zone_type)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Title
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            Initial subject label
            <input value={subjectLabel} onChange={(event) => setSubjectLabel(event.target.value)} />
          </label>
          <label>
            Species guess
            <input
              value={speciesGuess}
              onChange={(event) => setSpeciesGuess(event.target.value)}
              placeholder="optional"
            />
          </label>
          <label>
            Notes
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="optional review context"
            />
          </label>
          <button className="primary-action" disabled={isSubmitting || !file || !selectedStreamId} type="submit">
            {isSubmitting ? "Importing..." : "Create reviewable event"}
          </button>
          {streams.length === 0 ? (
            <span className="meta-text">A stream is required before local media can enter review.</span>
          ) : null}
        </form>

        <div className="panel">
          <div className="section-heading">
            <div>
              <h2>Imported media</h2>
              <span className="meta-text">
                Existing MediaAssets can be attached to Motion Evidence as visual context.
              </span>
            </div>
            <button className="secondary-action" onClick={() => void loadMedia()}>
              Refresh
            </button>
          </div>
          {isLoadingMedia ? <span className="meta-text">Loading imported media...</span> : null}
          <div className="media-list">
            {[...mediaAssets].reverse().map((asset) => (
              <article className="media-list-item" key={asset.id}>
                <MediaAssetPreview asset={asset} compact />
                <div className="data-row">
                  <span>Stream</span>
                  <strong>{streams.find((stream) => stream.id === asset.stream_id)?.name ?? asset.stream_id}</strong>
                </div>
                <div className="data-row">
                  <span>MediaAsset ID</span>
                  <strong>{asset.id}</strong>
                </div>
                {asset.notes ? <p>{asset.notes}</p> : null}
              </article>
            ))}
            {!isLoadingMedia && mediaAssets.length === 0 ? (
              <EmptyState
                title="No imported media yet"
                description="Choose local media to create the first reviewable observation."
              />
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}
