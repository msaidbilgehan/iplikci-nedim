// The Bildirimler screen on the service itself (F13): a test notification of the interface's own box lands in the box
// and the delivery history and is marked seen; a rule's switch saves the whole list; the editor previews a new rule's
// last 30 days, passes axe and gives the focus back when it closes; the detailed view passes axe too. No notification
// leaves the computer: the demo's settings turn every channel off ([notify] channels = []), and only the box is tried.
// The box and the rule file are shared by both themes' projects, so only the light one changes them.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const SAVES = { timeout: 20_000 };

async function loaded(page: Page): Promise<void> {
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
}

async function violations(page: Page, selector = "body"): Promise<string[]> {
  const found = await new AxeBuilder({ page }).include(selector).withTags(WCAG).analyze();
  return found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

test("uygulama içi deneme bildirimi kutuya ve teslim kaydına düşer, okundu sayılır", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "acik", "the box is shared: only the light theme's project adds to it");
  await page.goto("/bildirimler");
  await loaded(page);
  const channels = page.getByRole("region", { name: "Kanallar" });
  // Every channel that leaves the computer is off in the demo: only the box gets notifications.
  await expect(channels.getByText(/^Bildirimler yalnızca uygulamadaki kutuya düşüyor;/)).toBeVisible();
  await channels.getByRole("button", { name: "Uygulama içi: Deneme bildirimi gönder" }).click();
  await expect(channels.getByText("Deneme bildirimi kutuya düştü")).toBeVisible();

  // Another test's rule change may add a notification of its own meanwhile (a payment after a cancellation): this
  // test looks only at its own, and the box is marked seen up to the newest one shown, never past it.
  const box = page.getByRole("region", { name: "Bildirim kutusu" });
  const item = box.getByRole("listitem").filter({ hasText: "Deneme bildirimi" });
  await expect(item).toContainText("İplikçi Nedim bildirimleri bu kanala ulaşıyor.");
  await expect(item.getByText("Yeni", { exact: true })).toBeVisible();
  await expect(box.getByText(/bildirimi henüz görmediniz; en yenisi: .+\.$/)).toBeVisible();
  await box.getByRole("button", { name: "Tümünü okundu say" }).click();
  await expect(item.getByText("Yeni", { exact: true })).toHaveCount(0);

  const log = page.getByRole("region", { name: "Teslim kaydı" });
  const delivered = log.getByRole("listitem").filter({ hasText: "Deneme bildirimi" });
  await expect(delivered).toContainText("Gönderildi");
  await expect(delivered).toContainText("Uygulama içi");
});

test("bir kuralın anahtarı bütün listeyi kaydeder: kural kapanır ve yeniden açılır", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "acik", "the rule file is shared: only the light theme's project changes it");
  await page.goto("/bildirimler");
  await loaded(page);
  const rules = page.getByRole("region", { name: "Kurallar" });
  const backup = rules.getByRole("switch", { name: "Yedek alınamadı: Açık" });
  await expect(backup).toBeChecked();
  await backup.click();
  await expect(rules.getByText("Kurallar kaydedildi")).toBeVisible(SAVES);
  await expect(backup).not.toBeChecked();
  const backupRule = rules.getByRole("listitem").filter({ hasText: "Yedek alınamadı" });
  await expect(backupRule.getByText("Kapalı", { exact: true })).toBeVisible();
  // Saved once, the rules are the user's own: the sentence counts them.
  await expect(rules.getByText(/^\d+ kural açık, 1 kural kapalı\.$/)).toBeVisible();
  await backup.click();
  await expect(backup).toBeChecked(SAVES);
  await expect(rules.getByText(/^\d+ kuralın hepsi açık\.$/)).toBeVisible();
});

test("yeni bir kural son 30 günle önizlenir, düzenleyici denetimden geçer ve kapanınca odak geri döner", async ({
  page,
}) => {
  await page.goto("/bildirimler");
  await loaded(page);
  const rules = page.getByRole("region", { name: "Kurallar" });
  const add = rules.getByRole("button", { name: "Yeni kural" });
  await add.click();
  const editor = rules.getByRole("form", { name: "Yeni kural" });
  await expect(editor.getByLabel("Ad")).toBeFocused();
  await editor.getByLabel("Olay").selectOption({ label: "Belge geldi" });
  await editor.getByRole("button", { name: "Son 30 günde kaç kez?" }).click();
  // The demo's documents came when its folder was made: each one is an event of the last 30 days.
  await expect(editor.getByText(/^Son 30 günde \d+ kez bildirim verirdi\.$/)).toBeVisible();
  await expect(editor.getByText("Belge geldi: Yeni bir belge geldi.").first()).toBeVisible();
  expect(await violations(page)).toEqual([]);
  await editor.getByRole("button", { name: "Vazgeç" }).click();
  await expect(editor).toHaveCount(0);
  await expect(add).toBeFocused(); // nothing was saved: the button that opened it has the focus back
});

test("ayrıntılı görünüm kanalların durumunu ve olay kodlarını gösterir, erişilebilirlik denetiminden geçer", async ({
  page,
}) => {
  await page.goto("/bildirimler");
  await loaded(page);
  // The view's switch is a group of radio buttons drawn as words: its label is what one presses.
  await page.getByRole("group", { name: "Görünüm" }).getByText("Ayrıntılı").click();
  await expect(page.getByRole("radio", { name: "Ayrıntılı" })).toBeChecked();
  const channels = page.getByRole("region", { name: "Kanallar" });
  const states = channels.getByRole("table", { name: "Kanalların ayarları ve durumu, servisin verdiği gibi" });
  await expect(states.getByRole("row", { name: /^Telegram/ })).toContainText("Kurulmadı");
  const list = page.getByRole("list", { name: "Bildirim kuralları" });
  await expect(list.getByText("payment.due_soon")).toBeVisible();
  expect(await violations(page)).toEqual([]);
});
