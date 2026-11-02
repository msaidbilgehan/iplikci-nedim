import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { renderScreen } from "../test/render";
import {
  ACCOUNT_LIST,
  EXCLUDED,
  INCOME,
  LOCKED,
  PURCHASE,
  RECEIPT,
  server,
  STATEMENT,
  STATEMENT_DETAIL,
  tl,
} from "../test/server";
import DocumentPage from "./DocumentPage";

afterEach(() => localStorage.clear());

const open = (path: string) => renderScreen(<DocumentPage />, { path, route: "/belgeler/:id" });
const region = (name: string) => screen.findByRole("region", { name });

describe("DocumentPage: a statement's PDF", () => {
  it("names the document, says what was read from it, and shows its first page", async () => {
    open(`/belgeler/${STATEMENT}`);
    expect(await screen.findByRole("heading", { level: 1, name: "Örnek Kart Ekstresi Kasım 2026" })).toBeInTheDocument();
    expect(screen.getByText("Kart ekstresi · 16.10.2026 – 15.11.2026 · Örnek Kart •1234")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Belgeler" })).toHaveAttribute("href", "/belgeler");
    expect(
      screen.getByText(
        "Kart ekstresi, 16.10.2026 – 15.11.2026. Bu belgeden 1 işlem okundu. Toplamı belgenin yazdığıyla tutuyor. " +
          "Bir işlemi seçince belgedeki yeri işaretlenir.",
      ),
    ).toBeInTheDocument();
    const page = await screen.findByRole("img", { name: "Örnek Kart Ekstresi Kasım 2026, sayfa 1" });
    expect(page).toHaveAttribute("src", `/api/documents/${STATEMENT}/pages/1.png?width=1200`);
    expect(screen.getByText("Sayfa 1 / 2")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Aslını indir" })).toHaveAttribute(
      "href",
      `/api/documents/${STATEMENT}/download`,
    );
  });

  it("opens at a row's page with the row's box marked, and leads to the row on the İşlemler screen", async () => {
    open(`/belgeler/${STATEMENT}?satir=${PURCHASE.fingerprint}`);
    const page = await screen.findByRole("img", {
      name: "Örnek Kart Ekstresi Kasım 2026, sayfa 2; seçili işlemin satırı işaretli",
    });
    expect(page).toHaveAttribute("src", `/api/documents/${STATEMENT}/pages/2.png?width=1200`);
    const rows = await region("Okunan işlemler");
    expect(within(rows).getByRole("button", { name: /ORNEK MARKET KADIKOY/, pressed: true })).toBeInTheDocument();
    const chosen = within(rows).getByRole("region", { name: "Seçili işlem" });
    expect(
      within(chosen).getByText("12.11.2026 · Harcama · Örnek Kart •1234 · Market · sayfa 2 · satır 14 · Ekstreyle eşleşti"),
    ).toBeInTheDocument();
    expect(within(chosen).getByRole("link", { name: "İşlemler ekranında aç" })).toHaveAttribute(
      "href",
      `/islemler?satir=${PURCHASE.fingerprint}`,
    );
  });

  it("turns the pages, then back to the chosen row's", async () => {
    const user = userEvent.setup();
    const { location } = open(`/belgeler/${STATEMENT}?satir=${PURCHASE.fingerprint}`);
    await screen.findByText("Sayfa 2 / 2");
    await user.click(screen.getByRole("button", { name: "Önceki sayfa" }));
    expect(await screen.findByText("Sayfa 1 / 2")).toBeInTheDocument();
    expect(location()).toBe(`/belgeler/${STATEMENT}?satir=${PURCHASE.fingerprint}&sayfa=1`);
    await user.click(screen.getByRole("button", { name: "İşlemin sayfasına git (2)" }));
    expect(await screen.findByRole("img", { name: /sayfa 2; seçili işlemin satırı işaretli/ })).toBeInTheDocument();
  });

  it("chooses a row, and lets go of it when chosen again", async () => {
    const user = userEvent.setup();
    const { location } = open(`/belgeler/${STATEMENT}`);
    const rows = await region("Okunan işlemler");
    const button = within(rows).getByRole("button", { name: /ORNEK MARKET KADIKOY/ });
    expect(button).toHaveAttribute("aria-pressed", "false");
    await user.click(button);
    expect(location()).toBe(`/belgeler/${STATEMENT}?satir=${PURCHASE.fingerprint}`);
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByRole("img", { name: /sayfa 2; seçili işlemin satırı işaretli/ })).toBeInTheDocument();
    await user.click(button);
    expect(location()).toBe(`/belgeler/${STATEMENT}`);
  });

  it("shows the page's text with the row's line marked when the row has no box", async () => {
    server.use(
      http.get("/api/documents/:sha256", () =>
        HttpResponse.json({
          ...STATEMENT_DETAIL,
          rows: STATEMENT_DETAIL.rows.map((row) => ({ ...row, ref: { ...row.ref!, box: null } })),
        }),
      ),
    );
    open(`/belgeler/${STATEMENT}?satir=${PURCHASE.fingerprint}`);
    const lines = await screen.findByRole("list", { name: "Sayfa 2, metin; seçili işlemin satırı işaretli" });
    expect(within(lines).getByText("12.11.2026 ORNEK MARKET KADIKOY 840,50", { selector: "mark" })).toBeInTheDocument();
  });

  it("tells whether the statement's total holds: what it prints against its rows and the previous balance", async () => {
    server.use(
      http.get("/api/documents/:sha256", () =>
        HttpResponse.json({
          ...STATEMENT_DETAIL,
          checks: [
            {
              account: "Örnek Kart •1234",
              start: null,
              cut: "2026-11-15",
              printed: tl(940050),
              counted: tl(840050),
              verified: false,
              balance_checks: null,
              rows: 1,
            },
          ],
        }),
      ),
    );
    open(`/belgeler/${STATEMENT}`);
    const checks = await region("Doğrulama");
    expect(within(checks).getByText("Tutmuyor")).toBeInTheDocument();
    expect(
      within(checks).getByText(
        "Örnek Kart •1234, 15.11.2026: belgedeki toplam 9.400,50 TL, satırların toplamı 8.400,50 TL.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Toplamı belgenin yazdığıyla tutmuyor; satırlarına bakın\./)).toBeInTheDocument();
  });

  it("tells how the statement arrived, with the way to its e-mail in Gmail", async () => {
    server.use(
      http.get("/api/documents/:sha256", () =>
        HttpResponse.json({
          ...STATEMENT_DETAIL,
          arrivals: [
            {
              kind: "email",
              name: "ekstre.pdf",
              origin: "INBOX",
              sender: "ekstre@ornekbanka.example",
              subject: "Kasım 2026 kart ekstreniz",
              sent_at: "2026-11-16T07:55:00+00:00",
              received_at: "2026-11-16T08:00:00+00:00",
              gmail: "https://mail.google.com/mail/u/0/#search/rfc822msgid%3Aekstre-1%40ornekbanka.example",
            },
          ],
        }),
      ),
    );
    open(`/belgeler/${STATEMENT}`);
    const arrivals = await region("Nasıl geldi");
    expect(within(arrivals).getByText("ekstre@ornekbanka.example · Kasım 2026 kart ekstreniz")).toBeInTheDocument();
    const gmail = within(arrivals).getByRole("link", { name: "Gmail'de aç (yeni sekmede açılır)" });
    expect(gmail).toHaveAttribute("href", expect.stringMatching(/^https:\/\/mail\.google\.com\//));
    expect(gmail).toHaveAttribute("target", "_blank");
    expect(gmail).toHaveAttribute("rel", "noreferrer noopener");
  });
});

describe("DocumentPage: an account list's sheet", () => {
  it("marks the chosen row in the sheet, and tells the statement's checks", async () => {
    open(`/belgeler/${ACCOUNT_LIST}?satir=${INCOME.fingerprint}`);
    const table = await screen.findByRole("table", {
      name: "TEB Hesap Dökümü Şubat 2026, tablo; seçili işlemin satırı işaretli",
    });
    const marked = within(table).getByRole("rowheader", { name: "3 (seçili işlemin satırı)" });
    expect(marked.closest("tr")).toHaveTextContent("MAAS ODEMESI ORNEK ISVEREN");
    expect(screen.getByText("Hesap Hareketleri sayfası")).toBeInTheDocument();
    const checks = await region("Doğrulama");
    expect(within(checks).getByText("Tutuyor")).toBeInTheDocument();
    expect(
      within(checks).getByText("TEB Vadesiz TL 123456789, 01.02.2026 – 28.02.2026: kapanış bakiyesi 41.000,00 TL."),
    ).toBeInTheDocument();
    expect(within(checks).getByText("12 satır · 12/12 satırda bakiye tutarlı")).toBeInTheDocument();
    const rows = await region("Okunan işlemler");
    expect(within(rows).getByRole("button", { name: /MAAS ODEMESI ORNEK ISVEREN \+40\.000,00 TL/ })).toBeInTheDocument();
  });

  it("tells a file's arrival by its name", async () => {
    open(`/belgeler/${ACCOUNT_LIST}`);
    const arrivals = await region("Nasıl geldi");
    expect(within(arrivals).getByText("subat.xls")).toBeInTheDocument();
    expect(within(arrivals).getByText(/^Yükleme · 01\.11\.2026/)).toBeInTheDocument();
  });

  it("shows every value of the rows and every fact of the document in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    open(`/belgeler/${ACCOUNT_LIST}`);
    const table = await screen.findByRole("table", { name: "Bu belgeden okunan işlemler, belgedeki sırasıyla" });
    const income = within(table).getByRole("button", { name: "Belgede göster: MAAS ODEMESI ORNEK ISVEREN, 05.02.2026" });
    const cells = within(income.closest("tr")!).getAllByRole("cell").map((cell) => cell.textContent);
    expect(cells).toEqual([
      "05.02.2026",
      "MAAS ODEMESI ORNEK ISVEREN",
      "+40.000,00 TL",
      "Gelir",
      "TEB Vadesiz TL 123456789",
      "Maaş",
      "Hesap Hareketleri · satır 3",
      "",
    ]);
    const facts = await region("Belgenin bilgileri");
    expect(within(facts).getByText("TEB hesap hareketleri · sürüm 2.1")).toBeInTheDocument();
    expect(within(facts).getByText(ACCOUNT_LIST)).toBeInTheDocument();
    expect(screen.queryByText(/Bu belgeden 1 işlem okundu/)).not.toBeInTheDocument(); // the sentence is the simple view's
  });
});

describe("DocumentPage: an e-mail", () => {
  it("shows the e-mail's text with the chosen row's words marked, and what the statements say of the row", async () => {
    open(`/belgeler/${RECEIPT}?satir=${EXCLUDED.fingerprint}`);
    const body = await screen.findByRole("region", { name: "Örnek Banka dekontu, metin; seçili işlemin yeri işaretli" });
    expect(within(body).getByText("ORNEK KAFE 90,00 TL", { selector: "mark" })).toBeInTheDocument();
    expect(screen.getByText("İşlem bildirimi", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText("ornekbanka.example", { selector: "dd" })).toBeInTheDocument();
    const rows = await region("Okunan işlemler");
    expect(within(rows).getByRole("button", { name: /ORNEK KAFE −90,00 TL · toplamlara girmez/ })).toBeInTheDocument();
    const chosen = within(rows).getByRole("region", { name: "Seçili işlem" });
    expect(within(chosen).getByText(/Ekstrede görünmüyor/)).toBeInTheDocument();
  });

  it("opens the sender's own markup only in a sandbox that runs nothing", async () => {
    const user = userEvent.setup();
    open(`/belgeler/${RECEIPT}`);
    await user.click(await screen.findByRole("radio", { name: "Özgün görünüm" }));
    const frame = screen.getByTitle("Örnek Banka dekontu, özgün görünüm");
    expect(frame.tagName).toBe("IFRAME");
    expect(frame).toHaveAttribute("sandbox", "");
    expect(frame).toHaveAttribute("src", `/api/documents/${RECEIPT}/original.html`);
    expect(frame).toHaveAttribute("referrerpolicy", "no-referrer");
    await user.click(screen.getByRole("radio", { name: "Metin" }));
    expect(screen.queryByTitle("Örnek Banka dekontu, özgün görünüm")).not.toBeInTheDocument();
  });

  it("leads to the documents the e-mail brought", async () => {
    open(`/belgeler/${RECEIPT}`);
    const arrivals = await region("Nasıl geldi");
    const attachment = within(arrivals).getByRole("link", { name: "dekont.pdf" });
    expect(attachment).toHaveAttribute("href", `/belgeler/${"9".repeat(64)}`);
  });
});

describe("DocumentPage: a document no reader could read", () => {
  it("says why, and what the viewer could not show", async () => {
    open(`/belgeler/${LOCKED}`);
    expect(await screen.findByRole("heading", { level: 1, name: "sifreli.pdf" })).toBeInTheDocument();
    expect(screen.getByText("Okunamadı")).toBeInTheDocument();
    expect(screen.getByText("Bu belge okunamadı: PDF şifreli")).toBeInTheDocument();
    const viewer = await region("Belgenin kendisi");
    expect(await within(viewer).findByText("Belge gösterilemiyor: PDF şifreli")).toBeInTheDocument();
    expect(within(viewer).queryByRole("button", { name: "Yeniden dene" })).not.toBeInTheDocument(); // it would not help
    expect(within(await region("Okunan işlemler")).getByText("Bu belgeden işlem okunmadı.")).toBeInTheDocument();
  });
});

describe("DocumentPage: reading again and removing", () => {
  it("reads the document again and says what it is now", async () => {
    let read = "";
    server.use(
      http.post("/api/documents/:sha256/reparse", ({ params }) => {
        read = String(params["sha256"]);
        return HttpResponse.json({ status: "processed" });
      }),
    );
    const user = userEvent.setup();
    open(`/belgeler/${STATEMENT}`);
    await user.click(await screen.findByRole("button", { name: "Yeniden oku" }));
    expect(await screen.findByText("Belge yeniden okundu: İşlendi. Analiz arka planda yenileniyor.")).toBeInTheDocument();
    expect(read).toBe(STATEMENT);
  });

  it("says why a reading could not start", async () => {
    server.use(
      http.post("/api/documents/:sha256/reparse", () =>
        HttpResponse.json(
          { code: "documents_busy", title: "Belgeler şu an okunuyor; birazdan yeniden deneyin." },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    open(`/belgeler/${STATEMENT}`);
    await user.click(await screen.findByRole("button", { name: "Yeniden oku" }));
    expect(await screen.findByText("Belgeler şu an okunuyor; birazdan yeniden deneyin.")).toBeInTheDocument();
  });

  it("asks before moving the document to the Trash, and keeps it when the user says no", async () => {
    let removed = 0;
    server.use(
      http.post("/api/documents/:sha256/remove", () => {
        removed += 1;
        return HttpResponse.json({ trash: "iplikci" });
      }),
    );
    const user = userEvent.setup();
    const { location } = open(`/belgeler/${STATEMENT}`);
    await user.click(await screen.findByRole("button", { name: "Çöp kutusuna taşı" }));
    const ask = await screen.findByRole("alertdialog", { name: "Belge çöp kutusuna taşınsın mı?" });
    expect(ask).toHaveAccessibleDescription(
      "Örnek Kart Ekstresi Kasım 2026 sistemin çöp kutusuna gider; oradan geri alınabilir ve taşındığı denetim " +
        "kaydına yazılır. Bu belgeden okunan işlemler defterden çıkar.",
    );
    await user.click(within(ask).getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(removed).toBe(0);
    await user.click(screen.getByRole("button", { name: "Çöp kutusuna taşı" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Çöp kutusuna taşı" }));
    await waitFor(() => expect(location()).toBe("/belgeler"));
    expect(removed).toBe(1);
  });

  it("says in the question why the document could not be moved", async () => {
    server.use(
      http.post("/api/documents/:sha256/remove", () =>
        HttpResponse.json(
          { code: "documents_busy", title: "Belgeler şu an okunuyor; birazdan yeniden deneyin." },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    open(`/belgeler/${STATEMENT}`);
    await user.click(await screen.findByRole("button", { name: "Çöp kutusuna taşı" }));
    const ask = await screen.findByRole("alertdialog");
    await user.click(within(ask).getByRole("button", { name: "Çöp kutusuna taşı" }));
    expect(await within(ask).findByText("Belgeler şu an okunuyor; birazdan yeniden deneyin.")).toBeInTheDocument();
  });
});

describe("DocumentPage: a document that is not there", () => {
  it("says so and offers to try again", async () => {
    let missing = true;
    server.use(
      http.get("/api/documents/:sha256", () =>
        missing
          ? HttpResponse.json({ code: "document_missing", title: "Böyle bir belge yok ya da kaldırıldı." }, { status: 404 })
          : HttpResponse.json(STATEMENT_DETAIL),
      ),
    );
    const user = userEvent.setup();
    open(`/belgeler/${STATEMENT}`);
    expect(await screen.findByText("Böyle bir belge yok ya da kaldırıldı.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Belge" })).toBeInTheDocument();
    missing = false;
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Örnek Kart Ekstresi Kasım 2026" })).toBeInTheDocument();
  });
});
