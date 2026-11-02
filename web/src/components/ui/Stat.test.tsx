import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AppProviders } from "../AppProviders";
import { Stat } from "./Stat";

function renderStat() {
  return render(
    <AppProviders>
      <Stat
        label="Bu ay"
        value="12.500 TL"
        meta="6 tam ay: Nisan – Eylül 2026"
        comment="Bu ay tipik aydan %12 fazla harcandı."
      />
    </AppProviders>,
  );
}

describe("Stat", () => {
  afterEach(() => localStorage.clear());

  it("names its figure and says what it rests on", () => {
    renderStat();
    expect(screen.getByRole("term")).toHaveTextContent("Bu ay");
    expect(screen.getByRole("definition")).toHaveTextContent("12.500 TL");
    expect(screen.getByText("6 tam ay: Nisan – Eylül 2026")).toBeInTheDocument();
  });

  it("comments on the figure in the simple view only", () => {
    renderStat();
    expect(screen.getByText("Bu ay tipik aydan %12 fazla harcandı.")).toBeInTheDocument();
  });

  it("leaves the comment out of the detailed view, keeping the window", () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderStat();
    expect(screen.queryByText("Bu ay tipik aydan %12 fazla harcandı.")).not.toBeInTheDocument();
    expect(screen.getByText("6 tam ay: Nisan – Eylül 2026")).toBeInTheDocument();
  });
});
