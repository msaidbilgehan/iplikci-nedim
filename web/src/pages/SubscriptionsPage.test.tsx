import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { keys } from "../api/queries";
import type { RuleChange } from "../api/types";
import { CATEGORY_RULES, server, SUBSCRIPTIONS } from "../test/server";
import { renderScreen } from "../test/render";
import SubscriptionsPage from "./SubscriptionsPage";

afterEach(() => localStorage.clear());

const ENDED_DIFF = [
  "--- personal.yaml (önce)",
  "+++ personal.yaml (sonra)",
  "@@ -1,3 +1,4 @@",
  " _biten:",
  "   ORNEK VIDEO: 2026-09",
  "   Örnek Dergi: 2026-08",
  "+  Örnek Müzik: 2026-10  # kart değişti",
].join("\n");

function change(diff: string, saved = false): RuleChange {
  return { content: "", diff, changed: 0, moves: [], examples: [], saved, backup: saved ? "personal 1.yaml" : "" };
}

/** The rule edits the screen previews and saves, as the service received them. */
function serveRules(diff: string) {
  const previewed: unknown[] = [];
  const saved: unknown[] = [];
  server.use(
    http.post("/api/rules/categories/preview", async ({ request }) => {
      previewed.push(await request.json());
      return HttpResponse.json(change(diff));
    }),
    http.put("/api/rules/categories", async ({ request }) => {
      saved.push(await request.json());
      return HttpResponse.json(change(diff, true));
    }),
  );
  return { previewed, saved };
}

async function card(region: string, payee: string): Promise<HTMLElement> {
  const section = await screen.findByRole("region", { name: region });
  return within(section).getByRole("link", { name: payee }).closest("li")!;
}

