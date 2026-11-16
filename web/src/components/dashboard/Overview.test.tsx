import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { Dashboard, MonthClosing } from "../../api/types";
import { renderScreen } from "../../test/render";
import { DASHBOARD, FORECAST, INSIGHTS, server, SPENDING } from "../../test/server";
import { Overview } from "./Overview";

const region = (name: string) => screen.findByRole("region", { name });

const tl = (minor: number) => ({ minor, currency: "TRY" });
const CASH_REF = { id: "teb-123456789", label: "Örnek Vadesiz TL" };

interface October {
  income: number;
  expense: number;
  people?: number;
  debt?: number;
  saving?: number;
}

/** The dashboard with October's money changed, as the service sums it: what went out is the spending, the money
 * sent to people and the loan principal; what is left is the income less what went out and what was saved. */
function withOctober({ income, expense, people = 0, debt = 0, saving = 0 }: October): Dashboard {
  const out = expense + people + debt;
  const months = DASHBOARD.closing.months.map(
    (month): MonthClosing =>
      month.month === "2026-10"
        ? {
            ...month,
            income: tl(income),
            expense: tl(expense),
            people: tl(people),
            debt: tl(debt),
            out: tl(out),
            saving: tl(saving),
            left: tl(income - out - saving),
          }
        : month,
  );
  return { ...DASHBOARD, closing: { ...DASHBOARD.closing, months } };
}

