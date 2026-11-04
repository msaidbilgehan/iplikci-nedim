import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { renderScreen } from "../test/render";
import { DASHBOARD, server, tl } from "../test/server";
import DashboardPage from "./DashboardPage";

afterEach(() => localStorage.clear());

const card = (name: string) => screen.findByRole("region", { name });

/** The detailed view, chosen before the screen opens as the display panel would have saved it. */
function chooseDetailed() {
  localStorage.setItem("iplikci.view", "detailed");
}

describe("DashboardPage", () => {
  it("opens with four figures, each leading to its screen", async () => {
    chooseDetailed();
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

  it("says no document has come for the month yet instead of a zero spent", async () => {
    chooseDetailed();
    const pace = { ...DASHBOARD.month.pace, covered: 0, spent: { minor: 0, currency: "TRY" } };
    const month = { ...DASHBOARD.month, pace };
    server.use(http.get("/api/dashboard", () => HttpResponse.json({ ...DASHBOARD, month })));
    renderScreen(<DashboardPage />);
    const first = await screen.findByRole("region", { name: "Özet" });
    const tile = within(first).getByRole("link", { name: /^Bu ay harcanan/ });
    expect(tile).toHaveTextContent("Belge yok");
    expect(tile).toHaveTextContent("Kasım 2026 için ekstre ya da döküm henüz gelmedi");
    expect(tile).not.toHaveTextContent("0,00 TL");
  });

  it("tells the money in pictures in the simple view, without the detailed view's cards", async () => {
    renderScreen(<DashboardPage />);
    expect(await card("Ekim 2026: paranız ne durumda?")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Aylara göre gelen ve giden" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Ne yapmalısınız?" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Özet" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Veri tazeliği" })).not.toBeInTheDocument();
  });

  it("lets İplikçi Nedim have his say first, in the simple view and the detailed one", async () => {
    const nedim = "İplikçi Nedim'in paranız hakkındaki sözü";
    const { unmount } = renderScreen(<DashboardPage />);
    const said = await card(nedim);
    expect(within(said).getByText("Öngörüye göre hesaplarınızdan biri 18 gün sonra eksiye düşecek.")).toBeInTheDocument();
    expect(said.compareDocumentPosition(screen.getByRole("region", { name: "Ekim 2026: paranız ne durumda?" }))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    unmount();
    chooseDetailed();
    renderScreen(<DashboardPage />);
    expect(await card(nedim)).toBeInTheDocument();
  });

  it("leads each card to its screen once that screen is built", async () => {
    chooseDetailed();
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
    chooseDetailed();
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

  it("takes money no document tells yet off the net worth and says which account it came into", async () => {
    chooseDetailed();
    const untold = [{ account: { id: "garanti-tl", label: "Örnek Vadesiz TL" }, value: tl(500000), day: "2026-10-31" }];
    const net_worth = { ...DASHBOARD.net_worth, total: tl(750000), untold };
    server.use(http.get("/api/dashboard", () => HttpResponse.json({ ...DASHBOARD, net_worth })));
    renderScreen(<DashboardPage />);
    const worth = await card("Net varlık");
    expect(
      within(worth).getByText("Varlıklar 19.500,00 TL · Borçlar 7.000,00 TL · Belgede görünmeyen giriş −5.000,00 TL"),
    ).toBeInTheDocument();
    expect(
      within(worth).getByText(/^Örnek Vadesiz TL belgelerde görünen bakiyesinden 5\.000,00 TL fazla ödedi\./),
    ).toBeInTheDocument();
    const first = screen.getByRole("region", { name: "Özet" });
    const tile = within(first).getByRole("link", { name: /^Net varlık/ });
    expect(tile).toHaveTextContent("Belgede görünmeyen giriş 5.000,00 TL düşüldü");
  });

  it("says in the simple view's story that money no document tells yet was taken off the total", async () => {
    const untold = [{ account: { id: "garanti-tl", label: "Örnek Vadesiz TL" }, value: tl(500000), day: "2026-10-31" }];
    const net_worth = { ...DASHBOARD.net_worth, total: tl(750000), untold };
    server.use(http.get("/api/dashboard", () => HttpResponse.json({ ...DASHBOARD, net_worth })));
    renderScreen(<DashboardPage />);
    expect(
      await screen.findByText(/Belgede görünmeyen 5\.000,00 TL giriş de düşüldü\./),
    ).toHaveTextContent("kart borçları düşülünce: 7.500,00 TL.");
  });

  it("puts the month so far beside the typical month in the detailed view", async () => {
    chooseDetailed();
    renderScreen(<DashboardPage />);
    const month = await card("Bu ay ve tipik ay");
    expect(within(month).getByText("Kasım 2026'da bugüne kadar harcanan")).toBeInTheDocument();
    expect(within(month).getByText("4.200,00 TL")).toBeInTheDocument();
    expect(within(month).getByText("20.152,99 TL")).toBeInTheDocument();
  });

  it("lists the payments due within the week with their total", async () => {
    chooseDetailed();
    renderScreen(<DashboardPage />);
    const due = await card("Yaklaşan ödemeler");
    const row = within(within(due).getByRole("table")).getAllByText("Örnek Kart •1234")[0]!.closest("tr")!;
    expect(row).toHaveTextContent("20.11.2026");
    expect(row).toHaveTextContent("9.000,00 TL");
    expect(row).toHaveTextContent("asgari 1.800,00 TL");
    expect(within(due).getByText("Toplam 9.000,00 TL")).toBeInTheDocument();
  });

  it("lists the open alerts, each with its level in words and the way to what it is about", async () => {
    chooseDetailed();
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
    chooseDetailed();
    renderScreen(<DashboardPage />);
    const table = within(await card("Son 7 ayın kapanışı")).getByRole("table");
    const months = within(table).getAllByRole("row").slice(1);
    expect(months.map((month) => within(month).getAllByRole("cell")[0]?.textContent ?? "")).toEqual([
      "Mayıs 2026",
      "Haziran 2026",
      "Temmuz 2026",
      "Ağustos 2026",
      "Eylül 2026",
      "Ekim 2026",
      "Kasım 2026",
    ]);
    expect(within(table).getAllByText("Kapandı")).toHaveLength(5);
    expect(within(table).getByText("Belge eksik")).toBeInTheDocument();
    expect(within(table).getByText("Ay sürüyor")).toBeInTheDocument();
  });

  it("shows how far each account's documents reach and the months they skip", async () => {
    chooseDetailed();
    renderScreen(<DashboardPage />);
    const fresh = await card("Veri tazeliği");
    const cash = within(within(fresh).getByRole("table")).getByText("Örnek Vadesiz TL").closest("tr")!;
    expect(cash).toHaveTextContent("31.10.2026");
    expect(cash).toHaveTextContent("15 gün önce");
    expect(cash).toHaveTextContent("Temmuz 2026");
  });

  it("counts what there is to see to, by kind, in the detailed view", async () => {
    chooseDetailed();
    renderScreen(<DashboardPage />);
    const todo = await card("Yapılacaklar");
    expect(within(todo).getByText("3 iş bekliyor")).toBeInTheDocument();
    expect(within(todo).getByText("İşlenmeyen belge").closest("li")).toHaveTextContent("İşlenmeyen belge2");
  });

  it("gives the cards' tables in the detailed view, and the link beside each title", async () => {
    chooseDetailed();
    renderScreen(<DashboardPage />);
    const closing = await card("Son 7 ayın kapanışı");
    const july = within(within(closing).getByRole("table")).getByText("Temmuz 2026").closest("tr")!;
    expect(within(july).getByText("Belge eksik")).toBeInTheDocument();
    expect(within(july).getByText("−9.039,99 TL")).toBeInTheDocument();
    expect(within(july).getByText("Örnek Vadesiz TL: 1–4 Temmuz hesap dökümü eksik")).toBeInTheDocument();
    expect(within(july).getByText(/^gelir eksik olabilir: Örnek Vadesiz TL dökümü/)).toBeInTheDocument();
    const october = within(within(closing).getByRole("table")).getByText("Ekim 2026").closest("tr")!;
    expect(within(october).queryByText("hesap dökümlerindeki gelen para")).not.toBeInTheDocument(); // closed
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
    expect(screen.getByRole("region", { name: "İplikçi Nedim'in paranız hakkındaki sözü" })).toBeInTheDocument();
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
    expect(await screen.findByRole("region", { name: "Ekim 2026: paranız ne durumda?" })).toBeInTheDocument();
  });
});
