import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Settings } from "../api/types";
import { GIVE_UP_MS, POLL_MS } from "../components/settings/ServiceLife";
import { renderScreen } from "../test/render";
import { serviceState, SETUP, server, settings } from "../test/server";
import SettingsPage from "./SettingsPage";

afterEach(() => {
  localStorage.clear();
  vi.useRealTimers();
});

const card = (name: string) => screen.findByRole("region", { name });

/** The settings as given, then as each change leaves them; every change's path and body, in order. */
function serve(start: Settings = settings()) {
  const sent: Array<{ path: string; body: unknown }> = [];
  let current = start;
  server.use(
    http.get("/api/settings", () => HttpResponse.json(current)),
    http.put("/api/settings/:what", async ({ request, params }) => {
      const body = (await request.json()) as Record<string, unknown>;
      sent.push({ path: String(params["what"]), body });
      if (params["what"] === "identity") {
        current = { ...current, ...(body as Pick<Settings, "names" | "business_names">) };
      } else if (params["what"] === "backup") {
        current = { ...current, backup_days: Number(body["keep_days"]) };
      }
      return HttpResponse.json(current);
    }),
  );
  return sent;
}

const IMAP = settings({
  mail: {
    connector: "imap",
    configured: true,
    address: "k•••@example.com",
    start: "2026-01-01",
    server: "imap.example.com",
    stopped: false,
    last_error: "",
  },
});

