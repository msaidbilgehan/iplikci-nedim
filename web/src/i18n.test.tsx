import { render, screen } from "@testing-library/react";
import { useTranslation } from "react-i18next";
import { beforeAll, describe, expect, it } from "vitest";

import i18n, { resources } from "./i18n";

// A namespace of the tests' own, written as a screen's file would be: the formatters attach the suffixes.
const EXAMPLES = {
  since: "{{month, fromMonth}} beri",
  inMonths: "{{month, inMonth}} ödendi",
  share: "giderlerin {{share, percentPossessive}}",
  day: "her ayın {{day, possessiveLocative}}",
  year: "{{year, locative}} açıldı",
  count: "{{count, ablative}} fazla belge",
  amount: "{{amount, money}} ödendi",
  due: "son ödeme {{due, day}}",
};

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** A key of the tests' namespace; the typed t() knows only the app's own namespaces. */
function example(key: keyof typeof EXAMPLES, options: Record<string, unknown>): string {
  return (i18n.t as unknown as Translate)(key, { ns: "ornek", ...options });
}

describe("i18n", () => {
  beforeAll(() => {
    i18n.addResourceBundle("tr", "ornek", EXAMPLES);
  });

  it("speaks Turkish from the bundled files, without waiting", () => {
    expect(i18n.language).toBe("tr");
    expect(i18n.t("loading")).toBe("Yükleniyor…");
    expect(i18n.t("signedOut.title")).toBe("Oturum kapandı");
    expect(Object.keys(resources.tr)).toContain("common");
    // @ts-expect-error: the keys are typed from the files, so a misspelt one does not compile
    expect(i18n.t("loadng")).toBe("loadng");
  });

  it("attaches the suffix a number or a year asks for, never one typed into the text", () => {
    expect(example("since", { month: "2026-05" })).toBe("Mayıs 2026'dan beri");
    expect(example("since", { month: "2025-12" })).toBe("Aralık 2025'ten beri");
    expect(example("inMonths", { month: "2026-03" })).toBe("Mart 2026'da ödendi");
    expect(example("share", { share: 0.64 })).toBe("giderlerin %64'ü");
    expect(example("share", { share: 0.06 })).toBe("giderlerin %6'sı");
    expect(example("day", { day: 3 })).toBe("her ayın 3'ünde");
    expect(example("day", { day: 20 })).toBe("her ayın 20'sinde");
    expect(example("year", { year: "2025" })).toBe("2025'te açıldı");
    expect(example("count", { count: 1000 })).toBe("1.000'den fazla belge");
    expect(example("count", { count: 40 })).toBe("40'tan fazla belge");
  });

  it("writes amounts and days as the rest of the interface does", () => {
    expect(example("amount", { amount: { minor: 123456, currency: "TRY" } })).toBe("1.234,56 TL ödendi");
    expect(example("due", { due: "2026-11-25" })).toBe("son ödeme 25.11.2026");
  });

  it("gives components their words through useTranslation", () => {
    function Probe() {
      const { t } = useTranslation();
      return <p>{t("retry")}</p>;
    }
    render(<Probe />);
    expect(screen.getByText("Yeniden dene")).toBeInTheDocument();
  });
});
