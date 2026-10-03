import { expect, test, type Page } from "@playwright/test";
import {
  ALL_CAMERAS_LABEL,
  cameraScopeSummary,
  readCameraIds,
  sourceCameraOptions,
  streamCameraOptions,
  toggleCameraId,
  unavailableCameraIds,
  writeCameraIds,
} from "../src/cameraFilter";

// Multi-Camera Attribution & Filter Consolidation v1 (see docs/multi-camera-
// attribution-filter-consolidation-contract.md). One deterministic two-camera
// Place ("Feeder cam" + "Fence cam"): one cardinal encounter seen by both
// cameras (an `associated` pair), one unrelated finch on the fence camera.
// Backend derivation is proven against real seeded rows in tests/test_multi_
// camera_attribution_consolidation.py; this spec proves the presentation
// contract with schema-shaped responses (the house pattern of
// place-story.spec.ts / attention-integrity.spec.ts) plus the real filter
// serialization against the real backend request.

async function completeSetup(page: Page) {
  await page.route("**/api/setup/state", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ completed: true, current_step: "done", updated_at: new Date().toISOString() }),
    }),
  );
}

const NOW = new Date().toISOString();

function storyEntry(overrides: Record<string, unknown>) {
  return {
    event_end_date: null,
    information_class: "reviewed",
    importance: "major",
    group: "wildlife",
    feature_id: null,
    feature_name: null,
    visit_id: null,
    zone_id: null,
    zone_name: null,
    source_id: null,
    detail_refs: {},
    source_scope: "place_level",
    contributions: [],
    ...overrides,
  };
}

const storyResponse = {
  generated_at: NOW,
  period_start_at: NOW,
  period_end_at: NOW,
  has_more: false,
  next_offset: null,
  total_matched: 3,
  is_early_experience: false,
  entries: [
    storyEntry({
      id: "first-seen:northern_cardinal",
      kind: "first_seen",
      event_date: "2025-03-03",
      title: "First Northern Cardinal observation",
      summary: "First reviewed observation of Northern Cardinal recorded at this Place.",
      taxon_label: "northern_cardinal",
      taxon_display_name: "Northern Cardinal",
      visit_id: "v-a-cardinal",
      source_scope: "multiple_sources",
      contributions: [
        { source_id: "src-feeder-cam", source_name: "Feeder cam", visit_id: "v-a-cardinal", source_archived: false },
        { source_id: "src-fence-cam", source_name: "Fence cam", visit_id: "v-b-cardinal", source_archived: false },
      ],
    }),
    storyEntry({
      id: "first-seen:house_finch",
      kind: "first_seen",
      event_date: "2025-03-03",
      title: "First House Finch observation",
      summary: "First reviewed observation of House Finch recorded at this Place.",
      taxon_label: "house_finch",
      taxon_display_name: "House Finch",
      visit_id: "v-b-finch",
      source_scope: "single_source",
      contributions: [
        { source_id: "src-fence-cam", source_name: "Fence cam", visit_id: "v-b-finch", source_archived: false },
      ],
    }),
    storyEntry({
      id: "regularity:northern_cardinal:regular:2025-03-07",
      kind: "regularity_change",
      event_date: "2025-03-07",
      title: "Northern Cardinal became a regular presence",
      summary: "Northern Cardinal has become a regular presence at this Place.",
      taxon_label: "northern_cardinal",
      taxon_display_name: "Northern Cardinal",
    }),
  ],
};

test("Place Story names the contributing cameras and links each camera's own evidence", async ({ page }) => {
  await completeSetup(page);
  await page.route("**/api/place/story*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(storyResponse) }),
  );
  await page.goto("/place-story");

  const cards = page.locator("li.place-story-card");
  const shared = cards.filter({ hasText: "First Northern Cardinal observation" });
  await expect(shared.getByTestId("story-cameras")).toHaveText("Seen by Feeder cam, Fence cam");
  // No camera is arbitrarily chosen: one drill-down per contributing camera.
  await expect(shared.getByRole("button", { name: "View evidence from Feeder cam" })).toBeVisible();
  await expect(shared.getByRole("button", { name: "View evidence from Fence cam" })).toBeVisible();

  const single = cards.filter({ hasText: "First House Finch observation" });
  await expect(single.getByTestId("story-cameras")).toHaveText("Seen on Fence cam");
  await expect(single.getByRole("button", { name: "View evidence" })).toBeVisible();

  // A genuinely Place-level trend never grows an invented camera.
  const placeLevel = cards.filter({ hasText: "became a regular presence" });
  await expect(placeLevel.getByTestId("story-cameras")).toHaveCount(0);

  await shared.getByRole("button", { name: "View evidence from Fence cam" }).click();
  await expect(page).toHaveURL(/\/visits\/v-b-cardinal$/);
});

