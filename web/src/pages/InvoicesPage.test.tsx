import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { server } from "../test/server";
import { renderScreen } from "../test/render";
import InvoicesPage from "./InvoicesPage";

afterEach(() => localStorage.clear());

describe("InvoicesPage", () => {
  it("groups the bills and receipts by status, the pending ones first by when their row is due", async () => {
    renderScreen(<InvoicesPage />);
    expect(await screen.findByText("4 belge: 2 bekliyor, 1 eşleşmedi, 1 eşleşti.")).toBeInTheDocument();
    const groups = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
    expect(groups).toEqual(["Bekliyor", "Eşleşmedi", "Eşleşti"]);
    const pending = screen.getByRole("region", { name: "Bekliyor" });
    const [, first, second] = within(pending).getAllByRole("row");
    expect(first).toHaveTextContent("Örnekflix International B.V.");
    expect(within(first!).getByText("Makbuz")).toBeInTheDocument();
    expect(within(first!).getByText("9,99 USD")).toBeInTheDocument();
    expect(within(second!).getByText("Örnekenerji Elektrik Perakende Satış A.Ş.")).toBeInTheDocument();
    expect(within(second!).getByText("Fatura")).toBeInTheDocument();
    expect(within(second!).getByText("05.11.2026")).toBeInTheDocument();
    expect(within(second!).getByText("25.11.2026")).toBeInTheDocument();
    expect(within(second!).getByText("642,50 TL")).toBeInTheDocument();
    expect(within(second!).getByText("No: OE2026000000045")).toBeInTheDocument();
    expect(within(second!).getByText("05.11.2026 – 28.11.2026")).toBeInTheDocument(); // the days its row is looked for
  });

  it("marks the unmatched ones as information that changes no total, with what may explain them", async () => {
    renderScreen(<InvoicesPage />);
    const unmatched = await screen.findByRole("region", { name: "Eşleşmedi" });
    expect(within(unmatched).getByText("Bilgi — toplamlara girmez")).toBeInTheDocument();
    const phone = within(unmatched).getByText("ÖRNEKCELL İLETİŞİM HİZMETLERİ A.Ş.").closest("tr")!;
    expect(within(phone).getByText("412,90 TL")).toBeInTheDocument();
    expect(within(phone).getByText("bilgi — toplamlara girmez")).toBeInTheDocument();
    expect(within(phone).getByText("Başkası ödemiş olabilir.")).toBeInTheDocument();
    expect(within(phone).getByText("Henüz ödenmemiş olabilir.")).toBeInTheDocument();
    const matched = screen.getByRole("region", { name: "Eşleşti" });
    expect(within(matched).queryByText("bilgi — toplamlara girmez")).toBeNull();
  });

  it("shows the bank row that paid a matched one", async () => {
    renderScreen(<InvoicesPage />);
    const matched = await screen.findByRole("region", { name: "Eşleşti" });
    const receipt = within(matched).getByText("Örnek Uygulama Mağazası").closest("tr")!;
    expect(within(receipt).getByText("11.10.2026 · 59,99 TL")).toBeInTheDocument();
    expect(within(receipt).getByText("Örnek Kart •1234")).toBeInTheDocument();
    expect(within(receipt).getByText("ORNEKUYGULAMA.COM/BILL")).toBeInTheDocument();
    expect(within(receipt).getByText("—")).toBeInTheDocument(); // a receipt has no due date
  });

  it("names the pending bill due soonest and leads to the calendar", async () => {
    renderScreen(<InvoicesPage />);
    const sentence = "En yakın son ödeme 25.11.2026'da: Örnekenerji Elektrik Perakende Satış A.Ş., 642,50 TL.";
    expect(await screen.findByText(sentence)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Takvimi aç/ })).toHaveAttribute("href", "/takvim");
  });

  it("opens each bill in the viewer and a matched one's bank row in İşlemler", async () => {
    renderScreen(<InvoicesPage />);
    const matched = await screen.findByRole("region", { name: "Eşleşti" });
    const receipt = within(matched).getByText("Örnek Uygulama Mağazası").closest("tr")!;
    expect(within(receipt).getByRole("link", { name: "Örnek Uygulama Mağazası" })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/belgeler\/[0-9a-f]{64}$/),
    );
    expect(within(receipt).getByRole("link", { name: "11.10.2026 · 59,99 TL" })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/islemler\?satir=/),
    );
  });

  it("names each bill's file in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<InvoicesPage />);
    expect(await screen.findByText("Örnekenerji faturası.xml")).toBeInTheDocument();
  });

  it("opens the items a bill prints", async () => {
    renderScreen(<InvoicesPage />);
    const unmatched = await screen.findByRole("region", { name: "Eşleşmedi" });
    await userEvent.click(within(unmatched).getByText("2 kalem"));
    expect(within(unmatched).getByText("Aylık paket × 1 · 400,00 TL")).toBeVisible();
    expect(within(unmatched).getByText("Ek internet · 12,90 TL")).toBeVisible();
  });

  it("says where the senders are added when no bill came yet", async () => {
    server.use(
      http.get("/api/invoices", () =>
        HttpResponse.json({ items: [], counts: { pending: 0, unmatched: 0, matched: 0 } }),
      ),
    );
    renderScreen(<InvoicesPage />);
    expect(await screen.findByText("Henüz fatura ya da makbuz yok")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sistem" })).toHaveAttribute("href", "/sistem");
  });

  it("shows a placeholder while the list loads", () => {
    renderScreen(<InvoicesPage />);
    expect(screen.getByRole("status", { name: "Yükleniyor…" })).toBeInTheDocument();
  });

  it("offers to try again when the service fails", async () => {
    server.use(
      http.get("/api/invoices", () =>
        HttpResponse.json({ code: "busy", title: "Başka bir işlem belgeleri işliyor." }, { status: 503 }),
      ),
    );
    renderScreen(<InvoicesPage />);
    expect(await screen.findByText("Başka bir işlem belgeleri işliyor.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yeniden dene" })).toBeInTheDocument();
  });
});
