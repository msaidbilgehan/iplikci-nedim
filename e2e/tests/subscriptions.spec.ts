// The Düzenli ödemeler screen on the service itself (F08): a monthly payment is ended through "İptal ettim" — the month of
// its last payment chosen, the rule file's change previewed, then saved — and expected again through "Yeniden bekle".
// The light theme's project ends one at its last payment's month, so it reads as cancelled among what ended; the dark
// one names the month before, so the payment after it reads as a warning. Each ends a payment of its own, so the two
// run side by side on the one demo data folder and write the one rule file: two changes at once both stand. The
// salary, the demo's only income, is ended through "Artık gelmiyor" by the light theme's project alone.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const SAVES = { timeout: 20_000 }; // the service makes its analysis again before it answers a rule change
// The demo's monthly payments, last paid in October 2026: one for each theme, and the month each gives as the last.
const PLAN: Record<string, { payee: string; month: string; monthName: string }> = {
  acik: { payee: "Spotify", month: "2026-10", monthName: "Ekim 2026'dan" },
  koyu: { payee: "Turkcell", month: "2026-09", monthName: "Eylül 2026'dan" },
};

async function loaded(page: Page): Promise<void> {
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
}

async function violations(page: Page, selector: string): Promise<string[]> {
  const found = await new AxeBuilder({ page }).include(selector).withTags(WCAG).analyze();
  return found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`);
}

test("bir ödeme iptal edilir, önizlenip kaydedilir ve yeniden beklenir", async ({ page }, testInfo) => {
  test.slow(); // two rule changes, each with the analysis made again, and the other theme's beside them
  const plan = PLAN[testInfo.project.name] ?? { payee: "Spotify", month: "2026-10", monthName: "Ekim 2026'dan" };
  const late = plan.month !== "2026-10"; // a payment came after the month given
  await page.goto("/abonelikler");
  await loaded(page);
  const monthly = page.getByRole("region", { name: "Aylık ödemeler" });
  await monthly.getByRole("button", { name: `İptal ettim: ${plan.payee}` }).click();

  const panel = page.getByRole("dialog", { name: plan.payee });
  const month = panel.getByLabel("Son ödeme ayı");
  await expect(month).toBeFocused();
  await expect(month).toHaveValue("2026-10"); // its last payment's month
  await month.selectOption(plan.month);
  if (late) {
    await expect(panel.getByText("Bu aydan sonra 1 ödeme var;", { exact: false })).toBeVisible();
  }
  await panel.getByRole("button", { name: "Önizle" }).click();
  const change = panel.getByRole("figure", { name: "Kişisel kurallarınızdaki değişiklik" });
  await expect(change).toContainText(new RegExp(`\\+\\s+${plan.payee}: ${plan.month}`));
  expect(await violations(page, '[role="dialog"]')).toEqual([]);
  await panel.getByRole("button", { name: "Kaydet" }).click();
  const saved = `Kaydedildi: ${plan.payee} için ${plan.monthName} sonra ödeme beklenmiyor.`;
  await expect(panel.getByText(saved)).toBeVisible(SAVES);
  const again = panel.getByRole("region", { name: "Yeniden bekle" });
  await expect(again).toBeVisible(SAVES); // the rules read again: the entry is the user's own now
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();

  // Cancelled, it stands among what ended; paid after the month given, it stays a monthly payment with a warning.
  const section = late ? monthly : page.getByRole("region", { name: "Biten ve iptal edilenler" });
  await expect(section.getByRole("link", { name: plan.payee, exact: true })).toBeVisible(SAVES);
  if (late) {
    const warning = page.getByRole("status").filter({ hasText: "sonrasında da ödendi" });
    await expect(warning.getByRole("link", { name: plan.payee, exact: true })).toBeVisible(SAVES);
  }
  expect(await violations(page, "main")).toEqual([]);

  await section.getByRole("button", { name: `Yeniden bekle: ${plan.payee}` }).click();
  await expect(again.getByRole("button", { name: "Önizle" })).toBeFocused();
  await again.getByRole("button", { name: "Önizle" }).click();
  await expect(again.getByRole("figure")).toContainText(new RegExp(`-\\s+${plan.payee}: ${plan.month}`));
  await again.getByRole("button", { name: "Kaydet" }).click();
  const back = `Kaydedildi: ${plan.payee} için son ödeme ayı kurallarınızdan çıktı.`;
  await expect(panel.getByText(back)).toBeVisible(SAVES);
  await page.keyboard.press("Escape");
  await expect(monthly.getByRole("button", { name: `İptal ettim: ${plan.payee}` })).toBeVisible(SAVES);
});

/** text as a regular expression's own letters: a payer's name may hold a dot. */
function literal(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test("düzenli bir gelir artık gelmiyor diye bitirilir, önizlenip kaydedilir ve yeniden beklenir", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "acik", "the demo has one income: only the light theme's project ends it");
  test.slow(); // two rule changes, each with the analysis made again
  const payer = "Örnek İşveren A.Ş.";
  await page.goto("/abonelikler");
  await loaded(page);
  const income = page.getByRole("region", { name: "Düzenli gelirler" });
  await income.getByRole("button", { name: `Artık gelmiyor: ${payer}` }).click();

  const panel = page.getByRole("dialog", { name: payer });
  const month = panel.getByLabel("Son geliş ayı");
  await expect(month).toBeFocused();
  await expect(month).toHaveValue("2026-10"); // the last salary's month
  await panel.getByRole("button", { name: "Önizle" }).click();
  const change = panel.getByRole("figure", { name: "Kişisel kurallarınızdaki değişiklik" });
  await expect(change).toContainText(new RegExp(`\\+\\s+${literal(payer)}: 2026-10`));
  expect(await violations(page, '[role="dialog"]')).toEqual([]);
  await panel.getByRole("button", { name: "Kaydet" }).click();
  await expect(panel.getByText(`Kaydedildi: ${payer} için Ekim 2026'dan sonra gelir beklenmiyor.`)).toBeVisible(SAVES);
  const again = panel.getByRole("region", { name: "Yeniden bekle" });
  await expect(again).toBeVisible(SAVES);
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();

  // It stays on the list as no longer coming, with nothing to expect, and may be expected again.
  await expect(income.getByText("Artık gelmiyor", { exact: true })).toBeVisible(SAVES);
  await expect(income.getByText("Kişisel kurallarınızda son geliş ayı Ekim 2026.")).toBeVisible();
  expect(await violations(page, "main")).toEqual([]);
  await income.getByRole("button", { name: `Yeniden bekle: ${payer}` }).click();
  await expect(again.getByRole("button", { name: "Önizle" })).toBeFocused();
  await again.getByRole("button", { name: "Önizle" }).click();
  await expect(again.getByRole("figure")).toContainText(new RegExp(`-\\s+${literal(payer)}: 2026-10`));
  await again.getByRole("button", { name: "Kaydet" }).click();
  await expect(panel.getByText(`Kaydedildi: ${payer} için son geliş ayı kurallarınızdan çıktı.`)).toBeVisible(SAVES);
  await page.keyboard.press("Escape");
  await expect(income.getByRole("button", { name: `Artık gelmiyor: ${payer}` })).toBeVisible(SAVES);
});

