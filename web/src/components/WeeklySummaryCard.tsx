import type { PlaceActivityReportDigest, PlaceActivityReportDigestSpeciesHighlight } from "../api/types";

interface WeeklySummaryCardProps {
  weeklyDigest: PlaceActivityReportDigest | null | undefined;
}

function namesAnd(names: string[]): string {
  if (names.length === 0) {
    return "";
  }
  if (names.length === 1) {
    return names[0];
  }
  if (names.length === 2) {
    return `${names[0]} and ${names[1]}`;
  }
  return `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
}

// Reuses each highlight's own already-composed note verbatim -- this
// component invents no new language and does no string-matching against
// backend wording, only groups by the typed `reason` enum (see
// docs/place-yard-intelligence-v2-contract.md, Phase 13).
function noteFor(highlight: PlaceActivityReportDigestSpeciesHighlight): string | null {
  return (
    highlight.change_note ??
    highlight.regularity_note ??
    highlight.seasonal_note ??
    highlight.pattern_note ??
    highlight.historical_note ??
    null
  );
}

function composeSentences(digest: PlaceActivityReportDigest): string[] {
  const sentences: string[] = [];
  const byReason = (reason: PlaceActivityReportDigestSpeciesHighlight["reason"]) =>
    digest.primary_highlights.filter((highlight) => highlight.reason === reason);

  const regular = byReason("regular_activity");
  if (regular.length > 0) {
    const names = namesAnd(regular.map((highlight) => highlight.display_name));
    sentences.push(
      `${names} ${regular.length === 1 ? "was" : "were"} your most regular ${
        regular.length === 1 ? "visitor" : "visitors"
      } this week.`
    );
  }

  const firstRecord = byReason("first_confirmed_record");
  if (firstRecord.length > 0) {
    sentences.push(`${namesAnd(firstRecord.map((highlight) => highlight.display_name))} appeared for the first time.`);
  }

  const returned = byReason("returned_after_absence");
  if (returned.length > 0) {
    sentences.push(`${namesAnd(returned.map((highlight) => highlight.display_name))} returned after a quiet stretch.`);
  }

  // Everything else worth mentioning (meaningful change, unusual timing,
  // a typical-season match, or a strong photo) gets one compact clause
  // per species, using its own note directly -- never re-worded here.
  const already = new Set([...regular, ...firstRecord, ...returned].map((highlight) => highlight.label));
  const remaining = digest.primary_highlights.filter((highlight) => !already.has(highlight.label));
  const remainingClauses = remaining
    .map((highlight) => {
      const note = noteFor(highlight);
      return note ? `${highlight.display_name} — ${note.charAt(0).toLowerCase()}${note.slice(1)}` : null;
    })
    .filter((clause): clause is string => clause !== null);
  if (remainingClauses.length > 0) {
    sentences.push(`${remainingClauses.join("; ")}.`);
  }

  if (digest.place_change_note) {
    sentences.push(digest.place_change_note);
  }

  return sentences;
}

/**
 * Place / Yard Intelligence v2, Phase 13: a calm "what happened this week"
 * recap, reusing the identical `compute_daily_digest` ranking/wording the
 * daily digest already uses -- see docs/place-yard-intelligence-v2-contract.md
 * section 3.7. Every sentence is composed from already-resolved backend
 * facts; this component never invents ecological explanation or fetches
 * anything itself.
 *
 * Renders nothing when `weeklyDigest` is absent (the 7-usable-day recent
 * window is not valid yet) -- a genuinely young installation should not see
 * an empty "This week" card, matching every sibling card's absence-safety
 * discipline.
 */
export function WeeklySummaryCard({ weeklyDigest }: WeeklySummaryCardProps) {
  if (!weeklyDigest) {
    return null;
  }

  if (weeklyDigest.coverage.state === "no_monitoring" || weeklyDigest.coverage.state === "sparse_monitoring") {
    return (
      <section aria-label="This week at this Place" className="panel weekly-summary-card">
        <h3>This week</h3>
        <p className="meta-text">{weeklyDigest.coverage.message}</p>
      </section>
    );
  }

  const sentences = composeSentences(weeklyDigest);

  return (
    <section aria-label="This week at this Place" className="panel weekly-summary-card">
      <h3>This week</h3>
      {sentences.length > 0 ? (
        sentences.map((sentence, index) => <p key={index}>{sentence}</p>)
      ) : (
        <p className="meta-text">Nothing stood out from the usual this week.</p>
      )}
    </section>
  );
}
