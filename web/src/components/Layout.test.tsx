import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { stubSystemScheme } from "../test/media";
import { renderScreen } from "../test/render";
import { server } from "../test/server";
import { Layout } from "./Layout";
import { builtGroups, MENU, SETUP } from "./navigation";

const html = document.documentElement;

function menu() {
  return screen.getByRole("navigation", { name: "Ana menü" });
}

describe("Layout", () => {
  afterEach(() => {
    localStorage.clear();
    html.className = "";
    vi.unstubAllGlobals();
  });

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

  it("lists the screens built so far in their groups, setting up apart", () => {
    renderScreen(<Layout />);
    const expected: Record<string, string[]> = {
      Bugün: ["/", "/akis", "/yapilacaklar"],
      Para: ["/hesaplar", "/islemler", "/abonelikler", "/takvim", "/doviz"],
      Analiz: ["/degerlendirme", "/ay-sonu"],
      Arşiv: ["/belgeler", "/faturalar"],
      Uygulama: ["/bildirimler", "/kurallar", "/sistem"],
      Kurulum: ["/kurulum", "/kurulum/eklenti"],
    };
    const lists = within(menu()).getAllByRole("list");
    expect(lists.map(accessibleNameOf)).toEqual(Object.keys(expected));
    for (const [name, addresses] of Object.entries(expected)) {
      const links = within(within(menu()).getByRole("list", { name })).getAllByRole("link");
      expect(links.map((link) => link.getAttribute("href"))).toEqual(addresses);
    }
    // A screen that is not built yet has no way in.
    expect(within(menu()).queryByRole("link", { name: "Ayarlar" })).not.toBeInTheDocument();
  });

  it("shows every screen of a group once it is built", () => {
    const all = builtGroups(
      [...MENU, SETUP].map((group) => ({ ...group, screens: group.screens.map((s) => ({ ...s, ready: true })) })),
    );
    expect(all.map((group) => group.key)).toEqual(["today", "money", "analysis", "archive", "app", "setup"]);
    expect(all.flatMap((group) => group.screens).length).toBe(18);
  });

  it("marks the current screen for screen readers and with a bar", () => {
    renderScreen(<Layout />, { path: "/takvim" });
    const current = within(menu()).getByRole("link", { name: "Takvim" });
    expect(current).toHaveAttribute("aria-current", "page");
    expect(current.className).toContain("border-teal-700");
    expect(within(menu()).getByRole("link", { name: "Abonelikler" })).not.toHaveAttribute("aria-current");
  });

  it("lets the keyboard skip the menu to the screen's content", () => {
    renderScreen(<Layout />);
    const skip = screen.getByRole("link", { name: "İçeriğe geç" });
    expect(skip).toHaveAttribute("href", "#icerik");
    expect(screen.getByRole("main")).toHaveAttribute("id", "icerik");
  });

  it("opens and closes the menu with its button on narrow screens", async () => {
    renderScreen(<Layout />);
    const button = screen.getByRole("button", { name: "Menü" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAttribute("aria-controls", menu().id);
    expect(menu().className).toMatch(/(^| )hidden( |$)/);

    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(menu().className).not.toMatch(/(^| )hidden( |$)/);

    // Escape closes it and gives the focus back to the button.
    await userEvent.click(within(menu()).getByRole("link", { name: "Takvim" }));
    expect(button).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(button);
    within(menu()).getByRole("link", { name: "Sistem" }).focus();
    await userEvent.keyboard("{Escape}");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
  });

  it("switches the theme from the header and remembers it", async () => {
    stubSystemScheme(false);
    renderScreen(<Layout />);
    const theme = screen.getByRole("group", { name: "Tema" });
    expect(within(theme).getByRole("radio", { name: "Sistem" })).toBeChecked();
    expect(html).toHaveClass("light");

    await userEvent.click(within(theme).getByRole("radio", { name: "Koyu" }));
    expect(html).toHaveClass("dark");
    expect(localStorage.getItem("iplikci.theme")).toBe("dark");

    // The arrow keys move between the choices, as in any radio group.
    await userEvent.keyboard("{ArrowRight}");
    expect(within(theme).getByRole("radio", { name: "Sistem" })).toBeChecked();
    expect(html).toHaveClass("light");
  });

  it("switches between the simple and the detailed view from the header", async () => {
    renderScreen(<Layout />);
    const view = screen.getByRole("group", { name: "Görünüm" });
    expect(within(view).getByRole("radio", { name: "Sade" })).toBeChecked();
    await userEvent.click(within(view).getByRole("radio", { name: "Ayrıntılı" }));
    expect(within(view).getByRole("radio", { name: "Ayrıntılı" })).toBeChecked();
    expect(localStorage.getItem("iplikci.view")).toBe("detailed");
  });
});

function accessibleNameOf(element: HTMLElement): string {
  const id = element.getAttribute("aria-labelledby") ?? "";
  return document.getElementById(id)?.textContent ?? "";
}
