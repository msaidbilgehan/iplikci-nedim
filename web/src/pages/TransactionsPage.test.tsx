import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import type { SavedView } from "../api/types";
import { renderScreen } from "../test/render";
import { EXCLUDED, INCOME, OPEN_OCTOBER, PARTS, PURCHASE, server, TRANSACTIONS } from "../test/server";
import TransactionsPage from "./TransactionsPage";

afterEach(() => localStorage.clear());

const table = () => screen.findByRole("table", { name: /^İşlemler,/ });

/** The requests the list made, each with its query. */
function listen(): URLSearchParams[] {
  const asked: URLSearchParams[] = [];
  server.use(
    http.get("/api/transactions", ({ request }) => {
      asked.push(new URL(request.url).searchParams);
      return HttpResponse.json(TRANSACTIONS);
    }),
  );
  return asked;
}

describe("TransactionsPage: the list", () => {
  it("says what the rows add up to and lists them, a row the statements leave out faded and counted in nothing", async () => {
    renderScreen(<TransactionsPage />, { path: "/islemler" });
    expect(await screen.findByRole("heading", { level: 1, name: "İşlemler" })).toBeInTheDocument();
    expect(
      await screen.findByText("93 işlem; harcama 15.250,00 TL, giren 40.000,00 TL, çıkan 15.250,00 TL."),
    ).toBeInTheDocument();
    const totals = screen.getByRole("region", { name: "Toplamlar" });
    expect(totals).toHaveTextContent("Giren+40.000,00 TL");
    expect(totals).toHaveTextContent("Çıkan−15.250,00 TL");
    expect(totals).toHaveTextContent("Fark+24.750,00 TL"); // what is left between them, with its sign
    expect(totals).toHaveTextContent("Harcama15.250,00 TL");
    expect(totals).toHaveTextContent("93 işlem · 92 tanesi toplamlarda · 4 geçici (ekstre bekleniyor)");
    expect(totals).toHaveTextContent("1 ekstrede yok (listede soluk, toplamlara girmez)");
    const rows = within(await table()).getAllByRole("row");
    expect(rows).toHaveLength(1 + TRANSACTIONS.rows.length);
    const income = within(await table()).getByRole("link", { name: INCOME.title }).closest("tr")!;
    expect(within(income).getByText("+40.000,00 TL")).toBeInTheDocument();
    const excluded = within(await table()).getByRole("link", { name: EXCLUDED.title }).closest("tr")!;
    expect(within(excluded).getByRole("button", { name: "ekstrede yok" })).toBeInTheDocument();
    expect(within(excluded).getByRole("checkbox")).toBeDisabled(); // it carries no correction
  });

  it("marks each part of a split row with its place among the parts", async () => {
    renderScreen(<TransactionsPage />, { path: "/islemler" });
    const parts = within(await table()).getAllByRole("link", { name: PARTS[0]!.title });
    expect(parts).toHaveLength(2);
    expect(within(parts[0]!.closest("td")!).getByText("bölünmüş 1/2")).toBeInTheDocument();
    expect(within(parts[1]!.closest("td")!).getByText("bölünmüş 2/2")).toBeInTheDocument();
  });

  it("shows every column in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<TransactionsPage />, { path: "/islemler" });
    const purchase = within(await table()).getByRole("link", { name: PURCHASE.title }).closest("tr")!;
    expect(within(purchase).getByText(PURCHASE.description)).toBeInTheDocument();
    expect(within(purchase).getByText("Harcama")).toBeInTheDocument();
    expect(within(purchase).getByText("Gerekli")).toBeInTheDocument();
    expect(within(purchase).getByText("#ev · haftalık alışveriş")).toBeInTheDocument();
  });

  it("asks with the address's filters in the API's names and opens a row's detail without asking again", async () => {
    const asked = listen();
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, {
      path: "/islemler?merchant=%C3%96rnek+Market&kind=purchase&offset=50",
    });
    await table();
    expect(asked).toHaveLength(1);
    expect(asked[0]!.get("merchant")).toBe("Örnek Market");
    expect(asked[0]!.getAll("kind")).toEqual(["purchase"]);
    expect(asked[0]!.get("offset")).toBe("50");
    expect(asked[0]!.get("limit")).toBe("50");
    await user.click(within(await table()).getByRole("link", { name: PURCHASE.title }));
    expect(location()).toContain(`satir=${PURCHASE.fingerprint}`);
    expect(await screen.findByRole("dialog", { name: PURCHASE.title })).toBeInTheDocument();
    expect(asked).toHaveLength(1); // the open row is no filter
  });

  it("names a chart's month of spending by what its kinds add up to, its days as the period", async () => {
    const asked = listen();
    renderScreen(<TransactionsPage />, {
      path: "/islemler?from=2026-06-01&to=2026-06-30&kind=purchase&kind=refund&kind=interest_fee",
    });
    await table();
    expect(asked[0]!.getAll("kind")).toEqual(["purchase", "refund", "interest_fee"]);
    expect(screen.getByText("Giderler (harcama, iade, faiz ve ücret)")).toBeInTheDocument();
    expect(screen.getByText("Haziran 2026")).toBeInTheDocument(); // a whole month by its name
    expect(screen.getByRole("button", { name: "Tür süzgecini kaldır" })).toBeInTheDocument();
    // Its days show in the two day fields beside the period, which reads as days of one's own.
    expect(screen.getByLabelText("Dönem")).toHaveValue("custom");
    expect(screen.getByLabelText("Başlangıç")).toHaveValue("2026-06-01");
    expect(screen.getByLabelText("Bitiş")).toHaveValue("2026-06-30");
  });

  it("offers the periods by name beside the search and asks for the one chosen", async () => {
    const asked = listen();
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, { path: "/islemler?offset=50" });
    await table();
    const period = screen.getByLabelText("Dönem");
    expect(period).toHaveValue("");
    expect(within(period).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Tüm zamanlar",
      "Bu ay",
      "Geçen ay",
      "Son 30 gün",
      "Son 3 ay",
      "Bu yıl",
      "Geçen yıl",
      "Tarih aralığı seç…",
    ]);
    await user.selectOptions(period, "Bu ay");
    expect(location()).toBe("/islemler?period=this_month"); // the first page again
    await waitFor(() => expect(asked.at(-1)?.get("period")).toBe("this_month"));
    expect(screen.getByRole("button", { name: "Dönem süzgecini kaldır" }).closest("li")).toHaveTextContent(
      "Dönem:Bu ay",
    );
    expect(screen.queryByLabelText("Başlangıç")).not.toBeInTheDocument(); // a named period has no day fields
    await user.selectOptions(period, "Tüm zamanlar");
    expect(location()).toBe("/islemler");
  });

  it("opens two day fields for days of one's own, which take the place of a named period", async () => {
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, { path: "/islemler?period=last_month" });
    await table();
    await user.selectOptions(screen.getByLabelText("Dönem"), "Tarih aralığı seç…");
    expect(location()).toBe("/islemler");
    const start = screen.getByLabelText("Başlangıç");
    await user.type(start, "2026-10-05");
    await waitFor(() => expect(location()).toBe("/islemler?from=2026-10-05"));
    expect(screen.getByLabelText("Bitiş")).toHaveAttribute("min", "2026-10-05"); // the end never before the start
    expect(screen.getByLabelText("Dönem")).toHaveValue("custom");
    await user.click(screen.getByRole("button", { name: "Dönem süzgecini kaldır" }));
    expect(location()).toBe("/islemler");
    expect(screen.queryByLabelText("Başlangıç")).not.toBeInTheDocument();
  });

  it("keeps the money in or out alone and an amount's bounds, said in the chips", async () => {
    const asked = listen();
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, { path: "/islemler" });
    await table();
    await user.click(screen.getByRole("button", { name: /^Süzgeçler/ }));
    await user.selectOptions(screen.getByLabelText("Yön"), "Yalnızca çıkan para");
    expect(location()).toBe("/islemler?direction=out");
    const least = screen.getByLabelText("En az (TL)");
    await user.type(least, "1500,5");
    expect(location()).toBe("/islemler?direction=out"); // not at every key
    await user.keyboard("{Enter}");
    await waitFor(() => expect(location()).toBe("/islemler?direction=out&min=1500.5"));
    await waitFor(() => expect(asked.at(-1)?.get("min")).toBe("1500.5"));
    expect(asked.at(-1)?.get("direction")).toBe("out");
    expect(screen.getByRole("button", { name: "Yön süzgecini kaldır" }).closest("li")).toHaveTextContent("Yön:Çıkan");
    expect(screen.getByRole("button", { name: "Tutar süzgecini kaldır" }).closest("li")).toHaveTextContent(
      "Tutar:en az 1.500,50 TL",
    );
    await user.click(screen.getByRole("button", { name: "Tutar süzgecini kaldır" }));
    expect(location()).toBe("/islemler?direction=out");
    expect(least).toHaveValue(""); // the field follows the address
    // An amount that is no amount is said so, and asks nothing.
    await user.type(least, "bin lira{Enter}");
    expect(least).toHaveAttribute("aria-invalid", "true");
    expect(least).toHaveAccessibleDescription("Tutarı 1.500 ya da 1.500,50 gibi yazın.");
    expect(location()).toBe("/islemler?direction=out");
  });

  it("offers the tags the rows carry, the most used first, so one is chosen rather than guessed", async () => {
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, { path: "/islemler" });
    await table();
    await user.click(screen.getByRole("button", { name: /^Süzgeçler/ }));
    const offered = await screen.findAllByRole("button", { name: /etiketiyle süz/ });
    expect(offered.map((button) => button.getAttribute("aria-label"))).toEqual([
      "iş etiketiyle süz (3 işlem)",
      "tatil etiketiyle süz (1 işlem)",
    ]);
    await user.click(offered[0]!);
    expect(location()).toBe("/islemler?tag=i%C5%9F");
    expect(screen.getAllByRole("button", { name: /etiketiyle süz/ })).toHaveLength(1); // a chosen tag is not offered
  });

  it("starts again at the first page when a filter changes", async () => {
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, { path: "/islemler?merchant=Migros&offset=50" });
    await table();
    await user.click(screen.getByRole("button", { name: "İşyeri süzgecini kaldır" }));
    await waitFor(() => expect(location()).toBe("/islemler"));
  });

  it("sorts by a column, and by the same column again the other way", async () => {
    const asked = listen();
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, { path: "/islemler?offset=50" });
    const heading = within(await table()).getByRole("button", { name: "Tutar sırasına göre sırala" });
    await user.click(heading);
    expect(location()).toBe("/islemler?sort=amount&order=desc");
    await waitFor(() => expect(asked.at(-1)?.get("sort")).toBe("amount"));
    expect(heading.closest("th")).toHaveAttribute("aria-sort", "descending");
    await user.click(heading);
    expect(location()).toBe("/islemler?sort=amount&order=asc");
    await waitFor(() => expect(heading.closest("th")).toHaveAttribute("aria-sort", "ascending"));
  });

  it("pages through the rows", async () => {
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, { path: "/islemler" });
    const pages = await screen.findByRole("navigation", { name: "Sayfalar" });
    expect(within(pages).getByText("1–5 / 93")).toBeInTheDocument();
    expect(within(pages).getByRole("button", { name: "Önceki sayfa" })).toBeDisabled();
    await user.click(within(pages).getByRole("button", { name: "Sonraki sayfa" }));
    expect(location()).toBe("/islemler?offset=50");
    expect(await within(pages).findByText("51–51 / 93")).toBeInTheDocument();
    expect(within(await table()).getByRole("link", { name: "Örnek Kitapçı" })).toBeInTheDocument();
    expect(within(pages).getByRole("button", { name: "Sonraki sayfa" })).toBeDisabled();
  });

  it("downloads the rows as CSV with the same filters and order", async () => {
    renderScreen(<TransactionsPage />, { path: "/islemler?category=Market&sort=amount&order=asc&offset=50" });
    expect(await screen.findByRole("link", { name: "CSV indir" })).toHaveAttribute(
      "href",
      "/api/transactions.csv?category=Market&sort=amount&order=asc",
    );
  });

  it("says when no row matches the filters and resets them", async () => {
    server.use(
      http.get("/api/transactions", () =>
        HttpResponse.json({ ...TRANSACTIONS, rows: [], totals: { ...TRANSACTIONS.totals, count: 0 }, next: null }),
      ),
    );
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, { path: "/islemler?q=yok&sort=day&order=asc" });
    expect(await screen.findByText("Bu süzgeçlerle işlem yok")).toBeInTheDocument();
    expect(screen.getByText("Bu süzgeçlerle işlem yok.")).toBeInTheDocument(); // the totals' sentence
    await user.click(screen.getByRole("button", { name: "Süzgeçleri sıfırla" }));
    expect(location()).toBe("/islemler?sort=day&order=asc"); // the order stays
  });

  it("says where the rows come from before there are any", async () => {
    server.use(
      http.get("/api/transactions", () =>
        HttpResponse.json({ ...TRANSACTIONS, rows: [], totals: { ...TRANSACTIONS.totals, count: 0 }, next: null }),
      ),
    );
    renderScreen(<TransactionsPage />, { path: "/islemler" });
    expect(await screen.findByText("Henüz işlem yok")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Belgeleri göster" })).toHaveAttribute("href", "/belgeler");
  });

  it("asks nothing while a filter has nothing chosen, says which, and chooses all of it again", async () => {
    const asked = listen();
    const user = userEvent.setup();
    renderScreen(<TransactionsPage />, { path: "/islemler?kind=&from=2026-10-01&to=2026-10-31" });
    expect(await screen.findByText("Tür süzgecinde hiçbir seçenek seçili değil")).toBeInTheDocument();
    expect(asked).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Tür: hepsini seç" }));
    expect(await table()).toBeInTheDocument();
    // The period stays; the kinds are all of them again.
    expect(asked.at(-1)?.get("from")).toBe("2026-10-01");
    expect(asked.at(-1)?.has("kind")).toBe(false);
  });

  it("says what a month of the listed days still waits for, each account's document with its cut", async () => {
    server.use(http.get("/api/transactions", () => HttpResponse.json({ ...TRANSACTIONS, open: [OPEN_OCTOBER] })));
    renderScreen(<TransactionsPage />, { path: "/islemler?from=2026-10-01&to=2026-10-31" });
    const note = await screen.findByRole("region", { name: "Henüz kapanmamış aylar" });
    expect(
      within(note).getByText(
        "Ekim 2026 henüz kapanmadı, ama eksik değil: ayın son günlerini kapsayan belgeler bekleniyor, sonuncusu " +
          "24.11.2026 civarında gelir. Gelince o günlerin işlemleri bu listeye girer.",
      ),
    ).toBeInTheDocument();
    const awaited = within(note).getAllByRole("listitem").map((item) => item.textContent);
    expect(awaited).toEqual([
      "TEB Bonus •1111: 14–31 Ekim ekstresi, kesim ~13.11",
      "Garanti Bonus •2222: 25–31 Ekim ekstresi, kesim ~24.11",
    ]);
    expect(within(note).getByRole("link", { name: "Ekim 2026 için ne bekleniyor?" })).toHaveAttribute(
      "href",
      "/ay-sonu/2026-10",
    );
  });

  it("says nothing of months when the listed days' months have all closed", async () => {
    renderScreen(<TransactionsPage />, { path: "/islemler?from=2026-10-01&to=2026-10-31" });
    expect(await table()).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Henüz kapanmamış aylar" })).not.toBeInTheDocument();
  });

  it("goes from a month's money in to every row of the month in one click", async () => {
    const asked = listen();
    const user = userEvent.setup();
    renderScreen(<TransactionsPage />, { path: "/islemler?from=2026-10-01&to=2026-10-31&kind=income" });
    expect(await table()).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dönemin bütün işlemleri" }));
    await waitFor(() => expect(asked.at(-1)?.has("kind")).toBe(false));
    expect([asked.at(-1)?.get("from"), asked.at(-1)?.get("to")]).toEqual(["2026-10-01", "2026-10-31"]);
    // The period alone: nothing more to take off but the period itself.
    expect(screen.queryByRole("button", { name: "Dönemin bütün işlemleri" })).not.toBeInTheDocument();
  });

  it("says why the rows could not be read and tries again", async () => {
    let fail = true;
    server.use(
      http.get("/api/transactions", () =>
        fail
          ? HttpResponse.json({ code: "busy", title: "Belgeler şu an okunuyor." }, { status: 503 })
          : HttpResponse.json(TRANSACTIONS),
      ),
    );
    const user = userEvent.setup();
    renderScreen(<TransactionsPage />, { path: "/islemler" });
    expect(await screen.findByText("Belgeler şu an okunuyor.")).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await table()).toBeInTheDocument();
  });
});

