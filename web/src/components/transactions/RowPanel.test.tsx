import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import type { Annotation, Necessity, RuleChange, TransactionDetail } from "../../api/types";
import TransactionsPage from "../../pages/TransactionsPage";
import { renderScreen } from "../../test/render";
import {
  EXCLUDED,
  INCOME,
  NOWHERE,
  PARTS,
  PURCHASE,
  RECEIPT,
  server,
  SPLIT_DETAIL,
  STATEMENT,
  tl,
  transactionDetail,
} from "../../test/server";

afterEach(() => localStorage.clear());

const NOTHING_KEPT: Annotation = { note: "", tags: [], category: "", necessity: null, updated_at: "" };

/**
 * The service for one row: its detail with the annotation read fresh, as the database keeps it, and the corrections
 * it is sent; others are rows a link may open. The screen opens with the row's detail.
 */
function serve(detail: TransactionDetail, { others = [] as TransactionDetail[], at = detail.row.fingerprint } = {}) {
  let annotation = detail.annotation;
  const sent: Array<Record<string, unknown>> = [];
  server.use(
    http.get("/api/transactions/:fingerprint", ({ params }) => {
      const other = others.find((found) => found.row.fingerprint === params["fingerprint"]);
      return HttpResponse.json(other ?? { ...detail, annotation });
    }),
    http.put("/api/transactions/:fingerprint/annotation", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      sent.push(body);
      const was = annotation ?? NOTHING_KEPT;
      annotation = {
        note: typeof body["note"] === "string" ? body["note"] : was.note,
        tags: Array.isArray(body["tags"]) ? (body["tags"] as string[]) : was.tags,
        category: typeof body["category"] === "string" ? body["category"] : was.category,
        necessity: "necessity" in body ? ((body["necessity"] as Necessity | "") || null) : was.necessity,
        updated_at: "2026-11-15T10:00:00+00:00",
      };
      return HttpResponse.json(annotation);
    }),
  );
  const screenResult = renderScreen(<TransactionsPage />, { path: `/islemler?satir=${at}` });
  return { ...screenResult, sent };
}

const panel = (name: string) => screen.findByRole("dialog", { name });
const region = async (name: string, row = PURCHASE.title) => within(await panel(row)).getByRole("region", { name });

