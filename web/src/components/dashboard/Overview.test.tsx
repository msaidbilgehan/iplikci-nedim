import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { Dashboard, MonthClosing } from "../../api/types";
import { renderScreen } from "../../test/render";
import { DASHBOARD, FORECAST, INSIGHTS, server, SPENDING } from "../../test/server";
import { Overview } from "./Overview";

const region = (name: string) => screen.findByRole("region", { name });

const tl = (minor: number) => ({ minor, currency: "TRY" });

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
    expect(within(story).getByText("gelen paradan giden ve birikim çıkınca")).toBeInTheDocument();
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

  it("waits for the first closed month before telling one", async () => {
    const months = DASHBOARD.closing.months.map((month): MonthClosing => ({ ...month, income: null }));
    renderScreen(<Overview found={{ ...DASHBOARD, closing: { ...DASHBOARD.closing, months } }} />);
    const story = await region("Paranız ne durumda?");
    expect(within(story).getByText(/^Henüz kapanan bir ay yok\./)).toBeInTheDocument();
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

  it("leads from a month's money in to its income and from its money out to its spending", async () => {
    renderScreen(<Overview found={DASHBOARD} />);
    const months = await region("Aylara göre gelen ve giden");
    expect(
      within(months).getByText("Bir ayın gelen ya da giden parasına tıklayın: o işlemler listelenir."),
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
    expect(within(october).getAllByRole("link")).toHaveLength(2); // the month alone leads to neither
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
        "Dikkat: 03.12.2026'da paranız eksiye düşüyor (−14.019,00 TL). " +
          "Bir ödemeyi erteleyin ya da hesaba para aktarın.",
      ),
    ).toBeInTheDocument();
    expect(
      within(ahead).getByText(
        "Çizgi, ödemelerinizin çıktığı Örnek Vadesiz TL hesabını gösterir. Son belgelerde 1.000,00 TL vardı; o " +
          "günden bugüne beklenen gelir ve ödemeler eklenince bugün yaklaşık 999,00 TL.",
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
      await within(ahead).findByText("Paranız 30 gün boyunca yetiyor: en az 14.12.2026'da 971,00 TL kalıyor."),
    ).toBeInTheDocument();
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
