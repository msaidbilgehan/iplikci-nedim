import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import type { CategoryRules, Spending, TransactionPage } from "../api/types";
import { CATEGORY_RULES, category, INSIGHTS, server, SPENDING, tl, TRANSACTIONS } from "../test/server";
import { renderScreen } from "../test/render";
import InsightsPage from "./InsightsPage";

afterEach(() => localStorage.clear());

const detailed = () => localStorage.setItem("iplikci.view", "detailed");
const SPENT = "kind=interest_fee&kind=purchase&kind=refund"; // the spending's kinds, in the service's order
const KINDS = "kind=purchase&kind=refund&kind=interest_fee"; // as the screen writes them out
const REGULAR_HINT = "Dönem süzgecinden bağımsızdır, diğer süzgeçlere uyar; durumlar bugüne göredir.";
const RENT_ONLY = "Bu süzgeçlerle süren 1 aylık ödeme ayda 15.000,00 TL tutuyor.";
// The rules with the rent's category in a group of its own.
const GROUPED: CategoryRules = {
  ...CATEGORY_RULES,
  categories: [...CATEGORY_RULES.categories, category("Kira", "Ev", 4, { necessity: "required", regular: true })],
};

/** The spending as the service sends it for every request, with what the requests asked. */
function serveSpending(found: Spending | (() => Response)): string[] {
  const asked: string[] = [];
  server.use(
    http.get("/api/spending", ({ request }) => {
      asked.push(new URL(request.url).search);
      return typeof found === "function" ? found() : HttpResponse.json(found);
    }),
  );
  return asked;
}

async function card(name: string): Promise<HTMLElement> {
  return screen.findByRole("region", { name });
}

