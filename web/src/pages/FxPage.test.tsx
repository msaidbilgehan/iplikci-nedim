import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { FX_INCOME, FX_RATES, FX_SPREAD, HOLDINGS, server } from "../test/server";
import { renderScreen } from "../test/render";
import FxPage from "./FxPage";

afterEach(() => localStorage.clear());

const RATES = "/doviz?bolum=kurlar";
const COST = "/doviz?bolum=kur-makasi";
const INCOME = "/doviz?bolum=doviz-geliri";

function rowOf(table: HTMLElement, text: string): HTMLElement {
  const row = within(table).getByText(text).closest("tr");
  if (!row) {
    throw new Error(`no row for ${text}`);
  }
  return row;
}

function assetRow(name: string): HTMLElement {
  return rowOf(
    screen.getByRole("table", { name: "Varlıklar ve borçlar, kendi birimlerinde ve TL karşılıklarıyla" }),
    name,
  );
}

describe("FxPage", () => {
  it("says the net worth and the largest currency's share in one sentence", async () => {
    renderScreen(<FxPage />);
    expect(
      await screen.findByText(
        "Net varlığınız 238.000,00 TL. Değeri bilinen varlıklarınızın %71'i Türk lirası cinsinden.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Hesapları aç/ })).toHaveAttribute("href", "/hesaplar");
  });

  it("splits the screen into the assets, the rates, the cost of the banks' rates and the foreign income", async () => {
    renderScreen(<FxPage />);
    const parts = await screen.findByRole("tablist", { name: "Döviz ekranının bölümleri" });
    expect(
      within(parts)
        .getAllByRole("tab")
        .map((tab) => tab.textContent),
    ).toEqual(["Varlıklar", "Kurlar", "Kur makası", "Döviz geliri"]);
    expect(within(parts).getByRole("tab", { name: "Varlıklar" })).toHaveAttribute("aria-selected", "true");
  });

  it("shows the net worth in the other units with the rate's source and day, a unit without a rate never zero", async () => {
    renderScreen(<FxPage />);
    const summary = await screen.findByRole("region", { name: "Toplamlar" });
    expect(within(summary).getByText("6.520,55 EUR")).toBeInTheDocument();
    expect(within(summary).getByText("TCMB 30.10.2026 döviz satış kuruyla")).toBeInTheDocument();
    expect(within(summary).getByText("belgelerde USD kuru yok")).toBeInTheDocument();
    expect(within(summary).getByText("gram altının TL fiyatı belgelerde yok")).toBeInTheDocument();
    expect(within(summary).getByText("Garanti BBVA Vadesiz TL:")).toBeInTheDocument(); // left out of the total
  });

  it("lists every asset and debt in its own unit with its TL value", async () => {
    renderScreen(<FxPage />);
    await screen.findByRole("table", { name: /Varlıklar ve borçlar/ });
    const eur = assetRow("Garanti BBVA Döviz EUR");
    expect(within(eur).getByText("2.000,00 EUR")).toBeInTheDocument();
    expect(within(eur).getByText("73.000,00 TL")).toBeInTheDocument();
    expect(within(eur).getByRole("link", { name: "Garanti BBVA Döviz EUR" })).toHaveAttribute(
      "href",
      "/hesaplar/garanti-eur",
    );
    const gold = assetRow("VakıfBank Altın");
    expect(within(gold).getByText("12,50 gr altın")).toBeInTheDocument();
    expect(within(gold).getByText("Kuru bilinmiyor")).toBeInTheDocument();
    expect(within(assetRow("TEB Bonus ••4321")).getByText("borç")).toBeInTheDocument();
  });

  it("adds the rate with its source and day, the cost and the difference the rate made in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<FxPage />);
    await screen.findByRole("table", { name: /Varlıklar ve borçlar/ });
    const eur = assetRow("Garanti BBVA Döviz EUR");
    expect(within(eur).getByText("36,5000 TL")).toBeInTheDocument();
    expect(within(eur).getByText("TCMB'nin 30.10.2026 kuru")).toBeInTheDocument();
    expect(within(eur).getByText("70.000,00 TL")).toBeInTheDocument(); // the cost
    expect(within(eur).getByText("3.000,00 TL")).toBeInTheDocument(); // the difference
    expect(within(assetRow("TEB Vadesiz TL")).getAllByText("TL olduğu için yok")).toHaveLength(3); // no rate to know
  });

  it("spreads the valued assets over currencies, a unit without a rate apart", async () => {
    renderScreen(<FxPage />);
    const chart = await screen.findByRole("list", { name: "Varlıkların para birimlerine dağılımı, TL değeriyle" });
    expect(within(chart).getByText("Türk lirası")).toBeInTheDocument();
    expect(within(chart).getByText("Euro")).toBeInTheDocument();
    expect(within(chart).queryByText("Gram altın")).not.toBeInTheDocument();
    expect(screen.getByText("TL değeri bilinmeyenler")).toBeInTheDocument();
    expect(
      screen.getByText("Değeri bilinen varlıklar 250.000,00 TL; en büyük pay Türk lirası, %71."),
    ).toBeInTheDocument();
  });

  it("leads to the documents while there is nothing to value", async () => {
    const worth = { ...HOLDINGS.worth, parts: [], left_out: [] };
    server.use(http.get("/api/holdings", () => HttpResponse.json({ ...HOLDINGS, worth, holdings: [], spread: [] })));
    renderScreen(<FxPage />);
    expect(await screen.findByText("Henüz bir varlık ya da borç yok")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Belgeleri aç/ })).toHaveAttribute("href", "/belgeler");
  });

  it("offers to try again when the holdings cannot be loaded", async () => {
    server.use(http.get("/api/holdings", () => HttpResponse.json({ detail: "bozuk" }, { status: 500 })));
    renderScreen(<FxPage />);
    expect(await screen.findByText("Yüklenemedi")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yeniden dene" })).toBeInTheDocument();
  });
});

