import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { server, systemStatus } from "../test/server";
import { renderScreen } from "../test/render";
import ExtensionPage from "./ExtensionPage";

describe("ExtensionPage", () => {
  it("shows a one-time pairing code with its time to live", async () => {
    server.use(http.post("/api/bridge/pairings", () => HttpResponse.json({ code: "ABCDEFGH", expires_in: 600 })));
    renderScreen(<ExtensionPage />);
    await userEvent.click(screen.getByRole("button", { name: "Eşleştirme kodu al" }));
    expect(await screen.findByText("ABCD-EFGH")).toBeInTheDocument();
    expect(screen.getByText("Tek kullanımlık; 10 dakika içinde girin.")).toBeInTheDocument();
  });

  it("lists the paired extensions and revokes one after asking", async () => {
    const revoked: string[] = [];
    server.use(
      http.delete("/api/bridge/:id", ({ params }) => {
        revoked.push(String(params["id"]));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const ask = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    renderScreen(<ExtensionPage />);
    expect(await screen.findByText("Chrome 140, macOS")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "İptal et" }));
    expect(revoked).toEqual([]); // the user said no
    await userEvent.click(screen.getByRole("button", { name: "İptal et" }));
    expect(ask).toHaveBeenCalledTimes(2);
    await vi.waitFor(() => expect(revoked).toEqual(["k1"]));
  });

  it("says when the paired extension has not scanned the history yet", async () => {
    const mail = { ...systemStatus().mail, connector: "browser_bridge" as const, history_due: true };
    server.use(http.get("/api/system", () => HttpResponse.json(systemStatus({ mail }))));
    renderScreen(<ExtensionPage />);
    expect(await screen.findByText("Geçmiş iletilerin taraması tamamlanmadı")).toBeInTheDocument();
  });
});
