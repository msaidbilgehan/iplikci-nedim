import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Tone } from "./Badge";
import { Status } from "./Status";

describe("Status", () => {
  it.each<[Tone, string]>([
    ["good", "Kapandı"],
    ["warning", "Kontrol gerekli"],
    ["critical", "Eksik"],
    ["neutral", "Bekleniyor"],
  ])("says a %s state in words, with an icon beside the colour", (tone, label) => {
    const { container } = render(<Status tone={tone}>{label}</Status>);
    expect(screen.getByText(label)).toBeInTheDocument();
    const disc = container.querySelector("[aria-hidden='true']");
    expect(disc?.querySelector("svg")).not.toBeNull();
    expect(container).toHaveTextContent(label);
  });

  it("fills each judged state with its status colour", () => {
    const { container } = render(
      <>
        <Status tone="good">İyi</Status>
        <Status tone="warning">Uyarı</Status>
        <Status tone="critical">Kritik</Status>
      </>,
    );
    const fills = [...container.querySelectorAll("span[aria-hidden='true']")].map((disc) => disc.className);
    expect(fills[0]).toContain("bg-status-good");
    expect(fills[1]).toContain("bg-status-warning");
    expect(fills[2]).toContain("bg-status-critical");
  });
});