describe("FxPage, the rates", () => {
  it("says where the values' rate comes from and its day, and leads to where the rates stand", async () => {
    renderScreen(<FxPage />, { path: RATES });
    expect(
      await screen.findByText("Değerler TCMB'nin 30.10.2026 kuruyla bulunur: 1 EUR = 36,5000 TL."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Kurların durumunu Sistem'de gör/ })).toHaveAttribute("href", "/sistem");
  });

  it("shows a provider's two sides, and a document's one rate across both", async () => {
    renderScreen(<FxPage />, { path: RATES });
    const table = await screen.findByRole("table", { name: "Para birimlerinin en yeni kurları" });
    const eur = rowOf(table, "Euro");
    expect(within(eur).getByText("36,5000 TL")).toBeInTheDocument(); // buying: what the assets are valued at
    expect(within(eur).getByText("36,5658 TL")).toBeInTheDocument(); // selling: what the debts are valued at
    expect(within(eur).getByText("30.10.2026")).toBeInTheDocument();
    expect(within(eur).getByText("TCMB")).toBeInTheDocument();
    const gbp = rowOf(table, "GBP");
    expect(within(gbp).getByText("41,20 TL")).toBeInTheDocument();
    expect(within(gbp).getByText("belgedeki işlemin kuru")).toBeInTheDocument();
    expect(within(gbp).getByText("Belgedeki kur")).toBeInTheDocument();
    expect(screen.getByText("Kuru bilinmeyenler: Gram altın.")).toBeInTheDocument();
  });

  it("draws the providers' recent days of a currency with its window and numbers, and as a table", async () => {
    const user = userEvent.setup();
    renderScreen(<FxPage />, { path: RATES });
    const chart = await screen.findByRole("figure", { name: "Euro kuru, son 90 gün" });
    expect(
      within(chart).getByText("1 EUR: 28.10.2026 günü 36,3100 TL, 30.10.2026 günü 36,5000 TL. Kaynak: TCMB."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("figure", { name: "GBP kuru, son 90 gün" })).not.toBeInTheDocument(); // no provider's
    await user.click(within(chart).getByRole("tab", { name: "Tablo" }));
    const table = within(chart).getByRole("table", { name: "Euro kuru, son 90 gün" });
    expect(within(rowOf(table, "29.10.2026")).getByText("36,4205 TL")).toBeInTheDocument();
  });

  it("lists the rates the documents print in the detailed view, each with its digits", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<FxPage />, { path: RATES });
    const printed = await screen.findByRole("table", { name: "Euro için belgelerin yazdığı bütün kurlar" });
    expect(within(printed).getByText("35,8012 TL")).toBeInTheDocument();
    expect(within(printed).getByText("36,50 TL")).toBeInTheDocument();
    expect(within(printed).queryByText("36,4205 TL")).not.toBeInTheDocument(); // a provider's: in the chart's table
  });

  it("says when there is no rate yet", async () => {
    server.use(http.get("/api/fx", () => HttpResponse.json({ ...FX_RATES, currencies: [], missing: [], note: "" })));
    renderScreen(<FxPage />, { path: RATES });
    expect(await screen.findByText("Henüz döviz kuru yok")).toBeInTheDocument();
    expect(screen.getByText(/Kurlar her iş günü TCMB'den alınır/)).toBeInTheDocument();
  });
});

describe("FxPage, the cost of the banks' rates", () => {
  it("says what the banks' rates cost against TCMB's in the last 12 months, with its window", async () => {
    renderScreen(<FxPage />, { path: COST });
    expect(
      await screen.findByText(
        "Son 12 ayda bankaların kurları, aynı günün TCMB kuruna göre size 1.250,00 TL fazlaya mal oldu (2 işlem).",
      ),
    ).toBeInTheDocument();
    const figures = screen.getByRole("region", { name: "Kur makasının toplamları" });
    expect(within(figures).getByRole("button", { name: "Toplam kur makası" })).toBeInTheDocument(); // the glossary's
    expect(within(figures).getByText("03.11.2025 – 02.11.2026, 2 işlem")).toBeInTheDocument();
    expect(within(figures).getByText("1.000,00 TL")).toBeInTheDocument(); // the trades
    expect(within(figures).getByText("250,00 TL")).toBeInTheDocument(); // the card purchases
  });

  it("lists the trades and the card purchases, each leading to its row", async () => {
    renderScreen(<FxPage />, { path: COST });
    const trades = await screen.findByRole("table", { name: /Kendi hesaplarınız arasındaki döviz alım-satımları/ });
    expect(within(trades).getByRole("link", { name: "DÖVİZ ALIŞ EUR" })).toHaveAttribute(
      "href",
      `/islemler?satir=${"f".repeat(16)}`,
    );
    expect(within(trades).getByText("Döviz alımı · TEB Vadesiz TL")).toBeInTheDocument();
    const purchases = screen.getByRole("table", { name: /Döviz cinsinden kart harcamaları/ });
    expect(within(rowOf(purchases, "Örnek Otel")).getByText("50,00 USD")).toBeInTheDocument();
    expect(within(purchases).getByText("TEB Bonus ••4321")).toBeInTheDocument(); // a purchase: no side to say
  });

  it("adds the bank's rate and TCMB's, with the bulletin's day when it is another, in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<FxPage />, { path: COST });
    const trades = await screen.findByRole("table", { name: /Kendi hesaplarınız arasındaki döviz alım-satımları/ });
    const row = rowOf(trades, "DÖVİZ ALIŞ EUR");
    expect(within(row).getByText("37,00 TL")).toBeInTheDocument();
    expect(within(row).getByText("36,0000 TL")).toBeInTheDocument();
    expect(within(row).getByText("10.10.2026 bülteni")).toBeInTheDocument(); // a weekend's trade
    expect(within(row).getByText("37.000,00 TL")).toBeInTheDocument(); // the TL it took
  });

  it("says when the banks' rates were the better ones", async () => {
    server.use(
      http.get("/api/fx/spread", () => HttpResponse.json({ ...FX_SPREAD, total: { minor: -40000, currency: "TRY" } })),
    );
    renderScreen(<FxPage />, { path: COST });
    expect(
      await screen.findByText(
        "Son 12 ayda bankaların kurları, aynı günün TCMB kuruna göre size 400,00 TL kazandırdı (2 işlem).",
      ),
    ).toBeInTheDocument();
  });

  it("says when no row shows a bank's rate", async () => {
    const note =
      "03.11.2025 – 02.11.2026 arasında bankanın kurunu gösteren bir döviz alım-satımı ya da yurt dışı kart harcaması yok.";
    server.use(
      http.get("/api/fx/spread", () =>
        HttpResponse.json({ ...FX_SPREAD, trades: [], purchases: [], left_out: 0, note }),
      ),
    );
    renderScreen(<FxPage />, { path: COST });
    expect(await screen.findByText("Kur makası hesaplanacak bir işlem yok")).toBeInTheDocument();
    expect(screen.getByText(note)).toBeInTheDocument();
  });
});

describe("FxPage, the foreign income", () => {
  it("says what came in and what it is worth now, and what a 5% move of the rate does over complete months", async () => {
    renderScreen(<FxPage />, { path: INCOME });
    const part = await screen.findByRole("region", { name: "Euro geliri" });
    expect(
      within(part).getByText("Son 12 ayda 2.000,00 EUR geldi; bugünkü kurla 73.000,00 TL eder."),
    ).toBeInTheDocument();
    expect(within(part).getByText("1 EUR = 36,5000 TL, TCMB'nin 30.10.2026 kuruyla")).toBeInTheDocument();
    expect(within(part).getByText("± 3.650,00 TL")).toBeInTheDocument();
    expect(within(part).getByText(/EUR\/TRY %5 düşerse aylık gelir 3\.650,00 TL azalır/)).toBeInTheDocument();
  });

  it("lists the income rows and the days the currency was changed into TL, each leading to its row", async () => {
    renderScreen(<FxPage />, { path: INCOME });
    const rows = await screen.findByRole("table", { name: "Son 12 ayda gelen Euro gelirleri, TL karşılıklarıyla" });
    expect(within(rows).getByRole("link", { name: "Örnek Müşteri B.V." })).toHaveAttribute(
      "href",
      `/islemler?satir=${"d".repeat(16)}`,
    );
    const sales = screen.getByRole("table", { name: "Son 12 ayda Euro bozdurmaları" });
    const sale = rowOf(sales, "TEB Vadesiz TL");
    expect(within(sale).getByText("36.400,00 TL")).toBeInTheDocument();
    expect(within(sale).getByText("36,40 TL")).toBeInTheDocument();
    expect(within(sale).getByRole("link", { name: "05.10.2026" })).toHaveAttribute(
      "href",
      `/islemler?satir=${"c".repeat(16)}`,
    );
  });

  it("says when no complete month carries the income, and when the currency was never changed", async () => {
    const [eur] = FX_INCOME.currencies;
    server.use(
      http.get("/api/fx/income", () =>
        HttpResponse.json({ ...FX_INCOME, currencies: [{ ...eur, sensitivity: null, sold: [] }] }),
      ),
    );
    renderScreen(<FxPage />, { path: INCOME });
    expect(
      await screen.findByText("Kur duyarlılığı için bu gelirin girdiği bir tam ay yok; içinde bulunulan ay sayılmaz."),
    ).toBeInTheDocument();
    expect(screen.getByText("Son 12 ayda Euro TL'ye çevrilmedi.")).toBeInTheDocument();
  });

  it("says when no income comes in a foreign currency", async () => {
    const note = "Döviz cinsinden gelen bir gelir yok: döviz hesaplarında gelir satırı görünmüyor.";
    server.use(http.get("/api/fx/income", () => HttpResponse.json({ ...FX_INCOME, currencies: [], note })));
    renderScreen(<FxPage />, { path: INCOME });
    expect(await screen.findByText("Döviz cinsinden bir gelir yok")).toBeInTheDocument();
    expect(screen.getByText(note)).toBeInTheDocument();
  });
});
