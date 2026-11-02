import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { renderScreen } from "../test/render";
import { monthEndDetail, server } from "../test/server";
import MonthPage from "./MonthPage";

afterEach(() => localStorage.clear());

const open = (month: string) => renderScreen(<MonthPage />, { path: `/ay-sonu/${month}`, route: "/ay-sonu/:ay" });
const card = (name: string) => screen.findByRole("region", { name });
const detailed = () => localStorage.setItem("iplikci.view", "detailed");

describe("MonthPage: the month and its accounts", () => {
  it("names the month with its status and the closing in a sentence", async () => {
    open("2026-10");
    expect(screen.getByRole("heading", { level: 1, name: "Ekim 2026" })).toBeInTheDocument();
    expect(await screen.findByText("Ekstre bekleniyor")).toBeInTheDocument();
    expect(
      screen.getByText("Ekstresi beklenen hesap var: Örnek Kart •1234 (19–31 Ekim ekstresi, kesim ~18.11)."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ay sonu" })).toHaveAttribute("href", "/ay-sonu");
  });

  it("tells each account's closing and what it waits for", async () => {
    open("2026-10");
    const accounts = await card("Hesapların kapanışı");
    expect(within(accounts).getByText("1 hesap ayı açık tutuyor.")).toBeInTheDocument();
    expect(within(accounts).getByRole("link", { name: "Örnek Kart •1234" })).toHaveAttribute(
      "href",
      "/hesaplar/teb-1234",
    );
    expect(within(accounts).getByText("Beklenen: 19–31 Ekim ekstresi, kesim ~18.11")).toBeInTheDocument();
    expect(within(accounts).getByText("Gecikti")).toBeInTheDocument();
    expect(within(accounts).getByText("Ayı bekletmez")).toBeInTheDocument(); // the brokerage account
    expect(within(accounts).getAllByText("Kapandı")).toHaveLength(2);
  });

  it("adds the days covered, the documents with their checks and the receipts in the detailed view", async () => {
    detailed();
    open("2026-10");
    const table = within(await card("Hesapların kapanışı")).getByRole("table");
    const card1234 = within(table).getAllByRole("row")[1]!;
    expect(within(card1234).getByText("18/31 gün belgeyle kapsandı")).toBeInTheDocument();
    expect(within(card1234).getByText("Kapsanmayan günler: 19.10.2026 – 31.10.2026")).toBeInTheDocument();
    expect(within(card1234).getByText("Sonraki kesim 18.11.2026")).toBeInTheDocument();
    expect(within(card1234).getByRole("link", { name: "Kart ekstresi, 01.10.2026 – 18.10.2026" })).toHaveAttribute(
      "href",
      `/belgeler/${"d".repeat(64)}`,
    );
    expect(within(card1234).getByText("Tutarlı")).toBeInTheDocument();
    expect(
      within(card1234).getByText(
        "Dekontlar: 3 eşleşti, 2 geçici, 1 ekstrede yok, 0 ekstresi gelmemiş günlerde",
      ),
    ).toBeInTheDocument();
  });

  it("says a month no account has documents for", async () => {
    server.use(
      http.get("/api/month-end/:month", () =>
        HttpResponse.json(
          monthEndDetail("2026-10", { accounts: [], count: 0, groups: [], categories: [], merchants: [] }),
        ),
      ),
    );
    open("2026-10");
    expect(await screen.findByText("Bu ay için hiçbir hesabın belgesi yok.")).toBeInTheDocument();
    expect(within(await card("Para nereye gitti")).getByText("Bu ay harcama yok.")).toBeInTheDocument();
  });
});

describe("MonthPage: the totals", () => {
  it("does not compare a month that is not closed", async () => {
    detailed();
    open("2026-10");
    const totals = await card("Toplamlar");
    expect(
      within(totals).getByText(
        "Ay kapanmadığı için önceki aylarla karşılaştırılmıyor: belgeleri gelmemiş günler eksik.",
      ),
    ).toBeInTheDocument();
    expect(within(totals).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Kalem", "Bu ay"]);
  });

  it("compares a closed month with the month before and the typical month of complete months", async () => {
    detailed();
    open("2026-09");
    const totals = await card("Toplamlar");
    expect(within(totals).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Kalem",
      "Bu ay",
      "Önceki ay",
      "Tipik ay",
    ]);
    expect(within(totals).getByText("Önceki aya göre gider 854,43 TL fazla.")).toBeInTheDocument();
    const typical = within(totals).getByText(/ortanca gideri: 20\.302,99 TL\.$/);
    expect(typical).toHaveTextContent("Tipik ay, bu aydan önceki 6 tam ayın ortanca gideri: 20.302,99 TL.");
    expect(within(typical).getByRole("button", { name: "tam ayın" })).toBeInTheDocument(); // the glossary's word
  });

  it("does not compare with a month before that is not closed", async () => {
    open("2026-08");
    const totals = await card("Toplamlar");
    expect(within(totals).getByText("Önceki ay kapanmadığı için onunla karşılaştırılmıyor.")).toBeInTheDocument();
    expect(within(totals).queryByText(/^Önceki aya göre/)).not.toBeInTheDocument();
  });

  it("says the income is not known, and why, when no list covers half the month", async () => {
    open("2026-11");
    const totals = await card("Toplamlar");
    expect(
      within(totals).getByText("Gider 840,50 TL; bu ay için hesap dökümü yok: gelir bilinmiyor."),
    ).toBeInTheDocument();
  });

  it("puts where the income comes from under the income", async () => {
    open("2026-10");
    const totals = await card("Toplamlar");
    const income = within(totals).getByText("Gelir").nextElementSibling;
    expect(income).toHaveTextContent("40.000,00 TLhesap dökümlerindeki gelen para");
  });

  it("draws the months since the first with spending, naming the highest and the lowest of the closed ones", async () => {
    open("2026-10");
    const trend = await card("Son 12 ayın gideri");
    // June has a statement to check, July misses a list's days and October waits for a statement: none is ranked.
    expect(
      await within(trend).findByText(
        "Ocak 2026 – Ekim 2026: kapanmış aylardan en yüksek 28.727,99 TL (Nisan 2026), en düşük 19.847,99 TL " +
          "(Ağustos 2026). Tipik ay, önceki 6 tam ayın ortancası: 20.302,99 TL.",
      ),
    ).toBeInTheDocument();
    expect(
      within(trend).getByText("Kapanmamış ayların gideri eksik olabilir: Haziran 2026, Temmuz 2026, Ekim 2026."),
    ).toBeInTheDocument();
  });
});

describe("MonthPage: where the money went and the rows", () => {
  it("shows the spending by group and the merchants it went to most, each leading to its rows", async () => {
    open("2026-10");
    const spending = await card("Para nereye gitti");
    expect(
      within(spending).getByText("8 harcama, toplam 20.327,99 TL; en büyük pay Ev: 16.050,00 TL."),
    ).toBeInTheDocument();
    expect(within(spending).getByRole("link", { name: "Ayın işlemlerini göster" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10-01&to=2026-10-31",
    );
    expect(within(spending).getByRole("link", { name: "Örnek Market" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10-01&to=2026-10-31&merchant=%C3%96rnek+Market",
    );
    expect(within(spending).getByRole("link", { name: "Ev" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10-01&to=2026-10-31&group=Ev",
    );
  });

  it("lists every level, category and merchant in the detailed view, each leading to its rows", async () => {
    detailed();
    open("2026-10");
    const spending = await card("Para nereye gitti");
    const levels = within(spending).getByRole("figure", { name: "Gerekliliğe göre gider" });
    expect(within(levels).getByRole("link", { name: "Gereksiz" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10-01&to=2026-10-31&necessity=unnecessary",
    );
    const categories = within(spending).getByRole("table", { name: "Kategoriler" });
    expect(within(categories).getByRole("link", { name: "Kira" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10-01&to=2026-10-31&category=Kira",
    );
    expect(within(spending).getByRole("table", { name: "İşyerleri" })).toBeInTheDocument();
  });

  it("tells the regular payments paid and those expected", async () => {
    open("2026-10");
    const regular = await card("Düzenli ödemeler");
    expect(within(regular).getByText("2 ödeme yapıldı, 1 ödeme bekleniyor.")).toBeInTheDocument();
    expect(within(regular).getByText("Bekleniyor: 22.10.2026")).toBeInTheDocument();
    expect(within(regular).getByText("Ödendi: 15.000,00 TL")).toBeInTheDocument();
  });

  it("opens a big purchase's detail at the side", async () => {
    const user = userEvent.setup();
    const view = open("2026-10");
    const big = await card("Büyük harcamalar");
    expect(within(big).getByText("1 büyük, tek seferlik harcama; toplam 15.000,00 TL.")).toBeInTheDocument();
    await user.click(within(big).getByRole("link", { name: "Örnek Ev Sahibi" }));
    await waitFor(() => expect(view.location()).toBe(`/ay-sonu/2026-10?satir=${"c1".repeat(10)}`));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("lists the provisional rows and the receipts no statement shows, saying what each are", async () => {
    open("2026-10");
    const provisional = await card("Geçici kayıtlar");
    expect(within(provisional).getByText(/^Yalnızca dekont ya da banka bildiriminde görünen/)).toBeInTheDocument();
    expect(within(provisional).getByRole("link", { name: "Örnek Kafe" })).toBeInTheDocument();
    const unmatched = await card("Ekstrede görünmeyen kanıtlar");
    expect(within(unmatched).getByRole("link", { name: "Örnek Kitapçı" })).toBeInTheDocument();
  });

  it("says when there are no such rows", async () => {
    server.use(
      http.get("/api/month-end/:month", () =>
        HttpResponse.json(monthEndDetail("2026-10", { big: [], provisional: [], unmatched: [] })),
      ),
    );
    open("2026-10");
    const big = await card("Büyük harcamalar");
    expect(within(big).getByText("Bu ay büyük, tek seferlik bir harcama yok.")).toBeInTheDocument();
    expect(within(await card("Geçici kayıtlar")).getByText("Geçici kayıt yok.")).toBeInTheDocument();
    const unmatched = await card("Ekstrede görünmeyen kanıtlar");
    expect(within(unmatched).getByText("Ekstrede görünmeyen kanıt yok.")).toBeInTheDocument();
  });
});

describe("MonthPage: moving between months", () => {
  it("leads to the month before and the month after", async () => {
    open("2026-10");
    const months = await screen.findByRole("navigation", { name: "Aylar arasında gezinme" });
    const before = within(months).getByRole("link", { name: "Önceki ay: Eylül 2026" });
    const after = within(months).getByRole("link", { name: "Sonraki ay: Kasım 2026" });
    expect(before).toHaveAttribute("href", "/ay-sonu/2026-09");
    expect(after).toHaveAttribute("href", "/ay-sonu/2026-11");
  });

  it("has no month after the one that runs now", async () => {
    open("2026-11");
    const months = await screen.findByRole("navigation", { name: "Aylar arasında gezinme" });
    expect(within(months).getAllByRole("link").map((link) => link.getAttribute("aria-label"))).toEqual([
      "Önceki ay: Ekim 2026",
    ]);
  });

  it("says an address that names no month has no page, and asks for nothing", async () => {
    let asked = 0;
    server.use(
      http.get("/api/month-end/:month", () => {
        asked += 1;
        return HttpResponse.json(monthEndDetail());
      }),
    );
    open("2026-13");
    expect(await screen.findByText("Bu adreste bir ay yok")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ayları göster" })).toHaveAttribute("href", "/ay-sonu");
    expect(asked).toBe(0);
  });

  it("says a month to come has not started", async () => {
    open("2027-01");
    expect(await screen.findByText("Ocak 2027 henüz başlamadı")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Toplamlar" })).not.toBeInTheDocument();
  });

  it("says the month could not be read and asks again", async () => {
    let asked = 0;
    server.use(
      http.get("/api/month-end/:month", () => {
        asked += 1;
        return asked === 1
          ? HttpResponse.json({ code: "busy", title: "Analiz sürüyor; birazdan yeniden deneyin." }, { status: 503 })
          : HttpResponse.json(monthEndDetail());
      }),
    );
    const user = userEvent.setup();
    open("2026-10");
    expect(await screen.findByText("Analiz sürüyor; birazdan yeniden deneyin.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await card("Toplamlar")).toBeInTheDocument();
  });
});