describe("InsightsPage", () => {
  it("sums up the period's spending, its whole months' average and the last month against those before", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    const tiles = await card("Özet");
    expect(within(tiles).getByText("110.700,00 TL")).toBeInTheDocument();
    expect(within(tiles).getByText("Mayıs 2026 – Ekim 2026 · 60 işlem")).toBeInTheDocument();
    expect(within(tiles).getByText("20.240,00 TL")).toBeInTheDocument();
    expect(within(tiles).getByText("5 tam ay üzerinden · eksik 1 ay dahil değil")).toBeInTheDocument();
    expect(within(tiles).getByText("hesap hareketi olan 5 tam ay · giderler gelirin %51 kadarı")).toBeInTheDocument();
    expect(within(tiles).getByText("önceki 3 tam ayın ortalamasından %6 fazla")).toBeInTheDocument();
  });

  it("opens on the summary and keeps each part one tab away, the tab in the address", async () => {
    const { location } = renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    const parts = await screen.findByRole("tablist", { name: "Değerlendirmenin bölümleri" });
    expect(within(parts).getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Özet",
      "Harcamalar",
      "Gelir, varlık ve borç",
      "Önümüzdeki aylar",
      "İşlemler ve veriler",
    ]);
    await waitFor(() => expect(screen.getByRole("region", { name: "Değerlendirme ve strateji" })).toBeInTheDocument());
    expect(screen.queryByRole("region", { name: "Aylık giderler" })).not.toBeInTheDocument();
    await userEvent.click(within(parts).getByRole("tab", { name: "Harcamalar" }));
    expect(location()).toBe("/degerlendirme?bolum=harcamalar");
    expect(await screen.findByRole("region", { name: "Aylık giderler" })).toBeInTheDocument();
  });

  it("asks the service with the address's filters, the İşlemler screen's own", async () => {
    const asked = serveSpending(SPENDING);
    renderScreen(<InsightsPage />, { path: "/degerlendirme?account=teb-1234&necessity=required&q=market" });
    await card("Özet");
    expect(asked).toEqual(["?account=teb-1234&necessity=required&q=market"]);
  });

  it("writes a preset's days into the address and reads the address's period as its preset", async () => {
    const { location } = renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    const presets = await screen.findByRole("group", { name: "Dönem" });
    expect(within(presets).getByRole("button", { name: "Son 12 ay" })).toHaveAttribute("aria-pressed", "true");
    // The data begins in the last month's year: the year before has nothing.
    expect(within(presets).getByRole("button", { name: "Geçen yıl" })).toBeDisabled();
    await userEvent.click(within(presets).getByRole("button", { name: "Son 3 ay" }));
    expect(location()).toBe("/degerlendirme?from=2026-08-01&to=2026-10-31");
    expect(within(presets).getByRole("button", { name: "Son 3 ay" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(within(presets).getByRole("button", { name: "Son 12 ay" }));
    expect(location()).toBe("/degerlendirme");
  });

  it("adds a kind the spending leaves out, with its total under the same filters", async () => {
    server.use(
      http.get("/api/transactions", ({ request }) => {
        const kind = new URL(request.url).searchParams.get("kind");
        const out = kind === "p2p_transfer" ? tl(50000) : tl(0);
        const page: TransactionPage = { ...TRANSACTIONS, totals: { ...TRANSACTIONS.totals, money_out: out } };
        return HttpResponse.json(page);
      }),
    );
    const { location } = renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    const add = await screen.findByRole("button", { name: "Kişilere gönderilen para: 500,00 TL, toplama ekle" });
    expect(add).toHaveTextContent("+ Kişilere gönderilen para: 500,00 TL");
    expect(screen.queryByRole("button", { name: /^Nakit avans/ })).not.toBeInTheDocument(); // nothing of it
    await userEvent.click(add);
    expect(location()).toBe("/degerlendirme?kind=purchase&kind=refund&kind=interest_fee&kind=p2p_transfer");
    expect(await within(await card("Özet")).findByText("Toplam (seçili işlem türleri)")).toBeInTheDocument();
    expect(screen.queryByText("Toplama dahil değil:")).not.toBeInTheDocument();
  });

  it("asks what the spending leaves out beside the spending, so that its line comes with the tiles", async () => {
    let answer: () => void = () => undefined;
    const answered = new Promise<void>((resolve) => {
      answer = resolve;
    });
    const kinds: string[] = [];
    server.use(
      http.get("/api/spending", async () => {
        await answered;
        return HttpResponse.json(SPENDING);
      }),
      http.get("/api/transactions", ({ request }) => {
        kinds.push(new URL(request.url).searchParams.get("kind") ?? "");
        return HttpResponse.json(TRANSACTIONS);
      }),
    );
    renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    const leftOut = ["card_payment_no_statement", "cash_advance", "loan_principal", "p2p_transfer"];
    await waitFor(() => expect([...kinds].sort()).toEqual(leftOut)); // the spending not answered yet
    answer();
    expect(await card("Özet")).toBeInTheDocument();
  });

  it("states the interpretation's window and the months it left out", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    expect(
      await screen.findByText(
        "5 tam ay (Mayıs 2026 – Ekim 2026) üzerinden; bakiyeler 31.10.2026 itibarıyla. Süzgeçlerden bağımsızdır. " +
          "Tam olmayan aylar (Temmuz 2026) ortalamalara katılmadı.",
      ),
    ).toBeInTheDocument();
  });

  it("lists the highlights with their tone and their rows, and the steps with what a priced one frees", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    const highlights = await screen.findByRole("region", { name: "Öne çıkanlar" });
    const found = screen.getByRole("region", { name: "Değerlendirme ve strateji" });
    expect(within(highlights).getByText("Dikkat")).toBeInTheDocument();
    expect(within(highlights).getByRole("link", { name: "İşlemleri göster: Faiz ve banka ücretleri" })).toHaveAttribute(
      "href",
      "/islemler?kind=interest_fee",
    );
    // A highlight about the whole picture leads to this very screen: no link.
    expect(within(highlights).getAllByRole("link")).toHaveLength(1);
    const steps = within(found).getByRole("region", { name: "Önerilen adımlar" });
    expect(within(steps).getByText("ayda ~99,99 TL")).toBeInTheDocument();
    expect(within(steps).getAllByRole("listitem")).toHaveLength(2);
    expect(within(steps).getAllByText(/^ayda ~/)).toHaveLength(1); // the unpriced step says no amount
  });

  it("says in the simple view what the budget's plan leaves at the month's end", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    expect(
      await screen.findByText(
        "Bugünkü harcamanızla tipik bir ayın sonunda 21.184,00 TL kalıyor; önerilen bütçeyle 21.200,00 TL kalır.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the budget's lines, each one's share of the income and the plan's difference", async () => {
    detailed();
    renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    const table = await screen.findByRole("table", { name: "Aylık bütçe: bugünkü tipik ay ve önerilen ay" });
    const fees = within(table).getByRole("row", { name: /^Gereksiz harcamalar \(faiz, banka ücretleri…\)/ });
    expect(within(fees).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "16,00 TL",
      "%1'den az", // 16 TL of 40.000 TL: never "%0" for what is not nothing
      "0,00 TL",
      "−16,00 TL", // the plan spends that much less
      "öneri: borcu tam ödeyerek sıfırlayın",
    ]);
    const left = within(table).getByRole("row", { name: /^Ay sonunda kalan/ });
    expect(left.closest("tfoot")).not.toBeNull();
    expect(left).toHaveTextContent("+16,00 TL");
  });

  it("marks the partial month in the monthly heat table, whose average counts the whole months alone", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const monthly = await card("Aylık giderler");
    // July misses a document: the month-end closing says so, and the legend that its pale months have not closed.
    expect(await within(monthly).findByText("Soluk sütunlar: henüz kapanmamış aylar, ortalamaya girmez")).toBeInTheDocument();
    await userEvent.click(within(monthly).getByRole("tab", { name: "Tablo" }));
    const table = within(monthly).getByRole("table", { name: "Aylık giderler, ana gruplara göre" });
    expect(within(table).getByRole("rowheader", { name: "Temmuz 2026 (belge eksik)" })).toBeInTheDocument();
    const average = within(table).getByRole("row", { name: /^Aylık ortalama \(5 tam ay\)/ });
    expect(within(average).getAllByRole("cell").at(-1)).toHaveTextContent("20.240,00 TL");
  });

  it("leads from a month of the heat table, and from a group of it, to the rows it counts there", async () => {
    const path = "/degerlendirme?from=2026-08-15&to=2026-10-31&account=teb-123456789&bolum=harcamalar";
    renderScreen(<InsightsPage />, { path });
    const monthly = await card("Aylık giderler");
    expect(within(monthly).getByText("Bir aya ya da bir gruba tıklayın: o harcamalar listelenir.")).toBeInTheDocument();
    await userEvent.click(within(monthly).getByRole("tab", { name: "Tablo" }));
    const table = within(monthly).getByRole("table", { name: "Aylık giderler, ana gruplara göre" });
    const august = within(table).getByRole("row", { name: /^Ağustos 2026/ });
    // The screen's filters, the spending's kinds written out, and August's days within the period's.
    const rows = `/islemler?account=teb-123456789&from=2026-08-15&to=2026-08-31&${KINDS}`;
    expect(within(august).getByRole("link", { name: "Ağustos 2026" })).toHaveAttribute("href", rows);
    expect(within(august).getByRole("link", { name: "16.000,00 TL" })).toHaveAttribute(
      "href",
      `${rows}&group=Ev+%26+Faturalar`,
    );
  });

  it("narrows every card to a necessity level when its tile is pressed, and widens them again", async () => {
    const { location } = renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const levels = await screen.findByRole("group", { name: "Gereklilik düzeyleri" });
    const avoidable = within(levels).getByRole("button", { name: /^Gereksiz/ });
    expect(avoidable).toHaveAttribute("aria-pressed", "false");
    expect(avoidable).toHaveAccessibleName(/\(yalnızca bu düzeyi göster\)$/);
    await userEvent.click(avoidable);
    expect(location()).toBe("/degerlendirme?bolum=harcamalar&necessity=unnecessary"); // the tab stays
    await waitFor(() =>
      expect(within(levels).getByRole("button", { name: /^Gereksiz/ })).toHaveAttribute("aria-pressed", "true"),
    );
    await userEvent.click(within(levels).getByRole("button", { name: /^Gereksiz/ }));
    expect(location()).toBe("/degerlendirme?bolum=harcamalar");
  });

  it("says what the habits cost a month from now on, the largest named", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    expect(
      await screen.findByText(
        "Düzenli ödemeler dışındaki isteğe bağlı ve gereksiz alışkanlıklarınız bundan sonra ayda 136,00 TL tutuyor; " +
          "en büyüğü Örnek Kahve, ayda 120,00 TL.",
      ),
    ).toBeInTheDocument();
  });

  it("lists the habits with how often each comes, a one-off apart and never made monthly", async () => {
    detailed();
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const table = await screen.findByRole("table", { name: "Alışkanlıklar ve bundan sonra aylık maliyetleri" });
    const fees = within(table).getByRole("row", { name: /^Kart ücretleri/ });
    expect(fees).toHaveTextContent("Her ay");
    expect(fees).toHaveTextContent("Gereksiz · kategori");
    expect(within(table).getByRole("columnheader", { name: "5 ayda toplam" })).toBeInTheDocument();
    const apart = within(table).getByRole("columnheader", { name: /^Durmuş ya da tek seferlik/ });
    const oneOff = within(table).getByRole("row", { name: /^Örnek Teknoloji/ });
    expect(apart.compareDocumentPosition(oneOff) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(oneOff).getAllByRole("cell").at(-1)).toHaveTextContent("–");
    expect(within(table).getByRole("row", { name: /^Bundan sonra aylık toplam/ })).toHaveTextContent("136,00 TL");
  });

  it("shows income and spending by month, the partial month marked, with the whole months' averages", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=gelir-gider" });
    const flow = await card("Gelir ve gider");
    expect(
      within(flow).getByText(
        "Gelir yukarıda, gider aşağıda; sütunun toplamı net. Tam aylarda ortalama gelir 40.000,00 TL, gider " +
          "20.240,00 TL; hepsinden sonra ayda 19.460,00 TL kalıyor.",
      ),
    ).toBeInTheDocument();
    expect(within(flow).getByText("Örnek İşveren A.Ş.: ayda 40.000,00 TL, son 01.10.2026")).toBeInTheDocument();
    await userEvent.click(within(flow).getByRole("tab", { name: "Tablo" }));
    const table = within(flow).getByRole("table", { name: "Aylık gelir ve gider" });
    expect(within(table).getByRole("rowheader", { name: "Temmuz 2026 (belge eksik)" })).toBeInTheDocument();
    const september = within(table).getByRole("row", { name: /^Eylül 2026/ });
    expect(within(september).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "40.000,00 TL",
      "20.000,00 TL",
      "20.000,00 TL",
      "0,00 TL",
      "1.000,00 TL",
      "0,00 TL",
      "19.000,00 TL",
    ]);
  });

  it("leads from a month's income, spending and debt to their rows, and nowhere from what is left", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=gelir-gider" });
    const flow = await card("Gelir ve gider");
    expect(
      within(flow).getByText("Bir ayın gelirine ya da giderine tıklayın: o işlemler listelenir."),
    ).toBeInTheDocument();
    await userEvent.click(within(flow).getByRole("tab", { name: "Tablo" }));
    const september = within(within(flow).getByRole("table")).getByRole("row", { name: /^Eylül 2026/ });
    const days = "from=2026-09-01&to=2026-09-30";
    expect(within(september).getByRole("link", { name: "40.000,00 TL" })).toHaveAttribute(
      "href",
      `/islemler?${days}&kind=income`,
    );
    expect(within(september).getAllByRole("link", { name: "20.000,00 TL" })[0]).toHaveAttribute(
      "href",
      `/islemler?${KINDS}&${days}`,
    );
    expect(within(september).getByRole("link", { name: "1.000,00 TL" })).toHaveAttribute(
      "href",
      `/islemler?${days}&kind=loan_principal`,
    );
    expect(within(september).getAllByRole("link")).toHaveLength(3); // the net, nothing and what is left lead nowhere
  });

  it("forecasts the next month and what the income leaves after it, as an estimate", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=gelecek" });
    const forecast = await card("Önümüzdeki aylar");
    const heading = within(forecast).getByRole("heading", { name: "Önümüzdeki aylar" });
    expect(heading.parentElement).toHaveTextContent("Önümüzdeki aylartahmin"); // the estimate's mark beside it
    expect(
      within(forecast).getByText(
        "Kasım 2026 için tahmini gider 19.310,00 TL; beklenen gelirle ayın sonunda 20.440,00 TL kalır.",
      ),
    ).toBeInTheDocument();
    const tiles = within(forecast).getByRole("region", { name: "Tahminin özeti" });
    expect(
      within(tiles).getByText("Gerekli 18.800,00 TL · İsteğe bağlı 500,00 TL · Gereksiz 10,00 TL"),
    ).toBeInTheDocument();
    expect(within(tiles).getByText("3 aylık tahmini gider")).toBeInTheDocument();
    expect(within(tiles).getByText("57.930,00 TL")).toBeInTheDocument();
    expect(within(tiles).getByText("gelir − gider − kişilere ve borca tipik 250,00 TL")).toBeInTheDocument();
    expect(within(forecast).getByRole("link", { name: "Takvimi aç" })).toHaveAttribute("href", "/takvim");
  });

  it("lists the forecast's lines by part, two of one payee apart, and what is left after all of it", async () => {
    detailed();
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=gelecek" });
    const table = await screen.findByRole("table", { name: "Önümüzdeki üç ayın tahmini, kalem kalem" });
    const regular = within(table).getByRole("row", { name: /^Düzenli ödemeler/ });
    expect(within(regular).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "18.800,00 TL",
      "18.800,00 TL",
      "18.800,00 TL",
    ]);
    expect(within(table).getAllByRole("link", { name: "Örnek Market" })).toHaveLength(2);
    expect(
      within(table).getByRole("rowheader", { name: "Değişken harcamalar (son 5 tam ayın medyanı)" }),
    ).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /^Gelir − gider/ })).toHaveTextContent("20.690,00 TL");
    expect(within(table).getByRole("row", { name: /^Hepsinden sonra kalan/ })).toHaveTextContent("20.440,00 TL");
  });

  it("ranks the categories and the merchants, each bar and name leading to its rows of the period", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const period = `/islemler?from=2026-05-01&to=2026-10-31&${SPENT}`;
    const categories = await card("Kategoriler");
    expect(
      within(categories).getByText("Mayıs 2026 – Ekim 2026; en çok Kira, toplamın %68 kadarı."),
    ).toBeInTheDocument();
    const bars = within(categories).getByRole("list", { name: "Kategoriler" });
    expect(within(bars).getByRole("link", { name: "Kira" })).toHaveAttribute("href", `${period}&category=Kira`);
    await userEvent.click(within(categories).getByRole("tab", { name: "Tablo" }));
    expect(within(categories).getByRole("link", { name: "Kira" })).toHaveAttribute("href", `${period}&category=Kira`);
    const merchants = await card("En çok harcama yapılan yerler");
    expect(within(merchants).getByText("Mayıs 2026 – Ekim 2026; en çok Ev Sahibi Örnek, 5 işlem.")).toBeInTheDocument();
    await userEvent.click(within(merchants).getByRole("tab", { name: "Tablo" }));
    expect(within(merchants).getByRole("link", { name: "Örnek Market" })).toHaveAttribute(
      "href",
      `${period}&merchant=%C3%96rnek+Market`,
    );
  });

  it("says a category spent only in a partial month has no average of the complete months", async () => {
    const flight = {
      ...SPENDING.categories[2]!,
      category: "Uçak, Tren & Otobüs",
      total: tl(420000),
      share: "0.0003",
      average: tl(0),
    };
    serveSpending({ ...SPENDING, categories: [...SPENDING.categories, flight] });
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const categories = await card("Kategoriler");
    await userEvent.click(within(categories).getByRole("tab", { name: "Tablo" }));
    const row = within(categories).getByRole("link", { name: "Uçak, Tren & Otobüs" }).closest("tr")!;
    expect(within(row).getByText("yalnızca eksik ayda")).toBeInTheDocument();
    expect(within(row).getByText("%1'den az")).toBeInTheDocument();
  });

  it("folds the categories after the twelfth into one bar, and lists them all in the table", async () => {
    const many = Array.from({ length: 14 }, (_, i) => ({
      ...SPENDING.categories[0]!,
      category: `Kategori ${i + 1}`,
      total: tl(100000 - i * 1000),
    }));
    serveSpending({ ...SPENDING, categories: many });
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const categories = await card("Kategoriler");
    const bars = within(categories).getByRole("list", { name: "Kategoriler" });
    expect(within(bars).getAllByRole("listitem")).toHaveLength(13);
    expect(within(bars).getByText("Diğer 2 kategori")).toBeInTheDocument();
    await userEvent.click(within(categories).getByRole("tab", { name: "Tablo" }));
    expect(within(categories).getAllByRole("link")).toHaveLength(14);
  });

  it("compares the recent whole months with the ones before, with and without the large one-offs", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const trend = await card("Harcamalar nasıl değişti");
    expect(
      within(trend).getByText(
        "Son 3 tam ayda aylık ortalama 20.400,00 TL, önceki 2 tam ayda 20.000,00 TL. 1 büyük tek seferlik alışveriş " +
          "(6.500,00 TL) ortalamalardan ayrı tutuldu.",
      ),
    ).toBeInTheDocument();
    expect(
      within(trend).getByText("Ağustos 2026 – Ekim 2026 · büyük tek seferlik alışverişler olmadan 18.233,33 TL"),
    ).toBeInTheDocument();
  });

  it("says how to see the spending in real terms while no TÜFE is kept, leading to the settings", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const trend = await card("Harcamalar nasıl değişti");
    expect(within(trend).getByText(/Ayarlar'da bir EVDS anahtarı girilebilir/)).toBeInTheDocument();
    expect(within(trend).getByRole("link", { name: "Ayarlar'da EVDS anahtarı gir" })).toHaveAttribute("href", "/ayarlar");
  });

  it("tells the trend at one month's prices with TÜFE, its months and numbers, beside the TL of its time", async () => {
    const say =
      "Önceki dönemden (Mayıs 2026 – Haziran 2026 arasındaki 2 tam ay) son döneme (Ağustos 2026 – Ekim 2026 " +
      "arasındaki 3 tam ay) fiyatlar (TÜFE) %6,0 arttı. Aylık ortalama harcamanız TL olarak %2,0 arttı; Ekim 2026 " +
      "fiyatlarıyla 21.200,00 TL'den 20.400,00 TL'ye, yani fiyat artışı düşülünce %3,8 azaldı.";
    const real = {
      base: "2026-10",
      before: ["2026-05", "2026-06"],
      recent: ["2026-08", "2026-09", "2026-10"],
      before_nominal: tl(2000000),
      recent_nominal: tl(2040000),
      before_real: tl(2120000),
      recent_real: tl(2040000),
      nominal_change: 0.02,
      real_change: -0.0377,
      prices: 0.06,
      missing: [],
      say,
    };
    const insights = { ...INSIGHTS, trend: { ...INSIGHTS.trend!, real, real_note: "" } };
    server.use(http.get("/api/insights", () => HttpResponse.json(insights)));
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const trend = await card("Harcamalar nasıl değişti");
    const part = within(trend).getByRole("region", { name: "Enflasyondan arındırılmış" });
    expect(within(part).getByText(say)).toBeInTheDocument();
    expect(within(part).getByText("Önceki dönem, Ekim 2026 fiyatlarıyla")).toBeInTheDocument();
    expect(within(part).getByText("21.200,00 TL")).toBeInTheDocument();
    expect(within(part).getByText("TL olarak 20.000,00 TL")).toBeInTheDocument();
    expect(within(trend).queryByRole("link", { name: "Ayarlar'da EVDS anahtarı gir" })).not.toBeInTheDocument();
  });

  it("lists the categories that moved most and the large one-offs, each leading to its rows", async () => {
    detailed();
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const changes = await screen.findByRole("table", { name: "Kategorilerin aylık ortalaması: önceki ve son aylar" });
    const rows = within(changes).getAllByRole("row").slice(1);
    // The largest move first; a category that did not move is left out.
    expect(rows.map((row) => within(row).getByRole("link").textContent)).toEqual(["Elektrik", "Market & Gıda"]);
    expect(rows[0]).toHaveTextContent("+140,00 TL");
    expect(rows[1]).toHaveTextContent("−133,33 TL");
    const large = screen.getByRole("table", { name: "Büyük tek seferlik alışverişler" });
    expect(within(large).getByRole("link", { name: "Örnek Mobilya" })).toHaveAttribute(
      "href",
      "/islemler?satir=b1b1b1b1b1b1b1b1b1b1",
    );
    expect(
      screen.getByText("5.000,00 TL ve üstündeki tek alışverişler ortalamalardan ayrı tutulur."),
    ).toBeInTheDocument();
  });

  it("flags the movements worth a look, each leading to its row", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=harcamalar" });
    const unusual = await card("Olağan dışı hareketler");
    expect(within(unusual).getByText("Olası çift çekim")).toBeInTheDocument();
    expect(within(unusual).getByText(INSIGHTS.unusual[0]!.text)).toBeInTheDocument();
    expect(within(unusual).getByRole("link", { name: "İşlemi göster: Örnek Kafe" })).toHaveAttribute(
      "href",
      "/islemler?satir=c2c2c2c2c2c2c2c2c2c2",
    );
  });

  it("sums the monthly payments still running and leads to the regular payments screen", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=gelecek" });
    expect(await screen.findByText("Süren 4 aylık ödeme ayda 15.949,98 TL tutuyor.")).toBeInTheDocument();
    const regular = screen.getByRole("region", { name: "Düzenli ödemeler ve abonelikler" });
    expect(within(regular).getByRole("link", { name: "Düzenli ödemeleri aç" })).toHaveAttribute("href", "/abonelikler");
    expect(
      within(regular).getByText("Kalan taksitler toplam 2.000,00 TL; sonuncusu Şubat 2027'de bitiyor."),
    ).toBeInTheDocument();
  });

  it("lists the running monthly payments, each opening its panel, added up", async () => {
    detailed();
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=gelecek" });
    const table = await screen.findByRole("table", { name: "Süren aylık ödemeler" });
    expect(within(table).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Ev kirası",
      "Örnek Elektrik",
      "Örnek Video",
      "Örnek Müzik",
    ]);
    expect(within(table).getByRole("link", { name: "Ev kirası" })).toHaveAttribute("href", "/abonelikler?seri=fp-kira");
    expect(within(table).getByRole("row", { name: /^Aylık toplam/ })).toHaveTextContent("15.949,98 TL");
  });

  it("says the regular payments follow every filter but the period, the installments the account alone", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=gelecek" });
    expect(await screen.findByText(REGULAR_HINT)).toBeInTheDocument();
    const regular = screen.getByRole("region", { name: "Düzenli ödemeler ve abonelikler" });
    const installments = within(regular).getByRole("region", { name: "Taksitli alışverişler" });
    expect(within(installments).getByText("Yalnızca hesap süzgecine uyar.")).toBeInTheDocument();
  });

  it("narrows the regular payments by every filter but the period, the installments by the account", async () => {
    detailed();
    renderScreen(<InsightsPage />, { path: "/degerlendirme?account=teb-1234&from=2026-10-01&to=2026-10-31&bolum=gelecek" });
    const table = await screen.findByRole("table", { name: "Süren aylık ödemeler" });
    expect(within(table).getAllByRole("link").map((link) => link.textContent)).toEqual(["Örnek Video", "Örnek Müzik"]);
    expect(within(table).getByRole("row", { name: /^Aylık toplam/ })).toHaveTextContent("249,98 TL");
    const installments = screen.getByRole("table", { name: "Kalan taksitleri olan kart alışverişleri" });
    expect(installments).toHaveTextContent("Örnek Elektronik");
  });

  it("drops the installments of the other accounts, whatever the other filters", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?account=teb-123456789&category=Kira&bolum=gelecek" });
    expect(await screen.findByText(RENT_ONLY)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Taksitli alışverişler" })).not.toBeInTheDocument();
  });

  it.each(["simple", "detailed"])("says no regular payment runs under the filters in the %s view", async (view) => {
    localStorage.setItem("iplikci.view", view);
    renderScreen(<InsightsPage />, { path: "/degerlendirme?merchant=ORNEK%20MARKET&bolum=gelecek" });
    expect(await screen.findByText("Bu süzgeçlerle süren aylık ödeme yok.")).toBeInTheDocument();
  });

  it.each([
    ["tag=ev", "Etiket süzgecini dikkate almaz, çünkü etiket bir düzenli ödemeye değil tek tek işlemlere verilir."],
    [
      "certainty=provisional",
      "Kesinlik süzgecini dikkate almaz, çünkü kesinlik bir düzenli ödemenin değil tek tek işlemlerin özelliğidir.",
    ],
    [
      "tag=ev&certainty=provisional",
      "Etiket ve kesinlik süzgeçlerini dikkate almaz, çünkü ikisi de bir düzenli ödemenin değil tek tek işlemlerin " +
        "özelliğidir.",
    ],
  ])("keeps every regular payment with ?%s and says the card does not follow it", async (query, ignored) => {
    renderScreen(<InsightsPage />, { path: `/degerlendirme?${query}&bolum=gelecek` });
    expect(await screen.findByText(`${REGULAR_HINT} ${ignored}`)).toBeInTheDocument();
    expect(screen.getByText("Süren 4 aylık ödeme ayda 15.949,98 TL tutuyor.")).toBeInTheDocument();
  });

  it("finds a series' group in the category rules, and says when they cannot be read", async () => {
    let fail = true;
    server.use(
      http.get("/api/rules/categories", () =>
        fail
          ? HttpResponse.json({ code: "internal", title: "Kurallar okunamadı." }, { status: 500 })
          : HttpResponse.json(GROUPED),
      ),
    );
    const user = userEvent.setup();
    renderScreen(<InsightsPage />, { path: "/degerlendirme?group=Ev&bolum=gelecek" });
    expect(await screen.findByText("Kurallar okunamadı.")).toBeInTheDocument();
    fail = false;
    const regular = screen.getByRole("region", { name: "Düzenli ödemeler ve abonelikler" });
    await user.click(within(regular).getByRole("button", { name: "Yeniden dene" }));
    expect(await screen.findByText(RENT_ONLY)).toBeInTheDocument();
  });

  it("shows the regular payments without the category rules when no filter needs them", async () => {
    server.use(
      http.get("/api/rules/categories", () =>
        HttpResponse.json({ code: "internal", title: "Kurallar okunamadı." }, { status: 500 }),
      ),
    );
    renderScreen(<InsightsPage />, { path: "/degerlendirme?necessity=optional&bolum=gelecek" });
    expect(await screen.findByText("Bu süzgeçlerle süren 2 aylık ödeme ayda 249,98 TL tutuyor.")).toBeInTheDocument();
    expect(screen.queryByText("Kurallar okunamadı.")).not.toBeInTheDocument();
  });

  it("leads to the rows the cards count, the spending's kinds written out, and downloads them as CSV", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?account=teb-1234&bolum=veriler" });
    const rows = await card("İşlemler");
    expect(within(rows).getByText("Bu süzgeçlerle 60 işlem, toplam 110.700,00 TL.")).toBeInTheDocument();
    const query = "account=teb-1234&kind=purchase&kind=refund&kind=interest_fee";
    expect(within(rows).getByRole("link", { name: "İşlemleri bu süzgeçlerle göster" })).toHaveAttribute(
      "href",
      `/islemler?${query}`,
    );
    expect(within(rows).getByRole("link", { name: "CSV indir: bu süzgeçlerin işlemleri" })).toHaveAttribute(
      "href",
      `/api/transactions.csv?${query}`,
    );
  });

  it("says how many documents are kept, how many statements hold and how far the documents reach", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=veriler" });
    const sources = await card("Veri kaynakları ve kapsam");
    expect(await within(sources).findByText("4 belge kayıtlı: 3 işlendi, 1 okunamadı.")).toBeInTheDocument();
    expect(
      within(sources).getByText("Ekstre denetimi: 2/3 ekstre tutarlı; tutmayanlar Belgeler ekranında."),
    ).toBeInTheDocument();
    expect(
      await within(sources).findByText("3 hesabın belgeleri izleniyor; 1 hesapta eksik ay var."),
    ).toBeInTheDocument();
    expect(within(sources).getByRole("link", { name: "Belgeleri göster" })).toHaveAttribute("href", "/belgeler");
    expect(within(sources).getByRole("link", { name: "Hesapları göster" })).toHaveAttribute("href", "/hesaplar");
  });

  it("draws the months each account's statements cover, and says them per account in its table", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=veriler" });
    const sources = await card("Veri kaynakları ve kapsam");
    const grid = await within(sources).findByRole("figure", { name: "Belgelerin kapsadığı aylar" });
    expect(
      within(grid).getByText(
        "Ocak 2026 – Ekim 2026, 3 hesabın ekstreleri ve hesap dökümleri. 2 hesabın ilk ve son belgesi arasında " +
          "yarım kapsanan ya da belgesiz ay var.",
      ),
    ).toBeInTheDocument();
    expect(within(grid).getByRole("link", { name: "Eski Vadesiz TL (kapanmış)" })).toHaveAttribute(
      "href",
      "/hesaplar/teb-111111111",
    );
    await userEvent.click(within(grid).getByRole("tab", { name: "Tablo" }));
    const table = within(grid).getByRole("table", { name: "Hesap başına belgelerin kapsadığı aylar" });
    const cash = within(table).getByText("Örnek Vadesiz TL").closest("tr")!;
    expect(within(cash).getByText("Ocak 2026 – Ekim 2026")).toBeInTheDocument();
    expect(within(cash).getByText("9 ay")).toBeInTheDocument();
    expect(within(cash).getByText("Temmuz 2026 (%45)")).toBeInTheDocument();
    const cardRow = within(table).getByText("Örnek Kart •1234").closest("tr")!;
    expect(within(cardRow).getByText("Mart 2026 – Ekim 2026")).toBeInTheDocument();
    expect(within(cardRow).getByText("Mart 2026 (%55)")).toBeInTheDocument();
    const closed = within(table).getByText("Eski Vadesiz TL").closest("tr")!;
    expect(within(closed).getByText("kapanmış hesap")).toBeInTheDocument();
  });

  it("says how the debts moved over the window's complete months", async () => {
    const flow = { ...INSIGHTS.flow!, debt_start: tl(1000000), debt_end: tl(1250000) };
    server.use(http.get("/api/insights", () => HttpResponse.json({ ...INSIGHTS, flow })));
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=gelir-gider" });
    const debt = await card("Borç");
    expect(
      await within(debt).findByText(
        "Kart ekstre borçları ve ek hesap kullanımı Nisan 2026 sonundan Ekim 2026 sonuna 2.500,00 TL arttı.",
      ),
    ).toBeInTheDocument();
    expect(within(debt).getByText("Nisan 2026 sonunda").nextElementSibling).toHaveTextContent("10.000,00 TL");
    expect(within(debt).getByText("Ekim 2026 sonunda").nextElementSibling).toHaveTextContent("12.500,00 TL");
    expect(within(debt).getByText("Değişim").nextElementSibling).toHaveTextContent("+2.500,00 TL");
    expect(within(debt).getByRole("link", { name: /Hesapları göster/ })).toHaveAttribute("href", "/hesaplar");
  });

  it("says when the window has no card debt and no overdraft used", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme?bolum=gelir-gider" });
    const debt = await card("Borç");
    expect(
      within(debt).getByText("Mayıs 2026 – Ekim 2026 arasında kart ekstre borcu ya da ek hesap kullanımı yok."),
    ).toBeInTheDocument();
  });

  it("offers the report and the Excel file the last analysis wrote", async () => {
    renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    expect(
      await screen.findByRole("link", { name: "Raporu indir: tek dosya, HTML; süzgeçlerden bağımsız" }),
    ).toHaveAttribute("href", "/api/exports/report");
    expect(screen.getByRole("link", { name: "Excel indir: bütün işlemler; süzgeçlerden bağımsız" })).toHaveAttribute(
      "href",
      "/api/exports/xlsx",
    );
  });

  it("says when the filters keep no spending, and resets them", async () => {
    serveSpending({ ...SPENDING, tiles: { ...SPENDING.tiles, count: 0, total: tl(0) } });
    const { location } = renderScreen(<InsightsPage />, { path: "/degerlendirme?account=teb-1234" });
    expect(await screen.findByText("Bu süzgeçlerle harcama yok")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Özet" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Süzgeçleri sıfırla" }));
    expect(location()).toBe("/degerlendirme");
  });

  it("says when no document is kept yet, and leads to the documents", async () => {
    serveSpending({ ...SPENDING, period: null, tiles: { ...SPENDING.tiles, count: 0, total: tl(0) } });
    renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    const empty = (await screen.findByText("Henüz değerlendirilecek işlem yok")).parentElement!;
    expect(within(empty).getByRole("link", { name: "Belgeleri göster" })).toHaveAttribute("href", "/belgeler");
    expect(screen.queryByRole("region", { name: "Değerlendirme ve strateji" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Veri kaynakları ve kapsam" })).toBeInTheDocument();
  });

  it("says when the service refuses the filters, and resets them", async () => {
    serveSpending(() =>
      HttpResponse.json({ code: "invalid", title: "Süzgeç geçersiz: tarih okunamadı" }, { status: 422 }),
    );
    const { location } = renderScreen(<InsightsPage />, { path: "/degerlendirme?from=2026-13-01" });
    expect(await screen.findByText("Süzgeçler kullanılamadı")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Süzgeçleri sıfırla" }));
    expect(location()).toBe("/degerlendirme");
  });

  it("offers to ask again when the spending cannot be read, and keeps the interpretation", async () => {
    let fail = true;
    serveSpending(() =>
      fail
        ? HttpResponse.json({ code: "busy", title: "Analiz hazırlanıyor" }, { status: 503 })
        : HttpResponse.json(SPENDING),
    );
    renderScreen(<InsightsPage />, { path: "/degerlendirme" });
    expect(await screen.findByText("Analiz hazırlanıyor")).toBeInTheDocument();
    expect(await card("Değerlendirme ve strateji")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await card("Özet")).toBeInTheDocument();
  });

  it("asks nothing while a filter has nothing chosen", async () => {
    const asked = serveSpending(SPENDING);
    renderScreen(<InsightsPage />, { path: "/degerlendirme?account=" });
    expect(await screen.findByText("Bir süzgeçte hiçbir şey seçili değil")).toBeInTheDocument();
    expect(asked).toEqual([]);
  });
});
