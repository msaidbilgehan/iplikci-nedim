import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./Button";
import { PageHeader } from "./PageHeader";

describe("PageHeader", () => {
  it("names the screen as its one main heading, with what it shows and its actions", () => {
    render(
      <PageHeader
        title="Takvim"
        description="Önümüzdeki 60 günde beklenen ödemeler ve gelirler."
        actions={<Button>Yenile</Button>}
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Takvim" })).toBeInTheDocument();
    expect(screen.getByText("Önümüzdeki 60 günde beklenen ödemeler ve gelirler.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yenile" })).toBeInTheDocument();
  });

  it("names the window after the screen", async () => {
    render(<PageHeader title="Faturalar" />);
    await waitFor(() => expect(document.title).toBe("Faturalar · İplikçi Nedim"));
  });
});
