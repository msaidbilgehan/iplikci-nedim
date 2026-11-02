import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { FX_RATES, HOLDINGS, server } from "../test/server";
import { renderScreen } from "../test/render";
import FxPage from "./FxPage";

afterEach(() => localStorage.clear());

function assetRow(name: string): HTMLElement {
  const table = screen.getByRole("table", { name: "Varlıklar ve borçlar, kendi birimlerinde ve TL karşılıklarıyla" });
  const row = within(table).getByText(name).closest("tr");
  if (!row) {
    throw new Error(`no row for ${name}`);
  }
  return row;
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

  it("shows the net worth in the other units, a unit without a rate said and never zero", async () => {
    renderScreen(<FxPage />);
    const summary = await screen.findByRole("region", { name: "Toplamlar" });
    expect(within(summary).getByText("6.520,55 EUR")).toBeInTheDocument();
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
    expect(within(gold).getByText("Kuru belgelerde yok")).toBeInTheDocument();
    expect(within(assetRow("TEB Bonus ••4321")).getByText("borç")).toBeInTheDocument();
  });

  it("adds the rate, the cost and the difference the rate made in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<FxPage />);
    await screen.findByRole("table", { name: /Varlıklar ve borçlar/ });
    const eur = assetRow("Garanti BBVA Döviz EUR");
    expect(within(eur).getByText("30.10.2026 belgesindeki kur")).toBeInTheDocument();
    expect(within(eur).getByText("70.000,00 TL")).toBeInTheDocument(); // the cost
    expect(within(eur).getByText("3.000,00 TL")).toBeInTheDocument(); // the difference
    expect(within(assetRow("TEB Vadesiz TL")).getAllByText("TL olduğu için yok")).toHaveLength(3); // no rate to know
    expect(screen.getByRole("table", { name: "Euro için belgelerin yazdığı bütün kurlar" })).toBeInTheDocument();
    expect(screen.getByText("35,8012 TL")).toBeInTheDocument(); // a rate keeps its digits
  });

  it("spreads the valued assets over currencies, a unit without a rate apart", async () => {
    renderScreen(<FxPage />);
    const chart = await screen.findByRole("list", { name: "Varlıkların para birimlerine dağılımı, TL değeriyle" });
    expect(within(chart).getByText("Türk lirası")).toBeInTheDocument();
    expect(within(chart).getByText("Euro")).toBeInTheDocument();
    expect(within(chart).queryByText("Gram altın")).not.toBeInTheDocument();
    expect(screen.getByText("TL değeri bilinmeyenler")).toBeInTheDocument();
    expect(screen.getByText("Değeri bilinen varlıklar 250.000,00 TL; en büyük pay Türk lirası, %71.")).toBeInTheDocument();
  });

  it("shows the documents' rates and names the units held without one", async () => {
    renderScreen(<FxPage />);
    const rates = await screen.findByRole("table", { name: "Belgelerin yazdığı en yeni kurlar" });
    expect(within(rates).getByText("36,50 TL")).toBeInTheDocument();
    expect(within(rates).getByText("Belgedeki kur")).toBeInTheDocument();
    expect(screen.getByText("Kuru belgelerde olmayanlar: Gram altın.")).toBeInTheDocument();
  });

  it("says when no document prints a rate yet", async () => {
    server.use(http.get("/api/fx", () => HttpResponse.json({ ...FX_RATES, currencies: [], missing: [] })));
    renderScreen(<FxPage />);
    expect(await screen.findByText("Belgelerde döviz kuru yok")).toBeInTheDocument();
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
