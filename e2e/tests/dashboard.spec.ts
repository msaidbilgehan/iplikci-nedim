// The Pano's first word is İplikçi Nedim's (F06, K26): his face, coloured by how the money stands, a line of his and
// the situation it is said about; "Başka bir söz" goes on to the next line true today. Which line leads changes with
// the day and the demo's months with the date the tests run on, so the test reads what is shown.

import { expect, test } from "@playwright/test";

test("Pano'da İplikçi Nedim yüzüyle paranın durumuna göre konuşur ve başka bir söz de söyler", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Pano" })).toBeVisible();
  // The first page of a run may wait for the service's first analysis, as the screens' tests do.
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  const said = page.getByRole("region", { name: "İplikçi Nedim'in paranız hakkındaki sözü" });
  await expect(said).toBeVisible();
  const line = said.locator("blockquote");
  await expect(line).toHaveText(/\S/);
  await expect(said.getByText("İplikçi Nedim", { exact: true })).toBeVisible();
  const face = said.locator("img");
  await expect(face).toHaveAttribute("src", /^\/(logo|face-(warning|critical|neutral))\.png$/);
  await expect
    .poll(() => face.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0))
    .toBe(true); // the drawing itself, served with the interface
  const first = await line.innerText();
  await said.getByRole("button", { name: "Başka bir söz" }).click();
  await expect(line).not.toHaveText(first);
});
