import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { McpMasking } from "../api/types";
import { renderScreen } from "../test/render";
import { MCP_CONNECTION, server } from "../test/server";
import ClaudePage from "./ClaudePage";

describe("ClaudePage", () => {
  it("gives Claude Code's configuration with claude-SAK's steps, and no token in it", async () => {
    renderScreen(<ClaudePage />);
    const card = await screen.findByRole("region", {
      name: "Claude Code'a ekleyin",
    });
    expect(within(card).getAllByRole("listitem")).toHaveLength(4);
    expect(
      within(card).getByText(/Import \/ Export sekmesinde kaynak olarak “MCP JSON”u/),
    ).toBeInTheDocument();
    expect(
      within(card).getByText(/Profiles'ta “All profiles”u seçin; proje seçmeyin/),
    ).toBeInTheDocument();
    const config = within(card).getByText(/"headersHelper"/);
    expect(config.textContent).toContain('"url": "http://127.0.0.1:8643/mcp"');
    expect(
      within(card).getByRole("button", {
        name: "Kopyala: Claude Code ve claude-SAK yapılandırması",
      }),
    ).toBeEnabled();
    expect(within(card).getByText(/belirteç yok/)).toBeInTheDocument();
  });

  it("gives Claude Desktop's configuration and says it only reads while the service is down", async () => {
    renderScreen(<ClaudePage />);
    const card = await screen.findByRole("region", {
      name: "Claude Desktop'a ekleyin",
    });
    expect(within(card).getByText(/"--klasor"/)).toBeInTheDocument();
    expect(within(card).getByText(/yalnızca okuyabilir/)).toBeInTheDocument();
  });

  it("shows the token only when asked, and hides it again", async () => {
    server.use(
      http.post("/api/mcp/token", () =>
        HttpResponse.json({ token: "ornek-belirtec" }),
      ),
    );
    renderScreen(<ClaudePage />);
    const card = await screen.findByRole("region", {
      name: "Adres ve belirteç",
    });
    expect(
      within(card).getByText("http://127.0.0.1:8643/mcp"),
    ).toBeInTheDocument();
    expect(within(card).queryByText("ornek-belirtec")).not.toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "Göster" }));
    expect(await within(card).findByText("ornek-belirtec")).toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "Gizle" }));
    expect(within(card).queryByText("ornek-belirtec")).not.toBeInTheDocument();
  });

  it("saves what MCP's answers hide", async () => {
    const asked: McpMasking[] = [];
    server.use(
      http.put("/api/mcp/masking", async ({ request }) => {
        const { masking } = (await request.json()) as { masking: McpMasking };
        asked.push(masking);
        return HttpResponse.json({ ...MCP_CONNECTION, masking });
      }),
    );
    renderScreen(<ClaudePage />);
    const group = await screen.findByRole("group", {
      name: "Claude'dan gizlenecekler",
    });
    expect(
      within(group).getByRole("radio", { name: /Hiçbir şey gizlenmesin/ }),
    ).toBeChecked();
    await userEvent.click(
      within(group).getByRole("radio", {
        name: /Hesap numaraları ve kişi adları gizlensin/,
      }),
    );
    expect(
      await screen.findByText("Kaydedildi: bundan sonraki yanıtlar böyle."),
    ).toBeInTheDocument();
    expect(asked).toEqual(["accounts_and_names"]);
    expect(
      within(group).getByRole("radio", {
        name: /Hesap numaraları ve kişi adları gizlensin/,
      }),
    ).toBeChecked();
  });

  it("says when the connection cannot be loaded", async () => {
    server.use(
      http.get("/api/mcp/connection", () =>
        HttpResponse.json({ title: "olmadı" }, { status: 500 }),
      ),
    );
    renderScreen(<ClaudePage />);
    expect(
      await screen.findByRole("button", { name: "Yeniden dene" }),
    ).toBeInTheDocument();
  });
});
