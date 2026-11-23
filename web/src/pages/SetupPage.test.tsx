import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import type { Settings } from "../api/types";
import { renderScreen } from "../test/render";
import { server, settings, SETUP } from "../test/server";
import SetupPage from "./SetupPage";

afterEach(() => localStorage.clear());

const panel = (step: string) => screen.findByRole("region", { name: new RegExp(`^Adım \\d/9: ${step}$`) });

/** The settings as given, then as each change leaves them; every change's body, in order. */
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
      } else if (params["what"] === "mail") {
        current = { ...current, mail: { ...current.mail, ...body } };
      }
      return HttpResponse.json(current);
    }),
  );
  return sent;
}

describe("SetupPage: the steps", () => {
  it("waits for the setup, then opens at the first step still to do, every step listed with its state", async () => {
    serve();
    renderScreen(<SetupPage />, { path: "/kurulum" });
    expect(screen.getByRole("status", { name: "Yükleniyor…" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "Kurulum sihirbazı" })).toBeInTheDocument();
    const step = await panel("Adınız");
    expect(within(step).getByText("Yapılmadı")).toBeInTheDocument();
    expect(within(step).getByText("Henüz ad yok.")).toBeInTheDocument(); // the service's note
    const list = screen.getByRole("navigation", { name: "Kurulum adımları" });
    const links = within(list).getAllByRole("link");
    expect(links).toHaveLength(10); // the nine steps and the summary
    expect(links[9]).toHaveTextContent("Kurulumun özeti");
    expect(links[0]).toHaveTextContent("Veri klasörüTamam");
    expect(links[1]).toHaveAttribute("aria-current", "step");
    expect(links[2]).toHaveTextContent("Şirket adlarıİsteğe bağlı");
    expect(links[8]).toHaveAttribute("href", "/kurulum?adim=remote");
  });

  it("goes on and back with the step in the address, the focus on the step's heading", async () => {
    serve();
    const user = userEvent.setup();
    const { location } = renderScreen(<SetupPage />, { path: "/kurulum" });
    const names = await panel("Adınız");
    expect(within(names).getByText(/^Bu adım gerekli: tamamlanmadan ilk değerlendirme/)).toBeInTheDocument();
    await user.click(within(names).getByRole("button", { name: "Şimdilik geç" }));
    expect(location()).toBe("/kurulum?adim=business_names");
    const business = await panel("Şirket adları");
    await waitFor(() => expect(within(business).getByRole("heading", { level: 2 })).toHaveFocus());
    expect(within(business).getByRole("button", { name: "Atla" })).toBeInTheDocument(); // an optional step
    await user.click(within(business).getByRole("button", { name: "Geri" }));
    expect(location()).toBe("/kurulum?adim=names");
  });

  it("leads from the last step's Bitir to where the setup stands: the required steps that wait, each a link", async () => {
    serve();
    const user = userEvent.setup();
    const { location } = renderScreen(<SetupPage />, { path: "/kurulum?adim=remote" });
    const remote = await panel("Uzaktan erişim");
    await user.click(within(remote).getByRole("button", { name: "Bitir" }));
    expect(location()).toBe("/kurulum?adim=ozet");
    const summary = await screen.findByRole("region", { name: "Kurulumda 3 adım bekliyor" });
    await waitFor(() => expect(within(summary).getByRole("heading", { level: 2 })).toHaveFocus());
    expect(within(summary).getByText("9 adımın 3 tanesi tamam")).toBeInTheDocument();
    const waiting = within(summary).getByRole("heading", { level: 3, name: "Bekleyen adımlar" }).nextElementSibling;
    expect(within(waiting as HTMLElement).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Adınız",
      "E-posta",
      "Eski belgeler",
    ]);
    expect(within(summary).getByRole("link", { name: "Adınız" })).toHaveAttribute("href", "/kurulum?adim=names");
    expect(within(summary).getByRole("link", { name: "Pano'ya git" })).toHaveAttribute("href", "/");
    expect(within(summary).getByRole("link", { name: "Ayarlar'a git" })).toHaveAttribute("href", "/ayarlar");
    const list = screen.getByRole("navigation", { name: "Kurulum adımları" });
    expect(within(list).getByRole("link", { name: "Kurulumun özeti" })).toHaveAttribute("aria-current", "page");
  });

  it("opens on 'Kurulum tamamlandı' once every required step is done, the optional ones not used listed", async () => {
    serve();
    server.use(
      http.get("/api/setup", () =>
        HttpResponse.json({
          ...SETUP,
          steps: SETUP.steps.map((step) => (step.optional ? step : { ...step, done: true })),
        }),
      ),
    );
    renderScreen(<SetupPage />, { path: "/kurulum" });
    const summary = await screen.findByRole("region", { name: "Kurulum tamamlandı" });
    expect(within(summary).getByText(/^İplikçi Nedim belgelerinizi kendiliğinden toplayıp yorumluyor\./)).toBeInTheDocument();
    expect(within(summary).queryByRole("heading", { name: "Bekleyen adımlar" })).not.toBeInTheDocument();
    const unused = within(summary).getByRole("heading", { level: 3, name: "Kullanmadığınız isteğe bağlı adımlar" });
    expect(within(unused.nextElementSibling as HTMLElement).getAllByRole("listitem").map((i) => i.textContent)).toEqual([
      "Şirket adlarıYok.",
      "BildirimlerYalnızca uygulama içi.",
      "Uzaktan erişimKapalı: yalnızca bu bilgisayardan.",
    ]);
    // The last, optional step is no longer where the wizard opens, as if nothing had been finished.
    expect(screen.queryByRole("region", { name: /^Adım 9\/9/ })).not.toBeInTheDocument();
  });

  it("shows the data folder, the banks read and the senders taken in", async () => {
    serve();
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum?adim=data_folder" });
    const folder = await panel("Veri klasörü");
    expect(within(folder).getByText("/veri/iplikci")).toBeInTheDocument(); // once: the step says it, not its note too
    expect(within(folder).queryByRole("button", { name: "Geri" })).not.toBeInTheDocument(); // the first step
    // Another computer's data comes from the sync folder, set on the Settings screen (ADR-0025).
    expect(within(folder).getByRole("link", { name: "Eşitleme ve yedek" })).toHaveAttribute("href", "/ayarlar");
    await user.click(screen.getByRole("link", { name: /^Bankalar ve göndericiler/ }));
    const senders = await panel("Bankalar ve göndericiler");
    const banks = within(senders).getByRole("list", { name: "Okunan banka adresleri" });
    const domains = within(banks).getAllByRole("listitem");
    expect(domains.map((item) => item.textContent)).toEqual(["garanti.com.tr", "teb.com.tr", "vakifbank.com.tr"]);
    expect(await within(senders).findByRole("region", { name: "Banka dışı göndericiler" })).toBeInTheDocument();
  });

  it("offers the upload panel, the notification channels, the service's state and remote access as off", async () => {
    serve();
    const user = userEvent.setup();
    const { location } = renderScreen(<SetupPage />, { path: "/kurulum?adim=documents" });
    expect(within(await panel("Eski belgeler")).getByRole("region", { name: "Belge ekle" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /^Bildirimler/ }));
    const channels = await panel("Bildirimler");
    expect(await within(channels).findByRole("region", { name: "Telegram" })).toBeInTheDocument();
    expect(within(channels).getByRole("region", { name: "Kanallar" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /^Servis/ }));
    const service = await panel("Servis");
    expect(await within(service).findByText(/^Sürüm 0\.4\.0; .* tarihinden beri çalışıyor\.$/)).toBeInTheDocument();
    expect(within(service).getByText("Bilgisayar açılınca kendiliğinden başlar.")).toBeInTheDocument(); // its note
    await user.click(within(service).getByRole("button", { name: "İleri" }));
    const remote = await panel("Uzaktan erişim");
    expect(within(remote).getByText("Kapalı: yalnızca bu bilgisayardan.")).toBeInTheDocument();
    expect(within(remote).getByText(/^Telefonunuzdan Tailscale ile .* gelecek;/)).toBeInTheDocument();
    expect(within(remote).getByText("İsteğe bağlı")).toBeInTheDocument();
    await user.click(within(remote).getByRole("button", { name: "Bitir" }));
    expect(location()).toBe("/kurulum?adim=ozet"); // where the setup stands, not the Pano as if nothing changed
  });

  it("says what a service not registered with the computer means, with no command to type", async () => {
    serve();
    server.use(
      http.get("/api/setup", () =>
        HttpResponse.json({
          ...SETUP,
          steps: SETUP.steps.map((step) =>
            step.step === "service" ? { ...step, done: false, note: "Bu bilgisayara kayıtlı değil." } : step,
          ),
        }),
      ),
    );
    renderScreen(<SetupPage />, { path: "/kurulum?adim=service" });
    const service = await panel("Servis");
    expect(within(service).getByText("Bu bilgisayara kayıtlı değil.")).toBeInTheDocument();
    expect(within(service).getByText(/^Servis şu an çalışıyor, ama bilgisayar yeniden başlayınca/)).toBeInTheDocument();
    expect(within(service).getByRole("button", { name: "Şimdilik geç" })).toBeInTheDocument();
  });

  it("says the setup could not be read and asks again", async () => {
    let asked = 0;
    server.use(
      http.get("/api/setup", () => {
        asked += 1;
        return asked === 1
          ? HttpResponse.json({ code: "settings_invalid", title: "settings.toml okunamadı" }, { status: 409 })
          : HttpResponse.json(SETUP);
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum" });
    expect(await screen.findByText("settings.toml okunamadı")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await panel("Adınız")).toBeInTheDocument();
  });
});

describe("SetupPage: names", () => {
  it("adds the user's name and its forms, saving the list whole, and takes one off", async () => {
    const sent = serve();
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum?adim=names" });
    const step = await panel("Adınız");
    await user.type(within(step).getByLabelText("Ad ya da adın bir biçimi"), "Örnek Kullanıcı");
    await user.click(within(step).getByRole("button", { name: "Ekle" }));
    expect(await within(step).findByText("Adlar kaydedildi.")).toBeInTheDocument();
    await user.type(within(step).getByLabelText("Ad ya da adın bir biçimi"), "ORNEK KULLANICI{Enter}");
    await within(step).findByRole("button", { name: "ORNEK KULLANICI adını kaldır" });
    expect(sent).toEqual([
      { path: "identity", body: { names: ["Örnek Kullanıcı"], business_names: [] } },
      { path: "identity", body: { names: ["Örnek Kullanıcı", "ORNEK KULLANICI"], business_names: [] } },
    ]);
    await user.click(within(step).getByRole("button", { name: "Örnek Kullanıcı adını kaldır" }));
    await waitFor(() => expect(sent).toHaveLength(3));
    expect(sent[2]).toEqual({ path: "identity", body: { names: ["ORNEK KULLANICI"], business_names: [] } });
  });

  it("says beside the field when a name is missing or already listed, sending nothing", async () => {
    const sent = serve(settings({ names: ["Örnek Kullanıcı"] }));
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum?adim=names" });
    const step = await panel("Adınız");
    const field = within(step).getByLabelText("Ad ya da adın bir biçimi");
    await user.click(within(step).getByRole("button", { name: "Ekle" }));
    expect(field).toHaveAccessibleDescription(/Bir ad yazın\.$/);
    expect(field).toHaveAttribute("aria-invalid", "true");
    await user.type(field, "örnek kullanıcı{Enter}");
    expect(field).toHaveAccessibleDescription(/Bu ad zaten listede\.$/);
    expect(sent).toEqual([]);
  });

  it("keeps the company names apart from the user's", async () => {
    const sent = serve(settings({ names: ["Örnek Kullanıcı"] }));
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum?adim=business_names" });
    const step = await panel("Şirket adları");
    await user.type(within(step).getByLabelText("Şirket adı"), "Örnek Danışmanlık Ltd.{Enter}");
    expect(await within(step).findByText("Şirket adları kaydedildi; belgeler yeniden okunuyor.")).toBeInTheDocument();
    expect(sent).toEqual([
      { path: "identity", body: { names: ["Örnek Kullanıcı"], business_names: ["Örnek Danışmanlık Ltd."] } },
    ]);
  });

  it("says why the service refused the names", async () => {
    serve();
    server.use(
      http.put("/api/settings/identity", () =>
        HttpResponse.json({ code: "settings_refused", title: "ad çok uzun" }, { status: 400 }),
      ),
    );
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum?adim=names" });
    const step = await panel("Adınız");
    await user.type(within(step).getByLabelText("Ad ya da adın bir biçimi"), "Örnek{Enter}");
    const field = within(step).getByLabelText("Ad ya da adın bir biçimi");
    await waitFor(() => expect(field).toHaveAccessibleDescription(/ad çok uzun$/));
  });
});

describe("SetupPage: e-mail", () => {
  it("offers the extension first: installing it from its folder, then a code to type into it", async () => {
    serve();
    server.use(http.post("/api/bridge/pairings", () => HttpResponse.json({ code: "ABCDEFGH", expires_in: 600 })));
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum?adim=mail" });
    const step = await panel("E-posta");
    expect(within(step).getByText("E-posta bağlantısı henüz kurulmadı.")).toBeInTheDocument();
    expect(within(step).getByRole("radio", { name: /^Tarayıcı eklentisi/ })).toBeChecked();
    const install = within(step).getByRole("region", { name: "Kur" });
    const pair = within(step).getByRole("region", { name: "Eşleştir" });
    expect(install.compareDocumentPosition(pair) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy(); // installed first
    expect(within(install).getByRole("button", { name: "Eklenti klasörünü aç" })).toBeInTheDocument();
    await user.click(within(step).getByRole("button", { name: "Eşleştirme kodu al" }));
    expect(await within(step).findByText("ABCD-EFGH")).toBeInTheDocument();
  });

  it("sets an IMAP account up with one login, keeping no password in the page", async () => {
    serve();
    const bodies: unknown[] = [];
    server.use(
      http.post("/api/settings/mail/imap", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ folder: "INBOX", in_keyring: true });
      }),
    );
    const user = userEvent.setup();
    const { client } = renderScreen(<SetupPage />, { path: "/kurulum?adim=mail" });
    const step = await panel("E-posta");
    await user.click(within(step).getByRole("radio", { name: /^Uygulama şifresi/ }));
    const send = within(step).getByRole("button", { name: "Hesabı kur" });
    expect(send).toBeDisabled();
    await user.type(within(step).getByLabelText("E-posta adresi"), "kisi@example.com");
    await user.type(within(step).getByLabelText("Uygulama şifresi"), "abcd efgh ijkl mnop");
    await user.click(send);
    expect(await within(step).findByText("Hesap kuruldu: INBOX klasörü okunacak.")).toBeInTheDocument();
    expect(bodies).toEqual([{ address: "kisi@example.com", password: "abcd efgh ijkl mnop", start: null }]);
    expect(within(step).getByLabelText("Uygulama şifresi")).toHaveValue("");
    const mutations = client.getMutationCache().getAll();
    expect(JSON.stringify(mutations.map((m) => m.state))).not.toContain("abcd efgh");
  });

  it("says why a login was refused and never tries again until the password is typed anew", async () => {
    serve();
    let asked = 0;
    server.use(
      http.post("/api/settings/mail/imap", () => {
        asked += 1;
        return HttpResponse.json(
          { code: "mail_refused", title: "Giriş reddedildi: uygulama şifresi yanlış." },
          { status: 400 },
        );
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum?adim=mail" });
    const step = await panel("E-posta");
    await user.click(within(step).getByRole("radio", { name: /^Uygulama şifresi/ }));
    await user.type(within(step).getByLabelText("E-posta adresi"), "kisi@example.com");
    await user.type(within(step).getByLabelText("Uygulama şifresi"), "yanlis");
    await user.click(within(step).getByRole("button", { name: "Hesabı kur" }));
    expect(await within(step).findByText("Giriş reddedildi: uygulama şifresi yanlış.")).toBeInTheDocument();
    const password = within(step).getByLabelText("Uygulama şifresi");
    expect(password).toHaveValue("");
    expect(password).toHaveAccessibleDescription(/Giriş reddedildi: uygulama şifresi yanlış\./);
    expect(within(step).getByRole("button", { name: "Hesabı kur" })).toBeDisabled();
    await new Promise((done) => setTimeout(done, 50));
    expect(asked).toBe(1); // nothing tried it again
    await user.type(password, "yeni");
    expect(within(step).getByRole("button", { name: "Hesabı kur" })).toBeEnabled();
  });

  it("shows the account masked, says a refused login stopped it, and removes it after asking", async () => {
    const stopped = settings({
      mail: {
        connector: "imap",
        configured: true,
        address: "k•••@example.com",
        start: "2026-01-01",
        server: "imap.example.com",
        stopped: true,
        last_error: "AUTHENTICATIONFAILED",
      },
    });
    serve(stopped);
    let removed = 0;
    server.use(
      http.delete("/api/settings/mail/imap", () => {
        removed += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum?adim=mail" });
    const step = await panel("E-posta");
    expect(within(step).getByText("k•••@example.com hesabının girişi reddedildi")).toBeInTheDocument();
    expect(within(step).getByText(/^Program reddedilen girişi yeniden denemez/)).toBeInTheDocument();
    expect(within(step).getByRole("radio", { name: /^Uygulama şifresi/ })).toBeChecked();
    await user.click(within(step).getByRole("button", { name: "Hesabı kaldır" }));
    const ask = await screen.findByRole("alertdialog", { name: "IMAP hesabı kaldırılsın mı?" });
    await user.click(within(ask).getByRole("button", { name: "Hesabı kaldır" }));
    expect(await within(step).findByText("IMAP hesabı kaldırıldı.")).toBeInTheDocument();
    expect(removed).toBe(1);
  });

  it("saves the day e-mail is read from", async () => {
    const sent = serve();
    const user = userEvent.setup();
    renderScreen(<SetupPage />, { path: "/kurulum?adim=mail" });
    const step = await panel("E-posta");
    expect(within(step).getByText("E-postalar 01.01.2026'dan itibaren okunuyor.")).toBeInTheDocument();
    fireEvent.change(within(step).getByLabelText("Okumaya başlama günü"), { target: { value: "2025-03-01" } });
    await user.click(within(step).getByRole("button", { name: "Günü kaydet" }));
    const saved = "Kaydedildi: e-postalar 01.03.2025'ten itibaren yeniden okunur.";
    expect(await within(step).findByText(saved)).toBeInTheDocument();
    expect(sent).toEqual([{ path: "mail", body: { start: "2025-03-01" } }]);
  });
});
