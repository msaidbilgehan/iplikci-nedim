import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import type { MonthEndList } from "../api/types";
import { renderScreen } from "../test/render";
import { EXPORTS, MONTH_ENDS, server } from "../test/server";
import MonthEndPage from "./MonthEndPage";

afterEach(() => localStorage.clear());

const open = () => renderScreen(<MonthEndPage />, { path: "/ay-sonu" });
const card = (name: string) => screen.findByRole("region", { name });
const serve = (list: MonthEndList) => server.use(http.get("/api/month-end", () => HttpResponse.json(list)));

describe("MonthEndPage", () => {
  it("waits for the months, then lists each with its status and the closing in a sentence", async () => {
    open();
    expect(screen.getByRole("status", { name: "Yükleniyor…" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "Ay sonu" })).toBeInTheDocument();
    const months = await card("Aylar");
    const items = within(within(months).getByRole("list")).getAllByRole("listitem");
    expect(items).toHaveLength(6);
    const july = items[4]!;
    expect(within(july).getByRole("link", { name: "Temmuz 2026" })).toHaveAttribute("href", "/ay-sonu/2026-07");
    expect(within(july).getByText("Belge eksik")).toBeInTheDocument();
    expect(
      within(july).getByText("Kapanması için eksik belge var: Örnek Vadesiz TL (1–4 Temmuz hesap dökümü eksik)."),
    ).toBeInTheDocument();
    expect(within(items[0]!).getByText("Gider 840,50 TL · Gelir bilinmiyor · Kalan bilinmiyor")).toBeInTheDocument();
  });

  it("says a past month not closed is reckoned from the documents it has, and may change", async () => {
    open();
    const items = within(within(await card("Aylar")).getByRole("list")).getAllByRole("listitem");
    const partial = /^Ay kapanmadı: rakamlar eksik ya da kontrol bekleyen belgelerle hesaplandı/;
    expect(within(items[4]!).getByText(partial)).toBeInTheDocument(); // July misses a list's first days
    expect(within(items[2]!).queryByText(partial)).not.toBeInTheDocument(); // September closed
    expect(within(items[0]!).queryByText(partial)).not.toBeInTheDocument(); // November runs: its own words say so
  });

  it("says how many months are closed and leads to the newest one that is not", async () => {
    open();
    const months = await card("Aylar");
    expect(within(months).getByText("2 ay kapandı; 3 ay belge ya da kontrol bekliyor.")).toBeInTheDocument();
    expect(within(months).getByRole("link", { name: "Ekim 2026 sayfasını aç" })).toHaveAttribute(
      "href",
      "/ay-sonu/2026-10",
    );
  });

  it("leads to the running month once every month before it is closed", async () => {
    const closed = MONTH_ENDS.months.map((m) => (m.status === "running" ? m : { ...m, status: "closed" as const }));
    serve({ ...MONTH_ENDS, months: closed });
    open();
    const months = await card("Aylar");
    expect(within(months).getByText("Geçmiş ayların hepsi kapandı; Kasım 2026 sürüyor.")).toBeInTheDocument();
    expect(within(months).getByRole("link", { name: "Kasım 2026 sayfasını aç" })).toHaveAttribute(
      "href",
      "/ay-sonu/2026-11",
    );
  });

  it("explains the five statuses, each with its icon and its name", async () => {
    open();
    const statuses = await card("Durumlar");
    const names = within(statuses).getAllByRole("term").map((term) => term.textContent);
    expect(names).toEqual(["Ay sürüyor", "Ekstre bekleniyor", "Belge eksik", "Kontrol gerekli", "Kapandı"]);
    expect(within(statuses).getByText("Ayın bazı günlerini kapsayan belge yok.")).toBeInTheDocument();
  });

  it("adds each month's totals in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    open();
    const table = within(await card("Aylar")).getByRole("table", { name: "Ayların kapanış durumu ve toplamları" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(7);
    const october = within(rows[2]!).getAllByRole("cell").map((cell) => cell.textContent);
    expect(october.slice(2)).toEqual([
      "20.327,99 TL",
      "40.000,00 TLGelir: hesap dökümlerindeki gelen para",
      "19.672,01 TL",
      "2",
      "1",
    ]);
    expect(within(table).getByRole("link", { name: "Haziran 2026" })).toHaveAttribute("href", "/ay-sonu/2026-06");
  });

  it("offers the months' pages to download once the analysis wrote them", async () => {
    server.use(
      http.get("/api/exports", () =>
        HttpResponse.json([
          ...EXPORTS,
          { kind: "month_end", name: "iplikci-ay-sonu.zip", size: 90_000, made_at: "2026-11-15T06:00:00+00:00" },
        ]),
      ),
    );
    open();
    const pages = await card("Ay sayfaları");
    expect(await within(pages).findByRole("link", { name: "Ay sayfalarını indir" })).toHaveAttribute(
      "href",
      "/api/exports/month_end",
    );
    expect(within(pages).getByText(/^Ayların betiksiz sayfaları tek bir zip dosyasında; 15\.11\.2026/)).toBeVisible();
  });

  it("says the months' pages are not written yet", async () => {
    open();
    const pages = await card("Ay sayfaları");
    expect(
      await within(pages).findByText("Ay sayfaları henüz yazılmadı; servis ilk analizini yapınca yazar."),
    ).toBeInTheDocument();
    expect(within(pages).queryByRole("link")).not.toBeInTheDocument();
  });

  it("says there is no month to close yet", async () => {
    serve({ ...MONTH_ENDS, months: [] });
    open();
    expect(await screen.findByText("Henüz kapanacak bir ay yok")).toBeInTheDocument();
  });

  it("says the months could not be read and asks again", async () => {
    let asked = 0;
    server.use(
      http.get("/api/month-end", () => {
        asked += 1;
        return asked === 1
          ? HttpResponse.json({ code: "busy", title: "Analiz sürüyor; birazdan yeniden deneyin." }, { status: 503 })
          : HttpResponse.json(MONTH_ENDS);
      }),
    );
    const user = userEvent.setup();
    open();
    expect(await screen.findByText("Analiz sürüyor; birazdan yeniden deneyin.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await card("Aylar")).toBeInTheDocument();
  });
});
