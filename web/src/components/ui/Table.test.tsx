import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Table, Td, Th } from "./Table";

function Example() {
  return (
    <Table>
      <caption className="sr-only">Beklenen ödemeler</caption>
      <thead>
        <tr>
          <Th>Gün</Th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <Td>03.11.2026</Td>
        </tr>
      </tbody>
    </Table>
  );
}

describe("Table", () => {
  it("adds no stop for the keyboard while the table fits", () => {
    render(<Example />);
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(screen.getByRole("table").parentElement).not.toHaveAttribute("tabindex");
  });

  it("lets the keyboard reach a table wider than the screen, named by its caption", () => {
    vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockReturnValue(900);
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(320);
    render(<Example />);
    const region = screen.getByRole("region", { name: "Beklenen ödemeler" });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region).toContainElement(screen.getByRole("table"));
  });
});
