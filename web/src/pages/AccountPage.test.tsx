import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { renderScreen } from "../test/render";
import { accountPage, INCOME, server } from "../test/server";
import AccountPage from "./AccountPage";

afterEach(() => localStorage.clear());

const open = (id: string) => renderScreen(<AccountPage />, { path: `/hesaplar/${id}`, route: "/hesaplar/:id" });
const card = (name: string) => screen.findByRole("region", { name });

describe("AccountPage: a TL account", () => {
  it("names the account with its bank and type, and says where it stands", async () => {
    open("teb-123456789");
    expect(await screen.findByRole("heading", { level: 1, name: "Örnek Vadesiz TL" })).toBeInTheDocument();
    expect(screen.getByText("Örnek Bank · Vadesiz hesap")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Hesaplar" })).toHaveAttribute("href", "/hesaplar");
    const status = await card("Durum");
    expect(
      within(status).getByText("Bakiye 1.000,00 TL; 04.11.2026 itibarıyla. Kasım 2026'da giren 0,00 TL, çıkan 1.500,00 TL."),
    ).toBeInTheDocument();
    expect(within(status).getByText("son döküm 31.10.2026 · 15 gün önce")).toBeInTheDocument();
  });

  it("draws the balance by day, the days no document covers left blank", async () => {
    open("teb-123456789");
    const curve = await card("Günlük bakiye");
    expect(
      within(curve).getByText(
        "29.10.2026 – 04.11.2026: en düşük −300,00 TL, en yüksek 2.500,00 TL; son gün 1.000,00 TL. Hiçbir belgenin " +
          "kapsamadığı günler boş.",
      ),
    ).toBeInTheDocument();
    const line = within(curve).getByRole("img", { name: /gün sonu bakiyesi/ }).querySelector("path[fill='none']");
    expect((line?.getAttribute("d") ?? "").split("M").length - 1).toBe(2); // 1–3 November is blank
  });

  it("shows the last 12 months by the newest complete one, the interest and fees, and the regular payments", async () => {
    const user = userEvent.setup();
    open("teb-123456789");
    expect(
      within(await card("Son 12 ay")).getByText("Son tam ay Ekim 2026: giren 40.000,00 TL, çıkan 35.000,00 TL."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Düzenli ödemeler ve ücretler 2" }));
    expect(
      within(await card("Faiz ve ücretler")).getByText("Aralık 2025 – Ekim 2026: faiz ve ücretler toplam 112,50 TL."),
    ).toBeInTheDocument();
    expect(
      within(await card("Bu hesaptan düzenli ödemeler")).getByRole("link", { name: "Ev kirası" }),
    ).toHaveAttribute("href", "/abonelikler?seri=fp-kira");
    expect(
      within(await card("Bu hesaba düzenli gelirler")).getByRole("link", { name: "Örnek İşveren A.Ş." }),
    ).toHaveAttribute("href", "/abonelikler?seri=fp-maas");
  });

  it("says what the documents never print about the overdraft instead of a zero", async () => {
    open("teb-123456789");
    const overdraft = await card("Kredili mevduat (KMH)");
    expect(within(overdraft).getByText("Limit").nextElementSibling).toHaveTextContent("belgelerde yok");
    expect(within(overdraft).getByText("1 gün · 15.11.2025 – 15.11.2026 arasında")).toBeInTheDocument();
    expect(within(overdraft).getByText("Limit hiçbir belgede yazmıyor.")).toBeInTheDocument();
  });

  it("lists its rows with what they add up to, a row's detail at the side", async () => {
    const user = userEvent.setup();
    const { location } = open("teb-123456789");
    await user.click(await screen.findByRole("tab", { name: /^İşlemler/ }));
    const rows = await card("İşlemler");
    expect(within(rows).getByRole("link", { name: "İşlemler ekranında aç" })).toHaveAttribute(
      "href",
      "/islemler?account=teb-123456789",
    );
    await user.click(within(rows).getByRole("link", { name: INCOME.title }));
    expect(location()).toBe(`/hesaplar/teb-123456789?bolum=islemler&satir=${INCOME.fingerprint}`);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("says why the page could not be read and tries again", async () => {
    let fail = true;
    server.use(
      http.get("/api/accounts/:id", () =>
        fail
          ? HttpResponse.json({ code: "account_not_found", title: "Böyle bir hesap yok." }, { status: 404 })
          : HttpResponse.json(accountPage()),
      ),
    );
    const user = userEvent.setup();
    open("teb-123456789");
    expect(await screen.findByText("Böyle bir hesap yok.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Hesap" })).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await card("Durum")).toBeInTheDocument();
  });
});

describe("AccountPage: a credit card", () => {
  it("shows how each statement was paid, as a state with its words", async () => {
    open("teb-1234");
    const statements = await card("Kart");
    expect(within(statements).getByText("Son ödeme günü gelmedi")).toBeInTheDocument();
    expect(within(statements).getByText("Asgarisi ödendi")).toBeInTheDocument();
    expect(within(statements).getByText("Tamamı ödendi")).toBeInTheDocument();
    expect(within(statements).getByText("28.10.2026 kesimli ekstre")).toBeInTheDocument();
  });

  it("shows every statement's figures in the detailed view, a limit no statement printed as missing", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    open("teb-1234");
    const table = within(await card("Kart")).getByRole("table", { name: "Ekstreler ve ödemeleri" });
    const september = within(table).getByText("28.09.2026").closest("tr")!;
    expect(september).toHaveTextContent("belgelerde yok");
    expect(september).toHaveTextContent("Asgarisi ödendi");
    const august = within(table).getByText("28.08.2026").closest("tr")!;
    expect(august).toHaveTextContent("Doğrulanmadı");
  });

  it("says what the installments leave to pay and the month the last one comes", async () => {
    open("teb-1234");
    const installments = await card("Taksitler");
    expect(
      within(installments).getByText("1 taksitli alışverişin kalan tutarı 7.500,00 TL; son taksit Ocak 2027 ekstresinde."),
    ).toBeInTheDocument();
    expect(within(installments).getByText("taksit 3/6, 3 taksit kaldı")).toBeInTheDocument();
  });

  it("draws no balance curve for a card, and says why", async () => {
    open("teb-1234");
    expect(
      within(await card("Günlük bakiye")).getByText("Günlük bakiye TL vadesiz, vadeli ve ek hesaplar için çizilir."),
    ).toBeInTheDocument();
  });
});

describe("AccountPage: a foreign currency account", () => {
  it("shows its amount and value at the documents' rate, and what they never print as missing", async () => {
    open("teb-eur-1");
    const holding = await card("Döviz hesabı");
    const value = (name: string) => within(holding).getByText(name).nextElementSibling;
    expect(value("Miktar")).toHaveTextContent("500,00 EUR");
    expect(value("TL karşılığı")).toHaveTextContent("18.500,00 TL");
    expect(value("Kur")).toHaveTextContent("37,0000 TL · 31.10.2026 belgesindeki kur");
    expect(value("Maliyet")).toHaveTextContent("belgelerde yok");
    expect(value("Kur farkı")).toHaveTextContent("belgelerde yok");
  });
});

describe("AccountPage: the account's name", () => {
  it("gives the account a name of the user's own, keeping the bank's for the reports", async () => {
    let sent: unknown = null;
    server.use(
      http.put("/api/accounts/:id/alias", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ account: { id: "teb-123456789", label: "Maaş hesabı" }, alias: "Maaş hesabı" });
      }),
    );
    const user = userEvent.setup();
    open("teb-123456789");
    await user.click(await screen.findByRole("button", { name: "Adını değiştir" }));
    const name = screen.getByLabelText("Hesabın adı");
    expect(name).toHaveAccessibleDescription(
      "Ekranlarda bu ad görünür. Raporlar ve dışa aktarımlar bankanın adını (Örnek Vadesiz TL) kullanır.",
    );
    await user.clear(name);
    await user.type(name, "Maaş hesabı");
    await user.click(screen.getByRole("button", { name: "Adı kaydet" }));
    expect(await screen.findByText("Hesabın adı kaydedildi.")).toBeInTheDocument();
    expect(sent).toEqual({ alias: "Maaş hesabı" });
    expect(screen.queryByLabelText("Hesabın adı")).not.toBeInTheDocument();
  });

  it("gives the bank's name back", async () => {
    let sent: unknown = null;
    const named = accountPage();
    server.use(
      http.get("/api/accounts/:id", () =>
        HttpResponse.json({
          ...named,
          account: { ...named.account, alias: "Maaş hesabı", account: { id: "teb-123456789", label: "Maaş hesabı" } },
        }),
      ),
      http.put("/api/accounts/:id/alias", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ account: { id: "teb-123456789", label: "Örnek Vadesiz TL" }, alias: "" });
      }),
    );
    const user = userEvent.setup();
    open("teb-123456789");
    expect(await screen.findByRole("heading", { level: 1, name: "Maaş hesabı" })).toBeInTheDocument();
    expect(screen.getByText("Örnek Bank · Vadesiz hesap · bankadaki adı Örnek Vadesiz TL")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Adını değiştir" }));
    await user.click(screen.getByRole("button", { name: "Bankanın adına dön" }));
    await waitFor(() => expect(sent).toEqual({ alias: "" }));
    expect(await screen.findByText("Hesap yeniden bankanın adıyla görünüyor.")).toBeInTheDocument();
  });
});
