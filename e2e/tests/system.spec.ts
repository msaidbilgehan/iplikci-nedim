// The System screen's downloads on the service itself (F18, F20): the exports the analysis writes and the log without
// personal values, each saved as a file through the browser's session.

import { expect, test } from "@playwright/test";

test("dışa aktarımlar yeniden yazılır ve indirilir, günlük de indirilir", async ({ page }) => {
  await page.goto("/sistem");
  const card = page.getByRole("region", { name: "Dışa aktarımlar" });
  await card.getByRole("button", { name: "Yeniden yaz" }).click();
  await expect(card.getByText("İstek alındı")).toBeVisible();
  const report = card.getByRole("link", { name: "İndir: Rapor (tek dosya, HTML)" });
  await expect(report).toBeVisible({ timeout: 30_000 }); // the analysis writes it within moments
  const saved = page.waitForEvent("download");
  await report.click();
  expect((await saved).suggestedFilename()).toMatch(/^iplikci-rapor-\d{4}-\d{2}-\d{2}\.html$/);

  const log = page.waitForEvent("download");
  await page.getByRole("region", { name: "Servis" }).getByRole("link", { name: "Günlüğü indir" }).click();
  expect((await log).suggestedFilename()).toMatch(/^iplikci-gunluk-\d{4}-\d{2}-\d{2}\.log$/);
});
