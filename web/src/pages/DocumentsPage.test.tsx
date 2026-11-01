import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { Plan } from "../api/types";
import { server } from "../test/server";
import { renderScreen } from "../test/render";
import DocumentsPage from "./DocumentsPage";

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
      document: { kind: "hesap", account: "TEB vadesiz", start: "2026-02-01", end: "2026-02-28" },
    },
  ],
};

describe("DocumentsPage", () => {
  it("lists the documents with their labels, newest first, a page at a time", async () => {
    renderScreen(<DocumentsPage />);
    const statement = (await screen.findByText("TEB Hesap Dökümü Şubat 2026")).closest("tr")!;
    expect(within(statement).getByText("Hesap dökümü")).toBeInTheDocument();
    expect(within(statement).getByText("01.02.2026 – 28.02.2026")).toBeInTheDocument();
    expect(within(statement).getByText("İşlendi")).toBeInTheDocument();
    expect(within(statement).getByText("Yükleme")).toBeInTheDocument();
    const locked = screen.getByText("sifreli.pdf").closest("tr")!;
    expect(within(locked).getByText("Okunamadı")).toBeInTheDocument();
    expect(within(locked).getByText("PDF şifreli")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Daha eski belgeler" }));
    expect(await screen.findByText("TEB Hesap Dökümü Ocak 2026")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Daha eski belgeler" })).not.toBeInTheDocument();
  });

  it("narrows the list to what was not processed and to a search", async () => {
    renderScreen(<DocumentsPage />);
    await screen.findByText("TEB Hesap Dökümü Şubat 2026");
    await userEvent.click(screen.getByRole("button", { name: "İşlenmeyenler ve okunamayanlar" }));
    expect(await screen.findByText("sifreli.pdf")).toBeInTheDocument();
    expect(screen.queryByText("TEB Hesap Dökümü Şubat 2026")).not.toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox", { name: "Ara" }), "yok böyle");
    expect(await screen.findByText("Bu aramayla belge yok")).toBeInTheDocument();
  });

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
    renderScreen(<DocumentsPage />);
    const file = new File(["sahte"], "şubat ekstresi.xls", { type: "application/vnd.ms-excel" });
    await userEvent.upload(screen.getByLabelText("Dosya seç", { selector: "input" }), file);
    expect(await screen.findByText("Plan: arşive alınacak: 1")).toBeInTheDocument();
    expect(screen.getByText("subat.xls → TEB Hesap Dökümü Şubat 2026")).toBeInTheDocument();
    expect(applied).toBe(0); // nothing goes in before the plan is confirmed
    await userEvent.click(screen.getByRole("button", { name: "Planı uygula" }));
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
    renderScreen(<DocumentsPage />);
    await userEvent.upload(screen.getByLabelText("Dosya seç", { selector: "input" }), new File(["x"], "a.xls"));
    await userEvent.click(await screen.findByRole("button", { name: "Planı uygula" }));
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
    renderScreen(<DocumentsPage />);
    await userEvent.upload(screen.getByLabelText("Dosya seç", { selector: "input" }), new File(["x"], "notlar.txt"), {
      applyAccept: false,
    });
    expect(await screen.findByText("1 dosya alınmadı")).toBeInTheDocument();
    expect(screen.getByText("notlar.txt: desteklenmeyen dosya türü")).toBeInTheDocument();
    expect(screen.getByText("Alınacak belge yok")).toBeInTheDocument();
  });
});
