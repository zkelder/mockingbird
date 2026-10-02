import { expect, test } from "@playwright/test";

// Research Export & Ecological Workflow Completion v1: Visit -> export,
// against the real backend (non-demo Source/Stream/Zone, like
// reviewed-product-loop.spec.ts). An imported, never-reviewed Visit proves
// the deep link carries the Visit into the one existing workflow and that
// the server -- not the page -- refuses to treat a provisional record as
// exportable truth.

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

test("a Visit opens the export workflow scoped to it and an unreviewed Visit is explained, not exported", async ({
  page,
}) => {
  const created = await page.request.post("/api/sources", {
    data: { name: `Export Workflow Feeder ${Date.now()}` },
  });
  expect(created.ok()).toBeTruthy();
  const { stream } = await created.json();
  const zoneResponse = await page.request.post("/api/zones", {
    data: {
      stream_id: stream.id, name: "Feeder", zone_type: "feeder",
      polygon: [{ x: 0.1, y: 0.1 }, { x: 0.9, y: 0.1 }, { x: 0.9, y: 0.9 }, { x: 0.1, y: 0.9 }],
    },
  });
  const { zone } = await zoneResponse.json();
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: { name: "export-workflow.jpg", mimeType: "image/jpeg", buffer: Buffer.from(TINY_JPEG_BASE64, "base64") },
      stream_id: stream.id, zone_id: zone.id, subject_label: "bird",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const visitId = (await imported.json()).visit.id as string;

  await page.goto(`/visits/${visitId}`);
  await page.getByRole("button", { name: "Check export eligibility" }).click();

  await expect(page).toHaveURL(new RegExp(`/ecological-destinations\\?visit=${visitId}`));
  await expect(page.getByText("Showing one Visit")).toBeVisible();
  await expect(page.getByText("This Visit cannot be exported")).toBeVisible();
  await expect(page.getByRole("button", { name: /Prepare 0 selected/ })).toBeDisabled();

  // The same scope drives the research bundle: nothing eligible, with a reason.
  await page.getByRole("button", { name: "Preview bundle" }).click();
  await expect(page.getByText("Nothing eligible to bundle")).toBeVisible();
});
