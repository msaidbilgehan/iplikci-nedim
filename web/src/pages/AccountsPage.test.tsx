import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { renderScreen } from "../test/render";
import { ACCOUNTS, FLOWS, server } from "../test/server";
import AccountsPage from "./AccountsPage";

afterEach(() => localStorage.clear());

const group = (name: string) => screen.findByRole("region", { name });

describe("AccountsPage: the account map", () => {
  it("says what the accounts are worth, leaving out those without a TL value", async () => {
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    expect(await screen.findByRole("heading", { level: 1, name: "Hesaplar" })).toBeInTheDocument();
    expect(
      await screen.findByText(
        "Varlıklar 19.500,00 TL, borçlar 7.000,00 TL; net 12.500,00 TL. 1 hesabın TL değeri bilinmediği için " +
          "toplamlara girmedi.",
      ),
    ).toBeInTheDocument();
    const totals = screen.getByRole("region", { name: "Toplamlar" });
    expect(within(totals).getByText("12.500,00 TL")).toBeInTheDocument();
  });

  it("lists the accounts in their groups, each group with its assets, debts and total", async () => {
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    const cards = await group("Kredi kartları");
    expect(within(cards).getByText("−7.000,00 TL", { selector: "span.font-semibold" })).toBeInTheDocument();
    expect(within(cards).getByText("Varlık 0,00 TL · Borç 7.000,00 TL")).toBeInTheDocument();
    const current = await group("Vadesiz");
    expect(within(current).getByText(/1 hesabın TL değeri bilinmiyor/)).toBeInTheDocument();
    expect(await group("Döviz")).toBeInTheDocument();
    const closed = await group("Kapanmış hesaplar");
    expect(within(closed).getByText("Belgeleri en yeni belgeden 180 günden eski; hiçbir toplama girmez.")).toBeInTheDocument();
    expect(within(closed).getByRole("link", { name: "Örnek Eski Hesap" })).toHaveAttribute("href", "/hesaplar/ornek-999");
  });

  it("shows each account's balance, the day it knows of, how far its documents reach and this month's money", async () => {
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    const current = await group("Vadesiz");
    const cash = within(current).getByRole("link", { name: "Örnek Vadesiz TL" }).closest("li")!;
    expect(cash).toHaveTextContent("1.000,00 TL");
    expect(within(cash).getByRole("button", { name: "geçici" })).toBeInTheDocument();
    expect(within(cash).getByText("04.11.2026 itibarıyla")).toBeInTheDocument();
    expect(within(cash).getByText("son döküm 31.10.2026 · 15 gün önce")).toBeInTheDocument();
    expect(within(cash).getByText("Kasım 2026: giren 0,00 TL, çıkan 1.500,00 TL (2 tanesi geçici)")).toBeInTheDocument();
    const unknown = within(current).getByRole("link", { name: "Garanti Vadesiz TL" }).closest("li")!;
    expect(within(unknown).getByText("Bakiyesi belgelerde yok")).toBeInTheDocument();
    expect(within(unknown).queryByText(/^0,00 TL$/)).not.toBeInTheDocument(); // never a zero for what is not known
    const euro = within(await group("Döviz")).getByRole("link", { name: "Örnek Döviz EUR" }).closest("li")!;
    expect(euro).toHaveTextContent("500,00 EUR");
    expect(within(euro).getByText("TL karşılığı 18.500,00 TL")).toBeInTheDocument();
  });

  it("leads every account to its page", async () => {
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    expect(within(await group("Vadesiz")).getByRole("link", { name: "Örnek Vadesiz TL" })).toHaveAttribute(
      "href",
      "/hesaplar/teb-123456789",
    );
  });

  it("shows every value in a table in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    const table = within(await group("Vadesiz")).getByRole("table", { name: "Vadesiz grubundaki hesaplar" });
    const headers = within(table).getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["Seç", "Hesap", "Bakiye", "TL karşılığı", "Son belge", "Bu ay giren", "Bu ay çıkan", "Not"]);
    const unknown = within(table).getByRole("link", { name: "Garanti Vadesiz TL" }).closest("tr")!;
    expect(within(unknown).getByText("belgelerde yok")).toBeInTheDocument();
  });

  it("shows chosen accounts together, with their rows on the Transactions screen", async () => {
    const user = userEvent.setup();
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    const current = await group("Vadesiz");
    await user.click(within(current).getByRole("checkbox", { name: "Birlikte göster: Örnek Vadesiz TL" }));
    await user.click(within(current).getByRole("checkbox", { name: "Birlikte göster: Garanti Vadesiz TL" }));
    const together = screen.getByRole("region", { name: "Seçili hesaplar" });
    expect(
      within(together).getByText(
        "2 hesap seçildi; TL karşılıklarının toplamı 1.000,00 TL. 1 tanesinin TL karşılığı bilinmiyor; toplama " +
          "girmedi. Kasım 2026'da giren 0,00 TL, çıkan 1.500,00 TL.",
      ),
    ).toBeInTheDocument();
    expect(within(together).getByRole("link", { name: "İşlemlerini birlikte göster" })).toHaveAttribute(
      "href",
      "/islemler?account=teb-123456789&account=garanti-1234567",
    );
    await user.click(within(together).getByRole("button", { name: "Seçimi kaldır" }));
    expect(screen.queryByRole("region", { name: "Seçili hesaplar" })).not.toBeInTheDocument();
  });

  it("says where the accounts come from before there are any", async () => {
    server.use(http.get("/api/accounts", () => HttpResponse.json({ ...ACCOUNTS, groups: [], closed: [] })));
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    expect(await screen.findByText("Henüz hesap yok")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Belgeleri göster" })).toHaveAttribute("href", "/belgeler");
  });

  it("says why the accounts could not be read and tries again", async () => {
    let fail = true;
    server.use(
      http.get("/api/accounts", () =>
        fail
          ? HttpResponse.json({ code: "busy", title: "Belgeler şu an okunuyor." }, { status: 503 })
          : HttpResponse.json(ACCOUNTS),
      ),
    );
    const user = userEvent.setup();
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    expect(await screen.findByText("Belgeler şu an okunuyor.")).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await group("Vadesiz")).toBeInTheDocument();
  });
});