describe("SettingsPage", () => {
  it("waits for the settings, then shows each card with its sentence and next step", async () => {
    serve();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    expect(screen.getByRole("status", { name: "Yükleniyor…" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "Ayarlar" })).toBeInTheDocument();
    expect(within(await card("Adlar")).getByText("0 ad ve 0 şirket adı yazılı.")).toBeInTheDocument();
    const backup = await card("Yedekler");
    expect(within(backup).getByText("Her gün bir yedek alınır; günlük yedekler 30 gün saklanır.")).toBeInTheDocument();
    expect(within(backup).getByRole("link", { name: "Yedeklerin durumuna bak" })).toHaveAttribute("href", "/sistem");
    const more = await card("Diğer ayarlar");
    const links = within(more).getAllByRole("link");
    expect(links.map((link) => [link.textContent, link.getAttribute("href")])).toEqual([
      ["Bildirimler", "/bildirimler"],
      ["Tarayıcı eklentisi", "/kurulum/eklenti"],
      ["Belgeler", "/belgeler"],
      ["Sistem", "/sistem"],
      ["Kurulum sihirbazı", "/kurulum"],
    ]);
  });

  it("asks for a backup now and says when the last one was taken", async () => {
    serve();
    let asked = 0;
    server.use(
      http.post("/api/backups", () => {
        asked += 1;
        return HttpResponse.json({ queued: true }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const backup = await card("Yedekler");
    expect(await within(backup).findByText(/^Son yedek: \d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$/)).toBeInTheDocument();
    await user.click(within(backup).getByRole("button", { name: "Şimdi yedek al" }));
    expect(await within(backup).findByText("Yedek istendi: birkaç saniye içinde alınır.")).toBeInTheDocument();
    expect(asked).toBe(1);
  });

  it("says why a backup could not be asked for, and the same button asks again", async () => {
    serve();
    let asked = 0;
    server.use(
      http.post("/api/backups", () => {
        asked += 1;
        return asked === 1
          ? HttpResponse.json({ code: "busy", title: "Servis meşgul" }, { status: 503 })
          : HttpResponse.json({ queued: true }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const backup = await card("Yedekler");
    await user.click(within(backup).getByRole("button", { name: "Şimdi yedek al" }));
    expect(await within(backup).findByText("Servis meşgul")).toBeInTheDocument();
    await user.click(within(backup).getByRole("button", { name: "Şimdi yedek al" }));
    expect(await within(backup).findByText("Yedek istendi: birkaç saniye içinde alınır.")).toBeInTheDocument();
  });

  it("shows the service's version, since when and its registration, with its steps", async () => {
    serve();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const service = await card("Servis");
    expect(await within(service).findByText("0.7.0")).toBeInTheDocument();
    expect(within(service).getByText(/^15\.11\.2026 \d\d:\d\d$/)).toBeInTheDocument();
    expect(within(service).getByText("Bilgisayar açılınca kendiliğinden başlar.")).toBeInTheDocument(); // the step's
    expect(within(service).getByRole("button", { name: "Yeniden başlat" })).toBeEnabled();
    expect(within(service).getByRole("button", { name: "Servisi durdur" })).toBeEnabled();
    expect(within(service).getByRole("button", { name: "Servisi kaldır" })).toBeEnabled();
  });

  it("names a service registered for another data folder as the service says it", async () => {
    const elsewhere = "Bu bilgisayarda başka bir veri klasörü için kayıtlı.";
    serve();
    server.use(
      http.get("/api/setup", () =>
        HttpResponse.json({
          ...SETUP,
          steps: SETUP.steps.map((step) =>
            step.step === "service" ? { ...step, done: false, note: elsewhere } : step,
          ),
        }),
      ),
    );
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const service = await card("Servis");
    expect(await within(service).findByText(elsewhere)).toBeInTheDocument();
  });

  it("says the service's state could not be read and asks again", async () => {
    serve();
    let asked = 0;
    server.use(
      http.get("/api/service", () => {
        asked += 1;
        return asked === 1
          ? HttpResponse.json({ code: "unavailable", title: "Durum okunamadı" }, { status: 503 })
          : HttpResponse.json(serviceState());
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const service = await card("Servis");
    expect(await within(service).findByText("Durum okunamadı")).toBeInTheDocument();
    await user.click(within(service).getByRole("button", { name: "Yeniden dene" }));
    expect(await within(service).findByText("0.7.0")).toBeInTheDocument();
  });

  it("says the settings could not be read and asks again", async () => {
    let asked = 0;
    server.use(
      http.get("/api/settings", () => {
        asked += 1;
        return asked === 1
          ? HttpResponse.json({ code: "settings_invalid", title: "settings.toml okunamadı" }, { status: 409 })
          : HttpResponse.json(settings());
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    expect(await screen.findByText("settings.toml okunamadı")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await card("Adlar")).toBeInTheDocument();
  });

  it("changes the names and the company names, each list saved with the other as it is", async () => {
    const sent = serve(settings({ names: ["Örnek Kullanıcı"] }));
    const user = userEvent.setup();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const names = await card("Adlar");
    await user.type(within(names).getByLabelText("Şirket adı"), "Örnek Ltd.{Enter}");
    expect(await within(names).findByText("Şirket adları kaydedildi; belgeler yeniden okunuyor.")).toBeInTheDocument();
    await user.click(within(names).getByRole("button", { name: "Örnek Kullanıcı adını kaldır" }));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent).toEqual([
      { path: "identity", body: { names: ["Örnek Kullanıcı"], business_names: ["Örnek Ltd."] } },
      { path: "identity", body: { names: [], business_names: ["Örnek Ltd."] } },
    ]);
  });

  it("leads to the extension's screen for its pairing, rather than pairing here", async () => {
    serve(settings({ mail: { ...settings().mail, connector: "browser_bridge" } }));
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const mail = await card("E-posta");
    expect(within(mail).getByRole("link", { name: "Tarayıcı eklentisi ekranını açın." })).toHaveAttribute(
      "href",
      "/kurulum/eklenti",
    );
    expect(within(mail).queryByRole("button", { name: "Eşleştirme kodu al" })).not.toBeInTheDocument();
  });

  it("shows an IMAP account masked, as the service gives it, and never a password", async () => {
    serve(IMAP);
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const mail = await card("E-posta");
    const now = "E-postalar k•••@example.com hesabından geliyor (imap.example.com).";
    expect(within(mail).getByText(now)).toBeInTheDocument();
    expect(within(mail).getByRole("radio", { name: /^Uygulama şifresi/ })).toBeChecked();
    expect(within(mail).getByLabelText("Uygulama şifresi")).toHaveValue("");
    expect(within(mail).getByRole("button", { name: "Hesabı kaldır" })).toBeInTheDocument();
  });

  it("keeps backups for the days typed, and says beside the field when they are out of range", async () => {
    const sent = serve();
    const user = userEvent.setup();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const backup = await card("Yedekler");
    const days = within(backup).getByLabelText("Günlük yedekler kaç gün saklansın");
    expect(days).toHaveValue(30);
    await user.clear(days);
    await user.type(days, "0");
    await user.click(within(backup).getByRole("button", { name: "Kaydet" }));
    expect(days).toHaveAccessibleDescription(/1 ile 365 arasında bir gün sayısı yazın\.$/);
    expect(days).toHaveFocus();
    expect(sent).toEqual([]);
    await user.clear(days);
    await user.type(days, "90");
    await user.click(within(backup).getByRole("button", { name: "Kaydet" }));
    expect(await within(backup).findByText("Kaydedildi: günlük yedekler 90 gün saklanır.")).toBeInTheDocument();
    expect(sent).toEqual([{ path: "backup", body: { keep_days: 90 } }]);
  });

  it("adds the settings' values in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    serve(IMAP);
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const raw = await card("Ayarların değerleri");
    expect(within(raw).getByText("/veri/iplikci")).toBeInTheDocument();
    expect(within(raw).getByText("8643")).toBeInTheDocument();
    expect(within(raw).getByText("imap")).toBeInTheDocument();
    expect(within(raw).getByText("k•••@example.com")).toBeInTheDocument();
    expect(within(raw).getByText("01.01.2026")).toBeInTheDocument();
    expect(within(raw).getByText("garanti.com.tr, teb.com.tr, vakifbank.com.tr")).toBeInTheDocument();
    expect(within(raw).getByText("Kapalı; sonraki bir sürümde gelecek")).toBeInTheDocument();
    expect(await within(raw).findByText("launchd")).toBeInTheDocument(); // the service's manager
    expect(within(raw).getByText("Evet")).toBeInTheDocument(); // registered for this data folder
    expect(screen.queryByText("0 ad ve 0 şirket adı yazılı.")).not.toBeInTheDocument(); // the simple view's
  });
});

const ENDING = { ending: true, restarts: false };
const RESTARTING = { ending: true, restarts: true };
const LATER = "2026-11-15T08:05:00+00:00"; // when the new service started

/** The service as GET /api/service answers: as it was until a step ended it, then as `after` says; every question. */
function serviceAnswers(after: (asked: number) => Response) {
  const state = { ended: false, asked: 0 };
  server.use(
    http.get("/api/service", () => {
      if (!state.ended) {
        return HttpResponse.json(serviceState());
      }
      state.asked += 1;
      return after(state.asked);
    }),
  );
  return state;
}

/** A second more on the clock of the page that waits for the new service, and the question it asks then. */
async function nextQuestion(state: { asked: number }): Promise<void> {
  const before = state.asked;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(POLL_MS);
  });
  await waitFor(() => expect(state.asked).toBeGreaterThan(before));
}

describe("SettingsPage: the service's own life", () => {
  it("stops the service after saying what follows, then says it stopped and asks nothing more", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    serve();
    const state = serviceAnswers(() => HttpResponse.json(serviceState()));
    server.use(
      http.post("/api/service/stop", () => {
        state.ended = true;
        return HttpResponse.json(ENDING, { status: 202 });
      }),
    );
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const service = await card("Servis");
    await user.click(await within(service).findByRole("button", { name: "Servisi durdur" }));
    const asked = await screen.findByRole("alertdialog", { name: "Servis durdurulsun mu?" });
    expect(asked).toHaveAccessibleDescription(/^Servis kapanır: e-postalar alınmaz, belgeler okunmaz/);
    await user.click(within(asked).getByRole("button", { name: "Vazgeç" }));
    expect(state.ended).toBe(false); // the user said no
    await user.click(within(service).getByRole("button", { name: "Servisi durdur" }));
    const again = await screen.findByRole("alertdialog", { name: "Servis durdurulsun mu?" });
    await user.click(within(again).getByRole("button", { name: "Servisi durdur" }));
    const said = await screen.findByRole("heading", {
      level: 2,
      name: "Servis durdu; uygulamayı açınca yeniden başlar.",
    });
    await waitFor(() => expect(said).toHaveFocus()); // the button that asked is gone with the cards
    expect(screen.queryByRole("region", { name: "Adlar" })).not.toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS * 5);
    });
    expect(state.asked).toBe(0); // a stopped service is not waited for
  });

  it("restarts the service and waits until a new one answers, then shows the cards again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    serve();
    const state = serviceAnswers((asked) => {
      if (asked === 1) {
        return HttpResponse.json(serviceState()); // the one that ended still answers
      }
      return asked === 2 ? HttpResponse.error() : HttpResponse.json(serviceState({ started_at: LATER }));
    });
    server.use(
      http.post("/api/service/restart", () => {
        state.ended = true;
        return HttpResponse.json(RESTARTING, { status: 202 });
      }),
    );
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const service = await card("Servis");
    await user.click(await within(service).findByRole("button", { name: "Yeniden başlat" }));
    expect(await screen.findByRole("heading", { level: 2, name: "Servis yeniden başlıyor…" })).toHaveFocus();
    expect(screen.queryByRole("region", { name: "Adlar" })).not.toBeInTheDocument(); // the cards wait
    await nextQuestion(state); // the old one
    await nextQuestion(state); // none
    await nextQuestion(state); // the new one
    expect(await screen.findByRole("heading", { level: 2, name: "Servis yeniden başladı." })).toBeInTheDocument();
    expect(await card("Adlar")).toBeInTheDocument();
  });

  it("says when no service answers within a minute and a half, and waits again on request", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    serve();
    let back = false;
    const state = serviceAnswers(() =>
      back ? HttpResponse.json(serviceState({ started_at: LATER })) : HttpResponse.error(),
    );
    server.use(
      http.post("/api/service/restart", () => {
        state.ended = true;
        return HttpResponse.json(RESTARTING, { status: 202 });
      }),
    );
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    await user.click(await within(await card("Servis")).findByRole("button", { name: "Yeniden başlat" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(GIVE_UP_MS + POLL_MS);
    });
    expect(await screen.findByRole("heading", { level: 2, name: "Servis yanıt vermiyor" })).toBeInTheDocument();
    expect(screen.getByText(/^Servis 90 saniyedir yanıt vermiyor\./)).toBeInTheDocument();
    back = true;
    await user.click(screen.getByRole("button", { name: "Yeniden bekle" }));
    await nextQuestion(state);
    expect(await screen.findByRole("heading", { level: 2, name: "Servis yeniden başladı." })).toBeInTheDocument();
  });

  it("lists the backups and puts one back after saying what happens, then asks to open the app again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    serve();
    let restored = "";
    // The restored service does not know this session: it answers with a closed one.
    const state = serviceAnswers(() => HttpResponse.json({ code: "signed_out", title: "Oturum yok" }, { status: 401 }));
    server.use(
      http.post("/api/backups/:name/restore", ({ params }) => {
        restored = String(params["name"]);
        state.ended = true;
        return HttpResponse.json({ backup: restored, restarts: true }, { status: 202 });
      }),
    );
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const backup = await card("Yedekler");
    const list = await within(backup).findByRole("list", { name: "Yedekler, en yenisi önce" });
    const [, manual, damaged] = within(list).getAllByRole("listitem");
    expect(manual).toHaveTextContent("Elle · sürüm 0.7.0 · 41 belge · 4,5 MB");
    expect(within(damaged!).getByText("1 dosyası bozuk")).toBeInTheDocument();
    expect(within(damaged!).getByRole("button", { name: /yedeğini geri yükle$/ })).toBeDisabled();
    await user.click(within(manual!).getByRole("button", { name: /yedeğini geri yükle$/ }));
    const asked = await screen.findByRole("alertdialog", { name: /yedeği geri yüklensin mi\?$/ });
    expect(asked).toHaveAccessibleDescription(/^Önce şu anki verinin yedeği alınır\. Sonra servis yeniden başlar/);
    await user.click(within(asked).getByRole("button", { name: "Geri yükle" }));
    expect(
      await screen.findByRole("heading", { level: 2, name: "Yedek geri yükleniyor; servis yeniden başlıyor…" }),
    ).toBeInTheDocument();
    await nextQuestion(state);
    const done = await screen.findByRole("heading", { level: 2, name: "Geri yükleme bitti; uygulamayı yeniden açın." });
    expect(done).toBeInTheDocument();
    expect(restored).toBe("2026-11-14 18.30.00");
    expect(screen.queryByText("Oturum kapandı")).not.toBeInTheDocument(); // the session was not lost by mistake
  });

  it("says when the new service could not put the backup back, and that the data stayed as it was", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    serve();
    // The start gave up on the backup: the data and its sessions stayed, so the same session reads why.
    const outcome = { backup: "2026-11-14 18.30.00", ok: false, error: "yedek bozuk: 1 belgenin aslı yok", at: LATER };
    const state = serviceAnswers(() => HttpResponse.json(serviceState({ started_at: LATER, restore: outcome })));
    server.use(
      http.post("/api/backups/:name/restore", ({ params }) => {
        state.ended = true;
        return HttpResponse.json({ backup: String(params["name"]), restarts: true }, { status: 202 });
      }),
    );
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const backup = await card("Yedekler");
    const list = await within(backup).findByRole("list", { name: "Yedekler, en yenisi önce" });
    const [, manual] = within(list).getAllByRole("listitem");
    await user.click(within(manual!).getByRole("button", { name: /yedeğini geri yükle$/ }));
    const asked = await screen.findByRole("alertdialog", { name: /yedeği geri yüklensin mi\?$/ });
    await user.click(within(asked).getByRole("button", { name: "Geri yükle" }));
    await nextQuestion(state);
    const failed = await screen.findByRole("region", { name: "Yedek geri yüklenemedi" });
    expect(within(failed).getByText("yedek bozuk: 1 belgenin aslı yok")).toBeInTheDocument();
    expect(within(failed).getByText(/^Veriler geri yüklemeden önceki hâliyle duruyor/)).toBeInTheDocument();
    expect(screen.queryByText("Geri yükleme bitti; uygulamayı yeniden açın.")).not.toBeInTheDocument();
  });

  it("says why a backup could not be put back, and the cards stay", async () => {
    serve();
    const why = "2026-11-14 18.30.00 yedeği bozuk: iplikci.db";
    server.use(
      http.post("/api/backups/:name/restore", () =>
        HttpResponse.json({ code: "backup_refused", title: why }, { status: 400 }),
      ),
    );
    const user = userEvent.setup();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const backup = await card("Yedekler");
    const restore = await within(backup).findAllByRole("button", { name: /yedeğini geri yükle$/ });
    await user.click(restore[1]!);
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Geri yükle" }));
    const refusal = await within(backup).findByRole("alert");
    expect(refusal).toHaveTextContent("Yedek geri yüklenemedi");
    expect(refusal).toHaveTextContent(why);
    expect(screen.getByRole("region", { name: "Adlar" })).toBeInTheDocument();
  });

  it("removes the service after asking, the data folder kept unless ticked, and says how the app goes", async () => {
    serve();
    const sent: unknown[] = [];
    server.use(
      http.post("/api/service/remove", async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json(ENDING, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    await user.click(await within(await card("Servis")).findByRole("button", { name: "Servisi kaldır" }));
    const asked = await screen.findByRole("alertdialog", { name: "Servis bu bilgisayardan kaldırılsın mı?" });
    const trash = within(asked).getByRole("checkbox", { name: "Veri klasörünü de çöp kutusuna taşı" });
    expect(trash).not.toBeChecked();
    const kept = /^Belgeleriniz, ayarlarınız ve veritabanı bu klasörde: \/veri\/iplikci\./;
    expect(trash).toHaveAccessibleDescription(kept);
    await user.click(within(asked).getByRole("button", { name: "Servisi kaldır" }));
    expect(
      await screen.findByRole("heading", { level: 2, name: "Servis bu bilgisayardan kaldırıldı" }),
    ).toBeInTheDocument();
    expect(sent).toEqual([{ data_to_trash: false }]);
    expect(screen.getByText("Veri klasörünüz yerinde kaldı: /veri/iplikci")).toBeInTheDocument();
    expect(screen.getByText(/^macOS'ta Finder'ı açın/)).toBeInTheDocument(); // launchd: the Mac's way alone
    expect(screen.queryByText(/^Windows'ta/)).not.toBeInTheDocument();
  });

  it("moves the data folder to the Trash only when ticked, naming every system's way when it cannot tell", async () => {
    serve();
    const sent: unknown[] = [];
    server.use(
      http.get("/api/service", () => HttpResponse.json(serviceState({ manager: "" }))),
      http.post("/api/service/remove", async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json(ENDING, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    await user.click(await within(await card("Servis")).findByRole("button", { name: "Servisi kaldır" }));
    const asked = await screen.findByRole("alertdialog", { name: "Servis bu bilgisayardan kaldırılsın mı?" });
    await user.click(within(asked).getByRole("checkbox", { name: "Veri klasörünü de çöp kutusuna taşı" }));
    await user.click(within(asked).getByRole("button", { name: "Servisi kaldır" }));
    expect(await screen.findByText(/^Servis kapanınca veri klasörü çöp kutusuna taşınır/)).toBeInTheDocument();
    expect(sent).toEqual([{ data_to_trash: true }]);
    for (const way of [/^macOS'ta/, /^Windows'ta Ayarlar → Uygulamalar → İplikçi Nedim → Kaldır/, /^Linux'ta/]) {
      expect(screen.getByText(way)).toBeInTheDocument();
    }
  });

  it("offers restarting, putting a backup back and removing to a registered service only, saying why", async () => {
    serve();
    server.use(http.get("/api/service", () => HttpResponse.json(serviceState({ registered: false }))));
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const service = await card("Servis");
    const restart = await within(service).findByRole("button", { name: "Yeniden başlat" });
    expect(restart).toBeDisabled();
    expect(restart).toHaveAccessibleDescription(/^Servis bu bilgisayara bu veri klasörü için kayıtlı değil\./);
    expect(within(service).getByRole("button", { name: "Servisi kaldır" })).toBeDisabled();
    expect(within(service).getByRole("button", { name: "Servisi durdur" })).toBeEnabled(); // it can end itself
    const backup = await card("Yedekler");
    const [restore] = await within(backup).findAllByRole("button", { name: /yedeğini geri yükle$/ });
    expect(restore).toBeDisabled();
    expect(restore).toHaveAccessibleDescription(/^Bir yedek, servis bu bilgisayara bu veri klasörü için kayıtlıyken/);
  });

  it("says when the service cannot end itself from here", async () => {
    serve();
    server.use(http.get("/api/service", () => HttpResponse.json(serviceState({ can_end: false }))));
    renderScreen(<SettingsPage />, { path: "/ayarlar" });
    const service = await card("Servis");
    expect(await within(service).findByText("Bu servis arayüzden durdurulamaz.")).toBeInTheDocument();
    expect(within(service).queryByRole("button")).not.toBeInTheDocument();
  });
});