describe("TransactionsPage: many rows at once", () => {
  it("gives the chosen rows one category and says how many changed and which were skipped", async () => {
    let sent: unknown = null;
    server.use(
      http.post("/api/transactions/bulk", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ changed: 1, skipped: [PARTS[0]!.fingerprint] });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<TransactionsPage />, { path: "/islemler" });
    const rows = await table();
    await user.click(within(rows).getByRole("checkbox", { name: `Seç: ${PURCHASE.title}, 12.11.2026` }));
    await user.click(within(rows).getAllByRole("checkbox", { name: `Seç: ${PARTS[0]!.title}, 01.11.2026` })[0]!);
    const bar = screen.getByRole("region", { name: "Seçili işlemler" });
    expect(within(bar).getByText("2 işlem seçildi")).toBeInTheDocument();
    await user.selectOptions(within(bar).getByLabelText("Seçililere kategori"), "Kafe");
    await user.click(within(bar).getByRole("button", { name: "Kategoriyi ver" }));
    expect(
      await within(bar).findByText(
        "1 işlem değişti; liste birkaç saniye içinde güncellenir. 1 işlem atlandı: toplamlara girmeyen satırlar " +
          "düzeltme taşımaz, bölünmüş satırların kategorisi parçalarındadır.",
      ),
    ).toBeInTheDocument();
    expect(sent).toEqual({ fingerprints: [PURCHASE.fingerprint, PARTS[0]!.fingerprint], category: "Kafe" });
    expect(within(rows).getByRole("checkbox", { name: `Seç: ${PURCHASE.title}, 12.11.2026` })).not.toBeChecked();
  });

  it("chooses every row of the page that can carry a correction, and adds a tag to them", async () => {
    let sent: unknown = null;
    server.use(
      http.post("/api/transactions/bulk", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ changed: 3, skipped: [] });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<TransactionsPage />, { path: "/islemler" });
    await user.click(within(await table()).getByRole("checkbox", { name: "Bu sayfadaki işlemlerin hepsini seç" }));
    const bar = screen.getByRole("region", { name: "Seçili işlemler" });
    expect(within(bar).getByText("4 işlem seçildi")).toBeInTheDocument(); // not the one the statements leave out
    await user.type(within(bar).getByLabelText("Seçililere etiket"), "tatil");
    await user.click(within(bar).getByRole("button", { name: "Etiketi ekle" }));
    expect(await within(bar).findByText("3 işlem değişti; liste birkaç saniye içinde güncellenir.")).toBeInTheDocument();
    expect(sent).toEqual({
      fingerprints: [PURCHASE.fingerprint, INCOME.fingerprint, ...PARTS.map((part) => part.fingerprint)],
      tags: ["tatil"],
    });
  });
});

