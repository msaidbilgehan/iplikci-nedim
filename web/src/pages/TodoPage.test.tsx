import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TodoItem, Todos } from "../api/types";
import { renderScreen } from "../test/render";
import { IGNORED_TODO, LABELS, server, TALIMAT, todo, TODOS } from "../test/server";
import TodoPage from "./TodoPage";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

const region = (name: string) => screen.findByRole("region", { name });
const NONE: Todos["counts"] = Object.fromEntries(Object.keys(TODOS.counts).map((kind) => [kind, 0]));

/** The list as the service keeps it: an item taken off leaves it, one put back returns; what was asked, in order. */
function serve(items: TodoItem[] = TODOS.items) {
  const changes: Array<{ key: string; ignored: boolean }> = [];
  let ignored = new Set<string>([IGNORED_TODO.key]);
  const all = [...items, IGNORED_TODO];
  server.use(
    http.get("/api/todos", ({ request }) => {
      const withIgnored = new URL(request.url).searchParams.get("with_ignored") === "true";
      const listed = all
        .map((item) => ({ ...item, ignored: ignored.has(item.key) }))
        .filter((item) => withIgnored || !item.ignored);
      const counts = { ...NONE };
      for (const item of all) {
        if (!ignored.has(item.key)) {
          counts[item.kind] = (counts[item.kind] ?? 0) + 1;
        }
      }
      return HttpResponse.json({ items: listed, counts, ignored: ignored.size } satisfies Todos);
    }),
    http.post("/api/todos/ignored", async ({ request }) => {
      const change = (await request.json()) as { key: string; ignored: boolean };
      changes.push(change);
      ignored = new Set(change.ignored ? [...ignored, change.key] : [...ignored].filter((key) => key !== change.key));
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return changes;
}

describe("TodoPage: the list", () => {
  it("waits for the list, then shows each kind with how much it matters, what it means and its items", async () => {
    serve();
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    expect(screen.getByRole("status", { name: "Yükleniyor…" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "Yapılacaklar" })).toBeInTheDocument();
    expect(
      await screen.findByText(
        "4 iş bekliyor: Kategorisiz işlemler (1), Eksik belge (1), İşlenmeyen belge (1), Uygulanamayan bölme (1).",
      ),
    ).toBeInTheDocument();
    const uncategorized = await region("Kategorisiz işlemler");
    expect(within(uncategorized).getByText("Bilgi")).toBeInTheDocument();
    expect(within(uncategorized).getByText(/^Hiçbir kuralın adlandırmadığı işyerleri/)).toBeInTheDocument();
    expect(within(uncategorized).getByRole("link", { name: "Örnek Kafe" })).toHaveAttribute(
      "href",
      "/islemler?category=Di%C4%9Fer+Harcamalar&q=%C3%96rnek+Kafe",
    );
    expect(within(uncategorized).getByText(/^5 işlem, toplam 2\.521,50 TL;/)).toBeInTheDocument();
    expect(within(uncategorized).getByRole("link", { name: "Kural ekle: Örnek Kafe" })).toHaveAttribute(
      "href",
      "/kurallar?isyeri=%C3%96rnek+Kafe",
    );
    expect(within(uncategorized).getByRole("button", { name: "Claude'a ver: Örnek Kafe" })).toBeInTheDocument();
    expect(within(uncategorized).getByRole("button", { name: "Yok say: Örnek Kafe" })).toBeInTheDocument();
    const split = await region("Uygulanamayan bölme");
    expect(within(split).getByText("Bakılmalı")).toBeInTheDocument();
    expect(within(split).getByRole("link", { name: "Göster: Örnek Süpermarket" })).toHaveAttribute(
      "href",
      `/islemler?satir=${TODOS.items[3]!.target}`,
    );
    const document = await region("İşlenmeyen belge");
    expect(within(document).getByRole("button", { name: "Yeniden oku: TalimatFormu.pdf" })).toBeInTheDocument();
    const behind = await region("Eksik belge");
    expect(within(behind).getByRole("button", { name: "Belge yükle: Örnek Vadesiz TL" })).toBeInTheDocument();
  });

  it("narrows the list to a kind from the address, and shows every kind again", async () => {
    serve();
    const user = userEvent.setup();
    const { location } = renderScreen(<TodoPage />, { path: "/yapilacaklar?tur=missing_documents" });
    expect(await region("Eksik belge")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Kategorisiz işlemler" })).not.toBeInTheDocument();
    const kinds = screen.getByRole("navigation", { name: "Türler" });
    expect(within(kinds).getByRole("link", { name: "Eksik belge (1)" })).toHaveAttribute("aria-current", "true");
    await user.click(within(kinds).getByRole("link", { name: "Tümü (4)" }));
    expect(location()).toBe("/yapilacaklar");
    expect(await region("Kategorisiz işlemler")).toBeInTheDocument();
  });

  it("says when a kind has nothing waiting", async () => {
    serve();
    renderScreen(<TodoPage />, { path: "/yapilacaklar?tur=format_alarm" });
    expect(await screen.findByText("Bu türde bekleyen iş yok")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bütün işleri göster" })).toBeInTheDocument();
  });

  it("says when nothing waits at all", async () => {
    server.use(http.get("/api/todos", () => HttpResponse.json({ items: [], counts: NONE, ignored: 0 })));
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    expect(await screen.findByText("Yapılacak bir şey yok")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Türler" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yok sayılanları göster" })).not.toBeInTheDocument();
  });

  it("says the list could not be loaded and asks again", async () => {
    let asked = 0;
    server.use(
      http.get("/api/todos", () => {
        asked += 1;
        return asked === 1
          ? HttpResponse.json({ code: "documents_busy", title: "Belgeler şu an okunuyor." }, { status: 409 })
          : HttpResponse.json(TODOS);
      }),
    );
    const user = userEvent.setup();
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    expect(await screen.findByText("Belgeler şu an okunuyor.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await region("Kategorisiz işlemler")).toBeInTheDocument();
  });

  it("shows a kind this version does not know by its label, leaving out a step it cannot take", async () => {
    const future = todo({ key: "yeni:1", kind: "unverified_statement", actions: ["open", "ignore"] });
    const unknown = { ...future, kind: "future_kind", actions: ["future_step", "ignore"] } as unknown as TodoItem;
    serve([unknown]);
    server.use(
      http.get("/api/labels", () =>
        HttpResponse.json({ ...LABELS, TodoKind: { ...LABELS["TodoKind"], future_kind: "Gelecekteki tür" } }),
      ),
    );
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    const group = await region("Gelecekteki tür");
    expect(within(group).getByText("Bilgi")).toBeInTheDocument();
    expect(within(group).getByRole("button", { name: "Yok say: Örnek Kafe" })).toBeInTheDocument();
    expect(within(group).getAllByRole("button")).toHaveLength(1); // the unknown step is left out
  });

  it("lists every column in the detailed view, with the request for Claude", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    serve();
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    const table = await screen.findByRole("table", { name: "Kategorisiz işlemler: bekleyen işler" });
    const row = within(table).getByRole("link", { name: "Örnek Kafe" }).closest("tr")!;
    expect(within(row).getByText("5")).toBeInTheDocument();
    expect(within(row).getByText("−2.521,50 TL")).toBeInTheDocument();
    expect(within(row).getByText("Örnek Kafe", { selector: "code" })).toBeInTheDocument();
    expect(within(row).getByText("Claude'a verilecek istek")).toBeInTheDocument();
    expect(screen.queryByText(/^4 iş bekliyor/)).not.toBeInTheDocument(); // the simple view's sentence
  });
});

describe("TodoPage: the steps", () => {
  it("takes an item off the list, says so, and puts it back on undo", async () => {
    const changes = serve();
    const user = userEvent.setup();
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    const uncategorized = await region("Kategorisiz işlemler");
    await user.click(within(uncategorized).getByRole("button", { name: "Yok say: Örnek Kafe" }));
    const done = await screen.findByText("“Örnek Kafe” listeden çıkarıldı.");
    expect(changes).toEqual([{ key: "uncategorized:ornek kafe", ignored: true }]);
    await waitFor(() => expect(screen.queryByRole("region", { name: "Kategorisiz işlemler" })).not.toBeInTheDocument());
    await waitFor(() => expect(done.closest("[tabindex]")).toHaveFocus()); // its button left with it
    expect(screen.getByText("2 iş yok sayıldı.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Geri al" }));
    expect(await screen.findByText("“Örnek Kafe” listeye geri alındı.")).toBeInTheDocument();
    expect(changes.at(-1)).toEqual({ key: "uncategorized:ornek kafe", ignored: false });
    expect(await region("Kategorisiz işlemler")).toBeInTheDocument();
  });

  it("lists what was taken off when asked, and puts one back", async () => {
    const changes = serve();
    const user = userEvent.setup();
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    expect(await screen.findByText("1 iş yok sayıldı.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yok sayılanları göster" }));
    const restore = await screen.findByRole("button", { name: "Listeye geri al: Eski Kitapçı" });
    expect(within(restore.closest("li")!).getByText("Yok sayıldı")).toBeInTheDocument();
    await user.click(restore);
    expect(await screen.findByText("“Eski Kitapçı” listeye geri alındı.")).toBeInTheDocument();
    expect(changes).toEqual([{ key: IGNORED_TODO.key, ignored: false }]);
    expect(screen.getByRole("button", { name: "Yok sayılanları göster" })).toHaveAttribute("aria-pressed", "true");
  });

  it("reads a document again and says what it is now", async () => {
    serve();
    const asked: string[] = [];
    server.use(
      http.post("/api/documents/:sha256/reparse", ({ params }) => {
        asked.push(String(params["sha256"]));
        return HttpResponse.json({ status: "processed" });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    await user.click(await screen.findByRole("button", { name: "Yeniden oku: TalimatFormu.pdf" }));
    expect(await screen.findByText("“TalimatFormu.pdf” yeniden okundu: İşlendi.")).toBeInTheDocument();
    expect(asked).toEqual([TALIMAT]);
  });

  it("says beside the item why it could not be read again", async () => {
    serve();
    server.use(
      http.post("/api/documents/:sha256/reparse", () =>
        HttpResponse.json(
          { code: "documents_busy", title: "Belgeler şu an okunuyor; birazdan yeniden deneyin." },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    const document = await region("İşlenmeyen belge");
    await user.click(within(document).getByRole("button", { name: "Yeniden oku: TalimatFormu.pdf" }));
    expect(await within(document).findByText("Belgeler şu an okunuyor; birazdan yeniden deneyin.")).toBeInTheDocument();
  });

  it("copies the request for Claude", async () => {
    serve();
    const user = userEvent.setup();
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    await user.click(await screen.findByRole("button", { name: "Claude'a ver: Örnek Kafe" }));
    expect(await screen.findByText("İstek panoya kopyalandı: Claude'a yapıştırın.")).toBeInTheDocument();
    expect(await navigator.clipboard.readText()).toBe(TODOS.items[0]!.prompt);
  });

  it("shows the request to copy by hand when the clipboard refuses", async () => {
    serve();
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("izin yok"));
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    await user.click(await screen.findByRole("button", { name: "Claude'a ver: Örnek Kafe" }));
    expect(await screen.findByText("İstek panoya kopyalanamadı; aşağıdan seçip kopyalayın.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Claude'a verilecek istek" })).toHaveValue(TODOS.items[0]!.prompt);
  });

  it("opens the upload panel for an account behind, and gives the focus back on closing", async () => {
    serve();
    const user = userEvent.setup();
    renderScreen(<TodoPage />, { path: "/yapilacaklar" });
    const upload = await screen.findByRole("button", { name: "Belge yükle: Örnek Vadesiz TL" });
    await user.click(upload);
    const panel = await screen.findByRole("dialog", { name: "Belge yükle" });
    expect(within(panel).getByText(/^Örnek Vadesiz TL: Son hesap hareketleri/)).toBeInTheDocument();
    expect(within(panel).getByRole("region", { name: "Belge ekle" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(upload).toHaveFocus();
  });
});
