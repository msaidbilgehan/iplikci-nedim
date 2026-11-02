import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import type { CategoryRules, RuleChange, RuleEdit } from "../api/types";
import { renderScreen } from "../test/render";
import { CATEGORY_RULES, OWN_RULES, RULE_CHANGE, server } from "../test/server";
import RulesPage from "./RulesPage";

afterEach(() => localStorage.clear());

const region = (name: string) => screen.findByRole("region", { name });
const SAVED: RuleChange = { ...RULE_CHANGE, saved: true, backup: "personal 2026-11-15 09.00.00.yaml" };

/** The rules as given, then with the file a save wrote; every change the screen previews and saves, in order. */
function serve(rules: CategoryRules = OWN_RULES, preview: RuleChange = RULE_CHANGE) {
  const previewed: RuleEdit[] = [];
  const saved: RuleEdit[] = [];
  let current = rules;
  server.use(
    http.get("/api/rules/categories", () => HttpResponse.json(current)),
    http.post("/api/rules/categories/preview", async ({ request }) => {
      previewed.push((await request.json()) as RuleEdit);
      return HttpResponse.json(preview);
    }),
    http.put("/api/rules/categories", async ({ request }) => {
      saved.push((await request.json()) as RuleEdit);
      current = { ...current, content: SAVED.content };
      return HttpResponse.json(SAVED);
    }),
  );
  return { previewed, saved };
}

