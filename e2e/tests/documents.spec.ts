// The Belgeler screens on the service itself (F03): the list narrowed by kind opens a document in the viewer, where a
// sheet's row and a PDF's row are marked where they are printed, and the viewer passes axe; the tab of what was not
// read passes axe too; and a document is read again. Each theme's project reads a document of its own again, so the
// two run side by side on the one demo data folder.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const LIST = "Saklanan belgeler, en yenisi önce";

async function loaded(page: Page): Promise<void> {
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
}

async function violations(page: Page): Promise<string[]> {
  const found = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  return found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

/** Opens the newest document the filters keep in the viewer. */
async function openFirst(page: Page, filters: string): Promise<void> {
  await page.goto(`/belgeler?${filters}`);
  await loaded(page);
  await page.getByRole("list", { name: LIST }).getByRole("link").first().click();
  await expect(page).toHaveURL(/\/belgeler\/[0-9a-f]{64}$/);
  await loaded(page);
}

test("bir hesap dökümünün satırı tabloda işaretlenir ve görüntüleyici erişilebilirlik denetiminden geçer", async ({
  page,
}) => {
  await openFirst(page, "kind=account_statement&q=TEB"); // the TEB account's lists: sheets with rows
  const rows = page.getByRole("region", { name: "Okunan işlemler" });
  await rows.getByRole("listitem").first().getByRole("button").click();
  await expect(page).toHaveURL(/[?&]satir=/);
  await expect(page.getByRole("rowheader", { name: /\(seçili işlemin satırı\)/ })).toBeVisible();
  await expect(rows.getByRole("region", { name: "Seçili işlem" })).toBeVisible();
  expect(await violations(page)).toEqual([]);
});

test("bir dekontun sayfası gösterilir ve seçilen satırın yeri işaretlenir", async ({ page }) => {
  await openFirst(page, "kind=receipt");
  await expect(page.getByRole("img", { name: /, sayfa 1$/ })).toBeVisible();
  await page.getByRole("region", { name: "Okunan işlemler" }).getByRole("listitem").first().getByRole("button").click();
  const marked = page
    .getByRole("img", { name: /seçili işlemin satırı işaretli/ })
    .or(page.getByRole("list", { name: /seçili işlemin satırı işaretli/ }));
  await expect(marked.first()).toBeVisible();
  expect(await violations(page)).toEqual([]);
});

test("okunmayanlar sekmesi erişilebilirlik denetiminden geçer ve bir belge yeniden okunur", async ({
  page,
}, testInfo) => {
  await page.goto("/belgeler");
  await loaded(page);
  await page.getByText("İşlenmeyenler ve okunamayanlar", { exact: true }).click(); // the radio's label
  await expect(page).toHaveURL(/status=unprocessed&status=unreadable/);
  await loaded(page);
  expect(await violations(page)).toEqual([]);
  if (testInfo.project.name === "acik") {
    // The light theme's project reads again a document no reader took.
    const again = page.getByRole("button", { name: /^Yeniden dene: / }).first();
    const name = ((await again.getAttribute("aria-label")) ?? "").replace("Yeniden dene: ", "");
    await again.click();
    await expect(page.getByText(`${name} yeniden okundu:`, { exact: false })).toBeVisible({ timeout: 20_000 });
  } else {
    // The dark theme's, a statement read before: the same rows come back, and the corrections kept by them stay.
    await openFirst(page, "kind=account_statement");
    await page.getByRole("button", { name: "Yeniden oku" }).click();
    await expect(page.getByText("Belge yeniden okundu: İşlendi.", { exact: false })).toBeVisible({ timeout: 20_000 });
  }
});
