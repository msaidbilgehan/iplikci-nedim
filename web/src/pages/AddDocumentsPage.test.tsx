import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { Plan } from "../api/types";
import { renderScreen } from "../test/render";
import { server } from "../test/server";
import AddDocumentsPage from "./AddDocumentsPage";

const BATCH = "0123456789abcdef";

/** Two downloads with names that say nothing, both known by their content. */
const PLAN: Plan = {
  plan_id: "p1",
  changes: 2,
  by_action: { "arşive alınacak": 1, "zaten arşivde": 1 },
  items: [
    {
      action: "processed",
      label: "arşive alınacak",
      name: "Belge-2026-10-31.xls",
      source: "bankalar/Belge-2026-10-31.xls",
      reason: "",
      copyOf: "",
      target: "2025-10-31 - 2026-10-31 Garanti Vadesiz TL Hesap Hareketleri.xls",
      fromInbox: false,
      document: {
        kind: "hesap",
        account: "Garanti Vadesiz TL",
        start: "2025-10-31",
        end: "2026-10-31",
        rows: 120,
        verified: true,
        check: "bakiye 120/120 satır tutarlı",
      },
    },
    {
      action: "known",
      label: "zaten arşivde",
      name: "EKSTRE (3).pdf",
      source: "bankalar/QNB/EKSTRE (3).pdf",
      reason: "",
      copyOf: null,
      target: null,
      fromInbox: false,
      document: null,
    },
  ],
};

/** A file as a chosen folder gives it: with its place in the folder beside it. */
function inFolder(path: string, body = "sahte"): File {
  const file = new File([body], path.split("/").at(-1) ?? path);
  Object.defineProperty(file, "webkitRelativePath", { value: path });
  return file;
}

/** The service's side of a batch: the names it was sent, and a plan that waits until the test lets it go. */
function service() {
  const sent: string[] = [];
  let letPlanGo = () => {};
  const planned = new Promise<void>((resolve) => {
    letPlanGo = resolve;
  });
  server.use(
    http.post("/api/uploads", ({ request }) => {
      const name = decodeURIComponent(request.headers.get("x-filename") ?? "");
      sent.push(name);
      return HttpResponse.json({ batch: BATCH, status: "eklendi", name, reason: "" });
    }),
    http.post("/api/inbox/plan", async () => {
      await planned;
      return HttpResponse.json(PLAN);
    }),
    http.post("/api/inbox/apply", () =>
      HttpResponse.json({ stored: 1, counts: { processed: 1, known: 1 }, trash: null }),
    ),
  );
  return { sent, letPlanGo };
}

describe("AddDocumentsPage", () => {
  it("is the place for documents downloaded by hand: a folder or files, and how it goes", async () => {
    renderScreen(<AddDocumentsPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Belge ekle" })).toBeInTheDocument();
    const panel = screen.getByRole("region", { name: "Klasör ya da dosya seçin" });
    expect(within(panel).getByRole("button", { name: "Klasör seç" })).toBeInTheDocument();
    expect(within(panel).getByText(/Dosya ve klasör adları önemli değil/)).toBeInTheDocument();
    const how = screen.getByRole("region", { name: "Nasıl?" });
    expect(within(how).getAllByRole("listitem")).toHaveLength(4);
    expect(within(how).getByRole("link", { name: "Tarayıcı eklentisi" })).toHaveAttribute("href", "/kurulum/eklenti");
  });

  it("sends a chosen folder's files with their places in it, leaving its hidden files out", async () => {
    const { sent, letPlanGo } = service();
    renderScreen(<AddDocumentsPage />);
    await userEvent.upload(screen.getByLabelText("Klasör seç", { selector: "input" }), [
      inFolder("bankalar/Belge-2026-10-31.xls"),
      inFolder("bankalar/.DS_Store"),
      inFolder("bankalar/QNB/EKSTRE (3).pdf"),
    ]);
    expect(await screen.findByText("2 dosya okunuyor: her birinin ne olduğu içeriğinden anlaşılıyor…")).toHaveAttribute(
      "role",
      "status",
    );
    letPlanGo();
    expect(await screen.findByText(/Belge-2026-10-31\.xls → 2025-10-31 - 2026-10-31 Garanti/)).toBeInTheDocument();
    expect(sent).toEqual(["bankalar/Belge-2026-10-31.xls", "bankalar/QNB/EKSTRE (3).pdf"]);
  });

  it("takes a dropped folder whole, the files inside its folders too", async () => {
    const { sent, letPlanGo } = service();
    letPlanGo();
    renderScreen(<AddDocumentsPage />);
    const zone = screen.getByText(/Bankadan indirdiğiniz belgeleri buraya bırakın/).closest("div")!;
    fireEvent.drop(zone, { dataTransfer: { items: [{ webkitGetAsEntry: () => folder("/bankalar") }], files: [] } });
    expect(await screen.findByText("Plan: arşive alınacak: 1 · zaten arşivde: 1")).toBeInTheDocument();
    expect(sent).toEqual(["bankalar/Belge-2026-10-31.xls", "bankalar/QNB/EKSTRE (3).pdf"]);
  });

  it("says what was kept and what the archive had already, and leads on", async () => {
    const { letPlanGo } = service();
    letPlanGo();
    renderScreen(<AddDocumentsPage />);
    await userEvent.upload(screen.getByLabelText("Dosya seç", { selector: "input" }), new File(["x"], "a.xls"));
    await userEvent.click(await screen.findByRole("button", { name: "Arşive al" }));
    expect(await screen.findByText("1 belge arşive alındı")).toBeInTheDocument();
    expect(screen.getByText("1 belge zaten arşivdeydi; yeni bir kez sayılmadı.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Belgelere bak" })).toHaveAttribute("href", "/belgeler");
    expect(screen.getByRole("link", { name: "Pano'ya dön" })).toHaveAttribute("href", "/");
  });
});

// A dropped folder as the browser gives it: entries read a part at a time, the last part empty.

function file(path: string): FileSystemFileEntry {
  const name = path.split("/").at(-1) ?? path;
  return {
    isFile: true,
    isDirectory: false,
    name,
    fullPath: path,
    file: (done: (f: File) => void) => done(new File(["sahte"], name)),
  } as unknown as FileSystemFileEntry; // only what the panel reads of an entry
}

/** What each folder of the dropped one holds: a file, a hidden file and a folder with one more file in it. */
const TREE: Record<string, string[]> = {
  "/bankalar": ["/bankalar/Belge-2026-10-31.xls", "/bankalar/.DS_Store", "/bankalar/QNB"],
  "/bankalar/QNB": ["/bankalar/QNB/EKSTRE (3).pdf"],
};

function folder(path: string): FileSystemDirectoryEntry {
  return {
    isFile: false,
    isDirectory: true,
    name: path.split("/").at(-1) ?? path,
    fullPath: path,
    createReader: () => {
      let given = false;
      return {
        readEntries: (done: (entries: FileSystemEntry[]) => void) => {
          done(given ? [] : (TREE[path] ?? []).map((child) => (child in TREE ? folder(child) : file(child))));
          given = true;
        },
      };
    },
  } as unknown as FileSystemDirectoryEntry; // only what the panel reads of an entry
}
