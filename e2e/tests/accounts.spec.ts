// The Hesaplar screens on the service itself (F07): an account gets a name of the user's own, which the account map
// shows; accounts chosen together open their rows on the İşlemler screen; the bank's name comes back; and a band of the
// money's way between the accounts leads to its rows, from the table and from the drawing. Each theme's project names
// an account of its own, so the two run side by side on the one demo data folder; the TL account the screens' test
// opens is never renamed.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const TEB = { id: "teb-123456789", label: "TEB Vadesiz TL 123456789" };
// The demo's Garanti current account and its brokerage account: one for each theme.
const OWN: Record<string, string> = { acik: "garanti-1234567", koyu: "garanti-yatirim-1234567-101" };
const OCTOBER = "from=2026-10-01&to=2026-10-31"; // a window the demo's documents cover whole

async function loaded(page: Page): Promise<void> {
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
}

async function violations(page: Page, selector: string): Promise<string[]> {
  const found = await new AxeBuilder({ page }).include(selector).withTags(WCAG).analyze();
  return found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`);
}

test("bir hesaba kendi adı verilir, seçilen hesapların işlemleri birlikte açılır ve bankanın adına dönülür", async ({
  page,
}, testInfo) => {
  const id = OWN[testInfo.project.name] ?? "garanti-1234567";
  await page.goto(`/hesaplar/${id}`);
  await loaded(page);
  const heading = page.getByRole("heading", { level: 1 });
  const bank = (await heading.textContent()) ?? "";
  expect(bank).not.toBe("Hesap");

  await page.getByRole("button", { name: "Adını değiştir" }).click();
  expect(await violations(page, "form")).toEqual([]);
  const name = `Uçtan uca hesap (${testInfo.project.name})`;
  await page.getByLabel("Hesabın adı").fill(name);
  await page.getByRole("button", { name: "Adı kaydet" }).click();
  await expect(page.getByText("Hesabın adı kaydedildi.")).toBeVisible();
  await expect(heading).toHaveText(name);
  await expect(page.getByText(`bankadaki adı ${bank}`)).toBeVisible();

  await page.goto("/hesaplar");
  await loaded(page);
  await page.getByRole("checkbox", { name: `Birlikte göster: ${name}` }).check();
  await page.getByRole("checkbox", { name: `Birlikte göster: ${TEB.label}` }).check();
  const chosen = page.getByRole("region", { name: "Seçili hesaplar" });
  await expect(chosen).toContainText("2 hesap seçildi");
  expect(await violations(page, 'section[aria-label="Seçili hesaplar"]')).toEqual([]);
  await chosen.getByRole("link", { name: "İşlemlerini birlikte göster" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "İşlemler" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`[?&]account=${id}(&|$)`));
  await expect(page).toHaveURL(new RegExp(`[?&]account=${TEB.id}(&|$)`));
  await loaded(page);

  await page.goto(`/hesaplar/${id}`);
  await loaded(page);
  await page.getByRole("button", { name: "Adını değiştir" }).click();
  await page.getByRole("button", { name: "Bankanın adına dön" }).click();
  await expect(page.getByText("Hesap yeniden bankanın adıyla görünüyor.")).toBeVisible();
  await expect(heading).toHaveText(bank);
});

test("hesaplar arası akışın tablosu erişilebilirlik denetiminden geçer ve bir akış işlemlerine götürür", async ({
  page,
}) => {
  await page.goto(`/hesaplar?${OCTOBER}`);
  await loaded(page);
  const flows = page.getByRole("region", { name: "Hesaplar arası akış" });
  await flows.getByRole("tab", { name: "Tablo" }).click();
  const bands = flows.getByRole("link", { name: /^İşlemleri göster: / });
  await expect(bands.first()).toBeVisible();
  expect(await violations(page, "table")).toEqual([]);
  await bands.first().click();
  await expect(page.getByRole("heading", { level: 1, name: "İşlemler" })).toBeVisible();
  await expect(page).toHaveURL(/[?&]from=2026-10-01(&|$)/);
  await loaded(page);
  await expect(page.getByRole("table").first()).toBeVisible(); // the band's rows
});

test("akış diyagramında bir bant tıklanınca onu oluşturan işlemler açılır, toplamları bandınkine eşittir", async ({
  page,
}) => {
  await page.goto(`/hesaplar?${OCTOBER}`);
  await loaded(page);
  const flows = page.getByRole("region", { name: "Hesaplar arası akış" });
  await expect(flows.getByText("Bir akışa tıklayın: onu oluşturan işlemler listelenir.")).toBeVisible();
  // The band from the TL account to a spending group, and its amount as the table view writes it.
  await flows.getByRole("tab", { name: "Tablo" }).click();
  const row = flows.getByRole("row", { name: new RegExp(`^${TEB.label} Yeme & İçme`) });
  const amount = ((await row.getByRole("cell").nth(2).textContent()) ?? "").trim();
  await flows.getByRole("tab", { name: "Grafik" }).click();
  const drawing = flows.getByRole("img", { name: /: akış diyagramı\./ });
  await drawing.scrollIntoViewIfNeeded();
  const middles = await drawing.locator("g[fill='none'] path").evaluateAll((paths) =>
    paths.map((path) => {
      const band = path as SVGPathElement;
      const point = band.getPointAtLength(band.getTotalLength() / 2);
      const box = band.ownerSVGElement?.getBoundingClientRect();
      return { x: (box?.x ?? 0) + point.x, y: (box?.y ?? 0) + point.y };
    }),
  );
  const tip = flows.getByText(`${TEB.label} → Yeme & İçme: ${amount}`);
  let found = false;
  for (const { x, y } of middles) {
    await page.mouse.move(x, y);
    if (await tip.isVisible()) {
      found = true;
      await page.mouse.click(x, y);
      break;
    }
  }
  expect(found).toBe(true);
  await expect(page).toHaveURL(/\/islemler\?.*group=Yeme\+%26\+%C4%B0%C3%A7me/);
  await loaded(page);
  const totals = page.getByRole("region", { name: "Toplamlar" });
  await expect(totals.getByText(amount, { exact: true })).toBeVisible(); // the Harcama tile: the band's amount
});