describe("AccountsPage: where the money went", () => {
  it("draws the flow of the newest complete month and says what came in, what went out and the largest flow", async () => {
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    const flows = await group("Hesaplar arası akış");
    expect(
      await within(flows).findByText(
        "01.10.2026 – 31.10.2026: gelirlerden hesaplara 40.000,00 TL girdi, hesaplardan 25.900,50 TL çıktı. En " +
          "büyük akış Örnek İşveren A.Ş. → Örnek Vadesiz TL: 40.000,00 TL.",
      ),
    ).toBeInTheDocument();
    const drawing = within(flows).getByRole("img", { name: /^Hesaplar arası para akışı: akış diyagramı/ });
    expect(drawing.querySelectorAll("path")).toHaveLength(FLOWS.edges.length);
    expect(within(flows).getByLabelText("Başlangıç")).toHaveValue("2026-10-01");
    expect(within(flows).getByLabelText("Bitiş")).toHaveValue("2026-10-31");
  });

  it("lists every flow in the table view, each leading to its rows", async () => {
    const user = userEvent.setup();
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    const flows = await group("Hesaplar arası akış");
    await user.click(await within(flows).findByRole("tab", { name: "Tablo" }));
    const table = within(flows).getByRole("table", { name: "01.10.2026 – 31.10.2026 arasındaki akışlar" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(1 + FLOWS.edges.length);
    expect(rows[4]).toHaveTextContent("Örnek Kart •1234Gıda8.400,50 TL6Harcama");
    expect(within(rows[1]!).getByRole("link", { name: /^İşlemleri göster/ })).toHaveAttribute(
      "href",
      "/islemler?account=teb-123456789&kind=income&from=2026-10-01&to=2026-10-31",
    );
  });

  it("asks for another window of days, kept in the address", async () => {
    const asked: URLSearchParams[] = [];
    server.use(
      http.get("/api/accounts/flows", ({ request }) => {
        asked.push(new URL(request.url).searchParams);
        return HttpResponse.json(FLOWS);
      }),
    );
    const { location } = renderScreen(<AccountsPage />, { path: "/hesaplar" });
    const flows = await group("Hesaplar arası akış");
    await within(flows).findByRole("img", { name: /akış diyagramı/ });
    fireEvent.change(within(flows).getByLabelText("Başlangıç"), { target: { value: "2026-09-01" } });
    await waitFor(() => expect(asked.at(-1)?.get("from")).toBe("2026-09-01"));
    expect(location()).toBe("/hesaplar?from=2026-09-01");
  });

  it("says when no money moved in the window", async () => {
    server.use(http.get("/api/accounts/flows", () => HttpResponse.json({ ...FLOWS, nodes: [], edges: [] })));
    renderScreen(<AccountsPage />, { path: "/hesaplar" });
    const flows = await group("Hesaplar arası akış");
    expect(
      await within(flows).findByText("01.10.2026 – 31.10.2026 arasında hesaplara giren ya da çıkan para yok."),
    ).toBeInTheDocument();
  });
});