describe("RulesPage: what the rules hold", () => {
  it("waits for the rules, then lists the categories under their groups with their level and commitments", async () => {
    serve();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=kategoriler" });
    expect(screen.getByRole("status", { name: "Yükleniyor…" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "Kurallar" })).toBeInTheDocument();
    const categories = await region("Kategoriler");
    expect(within(categories).getByText("5 kategori, 5 grupta; 2 tanesi taahhüt kategorisi.")).toBeInTheDocument();
    expect(within(categories).getByRole("heading", { level: 3, name: "Gıda" })).toBeInTheDocument();
    const rent = within(categories).getByText("Kira").closest("li")!;
    expect(within(rent).getByText("Gerekli")).toBeInTheDocument();
    expect(within(rent).getByText("taahhüt")).toBeInTheDocument();
    expect(within(rent).getByRole("button", { name: "Taahhütten çıkar: Kira" })).toBeInTheDocument();
    const salary = within(categories).getByText("Maaş").closest("li")!;
    expect(within(salary).getByText("Belirsiz")).toBeInTheDocument(); // no rule says
    expect(within(salary).getByRole("button", { name: "Taahhüt say: Maaş" })).toBeInTheDocument();
  });

  it("lists the ended payments, the merchants weighed apart and the file's earlier versions", async () => {
    serve();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=biten" });
    const ended = await region("Biten ödemeler");
    expect(within(ended).getByText(/^Bittiğini yazdığınız 2 ödeme var;/)).toBeInTheDocument();
    const magazine = within(ended).getByText("Örnek Dergi").closest("li")!;
    expect(within(magazine).getByText("son ödeme Eylül 2026")).toBeInTheDocument();
    expect(within(magazine).getByRole("button", { name: "Yeniden bekle: Örnek Dergi" })).toBeInTheDocument();
    const shipped = within(ended).getByText("Eski Spor Salonu").closest("li")!;
    expect(within(shipped).getByText(/Uygulamayla gelir; buradan kaldırılamaz\./)).toBeInTheDocument();
    expect(within(shipped).queryByRole("button")).not.toBeInTheDocument(); // only the user's own is taken back
    await userEvent.click(screen.getByRole("tab", { name: "Gereklilik" }));
    const necessity = await region("İşyerlerinin gerekliliği");
    expect(within(necessity).getByText("1 işyerini kategorisinden farklı değerlendiriyorsunuz.")).toBeInTheDocument();
    expect(within(within(necessity).getByText("Örnek Kafe").closest("li")!).getByText("Gereksiz")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Dosya ve geçmiş" }));
    const history = await region("Geçmiş");
    const versions = within(history).getByRole("list", { name: "Kural dosyasının önceki sürümleri" });
    const earlier = within(versions).getAllByRole("listitem");
    expect(earlier.map((item) => item.textContent)).toEqual([
      "02.11.2026 10:00 öncesindeki sürüm",
      "20.10.2026 08:30 öncesindeki sürüm",
    ]);
  });

  it("says what is empty before the user has rules of their own", async () => {
    serve({ ...CATEGORY_RULES, ended: [] }); // the shipped rules alone
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=biten" });
    const ended = await region("Biten ödemeler");
    expect(within(ended).getByText(/^Bittiğini yazdığınız bir ödeme yok\./)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Gereklilik" }));
    const necessity = await region("İşyerlerinin gerekliliği");
    expect(
      within(necessity).getByText("Bütün işyerleri kategorilerinin gerekliliğiyle değerlendiriliyor."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Dosya ve geçmiş" }));
    const history = await region("Geçmiş");
    expect(within(history).getByText(/^Kişisel kural dosyanız henüz yok;/)).toBeInTheDocument();
  });

  it("says why the rules could not be read, and reads them again", async () => {
    let asked = 0;
    server.use(
      http.get("/api/rules/categories", () => {
        asked += 1;
        return asked === 1
          ? HttpResponse.json({ code: "rules_invalid", title: "kişisel kurallar okunamadı" }, { status: 409 })
          : HttpResponse.json(OWN_RULES);
      }),
    );
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar" });
    expect(await screen.findByText("kişisel kurallar okunamadı")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await region("İşyeri kuralı ekle")).toBeInTheDocument();
  });

  it("lists the categories in one table in the detailed view, with whose rule names each", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    serve();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=kategoriler" });
    const table = await screen.findByRole("table", { name: "Kategoriler, grupları ve gereklilik düzeyleri" });
    const market = within(table).getByText("Market").closest("tr")!;
    expect(within(market).getByText("Sizin kurallarınız")).toBeInTheDocument();
    const cafe = within(table).getByText("Kafe").closest("tr")!;
    expect(within(cafe).getByText("Hazır kurallar")).toBeInTheDocument();
    expect(within(cafe).getByText("Hayır")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /^Biten ödemeler/ }));
    const ended = await screen.findByRole("table", { name: "Biten ödemeler ve son ödeme ayları" });
    expect(within(within(ended).getByText("Örnek Dergi").closest("tr")!).getByText("Eylül 2026")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Dosya ve geçmiş" }));
    expect(within(await region("Geçmiş")).getByText("personal 2026-11-02 10.00.00.yaml")).toBeInTheDocument();
  });
});

describe("RulesPage: a merchant rule", () => {
  it("previews the rule before writing it, then says what it changed", async () => {
    const { previewed, saved } = serve();
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar" });
    const card = await region("İşyeri kuralı ekle");
    await user.type(within(card).getByLabelText("İşyerinin adı"), "Örnek Kafe");
    await user.type(within(card).getByLabelText("Desenler"), "ORNEK KAFE, KAFE ORNEK");
    await user.selectOptions(within(card).getByLabelText("Kategori"), "Kafe");
    await user.selectOptions(within(card).getByLabelText("Gereklilik"), "İsteğe bağlı");
    expect(within(card).queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument(); // not before a preview
    await user.click(within(card).getByRole("button", { name: "Önizle" }));
    expect(
      await within(card).findByText("Bu değişiklik 3 işlemin kategorisini, gerekliliğini ya da türünü değiştirir."),
    ).toBeInTheDocument();
    expect(previewed).toEqual([
      {
        action: "merchant",
        category: "Kafe",
        merchant: "Örnek Kafe",
        patterns: ["ORNEK KAFE", "KAFE ORNEK"],
        necessity: "optional",
      },
    ]);
    expect(within(card).getByText("Market → Kafe: 3 işlem, 2.521,50 TL")).toBeInTheDocument();
    const examples = within(card).getByRole("table", { name: "Değişecek işlemlerden örnekler" });
    const row = within(examples).getByText("ORNEK KAFE KADIKOY").closest("tr")!;
    expect(within(row).getByText("−840,50 TL")).toBeInTheDocument();
    expect(within(row).getByText("Market · Gerekli")).toBeInTheDocument();
    expect(within(row).getByText("Kafe · İsteğe bağlı")).toBeInTheDocument();
    expect(within(card).getByText("Kural dosyasındaki fark")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Kaydet" }));
    const notice = await within(card).findByText("Kaydedildi: 3 işlem değişti. Önceki sürüm geçmişe alındı.");
    expect(saved).toEqual(previewed);
    expect(within(card).getByLabelText("İşyerinin adı")).toHaveValue("");
    expect(within(card).queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
    // The button that saved is gone: the focus goes to what it did.
    await waitFor(() => expect(notice.closest("[tabindex]")).toHaveFocus());
  });

  it("says what is missing beside each field and goes to the first, asking nothing", async () => {
    const { previewed } = serve();
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar" });
    const card = await region("İşyeri kuralı ekle");
    await user.click(within(card).getByRole("button", { name: "Önizle" }));
    const name = within(card).getByLabelText("İşyerinin adı");
    expect(name).toHaveFocus();
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(name).toHaveAccessibleDescription(/İşyerinin adını yazın\./);
    expect(within(card).getByLabelText("Desenler")).toHaveAccessibleDescription(/En az bir desen yazın\./);
    expect(within(card).getByLabelText("Kategori")).toHaveAccessibleDescription("Bir kategori seçin.");
    await user.type(name, "Örnek Kafe");
    expect(name).not.toHaveAttribute("aria-invalid");
    expect(previewed).toEqual([]);
  });

  it("opens for a merchant from the address, its category left to choose", async () => {
    serve();
    renderScreen(<RulesPage />, { path: "/kurallar?isyeri=%C3%96rnek+Kafe" });
    const card = await region("İşyeri kuralı ekle");
    expect(within(card).getByLabelText("İşyerinin adı")).toHaveValue("Örnek Kafe");
    expect(within(card).getByLabelText("Desenler")).toHaveValue("Örnek Kafe");
    await waitFor(() => expect(within(card).getByLabelText("Kategori")).toHaveFocus());
  });

  it("says why the service refused to save", async () => {
    serve();
    server.use(
      http.put("/api/rules/categories", () =>
        HttpResponse.json(
          { code: "documents_busy", title: "Belgeler şu an okunuyor; birazdan yeniden deneyin." },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?isyeri=%C3%96rnek+Kafe" });
    const card = await region("İşyeri kuralı ekle");
    await user.selectOptions(within(card).getByLabelText("Kategori"), "Kafe");
    await user.click(within(card).getByRole("button", { name: "Önizle" }));
    await user.click(await within(card).findByRole("button", { name: "Kaydet" }));
    expect(await within(card).findByText("Kaydedilemedi")).toBeInTheDocument();
    expect(within(card).getByText("Belgeler şu an okunuyor; birazdan yeniden deneyin.")).toBeInTheDocument();
  });
});

describe("RulesPage: changes from the lists", () => {
  it("makes a category a commitment one after the panel shows what changes", async () => {
    const { previewed, saved } = serve();
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=kategoriler" });
    const categories = await region("Kategoriler");
    await user.click(within(categories).getByRole("button", { name: "Taahhüt say: Market" }));
    const panel = await screen.findByRole("dialog", { name: "Market taahhüt kategorisi olsun" });
    expect(within(panel).getByText("Bu kategorideki ödemeler, tutarı değişse de düzenli sayılır.")).toBeInTheDocument();
    expect(
      await within(panel).findByText("Bu değişiklik 3 işlemin kategorisini, gerekliliğini ya da türünü değiştirir."),
    ).toBeInTheDocument();
    expect(previewed).toEqual([{ action: "commitment", category: "Market", on: true }]);
    await user.click(within(panel).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(saved).toEqual(previewed);
    expect(within(categories).getByText(/^Kaydedildi: 3 işlem değişti\./)).toBeInTheDocument();
  });

  it("takes a commitment category back, and closes the panel without writing", async () => {
    const { previewed, saved } = serve();
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=kategoriler" });
    const categories = await region("Kategoriler");
    const toggle = within(categories).getByRole("button", { name: "Taahhütten çıkar: Kira" });
    await user.click(toggle);
    const panel = await screen.findByRole("dialog", { name: "Kira taahhüt kategorisi olmasın" });
    await within(panel).findByRole("button", { name: "Kaydet" });
    expect(previewed).toEqual([{ action: "commitment", category: "Kira", on: false }]);
    await user.click(within(panel).getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(toggle).toHaveFocus();
    expect(saved).toEqual([]);
  });

  it("expects an ended payment again from the panel", async () => {
    const { previewed, saved } = serve();
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=biten" });
    const ended = await region("Biten ödemeler");
    await user.click(within(ended).getByRole("button", { name: "Yeniden bekle: Örnek Dergi" }));
    const panel = await screen.findByRole("dialog", { name: "Örnek Dergi yeniden beklensin" });
    await user.click(await within(panel).findByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(previewed).toEqual([{ action: "not_ended", merchant: "Örnek Dergi" }]);
    expect(saved).toEqual(previewed);
  });

  it("writes a count with its thousands", async () => {
    serve(OWN_RULES, { ...RULE_CHANGE, changed: 1234 });
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=kategoriler" });
    await user.click(within(await region("Kategoriler")).getByRole("button", { name: "Taahhüt say: Market" }));
    const panel = await screen.findByRole("dialog");
    expect(await within(panel).findByText(/^Bu değişiklik 1\.234 işlemin kategorisini/)).toBeInTheDocument();
  });

  it("offers nothing to save when the rules would stay as they are", async () => {
    serve(OWN_RULES, { ...RULE_CHANGE, diff: "", changed: 0, moves: [], examples: [] });
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=kategoriler" });
    const categories = await region("Kategoriler");
    await user.click(within(categories).getByRole("button", { name: "Taahhüt say: Market" }));
    const panel = await screen.findByRole("dialog");
    expect(await within(panel).findByText(/^Kurallar zaten böyle:/)).toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
    expect(within(panel).getAllByRole("button", { name: "Kapat" })).not.toHaveLength(0);
  });

  it("writes an ended payment with its month, after saying why the service refused a name", async () => {
    const { previewed, saved } = serve();
    const refusal =
      "'Örnek Derg' adlı işyeri işlemlerde yok; işlemlerde göründüğü adı kullanın (yakın adlar: Örnek Dergi)";
    server.use(
      http.post("/api/rules/categories/preview", async ({ request }) => {
        const edit = (await request.json()) as RuleEdit;
        previewed.push(edit);
        return edit.action === "ended" && edit.merchant === "Örnek Derg"
          ? HttpResponse.json({ code: "rules_refused", title: refusal }, { status: 400 })
          : HttpResponse.json(RULE_CHANGE);
      }),
    );
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=biten" });
    const ended = await region("Biten ödemeler");
    const form = within(ended).getByRole("form", { name: "Biten ödeme ekle" });
    await user.click(within(form).getByRole("button", { name: "Önizle" }));
    expect(within(form).getByLabelText("İşyeri")).toHaveFocus();
    expect(within(form).getByLabelText("Son ödeme ayı")).toHaveAccessibleDescription(
      "Son ödemenin yapıldığı ay. Son ödemenin ayını seçin.",
    );
    await user.type(within(form).getByLabelText("İşyeri"), "Örnek Derg");
    fireEvent.change(within(form).getByLabelText("Son ödeme ayı"), { target: { value: "2026-10" } });
    await user.click(within(form).getByRole("button", { name: "Önizle" }));
    expect(await within(ended).findByText("Önizleme yapılamadı")).toBeInTheDocument();
    expect(within(ended).getByText(/yakın adlar: Örnek Dergi/)).toBeInTheDocument();
    expect(within(ended).queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
    await user.type(within(form).getByLabelText("İşyeri"), "i");
    expect(within(ended).queryByText("Önizleme yapılamadı")).not.toBeInTheDocument(); // the fields moved on
    await user.click(within(form).getByRole("button", { name: "Önizle" }));
    await user.click(await within(ended).findByRole("button", { name: "Kaydet" }));
    expect(await within(ended).findByText(/^Kaydedildi: 3 işlem değişti\./)).toBeInTheDocument();
    expect(saved).toEqual([{ action: "ended", merchant: "Örnek Dergi", month: "2026-10", note: "" }]);
    expect(within(form).getByLabelText("İşyeri")).toHaveValue("");
  });

  it("gives a merchant back to its category's level, and changes its level in the form", async () => {
    const { previewed, saved } = serve();
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=gereklilik" });
    const card = await region("İşyerlerinin gerekliliği");
    await user.click(within(card).getByRole("button", { name: "Kategorisine bırak: Örnek Kafe" }));
    const panel = await screen.findByRole("dialog", { name: "Örnek Kafe kategorisinin düzeyine dönsün" });
    await user.click(await within(panel).findByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(saved).toEqual([{ action: "necessity", merchant: "Örnek Kafe", necessity: null }]);

    await user.click(within(card).getByRole("button", { name: "Düzeyini değiştir: Örnek Kafe" }));
    const form = within(card).getByRole("form", { name: "Bir işyerinin gerekliliği" });
    expect(within(form).getByLabelText("İşyeri")).toHaveValue("Örnek Kafe");
    const level = within(form).getByLabelText("Gereklilik");
    expect(level).toHaveFocus();
    expect(level).toHaveValue("unnecessary");
    await user.selectOptions(level, "İsteğe bağlı");
    await user.click(within(form).getByRole("button", { name: "Önizle" }));
    await within(card).findByRole("button", { name: "Kaydet" });
    expect(previewed.at(-1)).toEqual({ action: "necessity", merchant: "Örnek Kafe", necessity: "optional" });
  });
});

describe("RulesPage: the rule file", () => {
  it("is edited whole in the detailed view, previewed and written", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    const { previewed, saved } = serve();
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=dosya" });
    const card = await region("Kural dosyası");
    const file = within(card).getByLabelText("Kişisel kurallar");
    expect(file).toHaveValue(OWN_RULES.content);
    await user.type(file, "Yeme içme:{Enter}");
    await user.click(within(card).getByRole("button", { name: "Önizle" }));
    await user.click(await within(card).findByRole("button", { name: "Kaydet" }));
    expect(await within(card).findByText(/^Kaydedildi: 3 işlem değişti\./)).toBeInTheDocument();
    expect(previewed).toEqual([{ action: "write", content: `${OWN_RULES.content}Yeme içme:\n` }]);
    expect(saved).toEqual(previewed);
    expect(file).toHaveValue(RULE_CHANGE.content); // the file as the service wrote it
  });

  it("ties the service's word on rules it cannot build to the file", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    serve();
    server.use(
      http.post("/api/rules/categories/preview", () =>
        HttpResponse.json({ code: "rules_refused", title: "kurallar okunamadı: 3. satır" }, { status: 400 }),
      ),
    );
    const user = userEvent.setup();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=dosya" });
    const card = await region("Kural dosyası");
    const file = within(card).getByLabelText("Kişisel kurallar");
    await user.type(file, "[["); // user-event's escape for one "["
    await user.click(within(card).getByRole("button", { name: "Önizle" }));
    expect(await within(card).findByText("kurallar okunamadı: 3. satır")).toBeInTheDocument();
    expect(file).toHaveAttribute("aria-invalid", "true");
    expect(file).toHaveAccessibleDescription(/kurallar okunamadı: 3\. satır/);
    expect(within(card).queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
  });

  it("offers the file's shape as an example while it is empty", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=dosya" }); // the shipped rules alone: no file of the user's yet
    const file = within(await region("Kural dosyası")).getByLabelText("Kişisel kurallar");
    expect(file).toHaveValue("");
    expect(file).toHaveAttribute("placeholder", "Yeme & İçme:\n  Kafe & Kahve:\n    Örnek Kafe: [ORNEK KAFE]\n");
  });

  it("is not in the simple view, which keeps the file's earlier versions", async () => {
    serve();
    renderScreen(<RulesPage />, { path: "/kurallar?bolum=dosya" });
    await region("Geçmiş");
    expect(screen.queryByRole("region", { name: "Kural dosyası" })).not.toBeInTheDocument();
  });
});