describe("RowPanel: what the row is and why", () => {
  it("names the row with its amount, day and account, and says where it counts and why", async () => {
    serve(transactionDetail());
    const detail = await panel(PURCHASE.title);
    expect(within(detail).getByText("−840,50 TL")).toBeInTheDocument();
    expect(within(detail).getByText("· 12.11.2026")).toBeInTheDocument();
    expect(
      within(detail).getByText("Market kategorisinde sayılıyor. Nedeni: Kategori kuralı (ORNEK MARKET)."),
    ).toBeInTheDocument();
    const facts = within(detail).getByRole("region", { name: "Ayrıntılar" });
    expect(within(facts).getByText("Market · Gıda")).toBeInTheDocument();
    expect(within(facts).getByText("Gerekli")).toBeInTheDocument();
    expect(within(facts).getByText("#ev")).toBeInTheDocument();
    expect(within(facts).getByText("haftalık alışveriş")).toBeInTheDocument();
    expect(within(facts).getByText(PURCHASE.description)).toBeInTheDocument();
  });

  it("says which rule gave the category and the necessity, from which file, and the evidence behind the row", async () => {
    serve(transactionDetail());
    const why = await region("Neden?");
    expect(within(why).getByText("Kategori kuralı · Kural: ORNEK MARKET · Hazır kurallar")).toBeInTheDocument();
    expect(within(why).getByText("Kategorisinin düzeyi · Hazır kurallar")).toBeInTheDocument();
    expect(within(why).getByText("Ekstreyle eşleşti: 12.11.2026, 840,50 TL")).toBeInTheDocument();
    expect(within(why).getByText("Örnek Banka dekontu")).toBeInTheDocument();
    expect(within(why).queryByText("Parmak izi")).not.toBeInTheDocument(); // the detailed view's
  });

  it("shows the fingerprint, and that no receipt tells the row, in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    serve(transactionDetail({ told: [] }));
    const why = await region("Neden?");
    expect(within(why).getByText("Bu satırı gösteren dekont ya da bildirim yok.")).toBeInTheDocument();
    expect(within(why).getByText(PURCHASE.fingerprint)).toBeInTheDocument();
  });

  it("names a transfer's pair in another account with the rate, and opens the pair in the panel", async () => {
    const pair = { ...INCOME, fingerprint: "b9b9b9b9b9b9b9b9b9b9", title: "Örnek Vadesiz TL hesabından gelen" };
    const plain = transactionDetail();
    const transfer = transactionDetail({
      row: { ...PURCHASE, kind: "own_transfer", necessity: null },
      why: {
        ...plain.why,
        category: "own_transfer",
        rule: "",
        layer: null,
        necessity: null,
        necessity_layer: null,
        transfer: "paired",
        pair,
        rate: "34.5012",
        rate_day: "2026-11-10",
      },
    });
    const user = userEvent.setup();
    serve(transfer, { others: [transactionDetail({ row: pair })] });
    const why = await region("Neden?");
    expect(within(why).getByText("Başka bir hesabınızda karşılığı var")).toBeInTheDocument();
    expect(within(why).getByText("34,5012 TL, 10.11.2026 belgesindeki kurla")).toBeInTheDocument();
    expect(within(why).queryByText("Gerekliliği")).not.toBeInTheDocument(); // a transfer is no spending
    const link = within(why).getByRole("link", { name: pair.title });
    expect(link).toHaveAttribute("href", `/islemler?satir=${pair.fingerprint}`);
    await user.click(link);
    expect(await panel(pair.title)).toBeInTheDocument();
  });

  it("shows where the row is printed, its box on the page, and offers the original", async () => {
    serve(transactionDetail());
    const printed = await region("Belgede");
    expect(within(printed).getByText("Örnek Kart Ekstresi Kasım 2026")).toBeInTheDocument();
    expect(within(printed).getByText("Kart ekstresi · Sayfa 2 · satır 14")).toBeInTheDocument();
    const page = await within(printed).findByRole("img", {
      name: "Örnek Kart Ekstresi Kasım 2026, sayfa 2; işlemin satırı işaretli",
    });
    expect(page).toHaveAttribute("src", `/api/documents/${STATEMENT}/pages/2.png?width=1000`);
    expect(within(printed).getByRole("link", { name: "Aslını indir" })).toHaveAttribute(
      "href",
      `/api/documents/${STATEMENT}/download`,
    );
  });

  it("shows the page's text with the row's line marked when the row has no box", async () => {
    server.use(http.get("/api/documents/:sha256", () => HttpResponse.json({ rows: [] })));
    serve(transactionDetail());
    const printed = await region("Belgede");
    const lines = await within(printed).findByRole("list", { name: "Sayfanın metni" });
    expect(within(lines).getByText("12.11.2026 ORNEK MARKET KADIKOY 840,50", { selector: "mark" })).toBeInTheDocument();
    expect(within(lines).getAllByRole("listitem")).toHaveLength(7); // three lines on each side
  });

  it("shows a sheet's rows around the row's own, the row marked", async () => {
    server.use(
      http.get("/api/documents/:sha256/view", () =>
        HttpResponse.json({
          kind: "table",
          pages: [],
          table: {
            name: "Hareketler",
            rows: [
              ["Tarih", "Açıklama", "Tutar"],
              ["12.11.2026", "ORNEK MARKET", "-840,50"],
            ],
            more: false,
          },
          mail: null,
          text: "",
          has_html: false,
        }),
      ),
    );
    const sheet = { ...transactionDetail().printed!, page: null, line: null, sheet: "Hareketler", row: 2 };
    serve(transactionDetail({ printed: sheet }));
    const printed = await region("Belgede");
    const rows = await within(printed).findByRole("table", { name: "Belgedeki tablo, işlemin satırı işaretli" });
    expect(within(rows).getByRole("rowheader", { name: "2 (işlemin satırı)" })).toBeInTheDocument();
    expect(within(rows).getByText("ORNEK MARKET")).toBeInTheDocument();
  });

  it("marks a notice's words in its e-mail", async () => {
    const text = "Sayın müşterimiz, kartınızla ORNEK MARKET işyerinde 840,50 TL harcama yapılmıştır. İyi günler.";
    const from = text.indexOf("ORNEK MARKET");
    server.use(
      http.get("/api/documents/:sha256/view", () =>
        HttpResponse.json({
          kind: "mail",
          pages: [],
          table: null,
          mail: { subject: "Harcama bildirimi", sender: "ornekbanka.example", sent: "", lines: [text], text },
          text: "",
          has_html: false,
        }),
      ),
      http.get("/api/documents/:sha256", () =>
        HttpResponse.json({
          rows: [
            {
              fingerprint: PURCHASE.fingerprint,
              ref: { page: null, box: null, line: null, sheet: null, row: null, span: [from, from + 12] },
            },
          ],
        }),
      ),
    );
    const notice = { ...NOWHERE, document: RECEIPT, name: "Harcama bildirimi", kind: null };
    serve(transactionDetail({ printed: notice }));
    const printed = await region("Belgede");
    const marked = await within(printed).findByText("ORNEK MARKET", { selector: "mark" });
    expect(marked.closest("figure")).toHaveAccessibleName("Belgenin metni, işlemin yeri işaretli");
  });

  it("says a row the statements leave out carries no correction", async () => {
    serve(transactionDetail({ row: EXCLUDED, correctable: false, splittable: false, annotation: null }));
    const detail = await panel(EXCLUDED.title);
    expect(within(detail).getByText("Bu satır ekstrede görünmüyor; hiçbir toplama girmez.")).toBeInTheDocument();
    const fix = within(detail).getByRole("region", { name: "Düzeltmeler" });
    expect(within(fix).getByText("Bu satır toplamlara girmez; düzeltme taşımaz.")).toBeInTheDocument();
    expect(within(fix).queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("closes, taking the row out of the address", async () => {
    const user = userEvent.setup();
    const { location } = serve(transactionDetail());
    await user.click(within(await panel(PURCHASE.title)).getByRole("button", { name: "Kapat" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(location()).toBe("/islemler");
  });

  it("says when no row has the fingerprint", async () => {
    server.use(
      http.get("/api/transactions/:fingerprint", () =>
        HttpResponse.json({ code: "transaction_not_found", title: "Bu parmak iziyle bir işlem yok." }, { status: 404 }),
      ),
    );
    renderScreen(<TransactionsPage />, { path: "/islemler?satir=0000000000aaaaaaaaaa" });
    expect(await within(await panel("İşlem")).findByText("Bu parmak iziyle bir işlem yok.")).toBeInTheDocument();
  });
});

describe("RowPanel: corrections", () => {
  it("gives this row alone another category, and says it shows once the analysis settles", async () => {
    const user = userEvent.setup();
    const { sent } = serve(transactionDetail());
    const fix = await region("Düzeltmeler");
    const only = within(fix).getByRole("button", { name: "Yalnızca bu işleme ver" });
    expect(only).toBeDisabled(); // the category it has
    await user.selectOptions(within(fix).getByLabelText("Kategori"), "Kafe");
    await user.click(only);
    expect(
      await within(fix).findByText("Kaydedildi; işlem birkaç saniye içinde yeni hâliyle görünür."),
    ).toBeInTheDocument();
    expect(sent).toEqual([{ category: "Kafe" }]);
    expect(within(fix).getByText("Sizin düzeltmeniz: Kafe")).toBeInTheDocument();
    expect(only).toBeDisabled();
  });

  it("gives a corrected category back to the rules", async () => {
    const user = userEvent.setup();
    const corrected = transactionDetail();
    const { sent } = serve({ ...corrected, annotation: { ...corrected.annotation!, category: "Kafe" } });
    const fix = await region("Düzeltmeler");
    expect(within(fix).getByText("Sizin düzeltmeniz: Kafe")).toBeInTheDocument();
    expect(within(fix).getByLabelText("Kategori")).toHaveValue("Kafe");
    await user.click(within(fix).getByRole("button", { name: "Kurallara bırak" }));
    expect(
      await within(fix).findByText("Kaydedildi; işlem birkaç saniye içinde yeni hâliyle görünür."),
    ).toBeInTheDocument();
    expect(sent).toEqual([{ category: "" }]);
    expect(within(fix).queryByText("Sizin düzeltmeniz: Kafe")).not.toBeInTheDocument();
  });

  it("makes the category a rule for the merchant only after showing what it would change", async () => {
    const change: RuleChange = {
      content: "kategoriler: …",
      diff: "+  Kafe:\n+    - ORNEK",
      changed: 3,
      moves: [{ before: "Market", after: "Kafe", count: 3, total: tl(252150) }],
      examples: [
        {
          fingerprint: PURCHASE.fingerprint,
          day: "2026-11-12",
          description: PURCHASE.description,
          amount: tl(84050),
          before: { merchant: "Örnek Market", category: "Market", necessity: "required", kind: "purchase" },
          after: { merchant: "Örnek Market", category: "Kafe", necessity: "optional", kind: "purchase" },
        },
      ],
      saved: false,
      backup: "",
    };
    const previewed: unknown[] = [];
    const saved: unknown[] = [];
    server.use(
      http.post("/api/rules/categories/preview", async ({ request }) => {
        previewed.push(await request.json());
        return HttpResponse.json(change);
      }),
      http.put("/api/rules/categories", async ({ request }) => {
        saved.push(await request.json());
        return HttpResponse.json({ ...change, saved: true, backup: "kurallar-1.yaml" });
      }),
    );
    const user = userEvent.setup();
    serve(transactionDetail());
    const fix = await region("Düzeltmeler");
    await user.selectOptions(within(fix).getByLabelText("Kategori"), "Kafe");
    await user.click(within(fix).getByRole("button", { name: "Kural olarak…" }));
    expect(within(fix).getByLabelText("İşyerinin adı")).toHaveValue("Örnek Market");
    expect(within(fix).getByLabelText("Desenler")).toHaveValue("ORNEK");
    expect(within(fix).queryByRole("button", { name: "Kuralı kaydet" })).not.toBeInTheDocument(); // not before a preview
    await user.click(within(fix).getByRole("button", { name: "Önizle" }));
    expect(
      await within(fix).findByText("Bu kural 3 işlemin kategorisini, gerekliliğini ya da türünü değiştirir."),
    ).toBeInTheDocument();
    expect(within(fix).getByText("Market → Kafe: 3 işlem, 2.521,50 TL")).toBeInTheDocument();
    expect(within(fix).getByRole("table", { name: "Değişecek işlemlerden örnekler" })).toBeInTheDocument();
    expect(previewed).toEqual([{ action: "merchant", category: "Kafe", merchant: "Örnek Market", patterns: ["ORNEK"] }]);
    await user.click(within(fix).getByRole("button", { name: "Kuralı kaydet" }));
    expect(await within(fix).findByText("Kural kaydedildi: 3 işlem değişti.")).toBeInTheDocument();
    expect(saved).toEqual(previewed);
    await user.click(within(fix).getByRole("button", { name: "Kapat" }));
    expect(within(fix).queryByLabelText("Desenler")).not.toBeInTheDocument();
  });

  it("corrects the necessity, and gives it back to the rules", async () => {
    const user = userEvent.setup();
    const { sent } = serve(transactionDetail());
    const fix = await region("Düzeltmeler");
    const save = within(fix).getByRole("button", { name: "Gerekliliği kaydet" });
    expect(save).toBeDisabled();
    await user.selectOptions(within(fix).getByLabelText("Gereklilik"), "unnecessary");
    await user.click(save);
    expect(await within(fix).findByText("Sizin düzeltmeniz: Gereksiz")).toBeInTheDocument();
    expect(save).toBeDisabled();
    await user.selectOptions(within(fix).getByLabelText("Gereklilik"), "");
    await user.click(save);
    await waitFor(() => expect(within(fix).queryByText("Sizin düzeltmeniz: Gereksiz")).not.toBeInTheDocument());
    expect(sent).toEqual([{ necessity: "unnecessary" }, { necessity: "" }]);
  });

  it("keeps a note, shown at once", async () => {
    const user = userEvent.setup();
    const { sent } = serve(transactionDetail());
    const facts = await region("Ayrıntılar");
    const fix = await region("Düzeltmeler");
    const note = within(fix).getByLabelText("Not");
    await user.clear(note);
    await user.type(note, "misafir için");
    await user.click(within(fix).getByRole("button", { name: "Notu kaydet" }));
    expect(within(facts).getByText("misafir için")).toBeInTheDocument();
    expect(await within(fix).findByText("Kaydedildi.")).toBeInTheDocument();
    expect(sent).toEqual([{ note: "misafir için" }]);
  });

  it("puts a refused note back and says why", async () => {
    const user = userEvent.setup();
    serve(transactionDetail());
    server.use(
      http.put("/api/transactions/:fingerprint/annotation", () =>
        HttpResponse.json({ code: "correction_refused", title: "Not kaydedilemedi." }, { status: 400 }),
      ),
    );
    const facts = await region("Ayrıntılar");
    const fix = await region("Düzeltmeler");
    await user.type(within(fix).getByLabelText("Not"), " ve fazlası");
    await user.click(within(fix).getByRole("button", { name: "Notu kaydet" }));
    expect(await within(fix).findByText("Not kaydedilemedi.")).toBeInTheDocument();
    expect(within(facts).getByText("haftalık alışveriş")).toBeInTheDocument();
  });

  it("adds tags, several at once, and removes one", async () => {
    const user = userEvent.setup();
    const { sent } = serve(transactionDetail());
    const tags = within(await region("Düzeltmeler")).getByRole("group", { name: "Etiketler" });
    await user.type(within(tags).getByLabelText("Yeni etiket"), "market, ev, misafir");
    await user.click(within(tags).getByRole("button", { name: "Ekle" }));
    expect(within(tags).getByRole("button", { name: "misafir etiketini kaldır" })).toBeInTheDocument(); // at once
    expect(await within(tags).findByText("Kaydedildi.")).toBeInTheDocument();
    await user.click(within(tags).getByRole("button", { name: "ev etiketini kaldır" }));
    await waitFor(() => expect(within(tags).queryByRole("button", { name: "ev etiketini kaldır" })).toBeNull());
    expect(sent).toEqual([{ tags: ["ev", "market", "misafir"] }, { tags: ["market", "misafir"] }]);
  });
});

describe("RowPanel: splitting", () => {
  it("splits a row into parts that add up to it, the first taking what the others leave", async () => {
    const user = userEvent.setup();
    const { sent } = serve(transactionDetail());
    const fix = await region("Düzeltmeler");
    await user.click(within(fix).getByRole("button", { name: "Parçalara böl…" }));
    const split = within(fix).getByRole("region", { name: "Bölme" });
    expect(within(split).getByText(/^Satırın tutarı 840,50 TL\./)).toBeInTheDocument();
    const second = within(split).getByRole("group", { name: "Parça 2" });
    await user.type(within(second).getByLabelText("Tutar (TL)"), "250");
    await user.selectOptions(within(second).getByLabelText("Kategori"), "Temizlik");
    const first = within(split).getByRole("group", { name: "Parça 1" });
    expect(within(first).getByRole("status", { name: "Kalan tutar" })).toHaveTextContent("590,50 TL");
    await user.click(within(split).getByRole("button", { name: "Böl" }));
    expect(
      await within(split).findByText("Kaydedildi; işlem birkaç saniye içinde yeni hâliyle görünür."),
    ).toBeInTheDocument();
    expect(sent).toEqual([
      {
        parts: [
          { minor: 59050, category: "Market" },
          { minor: 25000, category: "Temizlik" },
        ],
      },
    ]);
  });

  it("says what is wrong with a part before sending anything", async () => {
    const user = userEvent.setup();
    const { sent } = serve(transactionDetail());
    const fix = await region("Düzeltmeler");
    await user.click(within(fix).getByRole("button", { name: "Parçalara böl…" }));
    const split = within(fix).getByRole("region", { name: "Bölme" });
    await user.click(within(split).getByRole("button", { name: "Parça ekle" }));
    const second = within(split).getByRole("group", { name: "Parça 2" });
    const third = within(split).getByRole("group", { name: "Parça 3" });
    await user.type(within(second).getByLabelText("Tutar (TL)"), "900");
    await user.type(within(third).getByLabelText("Tutar (TL)"), "12.50");
    await user.click(within(split).getByRole("button", { name: "Böl" }));
    expect(within(second).getByText("Bir kategori seçin.")).toBeInTheDocument();
    expect(within(third).getByLabelText("Tutar (TL)")).toHaveAccessibleDescription(
      "Tutar 250 ya da 250,50 gibi, sıfırdan büyük bir TL tutarı olmalı.",
    );
    await user.clear(within(third).getByLabelText("Tutar (TL)"));
    await user.type(within(third).getByLabelText("Tutar (TL)"), "10");
    await user.click(within(split).getByRole("button", { name: "Böl" }));
    expect(
      within(split).getByText("Diğer parçalar satırın tutarını tutuyor ya da aşıyor; ilk parçaya bir şey kalmıyor."),
    ).toBeInTheDocument();
    await user.click(within(third).getByRole("button", { name: "3. parçayı kaldır" }));
    expect(within(split).queryByRole("group", { name: "Parça 3" })).not.toBeInTheDocument();
    expect(sent).toEqual([]);
  });

  it("shows a split row's parts, edits them in place of the category, and joins the row again after asking", async () => {
    const user = userEvent.setup();
    const { sent } = serve(SPLIT_DETAIL, { at: PARTS[1]!.fingerprint });
    const detail = await panel(PARTS[0]!.title);
    expect(within(detail).getByText("2 parçaya bölünmüş; her parça kendi kategorisinde sayılıyor.")).toBeInTheDocument();
    const parts = within(within(detail).getByRole("region", { name: "Parçalar" })).getAllByRole("row");
    expect(parts.map((part) => part.textContent)).toEqual([
      "ParçaKategoriGereklilikTutar",
      "1/2MarketGıdaGerekli−1.000,00 TL",
      "2/2TemizlikEvGerekli−250,00 TL",
    ]);
    const fix = within(detail).getByRole("region", { name: "Düzeltmeler" });
    expect(within(fix).queryByRole("button", { name: "Yalnızca bu işleme ver" })).not.toBeInTheDocument();
    expect(within(fix).queryByRole("button", { name: "Gerekliliği kaydet" })).not.toBeInTheDocument();
    const split = within(fix).getByRole("region", { name: "Bölme" });
    const first = within(split).getByRole("group", { name: "Parça 1" });
    expect(within(first).getByRole("status", { name: "Kalan tutar" })).toHaveTextContent("1.000,00 TL");
    const second = within(split).getByRole("group", { name: "Parça 2" });
    expect(within(second).getByLabelText("Tutar (TL)")).toHaveValue("250");
    expect(within(second).getByLabelText("Kategori")).toHaveValue("Temizlik");
    await user.click(within(split).getByRole("button", { name: "Bölmeyi kaldır" }));
    const ask = await screen.findByRole("alertdialog", { name: "Bölme kaldırılsın mı?" });
    await user.click(within(ask).getByRole("button", { name: "Bölmeyi kaldır" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(sent).toEqual([{ parts: [] }]);
  });
});
