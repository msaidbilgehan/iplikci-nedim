import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AlertRule, ChannelState, NotificationItem } from "../api/types";
import { CHECK_EVERY_MS } from "../components/notify/TelegramCard";
import {
  ALERT_RULES,
  BOX,
  LOG,
  notification,
  notifySettings,
  server,
  TELEGRAM_NOTES,
  TELEGRAM_PAIRED,
  TELEGRAM_UNPAIRED,
  telegramState,
} from "../test/server";
import { renderScreen } from "../test/render";
import NotificationsPage from "./NotificationsPage";

// A token as BotFather writes it, made at run time so that no token-like text sits in the repository.
const TOKEN = ["123456789", "B".repeat(35)].join(":");

/** The settings with the Telegram channel as the test has it now. */
function settingsWith(telegram: () => ChannelState) {
  return http.get("/api/notify/settings", () => HttpResponse.json(notifySettings(telegram())));
}

/** The rules the service saves: what was sent, read back. */
function savingRules(sent: AlertRule[][]) {
  return http.put("/api/rules/alerts", async ({ request }) => {
    const { rules } = (await request.json()) as { rules: AlertRule[] };
    sent.push(rules);
    return HttpResponse.json({ ...ALERT_RULES, rules });
  });
}

async function openNewRule() {
  const rules = await screen.findByRole("region", { name: "Kurallar" });
  await userEvent.click(await within(rules).findByRole("button", { name: "Yeni kural" }));
  return { rules, editor: within(rules).getByRole("form", { name: "Yeni kural" }) };
}

const detailed = () => localStorage.setItem("iplikci.view", "detailed");