test("her ay gelen bir gelir formu ödeyenin ayını söyler, önizlenir ve erişilebilirlik denetiminden geçer", async ({
  page,
}) => {
  // The demo's salary is a series already: offered as a payer whose income makes none yet, it shows the form on the
  // service's own screen. Nothing is saved: the other tests read the same rule file.
  await page.route("**/api/subscriptions", async (route) => {
    const response = await route.fetch();
    const found = await response.json();
    const candidate = {
      payee: "Örnek İşveren A.Ş.",
      account: { id: "teb-123456789", label: "TEB Vadesiz TL 123456789" },
      month: "2026-10",
      parts: [{ minor: 4000000, currency: "TRY" }],
      amount: { minor: 4000000, currency: "TRY" },
      day: 1,
    };
    await route.fulfill({ response, json: { ...found, income_candidates: [candidate] } });
  });
  await page.goto("/abonelikler");
  await loaded(page);
  const income = page.getByRole("region", { name: "Düzenli gelirler" });
  await income.getByRole("button", { name: "Her ay gelen bir gelir ekle…" }).click();
  const form = income.getByRole("region", { name: "Her ay gelen bir gelir" });
  await expect(form.getByLabel("Ayda gelen tutar (TL)")).toHaveValue("40.000");
  await form.getByLabel("Ayda gelen tutar (TL)").fill("42.000");
  await form.getByRole("button", { name: "Önizle" }).click();
  await expect(
    form.getByText("Kaydedince Örnek İşveren A.Ş. her ay 42.000,00 TL gelir diye sayılır, ayın 1. günü", {
      exact: false,
    }),
  ).toBeVisible(SAVES);
  expect(await violations(page, "main")).toEqual([]);
  await form.getByRole("button", { name: "Vazgeç" }).click();
});
