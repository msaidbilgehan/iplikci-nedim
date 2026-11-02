// Every screen opens on the demo data folder, finishes loading without an error, and passes axe's WCAG 2.1 A and
// AA checks (features.md, shared rules) — in the light and the dark theme, one project each.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// The screens and their main headings; each new screen joins this list.
const SCREENS = [
  { path: "/", heading: "Pano" },
  { path: "/akis", heading: "Akış" },
  { path: "/islemler", heading: "İşlemler" },
  { path: "/sistem", heading: "Sistem" },
  { path: "/belgeler", heading: "Belgeler" },
  { path: "/abonelikler", heading: "Abonelikler" },
  { path: "/takvim", heading: "Takvim" },
  { path: "/faturalar", heading: "Faturalar" },
  { path: "/bildirimler", heading: "Bildirimler" },
  { path: "/kurulum/eklenti", heading: "Tarayıcı eklentisi" },
] as const;

for (const screen of SCREENS) {
  test(`${screen.heading} ekranı yüklenir ve erişilebilirlik denetiminden geçer`, async ({ page }) => {
    await page.goto(screen.path);
    await expect(page.getByRole("heading", { level: 1, name: screen.heading })).toBeVisible();
    // The live event stream keeps a request open, so "network idle" never comes: wait for the loading states.
    await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
    await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
    await expect(page.getByText("Oturum kapandı")).toHaveCount(0);
    const found = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    // Each violation with its first elements and why they fail, so a failure in CI says what to fix.
    const violations = found.violations.map((v) => ({
      rule: v.id,
      impact: v.impact,
      where: v.nodes
        .slice(0, 5)
        .map((n) => `${n.target.join(" ")} — ${n.html.slice(0, 160)} — ${(n.failureSummary ?? "").slice(0, 300)}`),
    }));
    expect(violations).toEqual([]);
  });
}

test("bilinmeyen bir adres sayfanın olmadığını söyler", async ({ page }) => {
  await page.goto("/boyle-bir-yer-yok");
  await expect(page.getByRole("heading", { level: 1, name: "Böyle bir sayfa yok" })).toBeVisible();
});
