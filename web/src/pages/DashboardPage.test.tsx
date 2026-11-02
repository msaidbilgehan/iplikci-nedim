import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { renderScreen } from "../test/render";
import { DASHBOARD, server } from "../test/server";
import DashboardPage from "./DashboardPage";

afterEach(() => localStorage.clear());

const card = (name: string) => screen.findByRole("region", { name });

describe("DashboardPage", () => {
  it("opens with four figures, each leading to its screen", async () => {
    renderScreen(<DashboardPage />);
    expect(await screen.findByText("Bugün 15.11.2026; en yeni ekstre 31.10.2026 tarihine kadar.")).toBeInTheDocument();
    const first = screen.getByRole("region", { name: "Özet" });
    const tile = (name: RegExp) => within(first).getByRole("link", { name });
    expect(tile(/^Net varlık/)).toHaveAttribute("href", "/hesaplar");
    expect(tile(/^Net varlık/)).toHaveTextContent("12.500,00 TL");
    expect(tile(/^Net varlık/)).toHaveTextContent("Varlık 19.500,00 TL · Borç 7.000,00 TL");
    expect(tile(/^Net varlık/)).toHaveTextContent("1 hesap toplama girmedi");
    expect(tile(/^Net varlık/)).toHaveTextContent("Bir kısmı geçici kayıtlardan"); // not certain, said in words
    expect(tile(/^Bu ay harcanan/)).toHaveAttribute("href", "/ay-sonu/2026-11");
    expect(tile(/^Bu ay harcanan/)).toHaveTextContent("4.200,00 TL");
    expect(tile(/^Bu ay harcanan/)).toHaveTextContent("Kasım 2026 · tipik ay 20.152,99 TL");
    expect(tile(/^7 gün içinde ödenecek/)).toHaveAttribute("href", "/takvim");
    expect(tile(/^7 gün içinde ödenecek/)).toHaveTextContent("9.000,00 TL");
    expect(tile(/^7 gün içinde ödenecek/)).toHaveTextContent("1 ödeme; ilki 20.11.2026: Örnek Kart •1234");
    expect(tile(/^Yapılacaklar/)).toHaveAttribute("href", "/yapilacaklar");
    expect(tile(/^Yapılacaklar/)).toHaveTextContent("3 iş bekliyor");
  });

  it("says what each card shows in the service's words, and leaves out what the first row already says", async () => {
    renderScreen(<DashboardPage />);
    const says: Array<[string, string]> = [
      ["Açık uyarılar", DASHBOARD.alerts.say],
      ["Son 7 ayın kapanışı", DASHBOARD.closing.say],
      ["Veri tazeliği", DASHBOARD.freshness.say],
    ];
    for (const [name, say] of says) {
      expect(within(await card(name)).getByText(say)).toBeInTheDocument();
    }
    expect(screen.queryByText(DASHBOARD.due.say)).not.toBeInTheDocument();
    // The figures of the first row have no card of their own in the simple view.
    expect(screen.queryByRole("region", { name: "Net varlık" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Bu ay ve tipik ay" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Yapılacaklar" })).not.toBeInTheDocument();
  });

  it("leads each card to its screen once that screen is built", async () => {
    renderScreen(<DashboardPage />);
    expect(within(await card("Yaklaşan ödemeler")).getByRole("link", { name: "Takvimi aç" })).toHaveAttribute(
      "href",
      "/takvim",
    );
    expect(within(await card("Açık uyarılar")).getByRole("link", { name: "Bildirimleri aç" })).toHaveAttribute(
      "href",
      "/bildirimler",
    );
    expect(within(await card("Veri tazeliği")).getByRole("link", { name: "Hesaplara bak" })).toHaveAttribute(
      "href",
      "/hesaplar",
    );
    const closing = await card("Son 7 ayın kapanışı");
    expect(within(closing).getByRole("link", { name: "Ay sonunu aç" })).toHaveAttribute("href", "/ay-sonu/2026-07");
    expect(within(closing).getByRole("link", { name: "Ekim 2026" })).toHaveAttribute("href", "/ay-sonu/2026-10");
  });

  it("shows the net worth in TL and in other units in the detailed view, a missing rate as not known", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<DashboardPage />);
    const worth = await card("Net varlık");
    expect(within(worth).getAllByText("12.500,00 TL").length).toBeGreaterThan(0);
    expect(within(worth).getAllByRole("button", { name: "geçici" }).length).toBeGreaterThan(0);
    expect(within(worth).getByText("Varlıklar 19.500,00 TL · Borçlar 7.000,00 TL")).toBeInTheDocument();
    const units = within(worth).getByRole("heading", { name: "Diğer birimlerle" }).nextElementSibling as HTMLElement;
    expect(within(units).getByText("337,84 EUR")).toBeInTheDocument();
    expect(within(units).getByText("31.10.2026 belgesindeki kurla")).toBeInTheDocument();
    expect(within(units).getByText("belgelerde USD kuru yok")).toBeInTheDocument();
    expect(within(units).getByText("Gram altın")).toBeInTheDocument();
    expect(within(units).getByText("gram altının TL fiyatı belgelerde yok")).toBeInTheDocument();
    expect(within(units).queryByText(/^0,00/)).not.toBeInTheDocument(); // never a zero for what is not known
    expect(within(worth).getByText("bakiyesi hiçbir belgede yazmıyor")).toBeInTheDocument();
  });

  it("puts the month so far beside the typical month in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<DashboardPage />);
    const month = await card("Bu ay ve tipik ay");
    expect(within(month).getByText("Kasım 2026'da bugüne kadar harcanan")).toBeInTheDocument();
    expect(within(month).getByText("4.200,00 TL")).toBeInTheDocument();
    expect(within(month).getByText("20.152,99 TL")).toBeInTheDocument();
  });

  it("lists the payments due within the week with their total", async () => {
    renderScreen(<DashboardPage />);
    const due = await card("Yaklaşan ödemeler");
    expect(within(due).getByRole("heading", { name: "Cuma, 20.11.2026" })).toBeInTheDocument();
    expect(within(due).getByText("−9.000,00 TL")).toBeInTheDocument();
    expect(within(due).getByText("asgari 1.800,00 TL")).toBeInTheDocument();
    expect(within(due).getByText("Toplam 9.000,00 TL")).toBeInTheDocument();
  });

  it("lists the open alerts, each with its level in words and the way to what it is about", async () => {
    renderScreen(<DashboardPage />);
    const alerts = await card("Açık uyarılar");
    const items = within(alerts).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Kritik: Hesap eksiye düşecek");
    expect(within(items[0]!).getByRole("link", { name: "Öngörüyü aç: Hesap eksiye düşecek" })).toHaveAttribute(
      "href",
      "/takvim?hesap=teb-123456789",
    );
    expect(items[1]).toHaveTextContent("Uyarı: Okunamayan belgeler");
    expect(within(items[1]!).getByText("2 kayıt")).toBeInTheDocument();
    expect(within(items[1]!).getByRole("link", { name: "Belgeleri göster: Okunamayan belgeler" })).toHaveAttribute(
      "href",
      "/belgeler?status=unreadable",
    );
  });

  it("shows the last seven months' closing, each status in words", async () => {
    renderScreen(<DashboardPage />);
    const months = within(await card("Son 7 ayın kapanışı")).getAllByRole("listitem");
    expect(months.map((month) => month.textContent)).toEqual([
      "Mayıs 2026: Kapandı",
      "Haziran 2026: Kapandı",
      "Temmuz 2026: Belge eksik",
      "Ağustos 2026: Kapandı",
      "Eylül 2026: Kapandı",
      "Ekim 2026: Kapandı",
      "Kasım 2026: Ay sürüyor",
    ]);
  });

  it("shows how far each account's documents reach and the months they skip", async () => {
    renderScreen(<DashboardPage />);
    const fresh = await card("Veri tazeliği");
    const cash = within(fresh).getByText("Örnek Vadesiz TL").closest("li")!;
    expect(within(cash).getByText("son döküm 31.10.2026 · 15 gün önce")).toBeInTheDocument();
    expect(within(cash).getByText("Eksik aylar: Temmuz 2026")).toBeInTheDocument();
  });

  it("counts what there is to see to, by kind, in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<DashboardPage />);
    const todo = await card("Yapılacaklar");
    expect(within(todo).getByText("3 iş bekliyor")).toBeInTheDocument();
    expect(within(todo).getByText("İşlenmeyen belge").closest("li")).toHaveTextContent("İşlenmeyen belge2");
  });

  it("gives the cards' tables in the detailed view, and the link beside each title", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<DashboardPage />);
    const closing = await card("Son 7 ayın kapanışı");
    const july = within(within(closing).getByRole("table")).getByText("Temmuz 2026").closest("tr")!;
    expect(within(july).getByText("Belge eksik")).toBeInTheDocument();
    expect(within(july).getByText("−9.039,99 TL")).toBeInTheDocument();
    expect(within(july).getByText("Örnek Vadesiz TL: 1–4 Temmuz hesap dökümü eksik")).toBeInTheDocument();
    const november = within(within(closing).getByRole("table")).getByText("Kasım 2026").closest("tr")!;
    expect(within(november).getAllByText("bilinmiyor")).toHaveLength(2); // its income is not known yet
    const worth = await card("Net varlık");
    const parts = within(worth).getByRole("table", { name: "Net varlığın hesaplara dağılımı" });
    expect(within(parts).getByText("Örnek Kart •1234").closest("tr")).toHaveTextContent("−7.000,00 TL");
    expect(within(await card("Yaklaşan ödemeler")).getByRole("link", { name: "Takvimi aç" })).toBeInTheDocument();
    expect(within(await card("Açık uyarılar")).getByRole("link", { name: "Bildirimleri aç" })).toBeInTheDocument();
    expect(screen.queryByText(DASHBOARD.month.say)).not.toBeInTheDocument();
  });

  it("says when no document came yet, and still shows what asks for attention", async () => {
    server.use(
      http.get("/api/dashboard", () =>
        HttpResponse.json({
          ...DASHBOARD,
          net_worth: { ...DASHBOARD.net_worth, parts: [], left_out: [] },
          freshness: { ...DASHBOARD.freshness, accounts: [] },
        }),
      ),
    );
    renderScreen(<DashboardPage />);
    expect(await screen.findByText("Henüz belge yok")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Belge ekle" })).toHaveAttribute("href", "/belgeler");
    expect(await card("Açık uyarılar")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Net varlık" })).not.toBeInTheDocument();
  });

  it("offers to try again when the dashboard could not be read", async () => {
    let failing = true;
    server.use(
      http.get("/api/dashboard", () =>
        failing
          ? HttpResponse.json({ code: "busy", title: "Belgeler şu an okunuyor." }, { status: 503 })
          : HttpResponse.json(DASHBOARD),
      ),
    );
    const user = userEvent.setup();
    renderScreen(<DashboardPage />);
    expect(await screen.findByText("Belgeler şu an okunuyor.")).toBeInTheDocument();
    failing = false;
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await screen.findByRole("region", { name: "Özet" })).toBeInTheDocument();
  });
});
