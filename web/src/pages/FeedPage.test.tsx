import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { keys } from "../api/queries";
import { renderScreen } from "../test/render";
import { FEED_FIRST, feedItem, NOW, server } from "../test/server";
import FeedPage from "./FeedPage";

// The screen names "today" and "yesterday" by the computer's clock: midday on 15 November.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-15T13:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
  localStorage.clear();
});

const section = (name: string) => screen.findByRole("region", { name });

describe("FeedPage: what stands now", () => {
  it("shows each account's balance with what it rests on, a foreign one in TL too, and those without one", async () => {
    renderScreen(<FeedPage />);
    const balances = await section("Bakiyeler");
    expect(
      within(balances).getByText("2 hesabın bakiyesi belgelerden biliniyor; 1 hesabınki hiçbir belgede yazmıyor."),
    ).toBeInTheDocument();
    expect(within(balances).getByRole("link", { name: "Eksik dökümleri Belgeler'den ekle" })).toHaveAttribute(
      "href",
      "/belgeler",
    );
    const cash = within(balances).getByText("Örnek Vadesiz TL").closest("li")!;
    expect(within(cash).getByText("1.000,00 TL")).toBeInTheDocument();
    expect(within(cash).getByRole("button", { name: "geçici" })).toBeInTheDocument(); // moved by receipts since
    expect(within(cash).getByText(/sonraki 2 dekont ve bildirimle/)).toBeInTheDocument();
    const euros = within(balances).getByText("Örnek Döviz EUR").closest("li")!;
    expect(within(euros).getByText("500,00 EUR")).toBeInTheDocument();
    expect(within(euros).getByText(/18\.500,00 TL karşılığı/)).toBeInTheDocument();
    expect(within(euros).getByText("1 EUR = 37,0000 TL, 31.10.2026 belgesindeki kurla")).toBeInTheDocument();
    expect(within(balances).getByText("bakiyesi hiçbir belgede yazmıyor")).toBeInTheDocument();
  });

  it("shows each card's period and what its statement still asks, the next due date first", async () => {
    renderScreen(<FeedPage />);
    const cards = await section("Kartlar");
    expect(
      within(cards).getByText(
        "Örnek Kart •1234 için son ödeme 25.11.2026: kalan borç 7.000,00 TL, asgari ödeme 1.800,00 TL.",
      ),
    ).toBeInTheDocument();
    expect(within(cards).getByRole("link", { name: "Son ödemeleri takvimde gör" })).toHaveAttribute("href", "/takvim");
    expect(within(cards).getByText("3.200,00 TL")).toBeInTheDocument();
    expect(within(cards).getByText("29.10.2026 – 28.11.2026 · 5 işlem")).toBeInTheDocument();
    expect(
      within(cards).getByText("son ödeme 25.11.2026 · kalan borç 7.000,00 TL · asgari 1.800,00 TL"),
    ).toBeInTheDocument();
  });

  it("puts the month so far beside the typical month's same days, with what they rest on", async () => {
    renderScreen(<FeedPage />);
    const pace = await section("Ay içi tempo");
    expect(
      within(pace).getByText(
        "Kasım 2026'da bugüne kadar 4.200,00 TL harcandı (tipik ayın aynı günlerinde 9.800,00 TL); günlerin %60'ı belgelerle kapsandı.",
      ),
    ).toBeInTheDocument();
    expect(within(pace).getByText("Kasım 2026'da bugüne kadar harcanan")).toBeInTheDocument();
    expect(within(pace).getByText("bunun 1.200,00 TL kadarı")).toBeInTheDocument();
    expect(within(pace).getByText("9.800,00 TL")).toBeInTheDocument();
    expect(within(pace).getByText("20.152,99 TL")).toBeInTheDocument();
    expect(within(pace).getByText(/6 tam ayın medyanı/)).toBeInTheDocument();
  });

  it("says a month cannot be compared before three complete months", async () => {
    server.use(
      http.get("/api/feed/now", () =>
        HttpResponse.json({ ...NOW, pace: { ...NOW.pace, typical: null, by_day: null, months: [] } }),
      ),
    );
    renderScreen(<FeedPage />);
    const pace = await section("Ay içi tempo");
    expect(
      within(pace).getByText(
        "Kasım 2026'da bugüne kadar 4.200,00 TL harcandı; tipik ayla karşılaştırmak için en az 3 tam ay gerekiyor.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the balances as a table in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<FeedPage />);
    const balances = await section("Bakiyeler");
    const table = within(balances).getByRole("table", { name: "Hesapların belgelerden bilinen bakiyeleri" });
    const euros = within(table).getByText("Örnek Döviz EUR").closest("tr")!;
    expect(within(euros).getByText("Döviz hesabı")).toBeInTheDocument();
    expect(within(euros).getByText("18.500,00 TL")).toBeInTheDocument();
    expect(within(balances).queryByText(/hesabın bakiyesi belgelerden biliniyor/)).not.toBeInTheDocument();
  });

  it("says when no account has a balance, a card or spending to show yet", async () => {
    server.use(
      http.get("/api/feed/now", () => HttpResponse.json({ ...NOW, balances: [], unknown: [], cards: [], upcoming: [] })),
    );
    renderScreen(<FeedPage />);
    expect(await screen.findByText("Henüz bakiyesi, kartı ya da harcaması bilinen bir hesap yok")).toBeInTheDocument();
    expect(await screen.findByText("Önümüzdeki 14 günde beklenen ödeme ya da gelir yok.")).toBeInTheDocument();
  });

  it("offers to try again where what stands now could not be read", async () => {
    server.use(
      http.get("/api/feed/now", () =>
        HttpResponse.json({ code: "busy", title: "Belgeler şu an okunuyor." }, { status: 503 }),
      ),
    );
    renderScreen(<FeedPage />);
    const now = await section("Şu an");
    expect(await within(now).findByText("Belgeler şu an okunuyor.")).toBeInTheDocument();
    expect(within(now).getByRole("button", { name: "Yeniden dene" })).toBeInTheDocument();
  });
});

describe("FeedPage: the days ahead", () => {
  it("lists the next 14 days by day as estimates, and says how many payments and income come", async () => {
    renderScreen(<FeedPage />);
    const ahead = await section("Yaklaşanlar");
    expect(
      await within(ahead).findByText("Önümüzdeki 14 günde 2 ödeme ve 1 gelir bekleniyor; ilki bugün: Örnek Müzik."),
    ).toBeInTheDocument();
    expect(within(ahead).getByRole("link", { name: "Takvimi aç" })).toHaveAttribute("href", "/takvim");
    expect(within(ahead).getByRole("heading", { name: "Bugün · 15.11.2026" })).toBeInTheDocument();
    expect(within(ahead).getByRole("heading", { name: "Yarın · 16.11.2026" })).toBeInTheDocument();
    expect(within(ahead).getByRole("heading", { name: "Çarşamba, 25.11.2026" })).toBeInTheDocument();
    const salary = within(ahead).getByText("Örnek İşveren A.Ş.").closest("li")!;
    expect(within(salary).getByText("+40.000,00 TL")).toBeInTheDocument();
    expect(within(salary).getByText("Düzenli gelir · Örnek Vadesiz TL")).toBeInTheDocument();
    const card = within(ahead).getByText("Örnek Kart •1234").closest("li")!;
    expect(within(card).getByText("asgari 1.800,00 TL")).toBeInTheDocument();
  });
});

describe("FeedPage: the events", () => {
  it("lists the events newest first under their days, each with what it concerns now", async () => {
    renderScreen(<FeedPage />);
    const events = await section("Olaylar");
    const days = await within(events).findAllByRole("heading", { level: 3 });
    expect(days.map((day) => day.textContent)).toEqual(["Bugün", "Dün", "Salı, 10.11.2026"]);
    const large = within(events).getByRole("article", { name: "Büyük harcama" });
    expect(within(large).getByText("Örnek Elektronik: 12.500,00 TL (•1234, 15.11.2026).")).toBeInTheDocument();
    expect(within(large).getByText("−12.500,00 TL")).toBeInTheDocument();
    expect(within(large).getByRole("button", { name: "geçici" })).toBeInTheDocument(); // as the ledger counts it now
    const unreadable = within(events).getByRole("article", { name: "Belge okunamadı" });
    expect(within(unreadable).getByText("sifreli.pdf")).toBeInTheDocument();
    expect(within(unreadable).getByText("· Okunamadı")).toBeInTheDocument();
  });

  it("leads each event to its screen once that screen is built", async () => {
    renderScreen(<FeedPage />);
    const due = await screen.findByRole("article", { name: "Son ödeme yaklaşıyor" });
    expect(within(due).getByRole("link", { name: "Takvimde göster: Örnek Kart •1234" })).toHaveAttribute(
      "href",
      "/takvim?gun=2026-11-25",
    );
    // The month's page and the document viewer come later: no link leads nowhere meanwhile.
    expect(within(screen.getByRole("article", { name: "Ay kapandı" })).queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows every value an event carries in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<FeedPage />);
    const read = await screen.findByRole("article", { name: "Belge okundu" });
    expect(within(read).getByText("document.processed · #27")).toBeInTheDocument();
    expect(within(read).getByText("Örnek kart ekstresi · 1.2")).toBeInTheDocument();
    expect(within(read).getByText(/Örnek Kart Ekstresi Ekim 2026\.pdf · İşlendi · Kart ekstresi/)).toBeInTheDocument();
  });

  it("reads older events on request until the log has none left", async () => {
    const user = userEvent.setup();
    renderScreen(<FeedPage />);
    await user.click(await screen.findByRole("button", { name: "Daha eski olaylar" }));
    expect(await screen.findByRole("article", { name: "Yedek alınamadı" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Daha eski olaylar" })).not.toBeInTheDocument();
  });

  it("narrows the events by kind in the address, sending a whole family as one", async () => {
    const asked: URLSearchParams[] = [];
    server.use(
      http.get("/api/feed", ({ request }) => {
        asked.push(new URL(request.url).searchParams);
        return HttpResponse.json(FEED_FIRST);
      }),
    );
    const user = userEvent.setup();
    const { location } = renderScreen(<FeedPage />, { path: "/akis" });
    await user.click(await screen.findByRole("button", { name: "Olay türü: Tümü" }));
    const panel = await screen.findByRole("dialog", { name: "Olay türü" });
    await user.click(within(panel).getByRole("button", { name: "Hiçbiri" }));
    await user.click(within(panel).getByRole("checkbox", { name: "Belgeler" }));
    expect(location()).toBe("/akis?kind=document.processed&kind=document.received&kind=document.unreadable");
    await vi.waitFor(() => expect(asked.at(-1)?.getAll("kind")).toEqual(["document"]));
    await user.keyboard("{Escape}");
    expect(screen.getByRole("list", { name: "Etkin süzgeçler" })).toHaveTextContent("Olay türü:3/9");
  });

  it("narrows the events by certainty and says that only row events have one", async () => {
    const asked: URLSearchParams[] = [];
    server.use(
      http.get("/api/feed", ({ request }) => {
        asked.push(new URL(request.url).searchParams);
        return HttpResponse.json(FEED_FIRST);
      }),
    );
    renderScreen(<FeedPage />, { path: "/akis?certainty=provisional" });
    expect(await screen.findByText("Kesinlik süzgeci yalnızca işlem olaylarını gösterir.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Kesinlik: Geçici" })).toBeInTheDocument();
    await vi.waitFor(() => expect(asked.at(-1)?.getAll("certainty")).toEqual(["provisional"]));
  });

  it("asks nothing when a filter has none of its choices, and says nothing matches", async () => {
    const asked = vi.fn();
    server.use(
      http.get("/api/feed", () => {
        asked();
        return HttpResponse.json(FEED_FIRST);
      }),
    );
    const user = userEvent.setup();
    const { location } = renderScreen(<FeedPage />, { path: "/akis?account=" });
    expect(await screen.findByText("Bu süzgeçlerle olay yok")).toBeInTheDocument();
    expect(asked).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Hesap süzgecini kaldır" }));
    expect(location()).toBe("/akis");
    expect(await screen.findByRole("article", { name: "Büyük harcama" })).toBeInTheDocument();
  });

  it("marks the events that arrive after the list was shown and tells a screen reader how many", async () => {
    const { client } = renderScreen(<FeedPage />);
    expect(await screen.findByRole("article", { name: "Büyük harcama" })).toBeInTheDocument();
    const newer = feedItem({ id: 32, at: "2026-11-15T12:50:00+00:00", label: "Belge geldi", text: "Yeni bir belge geldi." });
    server.use(
      http.get("/api/feed", () => HttpResponse.json({ ...FEED_FIRST, items: [newer, ...FEED_FIRST.items] })),
    );
    await act(() => client.invalidateQueries({ queryKey: keys.feedAll }));
    const arrived = await screen.findByRole("article", { name: "Belge geldi" });
    expect(within(arrived).getByText("yeni")).toBeInTheDocument();
    expect(screen.getByText("1 yeni olay geldi.")).toBeInTheDocument();
    expect(within(screen.getByRole("article", { name: "Büyük harcama" })).queryByText("yeni")).not.toBeInTheDocument();
  });

  it("says when nothing has happened yet", async () => {
    server.use(http.get("/api/feed", () => HttpResponse.json({ items: [], next: null })));
    renderScreen(<FeedPage />);
    expect(await screen.findByText("Henüz olay yok")).toBeInTheDocument();
    expect(screen.getByText("Belgeler ve e-postalar geldikçe olaylar burada görünür.")).toBeInTheDocument();
  });

  it("offers to try again when the events could not be read", async () => {
    server.use(
      http.get("/api/feed", () =>
        HttpResponse.json({ code: "internal", title: "Beklenmeyen bir hata oldu." }, { status: 500 }),
      ),
    );
    renderScreen(<FeedPage />);
    const events = await section("Olaylar");
    expect(await within(events).findByText("Beklenmeyen bir hata oldu.")).toBeInTheDocument();
    expect(within(events).getByRole("button", { name: "Yeniden dene" })).toBeInTheDocument();
  });
});
