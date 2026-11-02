import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import glossary from "../../locales/tr/glossary.json";
import { tl } from "../../test/server";
import { AppProviders } from "../AppProviders";
import { Money } from "./Money";

function renderIt(ui: ReactNode) {
  return render(<AppProviders>{ui}</AppProviders>);
}

describe("Money", () => {
  it("shows a confirmed amount alone, as Turkish readers write it", () => {
    renderIt(<Money value={tl(123456)} />);
    expect(screen.getByText("1.234,56 TL")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("writes the sign, never leaving it to colour", () => {
    renderIt(
      <>
        <Money value={tl(-1400000)} />
        <Money value={tl(4000000)} direction="in" />
        <Money value={tl(9999)} direction="out" />
      </>,
    );
    expect(screen.getByText("−14.000,00 TL")).toBeInTheDocument();
    expect(screen.getByText("+40.000,00 TL")).toBeInTheDocument();
    expect(screen.getByText("−99,99 TL")).toBeInTheDocument();
  });

  it("marks a provisional amount, and the mark explains itself", async () => {
    renderIt(<Money value={tl(150000)} certainty="provisional" />);
    const mark = screen.getByRole("button", { name: "geçici" });
    await userEvent.tab();
    expect(mark).toHaveFocus();
    expect(await screen.findByRole("tooltip")).toHaveTextContent(glossary.provisional.text);
    // It still counts: the figure is not muted.
    expect(screen.getByText("1.500,00 TL").className).not.toContain("text-zinc-600");
  });

  it("marks and mutes the amounts that count in no total", () => {
    renderIt(
      <>
        <Money value={tl(25000)} certainty="excluded" />
        <Money value={tl(41290)} certainty="info" />
      </>,
    );
    expect(screen.getByRole("button", { name: "ekstrede yok" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "yalnızca bilgi" })).toBeInTheDocument();
    expect(screen.getByText("250,00 TL").className).toContain("text-zinc-600");
    expect(screen.getByText("412,90 TL").className).toContain("text-zinc-600");
  });
});
