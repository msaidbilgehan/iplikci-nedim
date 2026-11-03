import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Saying } from "../../api/types";
import { renderScreen } from "../../test/render";
import { DASHBOARD } from "../../test/server";
import { FACES, NedimSays } from "./NedimSays";

const bubble = () => screen.getByRole("region", { name: "İplikçi Nedim'in paranız hakkındaki sözü" });
const face = () => bubble().querySelector("img");

const NO_DATA: Saying = {
  situation: "no_data",
  mood: "neutral",
  reason: "Henüz belge yok; paranın nasıl gittiği bilinmiyor.",
  quote: { id: "dont_know", lines: ["İsa Muhammed aşkına bilmiyorum."] },
};

describe("NedimSays", () => {
  it("says the most pressing situation's line in quotation marks, with what it is said about", () => {
    renderScreen(<NedimSays sayings={DASHBOARD.sayings} />);
    const said = within(bubble());
    expect(said.getByText("“Değil ıhlamur içmek, ıhlamur ağacı yesem gevşemez sinirlerim.”")).toBeInTheDocument();
    expect(said.getByText("İplikçi Nedim")).toBeInTheDocument();
    expect(said.getByText("Öngörüye göre hesaplarınızdan biri 18 gün sonra eksiye düşecek.")).toBeInTheDocument();
  });

  it("colours his face by how the money stands, the logo itself when it goes well", () => {
    renderScreen(<NedimSays sayings={DASHBOARD.sayings} />);
    expect(face()).toHaveAttribute("src", FACES.critical);
    expect(face()).toHaveAttribute("alt", ""); // the line and its sentence say what the colour does
    expect(FACES.good).toBe("/logo.png");
  });

  it("goes through the other lines true today, and back to the first", async () => {
    const user = userEvent.setup();
    renderScreen(<NedimSays sayings={DASHBOARD.sayings} />);
    const another = within(bubble()).getByRole("button", { name: "Başka bir söz" });
    await user.click(another);
    expect(within(bubble()).getByText("“Bize iki ıhlamur getir kızım.”")).toBeInTheDocument();
    await user.click(another);
    // A dialogue: each turn on a line of its own, the reason and the face its situation's.
    expect(within(bubble()).getByText("– Ortadoğu mu büyük? Ben mi büyüğüm? Çabuk söyle.")).toBeInTheDocument();
    expect(within(bubble()).getByText("– Siz efendim.")).toBeInTheDocument();
    expect(within(bubble()).getByText("– Hıh. Tamam canım.")).toBeInTheDocument();
    expect(
      within(bubble()).getByText("Ekim 2026, kapanan son 5 ay içinde en çok paranın kaldığı ay oldu."),
    ).toBeInTheDocument();
    expect(face()).toHaveAttribute("src", FACES.good);
    await user.click(another);
    expect(within(bubble()).getByText("“Değil ıhlamur içmek, ıhlamur ağacı yesem gevşemez sinirlerim.”")).toBeInTheDocument();
  });

  it("offers no other line when there is one only, and says nothing when there is none", () => {
    const { unmount } = renderScreen(<NedimSays sayings={[NO_DATA]} />);
    expect(within(bubble()).getByText("“İsa Muhammed aşkına bilmiyorum.”")).toBeInTheDocument();
    expect(within(bubble()).queryByRole("button")).not.toBeInTheDocument();
    expect(face()).toHaveAttribute("src", FACES.neutral);
    unmount();
    renderScreen(<NedimSays sayings={[]} />);
    expect(screen.queryByRole("region", { name: "İplikçi Nedim'in paranız hakkındaki sözü" })).not.toBeInTheDocument();
  });
});
