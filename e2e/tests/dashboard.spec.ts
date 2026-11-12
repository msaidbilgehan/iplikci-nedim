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

test("Pano'nun hikâyesi biten son ayı anlatır ve oklarla önceki aya gider", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  const story = page.getByRole("region", { name: /: paranız ne durumda\?$/ });
  await expect(story).toBeVisible();
  const title = await story.getByRole("heading", { level: 2 }).innerText();
  const before = story.getByRole("navigation", { name: "Aylar" }).getByRole("link", { name: /^Önceki ay: / });
  const name = (await before.innerText()).replace(/^Önceki ay:\s*/, "").trim(); // the words after its hidden lead
  await before.click();
  await expect(page).toHaveURL(/\/\?ay=\d{4}-\d{2}$/);
  await expect(page.getByRole("region", { name: `${name}: paranız ne durumda?` })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("region", { name: title })).toBeVisible();
});

test("Pano'da bir ayın adına tıklayınca o ayın bütün işlemleri açılır", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  const months = page.getByRole("region", { name: "Aylara göre gelen ve giden" });
  const chart = months.getByRole("img", { name: /yığılmış sütun grafiği/ });
  // The month's name under the axis: the column's own click area lies over it, so the mouse clicks its place,
  // once the chart is in the window.
  await chart.scrollIntoViewIfNeeded();
  const name = chart.locator("text").filter({ hasText: /^\p{Lu}\p{Ll}{2} \d{2}$/u }).last();
  const box = await name.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.click((box?.x ?? 0) + (box?.width ?? 0) / 2, (box?.y ?? 0) + (box?.height ?? 0) / 2);
  await expect(page).toHaveURL(/\/islemler\?from=\d{4}-\d{2}-01&to=\d{4}-\d{2}-\d{2}$/);
  await expect(page.getByRole("table", { name: /^İşlemler,/ })).toBeVisible();
});
