import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it } from "vitest";

import type { Plan } from "../api/types";
import { renderScreen } from "../test/render";
import { ACCOUNT_LIST, FIRST_PAGE, LOCKED, server, STATEMENT } from "../test/server";
import DocumentPage from "./DocumentPage";
import DocumentsPage from "./DocumentsPage";

afterEach(() => localStorage.clear());

const PLAN: Plan = {
  plan_id: "p1",
  changes: 1,
  by_action: { "arşive alınacak": 1 },
  items: [
    {
      action: "processed",
      label: "arşive alınacak",
      name: "subat.xls",
      source: "subat.xls",
      reason: "",
      copyOf: "",
      target: "TEB Hesap Dökümü Şubat 2026",
      fromInbox: false,
      document: {
        kind: "hesap",
        account: "TEB vadesiz",
        start: "2026-02-01",
        end: "2026-02-28",
        rows: 12,
        verified: true,
        check: "bakiye 12/12 satır tutarlı",
      },
    },
  ],
};

const open = (path = "/belgeler") => renderScreen(<DocumentsPage />, { path });
const list = () => screen.findByRole("list", { name: "Saklanan belgeler, en yenisi önce" });
const card = async (name: string) => (await screen.findByRole("link", { name })).closest("li")!;

/** The list's requests, each as its query. */
function asked(): URLSearchParams[] {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get("/api/documents", ({ request }) => {
      seen.push(new URL(request.url).searchParams);
      return HttpResponse.json(FIRST_PAGE);
    }),
  );
  return seen;
}