describe("SubscriptionsPage", () => {
  it("says what the running monthly payments come to, and lists each with what it costs and expects", async () => {
    renderScreen(<SubscriptionsPage />);
    expect(
      await screen.findByText(
        "Süren 4 aylık ödemeniz ayda toplam 15.949,98 TL tutuyor. Ayrıca 1 dönemsel ödeme var.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Takvimde göster" })).toHaveAttribute("href", "/takvim");
    const rent = await card("Aylık ödemeler", "Ev kirası");
    expect(within(rent).getByText("Devam ediyor")).toBeInTheDocument();
    expect(within(rent).getByText("Ayda 15.000,00 TL")).toBeInTheDocument();
    expect(within(rent).getByText("Son ödeme 03.10.2026 · 15.000,00 TL")).toBeInTheDocument();
    expect(within(rent).getByText("Sıradaki 03.11.2026 · 15.000,00 TL")).toBeInTheDocument();
    expect(within(rent).getByText("Fiyat Temmuz 2026'dan beri 14.000,00 TL yerine 15.000,00 TL")).toBeInTheDocument();
    const basis = screen.getByText(/^Durumlar 31\.10\.2026 tarihli en yeni ekstreye göre\./);
    expect(basis).toHaveTextContent(
      "Durumlar 31.10.2026 tarihli en yeni ekstreye göre. Liste Nisan 2026 – Eylül 2026 arasındaki 6 tam aya bakıyor.",
    );
    expect(within(basis).getByRole("button", { name: "tam aya" })).toBeInTheDocument();
  });

  it("expects a moving bill at the median of its last three, and says so", async () => {
    renderScreen(<SubscriptionsPage />);
    const bill = await card("Aylık ödemeler", "Örnek Elektrik");
    expect(within(bill).getByText("Ayda 700,00 TL")).toBeInTheDocument();
    expect(within(bill).getByText(/son üç ödemenin medyanı/)).toBeInTheDocument();
    expect(within(bill).getByText("Son ödeme 20.10.2026 · 820,00 TL")).toBeInTheDocument();
  });

  it("shows a periodic payment per period, never as a month's amount", async () => {
    renderScreen(<SubscriptionsPage />);
    const insurance = await card("Dönemsel ödemeler", "Örnek Sigorta");
    expect(within(insurance).getByText("Yılda bir 4.800,00 TL")).toBeInTheDocument();
    expect(within(insurance).getByText("Sıradaki 08.01.2027 · 4.800,00 TL")).toBeInTheDocument();
    expect(screen.getByText("Tutarlar dönem başına; aylığa çevrilmez.")).toBeInTheDocument();
    const monthly = screen.getByRole("region", { name: "Aylık ödemeler" });
    expect(within(monthly).queryByText("Örnek Sigorta")).not.toBeInTheDocument();
  });

  it("keeps what ended or was cancelled apart, with what its status means, and leaves out the unlisted", async () => {
    renderScreen(<SubscriptionsPage />);
    const water = await card("Biten ve iptal edilenler", "Su faturası");
    expect(within(water).getByText("Bitti")).toBeInTheDocument();
    expect(within(water).getByText(/Belgelerde yok/)).toBeInTheDocument();
    expect(within(water).queryByText(/^Ayda/)).not.toBeInTheDocument(); // what it cost is no longer a commitment
    const magazine = await card("Biten ve iptal edilenler", "Örnek Dergi");
    expect(within(magazine).getByText("İptal edildi")).toBeInTheDocument();
    expect(within(magazine).getByText("Kişisel kurallarınızda son ödeme ayı Ağustos 2026.")).toBeInTheDocument();
    expect(screen.queryByText("Eski Dergi")).not.toBeInTheDocument();
  });

  it("warns of a payment after a cancellation, and opens the payments with the late one marked", async () => {
    const user = userEvent.setup();
    const view = renderScreen(<SubscriptionsPage />, { path: "/abonelikler" });
    const title = await screen.findByText("İptal ettiğiniz 1 ödeme sonrasında da ödendi");
    const alert = title.closest<HTMLElement>("[role=status]")!;
    expect(alert).toHaveTextContent(
      "Örnek Video: Kişisel kurallarınızda son ödeme ayı Eylül 2026, ama sonrasında da ödendi: aboneliği kontrol edin.",
    );
    await user.click(within(alert).getByRole("link", { name: "Örnek Video" }));
    expect(view.location()).toBe("/abonelikler?seri=fp-video");
    const panel = await screen.findByRole("dialog", { name: "Örnek Video" });
    const payments = within(panel).getByRole("table", { name: "Örnek Video ödemeleri, en yenisi önce" });
    const rows = within(payments).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("12.10.2026");
    expect(within(rows[0]!).getByText("İptalden sonra")).toBeInTheDocument();
    expect(within(rows[1]!).queryByText("İptalden sonra")).not.toBeInTheDocument();
  });

  it("opens a series' panel from its address, each payment leading to its row", async () => {
    const user = userEvent.setup();
    const view = renderScreen(<SubscriptionsPage />, { path: "/abonelikler?seri=fp-kira" });
    const panel = await screen.findByRole("dialog", { name: "Ev kirası" });
    expect(within(panel).getByText("Ayda 15.000,00 TL; sıradaki ödeme 03.11.2026'da bekleniyor.")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: "Takvimde göster" })).toHaveAttribute(
      "href",
      "/takvim?gun=2026-11-03",
    );
    expect(within(panel).getByRole("link", { name: "Örnek Vadesiz TL" })).toHaveAttribute(
      "href",
      "/hesaplar/teb-123456789",
    );
    const payments = within(panel).getByRole("table", { name: "Ev kirası ödemeleri, en yenisi önce" });
    const newest = within(payments).getByRole("link", { name: "03.11.2026" });
    expect(newest).toHaveAttribute("href", "/islemler?satir=fp-kira-11");
    expect(within(newest.closest("tr")!).getByText("geçici")).toBeInTheDocument();
    // Many documents share a file's name: each opens the very one, at the payment's row.
    expect(within(payments).getByRole("link", { name: "TEB Hesap Dökümü Ekim 2026.xls" })).toHaveAttribute(
      "href",
      `/belgeler/${"1".repeat(64)}?satir=fp-kira-10`,
    );
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(view.location()).toBe("/abonelikler");
  });

  it("says when the address names a series it does not know", async () => {
    renderScreen(<SubscriptionsPage />, { path: "/abonelikler?seri=yok" });
    const panel = await screen.findByRole("dialog", { name: "Ödeme bulunamadı" });
    expect(within(panel).getByText(/Bu ödeme listede yok/)).toBeInTheDocument();
  });

  it("ends a payment: the month of its last payment, the change previewed, then saved", async () => {
    const user = userEvent.setup();
    const { previewed, saved } = serveRules(ENDED_DIFF);
    renderScreen(<SubscriptionsPage />);
    const music = await card("Aylık ödemeler", "Örnek Müzik");
    await user.click(within(music).getByRole("button", { name: "İptal ettim: Örnek Müzik" }));
    const panel = await screen.findByRole("dialog", { name: "Örnek Müzik" });
    const month = within(panel).getByLabelText("Son ödeme ayı");
    expect(month).toHaveFocus(); // the panel opens at its form
    expect(month).toHaveValue("2026-10");
    expect(within(month).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Kasım 2026",
      "Ekim 2026 (son ödeme)",
      "Eylül 2026",
      "Ağustos 2026",
    ]);
    expect(within(panel).queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument(); // not before a preview
    await user.type(within(panel).getByLabelText("Not (isteğe bağlı)"), "kart değişti");
    await user.click(within(panel).getByRole("button", { name: "Önizle" }));
    const diff = await within(panel).findByRole("figure", { name: "Kişisel kurallarınızdaki değişiklik" });
    expect(diff).toHaveTextContent("+ Örnek Müzik: 2026-10 # kart değişti"); // toHaveTextContent folds the spaces
    expect(
      within(panel).getByText(
        "Kaydedince Örnek Müzik için Ekim 2026'dan sonra ödeme beklenmez; takvim ve öngörü onu saymaz.",
      ),
    ).toBeInTheDocument();
    expect(previewed).toEqual([{ action: "ended", merchant: "Örnek Müzik", month: "2026-10", note: "kart değişti" }]);
    server.use(
      http.get("/api/rules/categories", () =>
        HttpResponse.json({
          ...CATEGORY_RULES,
          ended: [...CATEGORY_RULES.ended, { merchant: "Örnek Müzik", month: "2026-10", own: true }],
        }),
      ),
    );
    await user.click(within(panel).getByRole("button", { name: "Kaydet" }));
    expect(
      await within(panel).findByText("Kaydedildi: Örnek Müzik için Ekim 2026'dan sonra ödeme beklenmiyor."),
    ).toBeInTheDocument();
    expect(saved).toEqual(previewed);
    // The rules read again, the payment is now the user's own ended one: it may be expected again.
    expect(await within(panel).findByRole("region", { name: "Yeniden bekle" })).toBeInTheDocument();
    expect(within(panel).queryByRole("region", { name: "İptal ettim" })).not.toBeInTheDocument();
  });

  it("puts the focus on the month once the rules come, when the panel opened before them", async () => {
    const user = userEvent.setup();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get("/api/rules/categories", async () => {
        await gate;
        return HttpResponse.json(CATEGORY_RULES);
      }),
    );
    renderScreen(<SubscriptionsPage />);
    const music = await card("Aylık ödemeler", "Örnek Müzik");
    await user.click(within(music).getByRole("button", { name: "İptal ettim: Örnek Müzik" }));
    const panel = await screen.findByRole("dialog", { name: "Örnek Müzik" });
    expect(within(panel).getByRole("heading", { name: "Örnek Müzik" })).toHaveFocus(); // its form is still to come
    release();
    const month = await within(panel).findByLabelText("Son ödeme ayı");
    await waitFor(() => expect(month).toHaveFocus());
  });

  it("keeps the form, its choice and the focus when reading the rules again fails", async () => {
    const user = userEvent.setup();
    const { client } = renderScreen(<SubscriptionsPage />, { path: "/abonelikler?seri=fp-muzik" });
    const panel = await screen.findByRole("dialog", { name: "Örnek Müzik" });
    const month = await within(panel).findByLabelText("Son ödeme ayı");
    await user.selectOptions(month, "2026-09");
    expect(month).toHaveFocus();
    server.use(
      http.get("/api/rules/categories", () =>
        HttpResponse.json({ code: "rules_invalid", title: "kişisel kurallar okunamadı" }, { status: 409 }),
      ),
    );
    await client.refetchQueries({ queryKey: keys.categoryRules });
    expect(client.getQueryState(keys.categoryRules)?.status).toBe("error");
    expect(within(panel).getByLabelText("Son ödeme ayı")).toBe(month); // the same form, not one made again
    expect(month).toHaveFocus();
    expect(month).toHaveValue("2026-09");
  });

  it("says when payments came after the month chosen, and that a cancellation reaches all of a payee's", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/subscriptions", () =>
        HttpResponse.json({
          ...SUBSCRIPTIONS,
          series: [
            ...SUBSCRIPTIONS.series,
            { ...SUBSCRIPTIONS.series[1]!, id: "fp-muzik-aile", amount: { minor: 19999, currency: "TRY" } },
          ],
        }),
      ),
    );
    renderScreen(<SubscriptionsPage />, { path: "/abonelikler?seri=fp-muzik" });
    const panel = await screen.findByRole("dialog", { name: "Örnek Müzik" });
    expect(
      within(panel).getByText("Örnek Müzik adına 2 düzenli ödeme var; iptal hepsine uygulanır."),
    ).toBeInTheDocument();
    expect(within(panel).queryByText(/Bu aydan sonra/)).not.toBeInTheDocument();
    await user.selectOptions(within(panel).getByLabelText("Son ödeme ayı"), "2026-09");
    expect(
      within(panel).getByText("Bu aydan sonra 1 ödeme var; kaydederseniz durumu “İptalden sonra ödeme var” olur."),
    ).toBeInTheDocument();
  });

  it("expects a cancelled payment again: the change previewed, then saved", async () => {
    const user = userEvent.setup();
    const { previewed, saved } = serveRules(
      [
        "--- personal.yaml (önce)",
        "+++ personal.yaml (sonra)",
        "@@ -1,3 +1,2 @@",
        " _biten:",
        "   ORNEK VIDEO: 2026-09",
        "-  Örnek Dergi: 2026-08",
      ].join("\n"),
    );
    renderScreen(<SubscriptionsPage />);
    const magazine = await card("Biten ve iptal edilenler", "Örnek Dergi");
    await user.click(within(magazine).getByRole("button", { name: "Yeniden bekle: Örnek Dergi" }));
    const panel = await screen.findByRole("dialog", { name: "Örnek Dergi" });
    const again = within(panel).getByRole("region", { name: "Yeniden bekle" });
    expect(again).toHaveTextContent(
      "Kişisel kurallarınızda Örnek Dergi için son ödeme ayı Ağustos 2026. " +
        "Ödeme yeniden bekleniyorsa bu satırı kaldırın.",
    );
    const preview = within(again).getByRole("button", { name: "Önizle" });
    expect(preview).toHaveFocus();
    await user.click(preview);
    expect(await within(again).findByRole("figure", { name: "Kişisel kurallarınızdaki değişiklik" })).toHaveTextContent(
      "- Örnek Dergi: 2026-08",
    );
    expect(previewed).toEqual([{ action: "not_ended", merchant: "Örnek Dergi" }]);
    await user.click(within(again).getByRole("button", { name: "Kaydet" }));
    expect(
      await within(panel).findByText("Kaydedildi: Örnek Dergi için son ödeme ayı kurallarınızdan çıktı."),
    ).toBeInTheDocument();
    expect(saved).toEqual(previewed);
  });

  it("offers both for a payment after a cancellation: expect it again, or give another month", async () => {
    const user = userEvent.setup();
    const { previewed } = serveRules("");
    renderScreen(<SubscriptionsPage />, { path: "/abonelikler?seri=fp-video" });
    const panel = await screen.findByRole("dialog", { name: "Örnek Video" });
    expect(
      within(panel).getByText(
        "Kişisel kurallarınızda son ödeme ayı Eylül 2026, ama sonrasında da ödendi: aboneliği kontrol edin.",
        { selector: "p" },
      ),
    ).toBeInTheDocument();
    // The user's rules write the payee their own way: the entry is found by its folded name and taken back as written.
    const again = within(panel).getByRole("region", { name: "Yeniden bekle" });
    await user.click(within(again).getByRole("button", { name: "Önizle" }));
    expect(previewed).toEqual([{ action: "not_ended", merchant: "ORNEK VIDEO" }]);
    expect(await within(again).findByText("Değişiklik yok: kurallarınız zaten böyle.")).toBeInTheDocument();
    const month = within(panel).getByRole("region", { name: "İptal ayını değiştir" });
    expect(within(month).getByLabelText("Son ödeme ayı")).toHaveValue("2026-10");
  });

  it("says why a change was refused, and keeps the form as it was", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/rules/categories/preview", () =>
        HttpResponse.json(
          { code: "documents_busy", title: "Belgeler şu an okunuyor; birazdan yeniden deneyin." },
          { status: 409 },
        ),
      ),
    );
    renderScreen(<SubscriptionsPage />, { path: "/abonelikler?seri=fp-muzik" });
    const panel = await screen.findByRole("dialog", { name: "Örnek Müzik" });
    await user.selectOptions(within(panel).getByLabelText("Son ödeme ayı"), "2026-11");
    await user.click(within(panel).getByRole("button", { name: "Önizle" }));
    expect(await within(panel).findByRole("alert")).toHaveTextContent(
      "Belgeler şu an okunuyor; birazdan yeniden deneyin.",
    );
    expect(within(panel).getByLabelText("Son ödeme ayı")).toHaveValue("2026-11");
  });

  it("says in the panel when the rules cannot be read, and offers to read them again", async () => {
    server.use(
      http.get("/api/rules/categories", () =>
        HttpResponse.json({ code: "rules_invalid", title: "kişisel kurallar okunamadı" }, { status: 409 }),
      ),
    );
    renderScreen(<SubscriptionsPage />, { path: "/abonelikler?seri=fp-muzik" });
    const panel = await screen.findByRole("dialog", { name: "Örnek Müzik" });
    expect(await within(panel).findByText("kişisel kurallar okunamadı")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Yeniden dene" })).toBeInTheDocument();
    expect(within(panel).queryByLabelText("Son ödeme ayı")).not.toBeInTheDocument();
    // A running payment has no entry in the rules, so its card offers to end it all the same; whether a cancelled one
    // is the user's own to expect again, only the rules say.
    expect(screen.getByRole("button", { name: "İptal ettim: Ev kirası", hidden: true })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Yeniden bekle:/, hidden: true })).not.toBeInTheDocument();
  });

  it("shows every value in tables in the detailed view, the running monthly payments added up", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<SubscriptionsPage />);
    const monthly = await screen.findByRole("table", { name: "Süren aylık ödemeler" });
    const rent = within(monthly).getByRole("link", { name: "Ev kirası" }).closest("tr")!;
    expect(within(rent).getByText("14.000,00 TL → 15.000,00 TL")).toBeInTheDocument();
    expect(within(rent).getByText("Temmuz 2026'dan beri")).toBeInTheDocument();
    expect(within(rent).getByText("2 ödeme")).toBeInTheDocument();
    expect(within(rent).getByRole("button", { name: "İptal ettim: Ev kirası" })).toBeInTheDocument();
    const total = within(monthly).getByRole("rowheader", { name: "Süren aylık ödemelerin toplamı" }).closest("tr")!;
    expect(total).toHaveTextContent("15.949,98 TL");
    const video = within(monthly).getByRole("link", { name: "Örnek Video" }).closest("tr")!;
    expect(within(video).getByRole("button", { name: "Yeniden bekle: Örnek Video" })).toBeInTheDocument();
    expect(screen.queryByText(/^Süren 4 aylık ödemeniz/)).not.toBeInTheDocument(); // the sentence is the simple view's
    const installments = screen.getByRole("table", { name: "Kalan taksitleri olan kart alışverişleri" });
    const left = within(installments).getByRole("rowheader", { name: "Kalan taksitlerin toplamı" });
    expect(left.closest("tr")).toHaveTextContent("2.000,00 TL");
  });

  it("shows the regular income and the installments left, each leading to its rows", async () => {
    renderScreen(<SubscriptionsPage />);
    const salary = await card("Düzenli gelirler", "Örnek İşveren A.Ş.");
    expect(within(salary).getByText("Beklenen 40.000,00 TL")).toBeInTheDocument();
    expect(within(salary).getByText("Son gelen 01.10.2026 · 41.500,00 TL")).toBeInTheDocument();
    const installments = screen.getByRole("region", { name: "Taksitli alışverişler" });
    expect(
      within(installments).getByText("Kalan taksitler toplam 2.000,00 TL; sonuncusu Şubat 2027'de bitiyor."),
    ).toBeInTheDocument();
    const purchase = within(installments).getByRole("link", { name: "Örnek Elektronik" });
    expect(purchase).toHaveAttribute("href", "/islemler?satir=fp-elektronik");
    expect(
      within(purchase.closest("li")!).getByText("Taksit 8/12 · kalan 4 taksit, 2.000,00 TL · bitiş Şubat 2027"),
    ).toBeInTheDocument();
  });

  it("ends a regular income that no longer comes: the month of its last coming, previewed, then saved", async () => {
    const user = userEvent.setup();
    const { previewed, saved } = serveRules(
      [
        "--- personal.yaml (önce)",
        "+++ personal.yaml (sonra)",
        "@@ -1,3 +1,4 @@",
        " _biten:",
        "   ORNEK VIDEO: 2026-09",
        "   Örnek Dergi: 2026-08",
        "+  Örnek İşveren A.Ş.: 2026-11",
      ].join("\n"),
    );
    renderScreen(<SubscriptionsPage />);
    const salary = await card("Düzenli gelirler", "Örnek İşveren A.Ş.");
    await user.click(within(salary).getByRole("button", { name: "Artık gelmiyor: Örnek İşveren A.Ş." }));
    const panel = await screen.findByRole("dialog", { name: "Örnek İşveren A.Ş." });
    expect(within(panel).getByRole("region", { name: "Artık gelmiyor" })).toHaveTextContent(
      "son ödeme henüz gelmediyse geleceği ayı",
    );
    const month = within(panel).getByLabelText("Son geliş ayı");
    expect(month).toHaveFocus();
    // From the last money that came on: an earlier month would leave money the income never meant.
    expect(within(month).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Kasım 2026",
      "Ekim 2026 (son gelen)",
    ]);
    expect(within(panel).queryByText(/düzenli gelir var/)).not.toBeInTheDocument();
    await user.selectOptions(month, "2026-11"); // the last salary is still to come
    await user.click(within(panel).getByRole("button", { name: "Önizle" }));
    expect(
      await within(panel).findByText(
        "Kaydedince Örnek İşveren A.Ş. için Kasım 2026'dan sonra gelir beklenmez; takvim ve öngörü onu saymaz.",
      ),
    ).toBeInTheDocument();
    expect(previewed).toEqual([{ action: "ended", merchant: "Örnek İşveren A.Ş.", month: "2026-11", note: "" }]);
    server.use(
      http.get("/api/rules/categories", () =>
        HttpResponse.json({
          ...CATEGORY_RULES,
          ended: [...CATEGORY_RULES.ended, { merchant: "Örnek İşveren A.Ş.", month: "2026-11", own: true }],
        }),
      ),
    );
    await user.click(within(panel).getByRole("button", { name: "Kaydet" }));
    expect(
      await within(panel).findByText("Kaydedildi: Örnek İşveren A.Ş. için Kasım 2026'dan sonra gelir beklenmiyor."),
    ).toBeInTheDocument();
    expect(saved).toEqual(previewed);
    expect(await within(panel).findByRole("region", { name: "Yeniden bekle" })).toHaveTextContent(
      "Kişisel kurallarınızda Örnek İşveren A.Ş. için son geliş ayı Kasım 2026. " +
        "Gelir yeniden bekleniyorsa bu satırı kaldırın.",
    );
  });

  it("shows an income the user ended as no longer coming, with nothing to expect, and offers it again", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    const ended = {
      ...SUBSCRIPTIONS.income[0]!,
      status: "cancelled" as const,
      next_day: null,
      note: "Kişisel kurallarınızda son geliş ayı Ekim 2026.",
    };
    server.use(
      http.get("/api/subscriptions", () => HttpResponse.json({ ...SUBSCRIPTIONS, income: [ended] })),
      http.get("/api/rules/categories", () =>
        HttpResponse.json({
          ...CATEGORY_RULES,
          ended: [...CATEGORY_RULES.ended, { merchant: "Örnek İşveren A.Ş.", month: "2026-10", own: true }],
        }),
      ),
    );
    renderScreen(<SubscriptionsPage />);
    const table = await screen.findByRole("table", { name: "Düzenli gelirler" });
    const row = within(table).getByRole("link", { name: "Örnek İşveren A.Ş." }).closest("tr")!;
    expect(within(row).getByText("Artık gelmiyor")).toBeInTheDocument();
    expect(within(row).getByText("Kişisel kurallarınızda son geliş ayı Ekim 2026.")).toBeInTheDocument();
    expect(within(row).queryByText("40.000,00 TL")).not.toBeInTheDocument(); // nothing to expect
    expect(await within(row).findByRole("button", { name: "Yeniden bekle: Örnek İşveren A.Ş." })).toBeInTheDocument();
  });

  it("declares a new salary as monthly: its month's parts said, the amount typed, previewed, saved", async () => {
    const user = userEvent.setup();
    const candidate = {
      payee: "Örnek Yazılım Ltd",
      account: { id: "garanti-7654321", label: "Garanti BBVA Vadesiz EUR 7654321" },
      month: "2026-10",
      parts: [
        { minor: 150000, currency: "EUR" },
        { minor: 50000, currency: "EUR" },
      ],
      amount: { minor: 200000, currency: "EUR" },
      day: 1,
    };
    server.use(
      http.get("/api/subscriptions", () => HttpResponse.json({ ...SUBSCRIPTIONS, income_candidates: [candidate] })),
    );
    const diff = "+_düzenli_gelir:\n+  Örnek Yazılım Ltd: {tutar: 2200, para: EUR, gün: 1}";
    const { previewed, saved } = serveRules(diff);
    renderScreen(<SubscriptionsPage />);
    const income = await screen.findByRole("region", { name: "Düzenli gelirler" });
    await user.click(within(income).getByRole("button", { name: "Her ay gelen bir gelir ekle…" }));
    const form = within(income).getByRole("region", { name: "Her ay gelen bir gelir" });
    expect(within(form).getByText("Örnek Yazılım Ltd")).toBeInTheDocument(); // the one payer to choose
    const amount = within(form).getByLabelText("Ayda gelen tutar (EUR)");
    expect(amount).toHaveValue("2.000");
    expect(amount).toHaveAccessibleDescription(/Ekim 2026 ayında gelen: 1\.500,00 EUR \+ 500,00 EUR/);
    expect(within(form).getByLabelText("Ayın kaçında gelir?")).toHaveValue(1);
    await user.clear(amount);
    await user.type(amount, "2.200");
    await user.click(within(form).getByRole("button", { name: "Önizle" }));
    expect(
      await within(form).findByText(
        "Kaydedince Örnek Yazılım Ltd her ay 2.200,00 EUR gelir diye sayılır, ayın 1. günü: takvim ve öngörü onu " +
          "ilk ödemesinden itibaren bekler.",
      ),
    ).toBeInTheDocument();
    const declared = { action: "income", merchant: "Örnek Yazılım Ltd", amount: "2200.00", currency: "EUR", day: 1 };
    expect(previewed).toEqual([declared]);
    await user.click(within(form).getByRole("button", { name: "Kaydet" }));
    expect(
      await within(income).findByText("Kaydedildi: Örnek Yazılım Ltd her ay 2.200,00 EUR gelir diye sayılıyor."),
    ).toBeInTheDocument();
    expect(saved).toEqual([declared]);
  });

  it("says an income is declared, at today's rate, and takes the declaration back", async () => {
    const user = userEvent.setup();
    const [salary] = SUBSCRIPTIONS.income;
    const declared = {
      ...salary!,
      declared: { amount: { minor: 200000, currency: "EUR" }, day: 1 },
      amount: { minor: 10200000, currency: "TRY" },
    };
    server.use(http.get("/api/subscriptions", () => HttpResponse.json({ ...SUBSCRIPTIONS, income: [declared] })));
    const { previewed, saved } = serveRules("-_düzenli_gelir:");
    renderScreen(<SubscriptionsPage />);
    const item = await card("Düzenli gelirler", declared.payee);
    expect(item).toHaveTextContent("Her ay 2.000,00 EUR, ayın 1. günü: sizin bildirdiğiniz");
    expect(item).toHaveTextContent("Beklenen 102.000,00 TL (bugünkü kurla)");
    await user.click(within(item).getByRole("button", { name: `Her ay gelir değil: ${declared.payee}` }));
    const form = within(item).getByRole("region", { name: "Her ay gelir değil" });
    await user.click(within(form).getByRole("button", { name: "Önizle" }));
    await user.click(await within(form).findByRole("button", { name: "Kaydet" }));
    expect(
      await screen.findByText(`Kaydedildi: ${declared.payee} artık her ay gelir diye yazılı değil.`),
    ).toBeInTheDocument();
    expect(previewed).toEqual([{ action: "not_income", merchant: declared.payee }]);
    expect(saved).toEqual(previewed);
  });

  it("says when no series is known yet, and where the documents are", async () => {
    server.use(
      http.get("/api/subscriptions", () =>
        HttpResponse.json({
          window: [],
          as_of: "2026-11-01",
          series: [],
          income: [],
          installments: [],
          income_candidates: [],
        }),
      ),
    );
    renderScreen(<SubscriptionsPage />);
    expect(await screen.findByText("Henüz düzenli ödeme bulunmadı")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Belgeleri göster" })).toHaveAttribute("href", "/belgeler");
  });

  it("offers to try again when the service fails, and shows the payments once it answers", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(
        "/api/subscriptions",
        () => HttpResponse.json({ code: "busy", title: "Başka bir işlem belgeleri işliyor." }, { status: 503 }),
        { once: true },
      ),
    );
    renderScreen(<SubscriptionsPage />);
    expect(await screen.findByText("Başka bir işlem belgeleri işliyor.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await screen.findByRole("region", { name: "Aylık ödemeler" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Başka bir işlem belgeleri işliyor.")).not.toBeInTheDocument());
  });
});
