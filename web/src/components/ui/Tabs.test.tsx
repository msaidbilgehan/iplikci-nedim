import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Tab, TabList, TabPanel, Tabs } from "./Tabs";

function Example({ look }: { look?: "line" | "segmented" }) {
  return (
    <Tabs defaultValue="all">
      <TabList aria-label="Belgeler" {...(look ? { look } : {})}>
        <Tab value="all">Tümü</Tab>
        <Tab value="unprocessed">İşlenmeyenler</Tab>
      </TabList>
      <TabPanel value="all">Bütün belgeler</TabPanel>
      <TabPanel value="unprocessed">İşlenmeyen belgeler</TabPanel>
    </Tabs>
  );
}

describe("Tabs", () => {
  it("shows the chosen tab's panel, labelled by the tab", () => {
    render(<Example />);
    const tab = screen.getByRole("tab", { name: "Tümü" });
    expect(tab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Tümü" })).toHaveTextContent("Bütün belgeler");
    expect(screen.queryByText("İşlenmeyen belgeler")).not.toBeInTheDocument();
  });

  it.each(["line", "segmented"] as const)("moves between the tabs with the arrow keys (%s)", async (look) => {
    render(<Example look={look} />);
    await userEvent.tab();
    expect(screen.getByRole("tab", { name: "Tümü" })).toHaveFocus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "İşlenmeyenler" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "İşlenmeyenler" })).toHaveTextContent("İşlenmeyen belgeler");
  });
});
