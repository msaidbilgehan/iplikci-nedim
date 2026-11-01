// The service as the interface's tests see it: MSW answers the API with synthetic data, nothing leaves the process.

import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { Bridge, DocumentPage, Labels, SystemStatus } from "../api/types";

export const LABELS: Labels = {
  DocumentStatus: { processed: "İşlendi", unprocessed: "İşlenmedi", unreadable: "Okunamadı", removed: "Kaldırıldı" },
  DocumentKind: { account_statement: "Hesap dökümü", card_statement: "Kart ekstresi", receipt: "Dekont" },
  SourceKind: { email: "E-posta", upload: "Yükleme", inbox: "Gelen klasörü", import: "İçe aktarma" },
};

export function systemStatus(overrides: Partial<SystemStatus> = {}): SystemStatus {
  return {
    service: { version: "0.4.0", started_at: "2026-11-01T07:30:00+00:00", pid: 4242, home: "/veri/iplikci" },
    documents: { processed: 3, unreadable: 1 },
    readers: [
      {
        parser: "teb.account_html",
        name: "TEB hesap hareketleri",
        version: "1.1",
        documents: 3,
        statements: 3,
        verified: 2,
        last_read: "2026-11-01T07:31:00+00:00",
        alarms: 0,
      },
    ],
    disk: { vault: 1536, database: 2 * 1024 * 1024, free: 50 * 1024 ** 3 },
    queue: { counts: { queued: 1, done: 9 }, next_run: "", failures: [] },
    mail: { connector: "imap", configured: true, last_run: "2026-11-01T07:45:00+00:00", last_error: "", stopped: false },
    backup: {
      last: "2026-11-01T00:30:00+00:00",
      next: "2026-11-02T00:30:00+00:00",
      count: 3,
      size: 10 * 1024 * 1024,
      rehearsal: "",
      rehearsal_ok: null,
    },
    ...overrides,
  };
}

export const FIRST_PAGE: DocumentPage = {
  items: [
    {
      sha256: "a".repeat(64),
      name: "TEB Hesap Dökümü Şubat 2026",
      file: "subat.xls",
      kind: "account_statement",
      parser: "teb.account_html",
      reader: "TEB hesap hareketleri",
      status: "processed",
      reason: "",
      verified: true,
      period_start: "2026-02-01",
      period_end: "2026-02-28",
      sources: ["upload"],
      added_at: "2026-11-01T07:31:00+00:00",
      size: 2048,
    },
    {
      sha256: "b".repeat(64),
      name: "sifreli.pdf",
      file: "sifreli.pdf",
      kind: "",
      parser: "",
      reader: "",
      status: "unreadable",
      reason: "PDF şifreli",
      verified: null,
      period_start: "",
      period_end: "",
      sources: ["email"],
      added_at: "2026-10-30T09:00:00+00:00",
      size: 4096,
    },
  ],
  next: "imlec-2",
};

export const SECOND_PAGE: DocumentPage = {
  items: [{ ...FIRST_PAGE.items[0]!, sha256: "c".repeat(64), name: "TEB Hesap Dökümü Ocak 2026", file: "ocak.xls" }],
  next: "",
};

export const BRIDGES: Bridge[] = [
  { id: "k1", name: "Chrome 140, macOS", created_at: "2026-11-01T08:00:00+00:00", last_seen: "", active: true },
];

export const handlers = [
  http.get("/api/labels", () => HttpResponse.json(LABELS)),
  http.get("/api/system", () => HttpResponse.json(systemStatus())),
  http.get("/api/bridge", () => HttpResponse.json(BRIDGES)),
  http.get("/api/documents", ({ request }) => {
    const url = new URL(request.url);
    if (url.searchParams.get("cursor") === "imlec-2") {
      return HttpResponse.json(SECOND_PAGE);
    }
    if (url.searchParams.getAll("status").includes("unreadable")) {
      return HttpResponse.json({ items: [FIRST_PAGE.items[1]], next: "" });
    }
    return HttpResponse.json(FIRST_PAGE);
  }),
];

export const server = setupServer(...handlers);