describe("TransactionsPage: kept views", () => {
  it("keeps the filters and the order under a name", async () => {
    let sent: unknown = null;
    server.use(
      http.put("/api/transactions/views", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json([sent]);
      }),
    );
    const user = userEvent.setup();
    renderScreen(<TransactionsPage />, { path: "/islemler?category=Market&category=Kafe&sort=amount&order=desc" });
    await user.click(await screen.findByRole("button", { name: "Görünümler" }));
    const views = await screen.findByRole("dialog", { name: "Kayıtlı görünümler" });
    expect(within(views).getByText("Henüz kayıtlı görünüm yok.")).toBeInTheDocument();
    await user.type(within(views).getByLabelText("Bu süzgeçleri kaydet"), "Yeme içme");
    await user.click(within(views).getByRole("button", { name: "Kaydet" }));
    expect(await within(views).findByText("“Yeme içme” kaydedildi.")).toBeInTheDocument();
    expect(sent).toEqual({
      name: "Yeme içme",
      query: { category: ["Market", "Kafe"], sort: ["amount"], order: ["desc"] },
    });
    expect(within(views).getByRole("button", { name: "Yeme içme görünümünü aç" })).toBeInTheDocument();
  });

  it("opens a kept view's filters, and removes one after asking", async () => {
    const kept: SavedView[] = [{ name: "Market", query: { category: ["Market"], tag: ["ev"] } }];
    let removed = "";
    server.use(
      http.get("/api/transactions/views", () => HttpResponse.json(kept)),
      http.delete("/api/transactions/views/:name", ({ params }) => {
        removed = String(params["name"]);
        return HttpResponse.json([]);
      }),
    );
    const user = userEvent.setup();
    const { location } = renderScreen(<TransactionsPage />, { path: "/islemler?q=kira" });
    await user.click(await screen.findByRole("button", { name: "Görünümler" }));
    const views = await screen.findByRole("dialog", { name: "Kayıtlı görünümler" });
    await user.click(await within(views).findByRole("button", { name: "Market görünümünü aç" }));
    expect(location()).toBe("/islemler?category=Market&tag=ev");
    await user.click(screen.getByRole("button", { name: "Görünümler" }));
    await user.click(await screen.findByRole("button", { name: "Market görünümünü sil" }));
    const ask = await screen.findByRole("alertdialog", { name: "Görünüm silinsin mi?" });
    await user.click(within(ask).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(removed).toBe("Market"));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Görünümler" }));
    expect(await screen.findByText("Henüz kayıtlı görünüm yok.")).toBeInTheDocument();
  });
});