test("Calm Attention shows one item for an overlapping-camera encounter and keeps both cameras reachable", async ({
  page,
}) => {
  await completeSetup(page);
  const alert = {
    id: "alert-review-a",
    category: "review",
    severity: "warning",
    title: "Visit ready for review",
    message: "Outdoor activity is ready for your explicit review and correction.",
    created_at: "2026-10-03T12:00:00Z",
    updated_at: "2026-10-03T12:00:00Z",
    status: "unread",
    stream_id: "stream-feeder-cam",
    stream_name: "Feeder cam stream",
    visit_id: "v-a-1",
    source_id: "src-feeder-cam",
    action: { action_type: "review_visit", visit_id: "v-a-1" },
    attention_category: "needs_help",
    urgency: "in_app_only",
    grouped_visits: [
      {
        alert_id: "alert-review-b",
        visit_id: "v-b-1",
        stream_id: "stream-fence-cam",
        stream_name: "Fence cam stream",
        source_id: "src-fence-cam",
        source_name: "Fence cam",
      },
    ],
  };
  const ungrouped = {
    ...alert,
    id: "alert-review-c",
    visit_id: "v-b-2",
    action: { action_type: "review_visit", visit_id: "v-b-2" },
    grouped_visits: [],
  };
  await page.route("**/api/alerts?*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [alert, ungrouped], next_offset: null }),
    }),
  );
  await page.goto("/alerts");

  const rows = page.locator(".alerts-inbox-list .alert-row");
  await expect(rows).toHaveCount(2);
  const grouped = rows.filter({ has: page.getByTestId("alert-grouped-cameras") });
  await expect(grouped).toHaveCount(1);
  await expect(grouped.getByTestId("alert-grouped-cameras")).toContainText("Also seen by Fence cam");
  // The unrelated simultaneous Visit is its own, ungrouped item.
  await expect(rows.filter({ hasNot: page.getByTestId("alert-grouped-cameras") })).toHaveCount(1);

  await grouped.getByRole("button", { name: "Review Fence cam’s Visit" }).click();
  await expect(page).toHaveURL(/\/visits\/v-b-1$/);
});

test("Place Report camera filter restores from, and writes back to, the URL", async ({ page, request }) => {
  await completeSetup(page);
  const sources = (await (await request.get("/api/sources")).json()) as Array<{ id: string; name: string }>;
  expect(sources.length).toBeGreaterThan(0);
  const first = sources[0];

  const requests: Array<Record<string, unknown>> = [];
  page.on("request", (candidate) => {
    if (candidate.url().includes("/api/analytics/place-activity-report") && candidate.method() === "POST") {
      requests.push(candidate.postDataJSON() as Record<string, unknown>);
    }
  });

  await page.goto(`/place-report?source=${encodeURIComponent(first.id)}`);
  await expect(page.getByRole("heading", { name: "Place Report" })).toBeVisible();
  const group = page.getByRole("group", { name: "Cameras" });
  await expect(group.getByRole("checkbox").first()).toBeChecked();
  await expect(group).toContainText("Limited to 1 of");
  await expect.poll(() => requests.some((body) => JSON.stringify(body.source_ids) === JSON.stringify([first.id]))).toBe(true);

  // Clearing the selection means "every camera": the param disappears and the
  // request omits `source_ids` rather than sending a rejected empty list.
  await group.getByRole("checkbox").first().uncheck();
  await expect(page).not.toHaveURL(/source=/);
  await expect(group).toContainText("every camera is included");
  await expect.poll(() => requests.some((body) => body.source_ids === undefined || body.source_ids === null)).toBe(true);
});

