// The Yapılacaklar screen on the service itself (F19): an item is taken off the list and put back from the notice that
// says so, and the detailed view passes axe. Each theme's project takes a different item of the demo off, so the two
// run side by side on the one demo data folder.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

// The demo's two items: an account whose July is missing, and a document no reader takes.
const ITEMS = { acik: "TEB Vadesiz TL", koyu: "TalimatFormu.pdf" } as const;
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

// One after the other in a project: while a project's item is off the list, its other test would miss it.
test.describe.configure({ mode: "serial" });

/** A step's button: its name is the step and the item's title, which may go on after these words. */
function step(page: Page, words: string) {
  return page.getByRole("button", { name: new RegExp(`^${words.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`) });
}

async function open(page: Page): Promise<void> {
  await page.goto("/yapilacaklar");
  await expect(page.getByRole("heading", { level: 1, name: "Yapılacaklar" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
}

async function violations(page: Page): Promise<string[]> {
  const found = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  return found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")} — ${v.nodes[0]?.failureSummary ?? ""}`);
}

test("bir iş listeden çıkarılır ve bildirimdeki düğmeyle geri alınır", async ({ page }, testInfo) => {
  const title = ITEMS[testInfo.project.name as keyof typeof ITEMS];
  await open(page);
  await step(page, `Yok say: ${title}`).click();
  await expect(page.getByText(new RegExp(`^“${title}.*” listeden çıkarıldı\\.$`))).toBeVisible();
  await expect(step(page, `Yok say: ${title}`)).toHaveCount(0);
  await page.getByRole("button", { name: "Geri al" }).click();
  await expect(page.getByText(new RegExp(`^“${title}.*” listeye geri alındı\\.$`))).toBeVisible();
  await expect(step(page, `Yok say: ${title}`)).toBeVisible();
});

// It touches nothing; the other project may be taking its own item off meanwhile, never this project's.
test("ayrıntılı görünümün tabloları erişilebilirlik denetiminden geçer", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /^Görünüm: / }).click(); // the header's display menu
  await page.getByRole("group", { name: "Görünüm" }).getByText("Ayrıntılı").click();
  await expect(page.getByRole("radio", { name: "Ayrıntılı" })).toBeChecked();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("table").first()).toBeVisible();
  expect(await violations(page)).toEqual([]);
});