describe("DocumentsPage: the archive", () => {
  it("lists the documents newest first with their kind, account, period, status and way, a page at a time", async () => {
    const user = userEvent.setup();
    open();
    const statement = await card("TEB Hesap Dökümü Şubat 2026");
    expect(within(statement).getByRole("link", { name: "TEB Hesap Dökümü Şubat 2026" })).toHaveAttribute(
      "href",
      `/belgeler/${ACCOUNT_LIST}`,
    );
    expect(
      within(statement).getByText("Hesap dökümü · TEB Vadesiz TL 123456789 · 01.02.2026 – 28.02.2026"),
    ).toBeInTheDocument();
    expect(within(statement).getByText("İşlendi")).toBeInTheDocument();
    expect(within(statement).getByText("01.11.2026 geldi · Yükleme")).toBeInTheDocument();
    const locked = await card("sifreli.pdf");
    expect(within(locked).getByText("Okunamadı")).toBeInTheDocument();
    expect(within(locked).getByText("Nedeni: PDF şifreli")).toBeInTheDocument();
    expect(within(locked).getByText("Türü bilinmiyor")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Daha eski belgeler" }));
    expect(await screen.findByRole("link", { name: "TEB Hesap Dökümü Ocak 2026" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Daha eski belgeler" })).not.toBeInTheDocument();
  });

  it("asks the service with the address's filters in the API's names, and shows each set filter as a chip", async () => {
    const seen = asked();
    open("/belgeler?kind=account_statement&q=%C5%9Fubat");
    await list();
    const query = seen.at(-1)!;
    expect(query.getAll("kind")).toEqual(["account_statement"]);
    expect(query.get("q")).toBe("şubat");
    expect(query.get("limit")).toBe("50");
    const chips = screen.getByRole("list", { name: "Etkin süzgeçler" });
    expect(within(chips).getByText("Hesap dökümü")).toBeInTheDocument();
    expect(within(chips).getByText("şubat")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Ara" })).toHaveValue("şubat");
  });

  it("narrows the list to the documents no reader took", async () => {
    const seen = asked();
    const user = userEvent.setup();
    const { location } = open();
    await list();
    await user.click(screen.getByRole("button", { name: "Tür: Tümü" }));
    const kinds = await screen.findByRole("dialog", { name: "Tür" });
    await user.click(within(kinds).getByRole("button", { name: "Hiçbiri" }));
    await user.click(within(kinds).getByRole("checkbox", { name: "Okuyucusu olmayan" }));
    await waitFor(() => expect(location()).toBe("/belgeler?kind=none"));
    await waitFor(() => expect(seen.at(-1)!.getAll("kind")).toEqual(["none"]));
  });

  it("sends a search once the typing pauses, keeping one entry in the address", async () => {
    const seen = asked();
    const user = userEvent.setup();
    const { location } = open();
    await list();
    await user.type(screen.getByRole("searchbox", { name: "Ara" }), "maaş");
    await waitFor(() => expect(location()).toBe("/belgeler?q=maa%C5%9F"));
    await waitFor(() => expect(seen.at(-1)!.get("q")).toBe("maaş"));
  });

  it("searches for several things at once with a comma, its parts named as alternatives", async () => {
    const seen = asked();
    open("/belgeler?q=maa%C5%9F%2Cekstre");
    await list();
    expect(seen.at(-1)!.get("q")).toBe("maaş,ekstre");
    expect(screen.getByRole("searchbox", { name: "Ara" })).toHaveAccessibleDescription(
      "Belgenin adı, başlığı ya da ondan okunan işlemler. Virgülle birkaçını birden arayın",
    );
    const chips = screen.getByRole("list", { name: "Etkin süzgeçler" });
    expect(within(chips).getByText("maaş veya ekstre")).toBeInTheDocument();
  });

  it("shows every value in the detailed view, the bank and the account apart", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    open();
    const table = await screen.findByRole("table", { name: "Saklanan belgeler, en yenisi önce" });
    const statement = within(table).getByRole("link", { name: "TEB Hesap Dökümü Şubat 2026" }).closest("tr")!;
    const cells = within(statement).getAllByRole("cell").map((cell) => cell.textContent);
    expect(cells).toEqual([
      "TEB Hesap Dökümü Şubat 2026subat.xls",
      "Hesap dökümüTEB hesap hareketleri",
      "TEB",
      "TEB Vadesiz TL 123456789",
      "01.02.2026 – 28.02.2026",
      "İşlendi",
      "Yükleme",
      "01.11.2026",
      "2,0 KB",
    ]);
  });
});

describe("DocumentsPage: what was not read", () => {
  it("opens the tab of what was not read, each with why, its original and a reading to try again", async () => {
    let read = "";
    server.use(
      http.post("/api/documents/:sha256/reparse", ({ params }) => {
        read = String(params["sha256"]);
        return HttpResponse.json({ status: "unreadable" });
      }),
    );
    const user = userEvent.setup();
    const { location } = open();
    await list();
    await user.click(screen.getByRole("radio", { name: "İşlenmeyenler ve okunamayanlar" }));
    expect(location()).toBe("/belgeler?status=unprocessed&status=unreadable");
    await waitFor(() => expect(screen.queryByRole("link", { name: "TEB Hesap Dökümü Şubat 2026" })).toBeNull());
    const locked = await card("sifreli.pdf");
    expect(within(locked).getByRole("link", { name: "Aslını indir: sifreli.pdf" })).toHaveAttribute(
      "href",
      `/api/documents/${LOCKED}/download`,
    );
    await user.click(within(locked).getByRole("button", { name: "Yeniden dene: sifreli.pdf" }));
    expect(await screen.findByText("sifreli.pdf yeniden okundu: Okunamadı.")).toBeInTheDocument();
    expect(read).toBe(LOCKED);
  });

  it("keeps a status a link narrowed the tab to, with a chip that widens it to the tab's", async () => {
    const user = userEvent.setup();
    const { location } = open("/belgeler?status=unreadable");
    await list();
    expect(screen.getByRole("radio", { name: "İşlenmeyenler ve okunamayanlar" })).toBeChecked();
    const chips = screen.getByRole("list", { name: "Etkin süzgeçler" });
    expect(within(chips).getByText("Okunamadı")).toBeInTheDocument();
    await user.click(within(chips).getByRole("button", { name: "Durum süzgecini kaldır" }));
    expect(location()).toBe("/belgeler?status=unprocessed&status=unreadable");
  });

  it("says when nothing is left unread", async () => {
    server.use(http.get("/api/documents", () => HttpResponse.json({ items: [], next: "" })));
    open("/belgeler?status=unprocessed&status=unreadable");
    expect(await screen.findByText("İşlenmeyen ya da okunamayan belge yok")).toBeInTheDocument();
  });
});

describe("DocumentsPage: its states", () => {
  it("says when no document matches, and takes the filters off", async () => {
    server.use(http.get("/api/documents", () => HttpResponse.json({ items: [], next: "" })));
    const user = userEvent.setup();
    const { location } = open("/belgeler?q=yok");
    expect(await screen.findByText("Bu süzgeçlerle belge yok")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Süzgeçleri sıfırla" }));
    expect(location()).toBe("/belgeler");
  });

  it("says the archive is empty and where documents come from", async () => {
    server.use(http.get("/api/documents", () => HttpResponse.json({ items: [], next: "" })));
    open();
    expect(await screen.findByText("Arşivde henüz belge yok")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tarayıcı eklentisini kur" })).toHaveAttribute("href", "/kurulum/eklenti");
  });

  it("says what was wrong with a filter the service refused, and takes it off", async () => {
    server.use(
      http.get("/api/documents", ({ request }) =>
        new URL(request.url).searchParams.has("kind")
          ? HttpResponse.json(
              { code: "filter_invalid", title: "Bilinmeyen belge durumu, türü ya da kaynağı." },
              { status: 400 },
            )
          : HttpResponse.json(FIRST_PAGE),
      ),
    );
    const user = userEvent.setup();
    const { location } = open("/belgeler?kind=boyle");
    expect(await screen.findByText("Bilinmeyen belge durumu, türü ya da kaynağı.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Süzgeçleri sıfırla" }));
    expect(location()).toBe("/belgeler");
    expect(await list()).toBeInTheDocument();
  });

  it("offers to try again when the list could not be read", async () => {
    let failing = true;
    server.use(
      http.get("/api/documents", () =>
        failing
          ? HttpResponse.json({ code: "busy", title: "Belgeler şu an okunuyor." }, { status: 503 })
          : HttpResponse.json(FIRST_PAGE),
      ),
    );
    const user = userEvent.setup();
    open();
    expect(await screen.findByText("Belgeler şu an okunuyor.")).toBeInTheDocument();
    failing = false;
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await list()).toBeInTheDocument();
  });

  it("says a document went to the Trash when its page sends the user back", async () => {
    server.use(http.post("/api/documents/:sha256/remove", () => HttpResponse.json({ trash: "iplikci" })));
    const user = userEvent.setup();
    const { location } = renderScreen(
      <Routes>
        <Route path="/belgeler" element={<DocumentsPage />} />
        <Route path="/belgeler/:id" element={<DocumentPage />} />
      </Routes>,
      { path: `/belgeler/${STATEMENT}` },
    );
    await user.click(await screen.findByRole("button", { name: "Çöp kutusuna taşı" }));
    const ask = await screen.findByRole("alertdialog", { name: "Belge çöp kutusuna taşınsın mı?" });
    await user.click(within(ask).getByRole("button", { name: "Çöp kutusuna taşı" }));
    expect(await screen.findByText("Örnek Kart Ekstresi Kasım 2026 çöp kutusuna taşındı.")).toBeInTheDocument();
    expect(location()).toBe("/belgeler");
  });
});

describe("DocumentsPage: adding documents", () => {
  it("uploads files, shows the plan and applies it only when confirmed", async () => {
    const sent: string[] = [];
    let applied = 0;
    server.use(
      http.post("/api/uploads", ({ request }) => {
        sent.push(decodeURIComponent(request.headers.get("x-filename") ?? ""));
        return HttpResponse.json({ batch: "0123456789abcdef", status: "eklendi", name: "subat.xls", reason: "" });
      }),
      http.post("/api/inbox/plan", async ({ request }) => {
        expect(await request.json()).toEqual({ upload: "0123456789abcdef" });
        return HttpResponse.json(PLAN);
      }),
      http.post("/api/inbox/apply", () => {
        applied += 1;
        return HttpResponse.json({ stored: 1, counts: { processed: 1 }, trash: null });
      }),
    );
    open();
    const file = new File(["sahte"], "şubat ekstresi.xls", { type: "application/vnd.ms-excel" });
    await userEvent.upload(screen.getByLabelText("Dosya seç", { selector: "input" }), file);
    expect(await screen.findByText("Plan: arşive alınacak: 1")).toBeInTheDocument();
    expect(screen.getByText("subat.xls → TEB Hesap Dökümü Şubat 2026")).toBeInTheDocument();
    expect(applied).toBe(0); // nothing goes in before the plan is confirmed
    await userEvent.click(screen.getByRole("button", { name: "Arşive al" }));
    expect(await screen.findByText("1 belge arşive alındı")).toBeInTheDocument();
    expect(sent).toEqual(["şubat ekstresi.xls"]);
    expect(applied).toBe(1);
  });

  it("makes the plan again when a file changed after it was shown", async () => {
    let plans = 0;
    server.use(
      http.post("/api/uploads", () =>
        HttpResponse.json({ batch: "0123456789abcdef", status: "eklendi", name: "a.xls", reason: "" }),
      ),
      http.post("/api/inbox/plan", () => {
        plans += 1;
        return HttpResponse.json({ ...PLAN, plan_id: `p${plans}` });
      }),
      http.post("/api/inbox/apply", () =>
        HttpResponse.json({ code: "plan_stale", title: "Plan eskidi." }, { status: 409 }),
      ),
    );
    open();
    await userEvent.upload(screen.getByLabelText("Dosya seç", { selector: "input" }), new File(["x"], "a.xls"));
    await userEvent.click(await screen.findByRole("button", { name: "Arşive al" }));
    expect(await screen.findByText("Plan yenilendi")).toBeInTheDocument();
    expect(plans).toBe(2);
  });

  it("names the files the service refused and why", async () => {
    server.use(
      http.post("/api/uploads", () =>
        HttpResponse.json({
          batch: "0123456789abcdef",
          status: "reddedildi",
          name: "notlar.txt",
          reason: "desteklenmeyen dosya türü",
        }),
      ),
      http.post("/api/inbox/plan", () => HttpResponse.json({ plan_id: "p0", changes: 0, by_action: {}, items: [] })),
    );
    open();
    await userEvent.upload(screen.getByLabelText("Dosya seç", { selector: "input" }), new File(["x"], "notlar.txt"), {
      applyAccept: false,
    });
    expect(await screen.findByText("1 dosya alınmadı")).toBeInTheDocument();
    expect(screen.getByText("notlar.txt: desteklenmeyen dosya türü")).toBeInTheDocument();
    expect(screen.getByText("Alınacak belge yok")).toBeInTheDocument();
  });
});