test("Activity Library uses one canonical camera control, keeps stream deep links honest, and round-trips the URL", async ({
  page,
  request,
}) => {
  await completeSetup(page);
  const sources = (await (await request.get("/api/sources")).json()) as Array<{ id: string; name: string }>;
  const streams = (await (await request.get("/api/streams")).json()) as Array<{ id: string; name: string; source_id: string }>;
  const stream = streams[0];

  await page.goto(`/activity?source=${encodeURIComponent(sources[0].id)}`);
  const camera = page.locator("label.camera-filter select");
  await expect(camera).toHaveValue(sources[0].id);
  // One camera control, not a "Camera" plus a confusable "Camera / Source".
  await expect(page.locator("label.camera-filter select")).toHaveCount(1);

  await camera.selectOption("");
  await expect(page).not.toHaveURL(/source=/);
  await expect(camera.locator("option").first()).toHaveText(ALL_CAMERAS_LABEL);

  // A legacy/deep-linked Stream stays visible and clearable rather than
  // silently widening or contradicting the camera choice.
  await page.goto(`/activity?stream=${encodeURIComponent(stream.id)}`);
  const chip = page.getByTestId("stream-filter-chip");
  await expect(chip).toContainText(stream.name);
  await chip.getByRole("button", { name: "Clear stream" }).click();
  await expect(page).not.toHaveURL(/stream=/);
  await expect(chip).toHaveCount(0);
});

test("a stale camera id stays visible as unavailable instead of silently widening the filter", async ({ page }) => {
  await completeSetup(page);
  await page.goto("/activity?source=src-does-not-exist");
  const camera = page.locator("label.camera-filter select");
  await expect(camera).toHaveValue("src-does-not-exist");
  await expect(camera.locator("option:checked")).toHaveText("Unavailable camera");
});

test.describe("camera filter vocabulary (pure)", () => {
  test("serializes and restores single, multiple, repeated and messy values", () => {
    expect(readCameraIds("?source=a&source=b&source=a&source=%20&source=c ", "source")).toEqual(["a", "b", "c"]);
    expect(readCameraIds("", "source")).toEqual([]);
    const params = new URLSearchParams("review=all&source=old&zone=z");
    writeCameraIds(params, "source", ["b", "a", "b", ""]);
    expect(params.getAll("source")).toEqual(["b", "a"]);
    expect(params.get("zone")).toBe("z");
    writeCameraIds(params, "source", []);
    expect(params.has("source")).toBe(false);
    expect(readCameraIds(writeCameraIds(new URLSearchParams(), "stream", ["s1", "s2"]), "stream")).toEqual(["s1", "s2"]);
  });

  test("multi-select toggles preserve order and empty means all", () => {
    expect(toggleCameraId([], "a")).toEqual(["a"]);
    expect(toggleCameraId(["a", "b"], "a")).toEqual(["b"]);
    expect(cameraScopeSummary(0, 3)).toContain("every camera is included");
    expect(cameraScopeSummary(2, 3)).toBe("Limited to 2 of 3 cameras.");
  });

  test("identity is the id: names never decide, archived/sample are labels, stale ids surface", () => {
    const sources = [
      { id: "s1", name: "Same name", kind: "rtsp", status: "connected" },
      { id: "s2", name: "Same name", kind: "rtsp", status: "archived" },
      { id: "s3", name: "Demo", kind: "demo", status: "connected" },
    ] as never;
    const options = sourceCameraOptions(sources);
    expect(options.map((option) => option.id)).toEqual(["s1", "s2", "s3"]);
    expect(options[1].label).toBe("Same name (archived)");
    expect(options[2].label).toBe("Demo (sample)");
    const streamOptions = streamCameraOptions(
      [{ id: "st1", source_id: "s2", name: "Main" }] as never,
      sources,
    );
    expect(streamOptions[0]).toEqual({ id: "st1", label: "Main (archived)" });
    expect(unavailableCameraIds(["s1", "gone"], options)).toEqual(["gone"]);
  });
});
