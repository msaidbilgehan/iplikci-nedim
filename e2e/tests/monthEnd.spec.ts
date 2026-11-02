// The Ay sonu screens on the service itself (F11): a month opens from the list with its status and its accounts'
// closing; the month before is one step away; a big purchase opens its detail at the side; the detailed view's tables
// pass axe. Nothing here changes data, so both themes' projects run it side by side on the one demo data folder.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function loaded(page: Page): Promise<void> {
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
}

async function violations(page: Page): Promise<string[]> {
  const found = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  return found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

test("bir ay listeden açılır, hesapların kapanışını gösterir ve önceki aya geçilir", async ({ page }) => {
  await page.goto("/ay-sonu");
  await loaded(page);
  await page.getByRole("region", { name: "Aylar" }).getByRole("link", { name: "Ekim 2026" }).click();
  await expect(page).toHaveURL(/\/ay-sonu\/2026-10$/);
  await expect(page.getByRole("heading", { level: 1, name: "Ekim 2026" })).toBeVisible();
  await loaded(page);
  const accounts = page.getByRole("region", { name: "Hesapların kapanışı" });
  await expect(accounts.getByRole("link", { name: "TEB Vadesiz TL 123456789" })).toBeVisible();

  const months = page.getByRole("navigation", { name: "Aylar arasında gezinme" });
  await months.getByRole("link", { name: /^Önceki ay/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Eylül 2026" })).toBeVisible();
  await loaded(page);
});

test("büyük bir harcama yan panelde açılır ve ayrıntılı görünüm erişilebilirlik denetiminden geçer", async ({
  page,
}) => {
  await page.goto("/ay-sonu/2026-10");
  await loaded(page);
  await page.getByRole("region", { name: "Büyük harcamalar" }).getByRole("link").first().click();
  await expect(page).toHaveURL(/[?&]satir=/);
  const panel = page.getByRole("dialog");
  await expect(panel).toBeVisible();
  await loaded(page);
  expect(await violations(page)).toEqual([]);
  await panel.getByRole("button", { name: "Kapat" }).first().click();
  await expect(page).not.toHaveURL(/[?&]satir=/);

  // The view's switch is a group of radio buttons drawn as words: its label is what one presses.
  await page.getByRole("button", { name: /^Görünüm: / }).click(); // the header's display menu
  await page.getByRole("group", { name: "Görünüm" }).getByText("Ayrıntılı").click();
  await expect(page.getByRole("radio", { name: "Ayrıntılı" })).toBeChecked();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("region", { name: "Toplamlar" }).getByRole("table")).toBeVisible();
  expect(await violations(page)).toEqual([]);
});
