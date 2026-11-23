import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SYNC_MOVING_MS, SYNC_WAIT_MS } from "../../api/queries";
import type { SyncPlace, SyncState } from "../../api/types";
import { renderScreen } from "../../test/render";
import { server, SYNC_FOLDER, SYNC_ME, SYNC_ON, SYNC_OTHER, SYNC_PLACE, syncState } from "../../test/server";
import { DRIVE_DOWNLOAD, SyncCard } from "./SyncCard";

afterEach(() => {
  localStorage.clear();
  vi.useRealTimers();
});

const card = () => screen.findByRole("region", { name: "Eşitleme ve yedek" });
const CONFIRM = "Eşitleme bu klasörde açılsın mı?";
const USE_DRIVE = "Bu klasörü kullan: Google Drive (kisi@example.com)";
const LATER = "2026-11-24T08:01:00+00:00"; // a round after SYNC_ON's

/** The sync as GET /api/sync gives it, changed by what a test's writes leave. */
function answer(start: SyncState) {
  const state = { current: start };
  server.use(http.get("/api/sync", () => HttpResponse.json(state.current)));
  return state;
}

function places(found: SyncPlace[]) {
  server.use(http.get("/api/sync/places", () => HttpResponse.json(found)));
}

describe("SyncCard while the sync is off", () => {
  it("lists Google Drive's folder, says what turning the sync on there does, then turns it on", async () => {
    const state = answer(syncState());
    places([SYNC_PLACE]);
    const sent: unknown[] = [];
    server.use(
      http.put("/api/sync", async ({ request }) => {
        sent.push(await request.json());
        state.current = { ...SYNC_ON, devices: [SYNC_ME], senders: {}, ready: [] };
        return HttpResponse.json(state.current);
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SyncCard />);
    const sync = await card();
    expect(await within(sync).findByText("Kapalı")).toBeInTheDocument();
    expect(within(sync).getByText(/^Kapalı: verileriniz yalnızca bu bilgisayarda\./)).toBeInTheDocument();
    const about = /^Açarsanız belgeleriniz ve kararlarınız \(notlar, kurallar, ayarlar\)/;
    expect(within(sync).getByText(about)).toBeInTheDocument();
    expect(await within(sync).findByText("Google Drive (kisi@example.com)")).toBeInTheDocument();
    expect(within(sync).getByText(SYNC_FOLDER)).toBeInTheDocument();
    expect(within(sync).getByText("Klasör yok; bu bilgisayarın verileriyle başlatılır.")).toBeInTheDocument();
    await user.click(within(sync).getByRole("button", { name: USE_DRIVE }));
    const asked = within(sync).getByRole("region", { name: CONFIRM });
    expect(within(asked).getByRole("heading", { name: CONFIRM })).toHaveFocus();
    expect(within(asked).getByText(/Google Drive uygulaması onları arka planda yükler\.$/)).toBeInTheDocument();
    expect(within(sync).queryByRole("button", { name: USE_DRIVE })).not.toBeInTheDocument(); // the list waits
    const name = within(asked).getByLabelText("Bu bilgisayarın adı");
    expect(name).toHaveAttribute("placeholder", "Dizüstü");
    expect(name).toHaveAccessibleDescription('Öteki bilgisayarlarda bu adla görünür. Boş bırakırsanız "Dizüstü" olur.');
    await user.click(within(asked).getByRole("button", { name: "Eşitlemeyi aç" }));
    expect(await within(sync).findByText("Eşitleme açıldı")).toBeInTheDocument();
    expect(sent).toEqual([{ folder: SYNC_FOLDER, name: "Dizüstü" }]); // the name the field showed
    expect(within(sync).getByText("Açık")).toBeInTheDocument();
    expect(within(sync).getByText("İplikçi Nedim (Google Drive)")).toBeInTheDocument();
    expect(within(sync).getByText(/^Açık: belgeleriniz ve kararlarınız Google Drive üzerinden bu bilgisayarın dışında/))
      .toBeInTheDocument();
    // The service begins the first round at once: the card follows it.
    expect(within(sync).getByRole("button", { name: "Eşitleniyor…" })).toBeDisabled();
  });

  it("says a folder holding other computers' data is joined, and what joining does to the decisions", async () => {
    answer(syncState({ device: SYNC_ME.id })); // this computer was in a set before
    const office = { ...SYNC_OTHER, id: "0123456789abcdef", name: "Ofis" };
    const iCloud = "/Users/ornek/Library/Mobile Documents/com~apple~CloudDocs/İplikçi Nedim";
    places([
      { ...SYNC_PLACE, exists: true, devices: [SYNC_OTHER, office] },
      { ...SYNC_PLACE, service: "iCloud Drive", account: "", folder: iCloud, exists: true, devices: [SYNC_ME] },
    ]);
    const user = userEvent.setup();
    renderScreen(<SyncCard />);
    const sync = await card();
    const joins = "Bu klasörde Masaüstü ve Ofis verileri var; bu bilgisayar onlara katılır.";
    expect(await within(sync).findByText(joins)).toBeInTheDocument();
    const rejoins = "Bu klasörde bu bilgisayarın önceki verileri var; eşitleme kaldığı yerden sürer.";
    expect(within(sync).getByText(rejoins)).toBeInTheDocument();
    const use = within(sync).getByRole("button", { name: USE_DRIVE });
    await user.click(use);
    const asked = within(sync).getByRole("region", { name: CONFIRM });
    expect(within(asked).getByText(joins)).toBeInTheDocument();
    expect(
      within(asked).getByText(
        "Katılınca belgeler birleşir; notlar, kurallar ve paylaşılan ayarlardan iki bilgisayarda da olanlarda " +
          "klasördeki geçerli olur (bu bilgisayardaki önceki kurallar Kurallar geçmişinde kalır).",
      ),
    ).toBeInTheDocument();
    await user.click(within(asked).getByRole("button", { name: "Vazgeç" }));
    expect(within(sync).queryByRole("region", { name: CONFIRM })).not.toBeInTheDocument();
    expect(use).toHaveFocus(); // back where the choice was made
  });

  it("leads to Google Drive's download when it is not on this computer, and checks a typed folder", async () => {
    const asked: unknown[] = [];
    const dropbox = "/Users/ornek/Dropbox/İplikçi Nedim";
    const full = "Belgeler klasörü boş değil; İplikçi Nedim için boş ya da yeni bir klasör seçin";
    server.use(
      http.post("/api/sync/inspect", async ({ request }) => {
        const { folder } = (await request.json()) as { folder: string };
        asked.push({ folder });
        return HttpResponse.json(
          folder === dropbox
            ? { ...SYNC_PLACE, service: "Dropbox", account: "", folder }
            : { ...SYNC_PLACE, service: "", account: "", folder, usable: false, problem: full },
        );
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SyncCard />);
    const sync = await card();
    expect(await within(sync).findByText(/^Bu bilgisayarda Google Drive bulunamadı\./)).toBeInTheDocument();
    const download = within(sync).getByRole("link", { name: "Google Drive'ı indirin (yeni sekmede açılır)" });
    expect(download).toHaveAttribute("href", DRIVE_DOWNLOAD);
    expect(download).toHaveAttribute("target", "_blank");
    expect(download).toHaveAttribute("rel", "noopener noreferrer");
    const field = within(sync).getByLabelText("Başka bir klasör");
    expect(field).toHaveAccessibleDescription(/^Eşitlenen bir klasörün tam yolu/);
    await user.click(within(sync).getByRole("button", { name: "Denetle" }));
    expect(field).toHaveAccessibleDescription(/Klasörün tam yolunu yazın\.$/);
    expect(field).toHaveFocus();
    await user.type(field, "/Users/ornek/Belgeler");
    await user.click(within(sync).getByRole("button", { name: "Denetle" }));
    expect(await within(sync).findByText(`Bu klasör kullanılamaz: ${full}`)).toBeInTheDocument();
    expect(within(sync).queryByRole("button", { name: /^Bu klasörü kullan/ })).not.toBeInTheDocument();
    await user.clear(field);
    await user.type(field, dropbox);
    await user.click(within(sync).getByRole("button", { name: "Denetle" }));
    expect(await within(sync).findByRole("button", { name: "Bu klasörü kullan: Dropbox" })).toBeInTheDocument();
    expect(within(sync).getByText("Klasör yok; bu bilgisayarın verileriyle başlatılır.")).toBeInTheDocument();
    expect(asked).toEqual([{ folder: "/Users/ornek/Belgeler" }, { folder: dropbox }]);
  });

  it("says why the service refused to turn the sync on, and keeps the choice open", async () => {
    places([SYNC_PLACE]);
    const sent: unknown[] = [];
    server.use(
      http.put("/api/sync", async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json(
          { code: "sync_refused", title: "klasöre yazılamadı: Permission denied" },
          { status: 400 },
        );
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SyncCard />);
    const sync = await card();
    await user.click(await within(sync).findByRole("button", { name: USE_DRIVE }));
    const asked = within(sync).getByRole("region", { name: CONFIRM });
    await user.type(within(asked).getByLabelText("Bu bilgisayarın adı"), "  Ev bilgisayarı ");
    await user.click(within(asked).getByRole("button", { name: "Eşitlemeyi aç" }));
    const refusal = await within(asked).findByRole("alert");
    expect(refusal).toHaveTextContent("Eşitleme açılamadı");
    expect(refusal).toHaveTextContent("klasöre yazılamadı: Permission denied");
    expect(sent).toEqual([{ folder: SYNC_FOLDER, name: "Ev bilgisayarı" }]);
    expect(within(sync).getByText("Kapalı")).toBeInTheDocument();
  });
});

describe("SyncCard while the sync is on", () => {
  it("shows the folder, the computers and who sends each channel, and moves Telegram's here", async () => {
    const state = answer(SYNC_ON);
    const sent: unknown[] = [];
    server.use(
      http.put("/api/sync/senders", async ({ request }) => {
        sent.push(await request.json());
        state.current = { ...SYNC_ON, senders: { ...SYNC_ON.senders, telegram: SYNC_ME.id } };
        return HttpResponse.json(state.current);
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SyncCard />);
    const sync = await card();
    expect(await within(sync).findByText("Açık")).toBeInTheDocument();
    const shared = /^Açık: belgeleriniz ve kararlarınız Google Drive üzerinden 2 bilgisayar arasında paylaşılıyor/;
    expect(within(sync).getByText(shared)).toBeInTheDocument();
    expect(within(sync).getByText("İplikçi Nedim (Google Drive)")).toBeInTheDocument();
    expect(within(sync).getByText(/^\d{2}\.11\.2026 \d{2}:\d{2}$/)).toBeInTheDocument(); // the last round
    expect(within(sync).getByText("42 belge")).toBeInTheDocument();
    const computers = within(sync).getByRole("region", { name: "Bilgisayarlar" });
    const [me, other] = within(computers).getAllByRole("listitem");
    expect(me).toHaveTextContent(/^Dizüstü \(bu bilgisayar\)macOS · sürüm 1\.0\.14Son görülme: /);
    expect(other).toHaveTextContent(/^MasaüstüWindows · sürüm 1\.0\.13Son görülme: \d{2}\.11\.2026 \d{2}:\d{2}$/);
    const senders = within(sync).getByRole("region", { name: "Telegram ve e-posta bildirimleri" });
    expect(within(senders).getByText(/^Telegram ve e-posta bildirimleri tek bilgisayardan gider;/)).toBeInTheDocument();
    expect(await within(senders).findByText("Telegram bildirimlerini Masaüstü gönderiyor.")).toBeInTheDocument();
    expect(within(senders).getByText("E-posta bildirimlerini Masaüstü gönderiyor.")).toBeInTheDocument();
    expect(within(senders).getAllByRole("button")).toHaveLength(1); // this computer cannot send e-mail
    await user.click(within(senders).getByRole("button", { name: "Bu bilgisayar göndersin: Telegram" }));
    expect(await within(senders).findByText("Telegram bildirimlerini bu bilgisayar gönderiyor.")).toBeInTheDocument();
    expect(within(senders).getByText("Telegram bildirimleri artık bu bilgisayardan gidiyor.")).toBeInTheDocument();
    expect(within(senders).queryByRole("button")).not.toBeInTheDocument();
    expect(sent).toEqual([{ channels: ["telegram"] }]);
  });

  it("says a channel no computer sends yet, and a computer that left", async () => {
    answer({
      ...SYNC_ON,
      devices: [SYNC_ME, { ...SYNC_OTHER, left: true }],
      senders: {},
      ready: ["telegram", "email"],
    });
    renderScreen(<SyncCard />);
    const sync = await card();
    const senders = await within(sync).findByRole("region", { name: "Telegram ve e-posta bildirimleri" });
    const none = "Telegram bildirimlerini gönderecek bilgisayar bir sonraki eşitlemede seçilir.";
    expect(await within(senders).findByText(none)).toBeInTheDocument();
    expect(within(senders).getAllByRole("button", { name: /^Bu bilgisayar göndersin/ })).toHaveLength(2);
    expect(within(sync).getByText("Eşitlemeyi kapattı")).toBeInTheDocument();
    // A computer that left shares nothing any more: the data is kept off this computer alone.
    expect(within(sync).getByText(/^Açık: belgeleriniz ve kararlarınız Google Drive üzerinden bu bilgisayarın dışında/))
      .toBeInTheDocument();
  });

  it("says what still moves, and why the last round failed and since when", async () => {
    answer({
      ...SYNC_ON,
      waiting_down: 3,
      waiting_up: 1,
      problem: "Masaüstü: durum dosyası okunamadı",
      since: "2026-11-24T06:00:00+00:00",
    });
    renderScreen(<SyncCard />);
    const sync = await card();
    expect(await within(sync).findByText("Sorun var")).toBeInTheDocument();
    expect(within(sync).getByText(/^Son eşitleme yapılamadı; nedeni/)).toBeInTheDocument(); // the simple view's
    expect(within(sync).getByText("3 belge öteki bilgisayarlardan geliyor")).toBeInTheDocument();
    expect(within(sync).getByText("1 belge klasöre gidiyor")).toBeInTheDocument();
    expect(within(sync).getByText("Son eşitleme yapılamadı")).toBeInTheDocument();
    expect(within(sync).getByText("Masaüstü: durum dosyası okunamadı")).toBeInTheDocument();
    expect(within(sync).getByText(/^Sorun \d{2}\.11\.2026 \d{2}:\d{2} tarihinden beri sürüyor\.$/)).toBeInTheDocument();
    expect(within(sync).getByText(/^Google Drive uygulamasının açık olduğuna/)).toBeInTheDocument();
  });

  it("renames this computer in place and gives the focus back to the button", async () => {
    const state = answer(SYNC_ON);
    const sent: unknown[] = [];
    server.use(
      http.put("/api/sync/name", async ({ request }) => {
        const body = (await request.json()) as { name: string };
        sent.push(body);
        state.current = { ...SYNC_ON, name: body.name };
        return HttpResponse.json(state.current);
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SyncCard />);
    const sync = await card();
    const toggle = await within(sync).findByRole("button", { name: "Adını değiştir" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const field = within(sync).getByLabelText("Bu bilgisayarın adı");
    expect(field).toHaveFocus();
    expect(field).toHaveValue("Dizüstü");
    await user.clear(field);
    await user.type(field, "Ev{Enter}");
    expect(await within(sync).findByText("Bu bilgisayarın adı kaydedildi.")).toBeInTheDocument();
    expect(sent).toEqual([{ name: "Ev" }]);
    expect(within(sync).getByText("Ev")).toBeInTheDocument();
    expect(within(sync).queryByLabelText("Bu bilgisayarın adı")).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });

  it("asks before turning the sync off, then says the folder and the data stay", async () => {
    const state = answer(SYNC_ON);
    let removed = 0;
    server.use(
      http.delete("/api/sync", () => {
        removed += 1;
        state.current = syncState({ device: SYNC_ME.id });
        return HttpResponse.json(state.current);
      }),
    );
    const user = userEvent.setup();
    renderScreen(<SyncCard />);
    const sync = await card();
    await user.click(await within(sync).findByRole("button", { name: "Eşitlemeyi kapat" }));
    const asked = await screen.findByRole("alertdialog", { name: "Eşitleme kapatılsın mı?" });
    expect(asked).toHaveAccessibleDescription(
      "Klasör ve veriler olduğu gibi kalır; bu bilgisayar değişiklikleri artık almaz ve göndermez.",
    );
    await user.click(within(asked).getByRole("button", { name: "Vazgeç" }));
    expect(removed).toBe(0); // the user said no
    await user.click(within(sync).getByRole("button", { name: "Eşitlemeyi kapat" }));
    const again = await screen.findByRole("alertdialog", { name: "Eşitleme kapatılsın mı?" });
    await user.click(within(again).getByRole("button", { name: "Eşitlemeyi kapat" }));
    expect(await within(sync).findByText("Eşitleme kapandı")).toBeInTheDocument();
    expect(removed).toBe(1);
    expect(within(sync).getByText("Kapalı")).toBeInTheDocument();
    await waitFor(() => expect(document.activeElement).toHaveTextContent(/^Eşitleme kapandı/)); // its button is gone
  });

  it("asks for a round now and says when it ran", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const state = answer(SYNC_ON);
    let asked = 0;
    server.use(
      http.post("/api/sync/round", () => {
        asked += 1;
        state.current = { ...SYNC_ON, last_at: LATER }; // the service runs it at once; the card hears of it later
        return HttpResponse.json({ asked: true }, { status: 202 });
      }),
    );
    renderScreen(<SyncCard />);
    const sync = await card();
    await user.click(await within(sync).findByRole("button", { name: "Şimdi eşitle" }));
    expect(await within(sync).findByRole("button", { name: "Eşitleniyor…" })).toBeDisabled();
    expect(within(sync).getByText("Eşitleme istendi; sonuç birkaç saniye içinde burada görünür.")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(SYNC_WAIT_MS);
    });
    expect(await within(sync).findByText("Eşitleme yapıldı.")).toBeInTheDocument();
    expect(within(sync).getByRole("button", { name: "Şimdi eşitle" })).toBeEnabled();
    expect(asked).toBe(1);
  });

  it("asks again every ten seconds while documents still move", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let asked = 0;
    server.use(
      http.get("/api/sync", () => {
        asked += 1;
        return HttpResponse.json({ ...SYNC_ON, waiting_up: asked === 1 ? 2 : 0 });
      }),
    );
    renderScreen(<SyncCard />);
    const sync = await card();
    expect(await within(sync).findByText("2 belge klasöre gidiyor")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(SYNC_MOVING_MS);
    });
    await waitFor(() => expect(within(sync).queryByText("2 belge klasöre gidiyor")).not.toBeInTheDocument());
    expect(asked).toBe(2);
  });

  it("adds the folder's path and the computers' ids and channels in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    answer(SYNC_ON);
    renderScreen(<SyncCard />);
    const sync = await card();
    expect(await within(sync).findByText(SYNC_FOLDER)).toBeInTheDocument();
    expect(within(sync).getAllByText(SYNC_ME.id)).toHaveLength(2); // this computer's id, and in the list
    expect(within(sync).getByText(SYNC_OTHER.id)).toBeInTheDocument();
    expect(await within(sync).findByText("Gönderebildiği bildirimler: Telegram, E-posta")).toBeInTheDocument();
    expect(within(sync).queryByText(/^Açık: belgeleriniz/)).not.toBeInTheDocument(); // the simple view's sentence
  });
});