describe("NotificationsPage", () => {
  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it("names the screen in the window's title", async () => {
    renderScreen(<NotificationsPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Bildirimler" })).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe("Bildirimler · İplikçi Nedim"));
  });

  describe("the box", () => {
    it("lists the notifications newest first with their rule and time, the unseen ones marked", async () => {
      renderScreen(<NotificationsPage />);
      const box = await screen.findByRole("region", { name: "Bildirim kutusu" });
      const list = await within(box).findByRole("list", { name: "Bildirimler, en yenisi önce" });
      const [due, large, month] = within(list).getAllByRole("listitem");
      expect(within(box).getByText("2 okunmamış bildirim")).toBeInTheDocument();
      expect(due).toHaveTextContent("Son ödeme yaklaşıyor");
      expect(due).toHaveTextContent("Örnek Kart •1234 · Kart son ödemesi: 3 gün sonra (05.11.2026), 9.000,00 TL.");
      expect(due).toHaveTextContent("Kural: Son ödemeye 3 gün");
      expect(within(due!).getByText("Yeni")).toBeInTheDocument();
      expect(within(due!).getByText(/^02\.11\.2026 \d\d:\d\d$/)).toHaveAttribute("datetime", BOX.items[0]!.created_at);
      expect(within(large!).getByText("Yeni")).toBeInTheDocument();
      expect(month).toHaveTextContent("Ekim 2026 kapandı: bütün belgeleri geldi ve doğrulandı.");
      expect(within(month!).queryByText("Yeni")).toBeNull();
    });

    it("says in the simple view how many are unseen and which is the newest of them", async () => {
      renderScreen(<NotificationsPage />);
      const box = await screen.findByRole("region", { name: "Bildirim kutusu" });
      expect(
        await within(box).findByText("2 bildirimi henüz görmediniz; en yenisi: Son ödeme yaklaşıyor."),
      ).toBeInTheDocument();
      expect(within(box).queryByText(/^Olay:/)).toBeNull(); // the events are the detailed view's
    });

    it("adds each notification's event and the page of what it concerns in the detailed view", async () => {
      detailed();
      renderScreen(<NotificationsPage />);
      const box = await screen.findByRole("region", { name: "Bildirim kutusu" });
      const list = await within(box).findByRole("list", { name: "Bildirimler, en yenisi önce" });
      const [due, large, month] = within(list).getAllByRole("listitem");
      expect(within(due!).getByText("Olay: Son ödeme yaklaşıyor")).toBeInTheDocument();
      expect(within(due!).getByRole("link", { name: "Takvim ekranı" })).toHaveAttribute("href", "/takvim");
      const row = within(large!).getByRole("link", { name: "İşlem 3f9a2c7d" });
      expect(row).toHaveAttribute("href", `/islemler?satir=${BOX.items[1]!.target}`);
      expect(within(month!).getByRole("link", { name: "Ekim 2026" })).toHaveAttribute("href", "/ay-sonu/2026-10");
      expect(within(box).queryByText(/henüz görmediniz/)).toBeNull(); // the sentence is the simple view's
    });

    it("marks the box seen up to the newest notification shown, from the service's own page", async () => {
      let sent: unknown;
      let fromOwnPage = false;
      let seen = false;
      server.use(
        http.post("/api/notifications/read", async ({ request }) => {
          sent = await request.json();
          fromOwnPage = request.headers.get("x-iplikci") === "1";
          seen = true;
          return HttpResponse.json({ marked: 2 });
        }),
        http.get("/api/notifications", ({ request }) => {
          const page = new URL(request.url).searchParams.get("channel") === "in_app" ? BOX : LOG;
          const items = page.items.map((item) => ({ ...item, read: seen || item.read }));
          return HttpResponse.json({ items, unread: seen ? 0 : 2 });
        }),
      );
      renderScreen(<NotificationsPage />);
      const box = await screen.findByRole("region", { name: "Bildirim kutusu" });
      await within(box).findByText("2 okunmamış bildirim");
      await userEvent.click(within(box).getByRole("button", { name: "Tümünü okundu say" }));
      expect(await within(box).findByText("Okunmamış bildirim yok")).toBeInTheDocument();
      expect(sent).toEqual({ up_to: 12 }); // the newest shown: one arriving meanwhile stays unread
      expect(fromOwnPage).toBe(true);
      expect(within(box).queryByText("Yeni")).toBeNull();
      expect(within(box).getByRole("button", { name: "Tümünü okundu say" })).toBeDisabled();
    });

    it("says when there is no notification yet", async () => {
      server.use(http.get("/api/notifications", () => HttpResponse.json({ items: [], unread: 0 })));
      renderScreen(<NotificationsPage />);
      const box = await screen.findByRole("region", { name: "Bildirim kutusu" });
      expect(await within(box).findByText("Henüz bildirim yok")).toBeInTheDocument();
      expect(within(box).getByRole("button", { name: "Tümünü okundu say" })).toBeDisabled();
    });

    it("offers to try again when the service cannot be reached", async () => {
      server.use(http.get("/api/notifications", () => HttpResponse.error()));
      renderScreen(<NotificationsPage />);
      const box = await screen.findByRole("region", { name: "Bildirim kutusu" });
      expect(await within(box).findByText("Servise ulaşılamadı; servis çalışıyor mu?")).toBeInTheDocument();
      server.resetHandlers();
      await userEvent.click(within(box).getByRole("button", { name: "Yeniden dene" }));
      expect(await within(box).findByText("Kural: Son ödemeye 3 gün")).toBeInTheDocument();
    });
  });

  describe("the history", () => {
    it("lists each delivery with its channel and status in the simple view, and says how many went", async () => {
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=gecmis" });
      const log = await screen.findByRole("region", { name: "Teslim kaydı" });
      const list = await within(log).findByRole("list", { name: "Gönderilen bildirimler, en yenisi önce" });
      const [failed, held] = within(list).getAllByRole("listitem");
      expect(within(failed!).getByText("Son ödeme yaklaşıyor")).toBeInTheDocument();
      expect(within(failed!).getByText("Gönderilemedi")).toBeInTheDocument();
      expect(within(failed!).getByText(/^Telegram · 02\.11\.2026 \d\d:\d\d$/)).toBeInTheDocument();
      expect(within(failed!).getByText("Telegram'a ulaşılamadı: zaman aşımı.")).toBeInTheDocument();
      expect(within(held!).getByText("Özete kaldı")).toBeInTheDocument();
      expect(
        within(log).getByText(
          "4 bildirim gönderildi, 1 bildirim gönderilemedi. " +
            "1 bildirim sessiz saat ya da sıklık sınırı yüzünden özete kaldı.",
        ),
      ).toBeInTheDocument();
      expect(within(log).queryByRole("table")).toBeNull(); // the table is the detailed view's
    });

    it("shows in the detailed view each delivery's level, rule, attempts and the page of what it concerns", async () => {
      detailed();
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=gecmis" });
      const log = await screen.findByRole("region", { name: "Teslim kaydı" });
      const failed = (await within(log).findByText("Telegram'a ulaşılamadı: zaman aşımı.")).closest("tr")!;
      expect(within(failed).getByText("Telegram")).toBeInTheDocument();
      expect(within(failed).getByText("Gönderilemedi")).toBeInTheDocument();
      expect(within(failed).getByText("Özet")).toBeInTheDocument(); // the channel's level of detail
      expect(within(failed).getByRole("cell", { name: "8" })).toBeInTheDocument(); // the attempts that failed
      expect(within(failed).getByRole("link", { name: "Takvim ekranı" })).toHaveAttribute("href", "/takvim");
      const held = within(log).getByText("Büyük harcama: 12.500,00 TL.").closest("tr")!;
      expect(within(held).getByText("Özete kaldı")).toBeInTheDocument();
      const row = within(held).getByRole("link", { name: "İşlem 3f9a2c7d" });
      expect(row).toHaveAttribute("href", `/islemler?satir=${LOG.items[1]!.target}`);
      expect(within(row).getByText("3f9a2c7d")).toHaveAttribute("title", LOG.items[1]!.target); // the row's code
      expect(within(log).getByRole("link", { name: "Faturalar ekranı" })).toHaveAttribute("href", "/faturalar");
      const unreadable = within(log).getByRole("link", { name: "Belge aaaaaaaa" });
      expect(unreadable).toHaveAttribute("href", `/belgeler/${"a".repeat(64)}`);
      expect(within(unreadable).getByText("aaaaaaaa")).toHaveAttribute("title", "a".repeat(64)); // its sha256
      // The month the event is about.
      expect(within(log).getByRole("link", { name: "Ekim 2026" })).toHaveAttribute("href", "/ay-sonu/2026-10");
      expect(
        within(log).getByText("Gönderildi: 3 · Özetle gönderildi: 1 · Özete kaldı: 1 · Gönderilemedi: 1"),
      ).toBeInTheDocument();
    });

    it("loads older deliveries a page at a time", async () => {
      const asked: string[] = [];
      const first: NotificationItem[] = Array.from({ length: 50 }, (_, i) =>
        notification({ id: 200 - i, channel: "desktop", title: `Bildirim ${200 - i}` }),
      );
      server.use(
        http.get("/api/notifications", ({ request }) => {
          const url = new URL(request.url);
          if (url.searchParams.get("channel") === "in_app") {
            return HttpResponse.json(BOX);
          }
          const before = url.searchParams.get("before") ?? "";
          asked.push(before);
          if (before === "151") {
            const oldest = notification({ id: 90, channel: "email", title: "En eski" });
            return HttpResponse.json({ items: [oldest], unread: 2 });
          }
          return HttpResponse.json({ items: first, unread: 2, next: 151 });
        }),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=gecmis" });
      const log = await screen.findByRole("region", { name: "Teslim kaydı" });
      expect(await within(log).findByText("Bildirim 200")).toBeInTheDocument();
      await userEvent.click(within(log).getByRole("button", { name: "Daha eski kayıtlar" }));
      expect(await within(log).findByText("En eski")).toBeInTheDocument();
      expect(asked).toEqual(["", "151"]); // where the service said the next page starts
      expect(within(log).queryByRole("button", { name: "Daha eski kayıtlar" })).toBeNull();
    });
  });

  describe("the channels", () => {
    it("shows each channel's state and what it still needs in the service's words", async () => {
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Kanallar" });
      const channels = await within(card).findByRole("list", { name: "Kanallar" });
      const [inApp, desktop, telegram, email] = within(channels).getAllByRole("listitem");
      expect(inApp).toHaveTextContent("Her zaman açık");
      expect(within(desktop!).getByText("Hazır")).toBeInTheDocument();
      expect(within(telegram!).getByText("Kurulmadı")).toBeInTheDocument(); // on, but no bot yet
      expect(telegram).toHaveTextContent(TELEGRAM_NOTES.none);
      // Off, and it could not carry a notification even if it were on.
      expect(within(email!).getByText("Kapalı")).toBeInTheDocument();
      expect(within(email!).getByText("Kullanılamıyor")).toBeInTheDocument();
      expect(within(email!).getByRole("checkbox", { name: "E-posta: Açık" })).not.toBeChecked();
    });

    it("says in the simple view where notifications go now and when the quiet hours are", async () => {
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Kanallar" });
      // Telegram is on but has no bot yet, so it carries nothing; e-mail is off.
      expect(
        await within(card).findByText(
          "Bildirimler uygulamadaki kutuya ve Masaüstü kanalına gidiyor. Sessiz saatler 23:00–08:00.",
        ),
      ).toBeInTheDocument();
      expect(within(card).queryByRole("table")).toBeNull(); // the states are the detailed view's
    });

    it("says when only the box gets notifications and there are no quiet hours", async () => {
      const settings = notifySettings();
      const channels = settings.channels.map((state) => ({ ...state, on: state.channel === "in_app" }));
      server.use(http.get("/api/notify/settings", () => HttpResponse.json({ ...settings, quiet_hours: "", channels })));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Kanallar" });
      expect(await within(card).findByText(/^Bildirimler yalnızca uygulamadaki kutuya düşüyor;/)).toHaveTextContent(
        "başka bir kanal açık değil ya da hazır değil. Sessiz saat yok.",
      );
    });

    it("adds every channel's state as the service gives it in the detailed view", async () => {
      detailed();
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Kanallar" });
      const name = "Kanalların ayarları ve durumu, servisin verdiği gibi";
      const table = await within(card).findByRole("table", { name });
      const telegram = within(table).getByRole("row", { name: /^Telegram/ });
      const cells = within(telegram).getAllByRole("cell");
      expect(cells.map((cell) => cell.textContent)).toEqual([
        "Telegram",
        "Evet", // on
        "Hayır", // but it cannot carry one yet
        "Kurulmadı",
        "Özet",
        TELEGRAM_NOTES.none,
      ]);
      const inApp = within(table).getByRole("row", { name: /^Uygulama içi/ });
      expect(within(inApp).getAllByRole("cell")[4]).toHaveTextContent("—"); // the box has no level of its own
      expect(within(card).queryByText(/^Bildirimler uygulamadaki kutuya/)).toBeNull();
    });

    it("saves the quiet hours, the channels turned on and each channel's level of detail", async () => {
      let sent: unknown;
      server.use(
        http.put("/api/notify/settings", async ({ request }) => {
          sent = await request.json();
          return HttpResponse.json({ ...notifySettings(), quiet_hours: "22:30-07:00" });
        }),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Kanallar" });
      const start = await within(card).findByLabelText("Başlangıç");
      await userEvent.clear(start);
      await userEvent.type(start, "22:30");
      const end = within(card).getByLabelText("Bitiş");
      await userEvent.clear(end);
      await userEvent.type(end, "07:00");
      await userEvent.click(within(card).getByRole("checkbox", { name: "E-posta: Açık" }));
      await userEvent.selectOptions(within(card).getByLabelText("Telegram: Ayrıntı düzeyi"), "Asgari");
      await userEvent.click(within(card).getByRole("button", { name: "Kaydet" }));
      expect(await within(card).findByText("Bildirim ayarları kaydedildi")).toBeInTheDocument();
      expect(sent).toEqual({
        quiet_hours: "22:30-07:00",
        detail: { desktop: "summary", telegram: "minimal", email: "full" },
        channels: ["desktop", "telegram", "email"],
      });
      expect(within(card).getByLabelText("Başlangıç")).toHaveValue("22:30"); // the saved settings show
    });

    it("turns the quiet hours off and refuses hours that start when they end", async () => {
      let sent: unknown;
      server.use(
        http.put("/api/notify/settings", async ({ request }) => {
          sent = await request.json();
          return HttpResponse.json({ ...notifySettings(), quiet_hours: "" });
        }),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Kanallar" });
      const end = await within(card).findByLabelText("Bitiş");
      await userEvent.clear(end);
      await userEvent.type(end, "23:00");
      expect(within(card).getByText("Başlangıç ve bitiş saati aynı olamaz.")).toBeInTheDocument();
      expect(end).toHaveAttribute("aria-invalid", "true");
      expect(within(card).getByRole("button", { name: "Kaydet" })).toBeDisabled();
      await userEvent.click(within(card).getByRole("checkbox", { name: "Sessiz saatleri kullan" }));
      expect(end).toBeDisabled();
      await userEvent.click(within(card).getByRole("button", { name: "Kaydet" }));
      await waitFor(() => expect(sent).toMatchObject({ quiet_hours: "" }));
    });

    it("sends a test notification and says it went", async () => {
      let asked: unknown;
      server.use(
        http.post("/api/notify/test", async ({ request }) => {
          asked = await request.json();
          return new HttpResponse(null, { status: 204 });
        }),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Kanallar" });
      await userEvent.click(await within(card).findByRole("button", { name: "Masaüstü: Deneme bildirimi gönder" }));
      expect(await within(card).findByText("Deneme bildirimi gönderildi")).toBeInTheDocument();
      expect(asked).toEqual({ channel: "desktop" });
    });

    it("shows why the service refused a test notification", async () => {
      const why = "Önce e-posta hesabını uygulama şifresiyle kurun.";
      server.use(
        http.post("/api/notify/test", () => HttpResponse.json({ code: "notify_refused", title: why }, { status: 400 })),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Kanallar" });
      await userEvent.click(await within(card).findByRole("button", { name: "E-posta: Deneme bildirimi gönder" }));
      const refusal = await within(card).findByRole("alert");
      expect(refusal).toHaveTextContent("Deneme bildirimi gönderilemedi");
      expect(refusal).toHaveTextContent(why);
      expect(refusal.closest("li")).toHaveTextContent("E-posta"); // beside the channel it was about
    });
  });

  describe("Telegram", () => {
    it("takes the token once and keeps no copy, then asks every few seconds until the code arrives", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      let telegram = telegramState();
      let sentToken: unknown;
      let checks = 0;
      server.use(
        settingsWith(() => telegram),
        http.post("/api/notify/telegram/token", async ({ request }) => {
          sentToken = await request.json();
          telegram = TELEGRAM_UNPAIRED;
          return HttpResponse.json({ bot: "ornek_bot", in_keyring: true });
        }),
        http.post("/api/notify/telegram/pairing", () =>
          HttpResponse.json({
            code: "a1b2c3d4",
            expires: new Date(Date.now() + 10 * 60_000).toISOString(),
            bot: "ornek_bot",
            link: "https://t.me/ornek_bot?start=a1b2c3d4",
          }),
        ),
        http.post("/api/notify/telegram/check", () => {
          checks += 1;
          if (checks < 2) {
            return HttpResponse.json({ paired: false });
          }
          telegram = TELEGRAM_PAIRED;
          return HttpResponse.json({ paired: true });
        }),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Telegram" });
      const botFather = await within(card).findByRole("link", { name: "@BotFather" });
      expect(within(card).getByText("Kurulmadı")).toBeInTheDocument();
      expect(botFather).toHaveAttribute("href", "https://t.me/BotFather");
      const field = within(card).getByLabelText("Bot belirteci");
      expect(field).toHaveAttribute("type", "password");
      await user.type(field, TOKEN);
      await user.click(within(card).getByRole("button", { name: "Belirteci kaydet" }));
      expect(await within(card).findByText("@ornek_bot botu kaydedildi")).toBeInTheDocument();
      expect(sentToken).toEqual({ token: TOKEN });
      expect(within(card).queryByLabelText("Bot belirteci")).toBeNull();
      expect(document.body.innerHTML).not.toContain(TOKEN); // never shown again

      await user.click(await within(card).findByRole("button", { name: "Eşleştirme kodu al" }));
      expect(await within(card).findByText("a1b2c3d4")).toBeInTheDocument();
      const chat = within(card).getByRole("link", { name: "Telegram'da @ornek_bot sohbetini aç" });
      expect(chat).toHaveAttribute("href", "https://t.me/ornek_bot?start=a1b2c3d4");
      expect(within(card).getByText("Tek kullanımlık; 10 dakika içinde gönderin.", { exact: false })).toBeVisible();
      expect(checks).toBe(0);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(CHECK_EVERY_MS);
      });
      await waitFor(() => expect(checks).toBe(1));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(CHECK_EVERY_MS);
      });
      expect(await within(card).findByText("Telegram bağlandı")).toBeInTheDocument();
      expect(await within(card).findByText(TELEGRAM_NOTES.paired)).toBeInTheDocument();
      expect(within(card).getByText("Hazır")).toBeInTheDocument();
      expect(within(card).queryByRole("button", { name: "Eşleştirme kodu al" })).toBeNull();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(CHECK_EVERY_MS * 3);
      });
      expect(checks).toBe(2); // paired: it stopped asking
    });

    it("shows why a token was refused and empties the field", async () => {
      const why = "Bu bir Telegram bot belirteci değil: BotFather'ın verdiği '123456789:AA…' biçiminde olmalı.";
      server.use(
        http.post("/api/notify/telegram/token", () =>
          HttpResponse.json({ code: "notify_refused", title: why }, { status: 400 }),
        ),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Telegram" });
      const field = await within(card).findByLabelText("Bot belirteci");
      await userEvent.type(field, "parola");
      await userEvent.click(within(card).getByRole("button", { name: "Belirteci kaydet" }));
      expect(await within(card).findByText(why)).toBeInTheDocument();
      expect(field).toHaveValue("");
      expect(field).toHaveAttribute("aria-invalid", "true");
      expect(within(card).getByRole("button", { name: "Belirteci kaydet" })).toBeDisabled();
    });

    it("stops asking and says so when the code ends before it reaches the bot", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      let checks = 0;
      server.use(
        settingsWith(() => TELEGRAM_UNPAIRED),
        http.post("/api/notify/telegram/pairing", () =>
          HttpResponse.json({
            code: "e5f6a7b8",
            expires: new Date(Date.now() + 2 * CHECK_EVERY_MS).toISOString(),
            bot: "ornek_bot",
            link: "",
          }),
        ),
        http.post("/api/notify/telegram/check", () => {
          checks += 1;
          return HttpResponse.json({ paired: false });
        }),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Telegram" });
      await user.click(await within(card).findByRole("button", { name: "Eşleştirme kodu al" }));
      expect(await within(card).findByText("/start e5f6a7b8")).toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(CHECK_EVERY_MS * 4);
      });
      expect(await within(card).findByText("Kodun süresi doldu")).toBeInTheDocument();
      const asked = checks;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(CHECK_EVERY_MS * 3);
      });
      expect(checks).toBe(asked);
      expect(within(card).getByRole("button", { name: "Yeni kod al" })).toBeEnabled();
    });

    it("asks for the token again when Telegram refused it and the channel stopped", async () => {
      const note = "Durdu: Telegram reddetti: Unauthorized";
      server.use(settingsWith(() => telegramState({ stage: "stopped", note })));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Telegram" });
      expect(await within(card).findByText(note)).toBeInTheDocument();
      expect(within(card).getByText("Durdu")).toBeInTheDocument();
      expect(within(card).getByText(/^Telegram reddettiği için kanal durdu; program kendiliğinden/)).toBeVisible();
      expect(within(card).getByText("Telegram reddettiği için kanal durdu; belirteci yeniden girin.")).toBeVisible();
      expect(within(card).getByText("Bot belirtecini yeniden girin.")).toBeInTheDocument();
      expect(within(card).getByLabelText("Bot belirteci")).toBeInTheDocument();
      expect(within(card).getByRole("button", { name: "Telegram'ı kaldır" })).toBeInTheDocument();
    });

    it("says when a paired bot's channel is turned off", async () => {
      server.use(settingsWith(() => ({ ...TELEGRAM_PAIRED, on: false, ready: false })));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Telegram" });
      expect(await within(card).findByText("Telegram kanalı kapalı")).toBeInTheDocument();
      expect(within(card).queryByLabelText("Bot belirteci")).toBeNull();
    });

    it("removes Telegram after asking", async () => {
      let telegram = TELEGRAM_PAIRED;
      let removed = 0;
      server.use(
        settingsWith(() => telegram),
        http.delete("/api/notify/telegram", () => {
          removed += 1;
          telegram = telegramState();
          return new HttpResponse(null, { status: 204 });
        }),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Telegram" });
      const remove = await within(card).findByRole("button", { name: "Telegram'ı kaldır" });
      await userEvent.click(remove);
      const asked = await screen.findByRole("alertdialog", { name: "Telegram kaldırılsın mı?" });
      expect(asked).toHaveAccessibleDescription(
        "Bot belirteci ve eşleşen sohbet unutulur; bildirimler Telegram'a gitmez.",
      );
      await userEvent.click(within(asked).getByRole("button", { name: "Vazgeç" }));
      expect(removed).toBe(0); // the user said no
      await waitFor(() => expect(remove).toHaveFocus()); // back where it was asked
      await userEvent.click(remove);
      const again = await screen.findByRole("alertdialog", { name: "Telegram kaldırılsın mı?" });
      await userEvent.click(within(again).getByRole("button", { name: "Telegram'ı kaldır" }));
      expect(await within(card).findByText("Telegram kaldırıldı")).toBeInTheDocument();
      expect(removed).toBe(1);
      expect(screen.queryByRole("alertdialog")).toBeNull();
      // The button is gone with the bot: the focus goes to the field that takes its place.
      await waitFor(() => expect(within(card).getByLabelText("Bot belirteci")).toHaveFocus());
    });

    it("says in the simple view what the bot's stage asks of the user", async () => {
      let telegram = telegramState();
      server.use(settingsWith(() => telegram));
      const { client } = renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kanallar" });
      const card = await screen.findByRole("region", { name: "Telegram" });
      const say = "Bildirimleri Telegram'dan da almak için kendi botunuzu kurun.";
      expect(await within(card).findByText(say)).toBeInTheDocument();
      telegram = { ...TELEGRAM_PAIRED, on: false, ready: false };
      await act(() => client.invalidateQueries());
      expect(
        await within(card).findByText("Telegram eşleşti, ama kanal kapalı: Kanallar kartında açın."),
      ).toBeInTheDocument();
      telegram = TELEGRAM_PAIRED;
      await act(() => client.invalidateQueries());
      expect(await within(card).findByText("Bildirimler Telegram sohbetinize gidiyor.")).toBeInTheDocument();
    });
  });

  describe("the rules", () => {
    it("lists the rules in words with a switch each", async () => {
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const list = await screen.findByRole("list", { name: "Bildirim kuralları" });
      const [due, large, month] = within(list).getAllByRole("listitem");
      expect(due).toHaveTextContent("Olay: Son ödeme yaklaşıyor · Koşul: en çok 3 gün kala");
      expect(due).toHaveTextContent("Kanallar: Uygulama içi, Masaüstü, Telegram · Ayrıntı: her kanalın kendi düzeyi");
      expect(due).not.toHaveTextContent("sessiz saatte de gider");
      expect(within(due!).getByRole("switch", { name: "Son ödemeye 3 gün: Açık" })).toBeChecked();
      expect(large).toHaveTextContent("Olay: Büyük harcama · Koşul: en az 7.500,00 TL");
      expect(large).toHaveTextContent("Kanallar: Uygulama içi, Telegram · Ayrıntı: Asgari · sessiz saatte de gider");
      expect(month).toHaveTextContent("Olay: Ay kapandı · Koşulsuz");
      expect(within(month!).getByText("Kapalı")).toBeInTheDocument();
      expect(within(month!).getByRole("switch", { name: "Ay kapandı: Açık" })).not.toBeChecked();
    });

    it("turns a rule off with its switch, saving the whole list", async () => {
      const sent: AlertRule[][] = [];
      server.use(savingRules(sent));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const list = await screen.findByRole("list", { name: "Bildirim kuralları" });
      const due = within(list).getByRole("switch", { name: "Son ödemeye 3 gün: Açık" });
      await userEvent.click(due);
      await waitFor(() => expect(due).not.toBeChecked());
      expect(sent.map((rules) => rules.map((rule) => rule.enabled))).toEqual([[false, true, false]]);
      expect(screen.getByText("Kurallar kaydedildi")).toBeInTheDocument();
    });

    it("offers only the conditions the chosen event allows and previews the last 30 days", async () => {
      let asked: unknown;
      const examples = [
        { title: "Büyük harcama", body: "Örnek Mobilya: 13.000,00 TL (•1234, 20.10.2026)." },
        { title: "Büyük harcama", body: "Örnek Seyahat: 12.900,00 TL (•1234, 08.10.2026)." },
      ];
      server.use(
        http.post("/api/rules/alerts/preview", async ({ request }) => {
          asked = await request.json();
          return HttpResponse.json({ count: 2, days: 30, examples });
        }),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const { editor } = await openNewRule();
      expect(within(editor).getByLabelText("Ad")).toHaveFocus();
      const event = within(editor).getByLabelText("Olay");
      await userEvent.selectOptions(event, "Ay kapandı");
      expect(within(editor).getByText("Bu olayda koşul yok: olay her olduğunda bildirim gelir.")).toBeInTheDocument();
      expect(within(editor).queryByLabelText("En az tutar (TL)")).toBeNull();
      await userEvent.selectOptions(event, "Büyük harcama");
      expect(within(editor).queryByLabelText("En çok kaç gün kala")).toBeNull();
      expect(within(editor).getByLabelText("Başlığında geçen yazı")).toBeInTheDocument();
      await userEvent.type(within(editor).getByLabelText("En az tutar (TL)"), "12.500,50");
      await userEvent.click(within(editor).getByRole("button", { name: "Son 30 günde kaç kez?" }));
      expect(await within(editor).findByText("Son 30 günde 2 kez bildirim verirdi.")).toBeInTheDocument();
      expect(within(editor).getByText(examples[0]!.body, { exact: false })).toBeVisible();
      expect(asked).toEqual({
        rule: {
          name: "Önizleme", // not named yet: the service wants a name, the preview none
          event: "transaction.large",
          condition: { days: null, amount: 1250050, text: "" }, // kuruş
          channels: ["desktop", "telegram"],
          detail: null,
          enabled: true,
          quiet: true,
        },
      });
      await userEvent.selectOptions(event, "Son ödeme yaklaşıyor");
      expect(within(editor).getByLabelText("En çok kaç gün kala")).toBeInTheDocument();
      // A changed rule's count no longer holds.
      expect(within(editor).queryByText("Son 30 günde 2 kez bildirim verirdi.")).toBeNull();
    });

    it("saves a new rule at the end of the whole list and closes the editor", async () => {
      const sent: AlertRule[][] = [];
      server.use(savingRules(sent));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const { rules, editor } = await openNewRule();
      await userEvent.type(within(editor).getByLabelText("Ad"), "Kira yaklaşıyor");
      await userEvent.selectOptions(within(editor).getByLabelText("Olay"), "Son ödeme yaklaşıyor");
      await userEvent.type(within(editor).getByLabelText("En çok kaç gün kala"), "5");
      await userEvent.type(within(editor).getByLabelText("Başlığında geçen yazı"), " Kira ");
      await userEvent.click(within(editor).getByRole("checkbox", { name: "Masaüstü" }));
      await userEvent.selectOptions(within(editor).getByLabelText("Ayrıntı düzeyi"), "Tam");
      await userEvent.click(within(editor).getByRole("checkbox", { name: "Sessiz saatlere uy" }));
      await userEvent.click(within(editor).getByRole("button", { name: "Kaydet" }));
      expect(await within(rules).findByText("Kurallar kaydedildi")).toBeInTheDocument();
      expect(sent).toEqual([
        [
          ...ALERT_RULES.rules,
          {
            name: "Kira yaklaşıyor",
            event: "payment.due_soon",
            condition: { days: 5, amount: null, text: "Kira" },
            channels: ["telegram"],
            detail: "full",
            enabled: true,
            quiet: false,
          },
        ],
      ]);
      expect(within(rules).queryByRole("form")).toBeNull();
      expect(within(rules).getByRole("button", { name: "Yeni kural" })).toHaveFocus();
      expect(within(rules).getByText("Kira yaklaşıyor")).toBeInTheDocument();
    });

    it("edits a rule in place, starting from what it says", async () => {
      const sent: AlertRule[][] = [];
      server.use(savingRules(sent));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const list = await screen.findByRole("list", { name: "Bildirim kuralları" });
      const edit = within(list).getByRole("button", { name: "Büyük harcama: Düzenle" });
      await userEvent.click(edit);
      const editor = screen.getByRole("form", { name: "“Büyük harcama” kuralını düzenle" });
      const amount = within(editor).getByLabelText("En az tutar (TL)");
      expect(amount).toHaveValue("7.500");
      expect(within(editor).getByRole("checkbox", { name: "Sessiz saatlere uy" })).not.toBeChecked();
      await userEvent.clear(amount);
      await userEvent.type(amount, "10.000");
      await userEvent.click(within(editor).getByRole("button", { name: "Kaydet" }));
      await waitFor(() => expect(sent).toHaveLength(1));
      expect(sent[0]![1]).toMatchObject({ name: "Büyük harcama", condition: { amount: 1000000 }, quiet: false });
      expect(sent[0]!.map((rule) => rule.name)).toEqual(["Son ödemeye 3 gün", "Büyük harcama", "Ay kapandı"]);
      await waitFor(() => expect(within(list).getByRole("button", { name: "Büyük harcama: Düzenle" })).toHaveFocus());
    });

    it("checks the editor's fields first, then shows the service's refusal as it says it", async () => {
      const why = "alerts.yaml: 'büyük harcama' adında iki kural var; her kuralın adı ayrı olmalı";
      server.use(
        http.put("/api/rules/alerts", () => HttpResponse.json({ code: "rules_invalid", title: why }, { status: 400 })),
      );
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const { editor } = await openNewRule();
      await userEvent.click(within(editor).getByRole("button", { name: "Kaydet" }));
      const name = within(editor).getByLabelText("Ad");
      expect(within(editor).getByText("Kurala bir ad verin.")).toBeInTheDocument();
      expect(within(editor).getByText("İzlenecek olayı seçin.")).toBeInTheDocument();
      expect(name).toHaveAttribute("aria-invalid", "true");
      expect(name).toHaveAccessibleDescription("Kurala bir ad verin.");
      expect(name).toHaveFocus();
      await userEvent.type(name, "büyük harcama");
      expect(within(editor).queryByText("Kurala bir ad verin.")).toBeNull();
      await userEvent.selectOptions(within(editor).getByLabelText("Olay"), "Büyük harcama");
      await userEvent.type(within(editor).getByLabelText("En az tutar (TL)"), "7500.50");
      await userEvent.click(within(editor).getByRole("button", { name: "Kaydet" }));
      expect(within(editor).getByText("Tutar 7.500 ya da 7.500,50 gibi bir TL tutarı olmalı.")).toBeInTheDocument();
      await userEvent.clear(within(editor).getByLabelText("En az tutar (TL)"));
      await userEvent.click(within(editor).getByRole("button", { name: "Kaydet" }));
      expect(await within(editor).findByText(why)).toBeInTheDocument();
      expect(within(editor).getByText("Kurallar kaydedilemedi")).toBeInTheDocument();
      expect(name).toHaveValue("büyük harcama"); // the editor stays open with what was typed
    });

    it("deletes a rule after asking, then moves the focus to the button that adds one", async () => {
      const sent: AlertRule[][] = [];
      server.use(savingRules(sent));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const list = await screen.findByRole("list", { name: "Bildirim kuralları" });
      const remove = within(list).getByRole("button", { name: "Ay kapandı: Sil" });
      await userEvent.click(remove);
      const asked = await screen.findByRole("alertdialog", { name: "“Ay kapandı” kuralı silinsin mi?" });
      expect(asked).toHaveAccessibleDescription(/^Kural listeden çıkar; bu olay için bildirim gelmez\./);
      await userEvent.click(within(asked).getByRole("button", { name: "Vazgeç" }));
      expect(sent).toEqual([]); // the user said no
      await waitFor(() => expect(remove).toHaveFocus()); // back where it was asked
      await userEvent.click(remove);
      const again = await screen.findByRole("alertdialog", { name: "“Ay kapandı” kuralı silinsin mi?" });
      await userEvent.click(within(again).getByRole("button", { name: "Kuralı sil" }));
      await waitFor(() => expect(within(list).queryByText("Ay kapandı")).toBeNull());
      expect(sent.map((rules) => rules.map((rule) => rule.name))).toEqual([["Son ödemeye 3 gün", "Büyük harcama"]]);
      expect(screen.queryByRole("alertdialog")).toBeNull();
      await waitFor(() => expect(screen.getByRole("button", { name: "Yeni kural" })).toHaveFocus());
    });

    it("says in the simple view how many rules are on", async () => {
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const rules = await screen.findByRole("region", { name: "Kurallar" });
      expect(await within(rules).findByText("2 kural açık, 1 kural kapalı.")).toBeInTheDocument();
      expect(within(rules).queryByText(/^Olayın kodu:/)).toBeNull(); // the codes are the detailed view's
    });

    it.each([
      [true, "3 kuralın hepsi açık."],
      [false, "3 kuralın hepsi kapalı; hiçbir olay bildirim vermez."],
    ])("says so when every rule is on or every one off (on: %s)", async (enabled, said) => {
      const rules = ALERT_RULES.rules.map((rule) => ({ ...rule, enabled }));
      server.use(http.get("/api/rules/alerts", () => HttpResponse.json({ ...ALERT_RULES, rules })));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const card = await screen.findByRole("region", { name: "Kurallar" });
      expect(await within(card).findByText(said)).toBeInTheDocument();
    });

    it("adds each rule's event code in the detailed view", async () => {
      detailed();
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const list = await screen.findByRole("list", { name: "Bildirim kuralları" });
      const [due, large] = within(list).getAllByRole("listitem");
      expect(within(due!).getByText("payment.due_soon")).toBeInTheDocument();
      expect(within(large!).getByText(/^Olayın kodu:/)).toHaveTextContent("Olayın kodu: transaction.large");
      expect(screen.queryByText("2 kural açık, 1 kural kapalı.")).toBeNull();
    });

    it("says the shipped rules apply until the user changes one", async () => {
      server.use(http.get("/api/rules/alerts", () => HttpResponse.json({ ...ALERT_RULES, own: false })));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const rules = await screen.findByRole("region", { name: "Kurallar" });
      expect(await within(rules).findByText(/^Bunlar uygulamayla gelen hazır kurallar\./)).toBeInTheDocument();
      expect(within(rules).getByText("Uygulamayla gelen 3 hazır kural geçerli.")).toBeInTheDocument();
    });

    it("warns when the user's rule file could not be read and the shipped rules stand in", async () => {
      const problem = "alerts.yaml, 2. kural: bilinmeyen anahtar 'renk'";
      server.use(http.get("/api/rules/alerts", () => HttpResponse.json({ ...ALERT_RULES, problem })));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const rules = await screen.findByRole("region", { name: "Kurallar" });
      const warning = (await within(rules).findByText("Kural dosyanız okunamadı")).closest("[role=status]");
      expect(warning).toHaveTextContent(problem);
      expect(warning).toHaveTextContent("Şimdilik uygulamayla gelen kurallar geçerli.");
      expect(within(rules).getByRole("list", { name: "Bildirim kuralları" })).toBeInTheDocument(); // they stand in
    });

    it("says when there is no rule at all", async () => {
      server.use(http.get("/api/rules/alerts", () => HttpResponse.json({ ...ALERT_RULES, rules: [] })));
      renderScreen(<NotificationsPage />, { path: "/bildirimler?bolum=kurallar" });
      const rules = await screen.findByRole("region", { name: "Kurallar" });
      expect(await within(rules).findByText("Hiç kural yok")).toBeInTheDocument();
    });
  });
});
