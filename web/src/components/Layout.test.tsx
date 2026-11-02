import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { renderScreen } from "../test/render";
import { Layout } from "./Layout";

describe("Layout", () => {
  it("shows beside Bildirimler how many notifications are not seen yet, in words for screen readers too", async () => {
    renderScreen(<Layout />);
    const link = await screen.findByRole("link", { name: "Bildirimler (2 okunmamış)" });
    expect(link).toHaveAttribute("href", "/bildirimler");
    expect(within(link).getByText("2")).toHaveAttribute("aria-hidden", "true");
  });

  it("shows no count once every notification is seen", async () => {
    let asked = 0;
    server.use(
      http.get("/api/notifications", () => {
        asked += 1;
        return HttpResponse.json({ items: [], unread: 0 });
      }),
    );
    renderScreen(<Layout />);
    await waitFor(() => expect(asked).toBe(1));
    expect(screen.getByRole("link", { name: "Bildirimler" })).toBeInTheDocument();
  });
});