describe("Overview", () => {
  it("tells the last closed month's money in, out and left, and says how it went in words", async () => {
    renderScreen(<Overview found={DASHBOARD} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(within(story).getByText("40.000,00 TL")).toBeInTheDocument();
    expect(within(story).getByText("19.977,99 TL")).toBeInTheDocument();
    expect(within(story).getByText("20.022,01 TL")).toBeInTheDocument();
    expect(within(story).getByText("Gelen paranın %50'si elinizde kaldı. İyi gidiyor.")).toBeInTheDocument();
    expect(within(story).getByText("Kasım 2026 sürüyor: şimdiye kadar 4.200,00 TL harcandı.")).toBeInTheDocument();
  });

  it("says what the total rests on: the last documents, the card debts taken off and an account left out", async () => {
    renderScreen(<Overview found={DASHBOARD} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(
      within(story).getByText(
        "Son belgelere göre hesaplarınızdaki para, kart borçları düşülünce: 12.500,00 TL. " +
          "Bakiyesi bilinmeyen 1 hesap bu toplamda yok.",
      ),
    ).toBeInTheDocument();
    expect(within(story).getByRole("link", { name: "Hesaplara bak" })).toHaveAttribute("href", "/hesaplar");
  });

  it("says plainly when more went out than came in", async () => {
    renderScreen(<Overview found={withOctober({ income: 1000000, expense: 1200000 })} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(within(story).getByText("Fazla çıkan")).toBeInTheDocument();
    expect(
      within(story).getByText(
        "Giden para gelenden 2.000,00 TL fazla: bu ay gelirinizden çok para çıktı. " +
          "Aşağıda paranın nereye gittiğine bakın.",
      ),
    ).toBeInTheDocument();
  });

  it("takes off the money sent to people, the loan principal and the saving, as the month-end page does", async () => {
    const october = withOctober({ income: 4000000, expense: 2000000, people: 750000, debt: 120000, saving: 480000 });
    renderScreen(<Overview found={october} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(within(story).getByText("28.700,00 TL")).toBeInTheDocument(); // what went out: 20.000 + 7.500 + 1.200
    expect(
      within(story).getByText("harcamalar, faturalar, kişilere gönderilen para ve kredi ödemeleri"),
    ).toBeInTheDocument();
    expect(within(story).getByText("Birikim")).toBeInTheDocument();
    expect(within(story).getByText("4.800,00 TL")).toBeInTheDocument();
    expect(within(story).getByText("6.500,00 TL")).toBeInTheDocument(); // left: 40.000 − 28.700 − 4.800
    expect(
      within(story).getByText("gelen paradan giden ve birikim çıkınca; ayın sonucu, bugünkü bakiye değil"),
    ).toBeInTheDocument();
    expect(
      within(story).getByText(
        "Gelen paranın %12'si birikime gitti, %16'sı elinizde kaldı. İyi gidiyor.",
      ),
    ).toBeInTheDocument();
  });

  it("says what went out beyond the money that came in when the saving takes it below zero", async () => {
    renderScreen(<Overview found={withOctober({ income: 1000000, expense: 900000, saving: 200000 })} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(
      within(story).getByText(
        "Giden para ve birikim gelenden 1.000,00 TL fazla: aradaki fark hesaplarınızdaki paradan ya da borçla " +
          "karşılandı. Aşağıda paranın nereye gittiğine bakın.",
      ),
    ).toBeInTheDocument();
  });

  it("says when only a little of the money that came in is left", async () => {
    renderScreen(<Overview found={withOctober({ income: 4000000, expense: 3800000 })} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(
      within(story).getByText(
        "Gelen paranın yalnızca %5'i elinizde kaldı. Biraz daha az harcarsanız birikiminiz büyür.",
      ),
    ).toBeInTheDocument();
  });

  it("tells the newest ended month before it closes, for now, with what it waits for and by when", async () => {
    // On 11 November October still waits for the card statements that cover its last days: it is told at once, not
    // September for weeks more.
    const card = (label: string, waiting_for: string) => ({ account: { id: label, label }, waiting_for });
    const months = DASHBOARD.closing.months.map(
      (month): MonthClosing =>
        month.month === "2026-10"
          ? {
              ...month,
              status: "waiting",
              closes_by: "2026-11-24",
              waiting: [
                card("Örnek Kart •1234", "14–31 Ekim, 14 Ekim–12 Kasım ekstresinde"),
                card("Örnek Kart •5678", "25–31 Ekim, 25 Ekim–~24 Kasım ekstresinde"),
              ],
            }
          : month,
    );
    renderScreen(<Overview found={{ ...DASHBOARD, closing: { ...DASHBOARD.closing, months } }} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(within(story).getByText("Şimdilik kalan")).toBeInTheDocument();
    expect(within(story).getByText("Gelen paranın şimdilik %50'si elinizde kaldı. İyi gidiyor.")).toBeInTheDocument();
    expect(
      within(story).getByText(
        "Ekim 2026 henüz kapanmadı: ayın son günlerini kapsayan 2 belge bekleniyor, sonuncusu 24.11.2026 civarında " +
          "gelir. Rakamlar şimdiye kadar gelen belgelere göre; belgeler gelince giden artabilir, kalan azalabilir.",
      ),
    ).toBeInTheDocument();
    expect(within(story).getByRole("link", { name: "Ekim 2026 için ne bekleniyor?" })).toHaveAttribute(
      "href",
      "/ay-sonu/2026-10",
    );
    // The month that runs is told after it, as before.
    expect(within(story).getByText("Kasım 2026 sürüyor: şimdiye kadar 4.200,00 TL harcandı.")).toBeInTheDocument();
    const where = await region("Paranız nereye gitti?");
    expect(
      await within(where).findByText("Ekim 2026'da şimdiye kadar 110.700,00 TL harcandı; en çok Kira: 75.000,00 TL."),
    ).toBeInTheDocument();
  });

  it("says what went out beyond the money in already, while the month waits for its documents", async () => {
    const months = DASHBOARD.closing.months.map(
      (month): MonthClosing =>
        month.month === "2026-10"
          ? { ...month, status: "waiting", expense: tl(4200000), out: tl(4200000), left: tl(-200000) }
          : month,
    );
    renderScreen(<Overview found={{ ...DASHBOARD, closing: { ...DASHBOARD.closing, months } }} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(
      within(story).getByText(
        "Giden para şimdiden gelenden 2.000,00 TL fazla: bu ay gelirinizden çok para çıktı. " +
          "Aşağıda paranın nereye gittiğine bakın.",
      ),
    ).toBeInTheDocument();
  });

  it("says a month held open without a day to promise, or by a missing document, in its own words", async () => {
    const months = DASHBOARD.closing.months.map(
      (month): MonthClosing =>
        month.month === "2026-09"
          ? { ...month, status: "missing", waiting: [{ account: CASH_REF, waiting_for: "1–9 Eylül hesap dökümü eksik" }] }
          : month.month === "2026-10"
            ? { ...month, status: "waiting", waiting: [{ account: CASH_REF, waiting_for: "25–31 Ekim hesap dökümü" }] }
            : month,
    );
    const { location } = renderScreen(<Overview found={{ ...DASHBOARD, closing: { ...DASHBOARD.closing, months } }} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(
      within(story).getByText(
        "Ekim 2026 henüz kapanmadı: ayın son günlerini kapsayan bir belge bekleniyor. Rakamlar şimdiye kadar gelen " +
          "belgelere göre; belge gelince giden artabilir, kalan azalabilir.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(within(story).getByRole("link", { name: "Önceki ay: Eylül 2026" }));
    expect(location()).toBe("/?ay=2026-09");
    const september = await region("Eylül 2026: paranız ne durumda?");
    expect(
      within(september).getByText(
        "Eylül 2026 kapanmadı: ayın bazı günlerinin belgesi eksik. Rakamlar şimdiye kadar gelen belgelere göre; " +
          "eksik belgeler eklenince değişebilir.",
      ),
    ).toBeInTheDocument();
  });

  it("goes to the months before and back to the newest, keeping the month in the address", async () => {
    let asked = "";
    server.use(
      http.get("/api/spending", ({ request }) => {
        asked = new URL(request.url).search;
        return HttpResponse.json(SPENDING);
      }),
    );
    const { location } = renderScreen(<Overview found={DASHBOARD} />, { path: "/?ay=2026-08" });
    const story = await region("Ağustos 2026: paranız ne durumda?");
    await waitFor(() => expect(asked).toBe("?from=2026-08-01&to=2026-08-31")); // where that month's money went
    const months = within(story).getByRole("navigation", { name: "Aylar" });
    expect(within(months).getByRole("link", { name: "Önceki ay: Temmuz 2026" })).toHaveAttribute("href", "/?ay=2026-07");
    // The newest is the Pano's own: its address needs no month.
    await userEvent.click(within(months).getByRole("link", { name: "Sonraki ay: Eylül 2026" }));
    expect(location()).toBe("/?ay=2026-09");
    const next = within(await region("Eylül 2026: paranız ne durumda?")).getByRole("link", {
      name: "Sonraki ay: Ekim 2026",
    });
    expect(next).toHaveAttribute("href", "/");
    await userEvent.click(next);
    expect(location()).toBe("/");
    const newest = await region("Ekim 2026: paranız ne durumda?");
    expect(within(newest).queryByRole("link", { name: /^Sonraki ay/ })).not.toBeInTheDocument();
  });

  it("opens on the newest ended month when the address names one the story cannot tell", async () => {
    renderScreen(<Overview found={DASHBOARD} />, { path: "/?ay=2026-11" }); // the month that runs is none of them
    expect(await region("Ekim 2026: paranız ne durumda?")).toBeInTheDocument();
  });

  it("says why an ended month whose money in is not known yet is not told, and what it shows so far", async () => {
    const months = DASHBOARD.closing.months.map(
      (month): MonthClosing =>
        month.month === "2026-10" ? { ...month, status: "waiting", income: null, left: null } : month,
    );
    renderScreen(<Overview found={{ ...DASHBOARD, closing: { ...DASHBOARD.closing, months } }} />);
    const story = await region("Eylül 2026: paranız ne durumda?");
    expect(
      within(story).getByText(
        "Ekim 2026: gelen para henüz bilinmiyor, çünkü hesap dökümleri ayın yarısını kapsamıyor; dökümler gelince bu " +
          "özet o ayı gösterir. Şimdiye kadar gelen belgelere göre Ekim 2026'da 19.977,99 TL harcandı.",
      ),
    ).toBeInTheDocument();
    expect(within(story).getByRole("link", { name: "Ekim 2026 için ne bekleniyor?" })).toHaveAttribute(
      "href",
      "/ay-sonu/2026-10",
    );
  });

  it("says plainly that no document shows the running month's spending yet", async () => {
    const months = DASHBOARD.closing.months.map(
      (month): MonthClosing => (month.month === "2026-11" ? { ...month, expense: tl(0), out: tl(0) } : month),
    );
    renderScreen(<Overview found={{ ...DASHBOARD, closing: { ...DASHBOARD.closing, months } }} />);
    const story = await region("Ekim 2026: paranız ne durumda?");
    expect(
      within(story).getByText(
        "Kasım 2026 sürüyor: bu aya ait harcama henüz hiçbir belgede yok; ekstreler geldikçe görünür.",
      ),
    ).toBeInTheDocument();
  });

  it("waits for a month whose money in is known before telling one", async () => {
    const months = DASHBOARD.closing.months.map((month): MonthClosing => ({ ...month, income: null }));
    renderScreen(<Overview found={{ ...DASHBOARD, closing: { ...DASHBOARD.closing, months } }} />);
    const story = await region("Paranız ne durumda?");
    expect(within(story).getByText(/^Henüz gelen parası bilinen bir ay yok\./)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Aylara göre gelen ve giden" })).not.toBeInTheDocument();
  });

  it("sums up the months' bars in words: how many closed months brought in more than went out", async () => {
    renderScreen(<Overview found={DASHBOARD} />);
    const months = await region("Aylara göre gelen ve giden");
    expect(within(months).getByText("Kapanan 5 ayın hepsinde gelen para gideni geçti.")).toBeInTheDocument();
  });

  it("counts the closed months that brought in more, when one did not", async () => {
    const months = DASHBOARD.closing.months.map(
      (month): MonthClosing =>
        month.month === "2026-05"
          ? { ...month, expense: tl(4500000), out: tl(4500000), left: tl(-500000) }
          : month,
    );
    renderScreen(<Overview found={{ ...DASHBOARD, closing: { ...DASHBOARD.closing, months } }} />);
    const chart = await region("Aylara göre gelen ve giden");
    expect(within(chart).getByText("Kapanan 5 ayın 4'ünde gelen para gideni geçti.")).toBeInTheDocument();
  });

  it("leads from a month's money in to its income, from its money out to its spending and from it to its rows", async () => {
    renderScreen(<Overview found={DASHBOARD} />);
    const months = await region("Aylara göre gelen ve giden");
    expect(
      within(months).getByText(
        "Bir ayın gelen ya da giden parasına tıklayın: o işlemler listelenir. Ayın adına tıklarsanız ayın bütün işlemleri.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(within(months).getByRole("tab", { name: "Tablo" }));
    const october = within(within(months).getByRole("table")).getByRole("row", { name: /^Ekim 2026/ });
    const days = "from=2026-10-01&to=2026-10-31";
    expect(within(october).getByRole("link", { name: "40.000,00 TL" })).toHaveAttribute(
      "href",
      `/islemler?${days}&kind=income`,
    );
    expect(within(october).getByRole("link", { name: "−19.977,99 TL" })).toHaveAttribute(
      "href",
      `/islemler?${days}&kind=purchase&kind=refund&kind=interest_fee&kind=p2p_transfer&kind=loan_principal`,
    );
    // The month itself: every row of it, in and out.
    expect(within(october).getByRole("link", { name: "Ekim 2026" })).toHaveAttribute("href", `/islemler?${days}`);
  });

  it("marks a month that waits for its statements by the day it should close, not as missing anything", async () => {
    const waiting = {
      ...DASHBOARD,
      closing: {
        ...DASHBOARD.closing,
        months: DASHBOARD.closing.months.map((m) =>
          m.month === "2026-10"
            ? {
                ...m,
                status: "waiting" as const,
                closes_by: "2026-11-24",
                waiting: [
                  { account: { id: "teb-1111", label: "TEB Bonus •1111" }, waiting_for: "14–31 Ekim, 14 Ekim–12 Kasım ekstresinde" },
                  { account: { id: "garanti-2222", label: "Garanti Bonus •2222" }, waiting_for: "25–31 Ekim, 25 Ekim–~24 Kasım ekstresinde" },
                ],
              }
            : m.month === "2026-11"
              ? { ...m, income: { minor: 1500000, currency: "TRY" } } // a running month's income known so far
              : m,
        ),
      },
    };
    renderScreen(<Overview found={waiting} />);
    const months = await region("Aylara göre gelen ve giden");
    expect(within(months).getByText("Soluk sütunlar: henüz kapanmamış aylar, ortalamaya girmez")).toBeInTheDocument();
    const said = within(months).getByText(/^Ekim 2026 eksik değil/);
    expect(said).toHaveTextContent(
      "Ekim 2026 eksik değil: ayın son günlerini kapsayan 2 belge bekleniyor, sonuncusu 24.11.2026 civarında gelir.",
    );
    expect(within(months).getByRole("link", { name: "Ekim 2026 işlemleri" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10-01&to=2026-10-31",
    );
    expect(within(months).getByText(/^Kasım 2026 sürüyor/)).toBeInTheDocument();
    expect(within(months).getByText(/^Temmuz 2026: bazı günlerin belgesi eksik/)).toBeInTheDocument();
    await userEvent.click(within(months).getByRole("tab", { name: "Tablo" }));
    const table = within(within(months).getByRole("table"));
    expect(table.getByRole("link", { name: "Ekim 2026 (bekliyor, ~24.11)" })).toBeInTheDocument();
    expect(table.getByRole("link", { name: "Temmuz 2026 (belge eksik)" })).toBeInTheDocument();
  });

  it("names the documents the story's month waits for, each with its days and its cut", async () => {
    const story = {
      ...DASHBOARD,
      closing: {
        ...DASHBOARD.closing,
        months: DASHBOARD.closing.months.map((m) =>
          m.month === "2026-10"
            ? {
                ...m,
                status: "waiting" as const,
                closes_by: "2026-11-13",
                waiting: [
                  { account: { id: "teb-1111", label: "TEB Bonus •1111" }, waiting_for: "14–31 Ekim, 14 Ekim–12 Kasım ekstresinde" },
                ],
              }
            : m,
        ),
      },
    };
    renderScreen(<Overview found={story} />);
    const card = await region("Ekim 2026: paranız ne durumda?");
    const list = within(card).getByText("Beklenen belgeler:").nextElementSibling;
    expect(list).toHaveTextContent("TEB Bonus •1111: 14–31 Ekim, 14 Ekim–12 Kasım ekstresinde");
  });

  it("draws a month's saving below the line, leading to its savings", async () => {
    renderScreen(<Overview found={withOctober({ income: 4000000, expense: 2000000, saving: 500000 })} />);
    const months = await region("Aylara göre gelen ve giden");
    expect(within(months).getByText(/mavi çubuk birikime ayrılan parayı gösterir/)).toBeInTheDocument();
    await userEvent.click(within(months).getByRole("tab", { name: "Tablo" }));
    const october = within(within(months).getByRole("table")).getByRole("row", { name: /^Ekim 2026/ });
    expect(within(october).getByRole("link", { name: "−5.000,00 TL" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10-01&to=2026-10-31&kind=investment",
    );
  });

  it("shows where the last closed month's money went, asking for that month only", async () => {
    let asked = "";
    server.use(
      http.get("/api/spending", ({ request }) => {
        asked = new URL(request.url).search;
        return HttpResponse.json(SPENDING);
      }),
    );
    renderScreen(<Overview found={DASHBOARD} />);
    const where = await region("Paranız nereye gitti?");
    expect(
      await within(where).findByText("Ekim 2026'da 110.700,00 TL harcandı; en çok Kira: 75.000,00 TL."),
    ).toBeInTheDocument();
    expect(asked).toBe("?from=2026-10-01&to=2026-10-31");
    expect(within(where).getByRole("link", { name: "Bu ayın harcamalarını göster" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10-01&to=2026-10-31",
    );
    // Each bar leads where the service says its rows are: that month's spending of the category.
    const bars = within(where).getByRole("list", { name: "Ekim 2026 harcamaları, türlerine göre" });
    expect(within(bars).getByRole("link", { name: "Kira" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-05-01&to=2026-10-31&kind=interest_fee&kind=purchase&kind=refund&category=Kira",
    );
  });

  it("leads from a day of the next 30 to what the calendar expects on it", async () => {
    renderScreen(<Overview found={DASHBOARD} />);
    const ahead = await region("Önümüzdeki 30 gün");
    await within(ahead).findByRole("img", { name: /çizgi grafiği/ });
    expect(
      within(ahead).getByText("Bir güne tıklayın: o gün beklenen ödemeler ve gelirler Takvim'de açılır."),
    ).toBeInTheDocument();
    await userEvent.click(within(ahead).getByRole("tab", { name: "Tablo" }));
    expect(within(ahead).getByRole("link", { name: "03.12.2026" })).toHaveAttribute("href", "/takvim?gun=2026-12-03");
  });

  it("warns when the next 30 days take the account below zero, and says where the line starts", async () => {
    renderScreen(<Overview found={DASHBOARD} />);
    const ahead = await region("Önümüzdeki 30 gün");
    expect(
      await within(ahead).findByText(
        "Dikkat: 03.12.2026'da TL hesaplarınız eksiye düşüyor (−14.019,00 TL). " +
          "Bir ödemeyi erteleyin ya da TL hesabınıza para aktarın. " +
          "Döviz ve yatırımlarınızda 25.000,00 TL var: bir kısmını bozdurup TL hesabınıza aktarabilirsiniz.",
      ),
    ).toBeInTheDocument();
    // What the line counts and what it leaves out, and why it goes down every day.
    expect(
      within(ahead).getByText(
        "Çizgi, ödemelerinizin çıktığı Örnek Vadesiz TL hesabını gösterir. Son belgelerde 1.000,00 TL vardı; o " +
          "günden bugüne beklenen gelir ve ödemeler eklenince bugün yaklaşık 999,00 TL. Döviz ve yatırımlarınız " +
          "(bugünkü kurla 25.000,00 TL) bu çizgide yok: değerleri kurla ve piyasayla değişir. Fiyatı belgelerde " +
          "olmayan 1 hesap (altın gibi) sayılmadı. Belgesi hiç gelmemiş hesaplarınız da bu çizgide yok.",
      ),
    ).toBeInTheDocument();
    expect(
      within(ahead).getByText(
        "Çizgi her gün biraz iner: Nisan 2026 – Eylül 2026 arasındaki tipik bir ayda bu hesaplardan 30,00 TL " +
          "harcama çıktı; öngörü bunu günlere yayar.",
      ),
    ).toBeInTheDocument();
    const coming = within(ahead).getByRole("list", { name: "Yaklaşan ödemeler ve gelirler" });
    expect(within(coming).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "03.12.2026Ev kirası−15.000,00 TL",
      "09.12.2026Örnek Müzik−99,99 TL",
    ]);
    expect(within(ahead).getByRole("link", { name: "Takvimde hepsini göster" })).toHaveAttribute("href", "/takvim");
  });

  it("says the money lasts the 30 days when no day goes below zero, with the lowest day", async () => {
    const days = Array.from({ length: 60 }, (_, i) => ({
      day: new Date(Date.UTC(2026, 10, 15 + i)).toISOString().slice(0, 10),
      balance: tl(100000 - i * 100),
    }));
    server.use(
      http.get("/api/forecast", () =>
        HttpResponse.json({ ...FORECAST, accounts: [{ ...FORECAST.accounts[0]!, days, negative: null }] }),
      ),
    );
    renderScreen(<Overview found={DASHBOARD} />);
    const ahead = await region("Önümüzdeki 30 gün");
    expect(
      await within(ahead).findByText("TL hesaplarınız 30 gün boyunca yetiyor: en az 14.12.2026'da 971,00 TL kalıyor."),
    ).toBeInTheDocument();
  });

  it("counts foreign currency and investments too when asked, at today's value, and remembers it", async () => {
    try {
      renderScreen(<Overview found={DASHBOARD} />);
      const ahead = await region("Önümüzdeki 30 gün");
      const choice = await within(ahead).findByRole("group", { name: "Çizgide sayılanlar" });
      expect(within(choice).getByRole("radio", { name: "Yalnız TL hesaplar" })).toBeChecked();
      await userEvent.click(within(choice).getByRole("radio", { name: "Döviz ve yatırımlarla" }));
      expect(
        within(ahead).getByText(
          "Döviz ve yatırımlarınızla birlikte paranız 30 gün boyunca yetiyor: en az 14.12.2026'da 10.970,00 TL kalıyor.",
        ),
      ).toBeInTheDocument();
      expect(
        within(ahead).getByText(/Döviz ve yatırımlarınız da bugünkü kurla \(25\.000,00 TL\) eklendi/),
      ).toBeInTheDocument();
      expect(window.localStorage.getItem("iplikci.forecast")).toBe("all");
    } finally {
      window.localStorage.removeItem("iplikci.forecast");
    }
  });

  it("puts the open alerts first, each level in words, then the assessment's advice with its way on", async () => {
    renderScreen(<Overview found={DASHBOARD} />);
    const todo = await region("Ne yapmalısınız?");
    await within(todo).findByText("Abonelikleri gözden geçirin");
    const items = within(todo).getAllByRole("listitem");
    expect(items.map((item) => within(item).getAllByText(/./)[0]?.textContent)).toEqual([
      "Kritik: Hesap eksiye düşecek",
      "Uyarı: Okunamayan belgeler",
      "Abonelikleri gözden geçirin",
      "Acil durum fonu",
    ]);
    expect(within(todo).getByRole("link", { name: "Göster: Hesap eksiye düşecek" })).toHaveAttribute(
      "href",
      "/takvim?hesap=teb-123456789",
    );
    expect(within(todo).getByRole("link", { name: "Ayrıntısı: Abonelikleri gözden geçirin" })).toHaveAttribute(
      "href",
      "/degerlendirme",
    );
    expect(within(todo).getByText("Ayda yaklaşık 99,99 TL etkisi var.")).toBeInTheDocument();
    expect(
      within(todo).getByText("Bilgilerin tam olması için 3 iş bekliyor (eksik ya da okunamayan belgeler gibi)."),
    ).toBeInTheDocument();
    expect(within(todo).getByRole("link", { name: "Yapılacaklara bak" })).toHaveAttribute("href", "/yapilacaklar");
    expect(within(todo).getByRole("link", { name: "Belge ekle" })).toHaveAttribute("href", "/belge-ekle");
  });

  it("says there is nothing to do when no alert, advice or work is open", async () => {
    server.use(http.get("/api/insights", () => HttpResponse.json({ ...INSIGHTS, steps: [] })));
    const quiet: Dashboard = {
      ...DASHBOARD,
      alerts: { ...DASHBOARD.alerts, items: [] },
      todo: { ...DASHBOARD.todo, total: 0, kinds: [] },
    };
    renderScreen(<Overview found={quiet} />);
    const todo = await region("Ne yapmalısınız?");
    expect(await within(todo).findByText("Şimdilik yapmanız gereken bir şey yok.")).toBeInTheDocument();
    expect(within(todo).queryByRole("link", { name: "Yapılacaklara bak" })).not.toBeInTheDocument();
  });
});
