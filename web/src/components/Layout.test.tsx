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

function addressesIn(list: HTMLElement): Array<string | null> {
  return within(list).getAllByRole("link").map((link) => link.getAttribute("href"));
}

/** The detailed view, chosen before the screen opens as the display panel would have saved it. */
function chooseDetailed() {
  localStorage.setItem("iplikci.view", "detailed");
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

  it("lists the everyday screens first in the simple view and folds the others under Diğer ekranlar", async () => {
    renderScreen(<Layout />);
    const everyday = within(menu()).getByRole("list", { name: "Sık kullanılan ekranlar" });
    expect(addressesIn(everyday)).toEqual([
      "/",
      "/hesaplar",
      "/islemler",
      "/abonelikler",
      "/takvim",
      "/degerlendirme",
      "/yapilacaklar",
      "/belge-ekle",
    ]);
    const rules = within(menu()).getByRole("link", { name: "Kurallar" });
    expect(rules).not.toBeVisible();

    await userEvent.click(within(menu()).getByText("Diğer ekranlar"));
    expect(rules).toBeVisible();
    const groups = within(menu())
      .getAllByRole("list")
      .filter((list) => list !== everyday);
    expect(groups.map(accessibleNameOf)).toEqual(["Bugün", "Para", "Analiz", "Arşiv", "Uygulama", "Kurulum"]);
    expect(groups.map(addressesIn)).toEqual([
      ["/akis"],
      ["/doviz"],
      ["/ay-sonu"],
      ["/belgeler", "/faturalar"],
      ["/bildirimler", "/kurallar", "/ayarlar", "/sistem"],
      ["/kurulum", "/kurulum/eklenti"],
    ]);
  });

  it("opens Diğer ekranlar by itself while one of its screens is shown, so the current screen stays in sight", () => {
    renderScreen(<Layout />, { path: "/kurallar" });
    const current = within(menu()).getByRole("link", { name: "Kurallar" });
    expect(current).toBeVisible();
    expect(current).toHaveAttribute("aria-current", "page");
  });

  it("says on Diğer ekranlar how many notifications are not seen yet while Bildirimler is folded inside", async () => {
    renderScreen(<Layout />);
    const more = within(menu()).getByText("Diğer ekranlar");
    expect(await within(more).findByText("(2 okunmamış)")).toBeInTheDocument();
    expect(within(more).getByText("2")).toHaveAttribute("aria-hidden", "true");
  });

  it("lists every screen built so far in its group in the detailed view, setting up apart", () => {
    chooseDetailed();
    renderScreen(<Layout />);
    const expected: Record<string, string[]> = {
      Bugün: ["/", "/akis", "/yapilacaklar"],
      Para: ["/hesaplar", "/islemler", "/abonelikler", "/takvim", "/doviz"],
      Analiz: ["/degerlendirme", "/ay-sonu"],
      Arşiv: ["/belge-ekle", "/belgeler", "/faturalar"],
      Uygulama: ["/bildirimler", "/kurallar", "/ayarlar", "/sistem"],
      Kurulum: ["/kurulum", "/kurulum/eklenti"],
    };
    const lists = within(menu()).getAllByRole("list");
    expect(lists.map(accessibleNameOf)).toEqual(Object.keys(expected));
    for (const [name, addresses] of Object.entries(expected)) {
      expect(addressesIn(within(menu()).getByRole("list", { name }))).toEqual(addresses);
    }
    expect(within(menu()).queryByText("Diğer ekranlar")).not.toBeInTheDocument();
  });

  it("leaves out a screen that is not built yet, and a group with none built", () => {
    const groups = builtGroups(
      MENU.map((group) => ({
        ...group,
        screens: group.screens.map((s) => ({ ...s, ready: s.key !== "settings" && group.key !== "analysis" })),
      })),
    );
    expect(groups.flatMap((group) => group.screens).map((s) => s.key)).not.toContain("settings");
    expect(groups.map((group) => group.key)).toEqual(["today", "money", "archive", "app"]);
  });

  it("shows every screen of a group once it is built", () => {
    const all = builtGroups(
      [...MENU, SETUP].map((group) => ({ ...group, screens: group.screens.map((s) => ({ ...s, ready: true })) })),
    );
    expect(all.map((group) => group.key)).toEqual(["today", "money", "analysis", "archive", "app", "setup"]);
    expect(all.flatMap((group) => group.screens).length).toBe(19);
  });

  it("marks the current screen for screen readers and with a bar", () => {
    renderScreen(<Layout />, { path: "/takvim" });
    const current = within(menu()).getByRole("link", { name: "Takvim" });
    expect(current).toHaveAttribute("aria-current", "page");
    expect(current.className).toContain("before:bg-teal-700");
    expect(within(menu()).getByRole("link", { name: "Düzenli ödemeler" })).not.toHaveAttribute("aria-current");
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
    within(menu()).getByRole("link", { name: "Hesaplar" }).focus();
    await userEvent.keyboard("{Escape}");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
  });

  it("leads from the header's bell to the notification box, saying how many are not seen yet", async () => {
    renderScreen(<Layout />);
    const bell = await screen.findByRole("link", { name: "Bildirim kutusu (2 okunmamış)" });
    expect(bell).toHaveAttribute("href", "/bildirimler");
  });

  it("switches the theme from the header's display panel and remembers it", async () => {
    stubSystemScheme(false);
    renderScreen(<Layout />);
    await userEvent.click(screen.getByRole("button", { name: "Görünüm: Sade" }));
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

  it("switches between the simple and the detailed view from the header, naming the view on its button", async () => {
    renderScreen(<Layout />);
    await userEvent.click(screen.getByRole("button", { name: "Görünüm: Sade" }));
    const view = screen.getByRole("group", { name: "Görünüm" });
    expect(within(view).getByRole("radio", { name: "Sade" })).toBeChecked();
    await userEvent.click(within(view).getByRole("radio", { name: "Ayrıntılı" }));
    expect(within(view).getByRole("radio", { name: "Ayrıntılı" })).toBeChecked();
    expect(localStorage.getItem("iplikci.view")).toBe("detailed");
    expect(screen.getByRole("button", { name: "Görünüm: Ayrıntılı" })).toBeInTheDocument();
  });
});

function accessibleNameOf(element: HTMLElement): string {
  const id = element.getAttribute("aria-labelledby") ?? "";
  return document.getElementById(id)?.textContent ?? "";
}
