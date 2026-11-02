import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { FilterChips, type FilterOption, FilterPopover, type Selection, toggled } from "./FilterPopover";

const ACCOUNTS: FilterOption[] = [
  { value: "teb-1", label: "Vadesiz TL", group: "Örnek Banka", note: "Vadesiz" },
  { value: "teb-2", label: "Kart •1234", group: "Örnek Banka", note: "Kredi kartı" },
  { value: "is-1", label: "Vadesiz TL", group: "Başka Banka", note: "Vadesiz" },
];

function Harness({ options = ACCOUNTS, start = null }: { options?: FilterOption[]; start?: Selection }) {
  const [selected, setSelected] = useState<Selection>(start);
  return <FilterPopover label="Hesaplar" options={options} selected={selected} onChange={setSelected} />;
}

async function openIt() {
  await userEvent.click(screen.getByRole("button", { name: /^Hesaplar:/ }));
  return screen.findByRole("dialog", { name: "Hesaplar" });
}

describe("toggled", () => {
  it("turns options off and on, every option on being no filter", () => {
    const all = ["a", "b", "c"];
    const without = toggled(null, all, ["b"], false);
    expect(without).toEqual(new Set(["a", "c"]));
    expect(toggled(without, all, ["b"], true)).toBeNull();
    expect(toggled(null, all, ["a", "b", "c"], false)).toEqual(new Set());
  });
});

describe("FilterPopover", () => {
  it("says what is chosen on its button", async () => {
    render(<Harness />);
    expect(screen.getByRole("button", { name: "Hesaplar: Tümü" })).toBeInTheDocument();
    const panel = await openIt();
    await userEvent.click(within(panel).getByRole("checkbox", { name: "Kart •1234 Kredi kartı" }));
    expect(screen.getByRole("button", { name: "Hesaplar: 2/3" })).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Hiçbiri" }));
    expect(screen.getByRole("button", { name: "Hesaplar: Hiçbiri" })).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("checkbox", { name: "Kart •1234 Kredi kartı" }));
    expect(screen.getByRole("button", { name: "Hesaplar: Kart •1234" })).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Tümü" }));
    expect(screen.getByRole("button", { name: "Hesaplar: Tümü" })).toBeInTheDocument();
  });

  it("chooses a whole group with its own box, which shows when only some of it is chosen", async () => {
    render(<Harness />);
    const panel = await openIt();
    const bank = within(panel).getByRole("group", { name: "Örnek Banka" });
    const groupBox = within(bank).getByRole("checkbox", { name: "Örnek Banka" });
    expect(groupBox).toBeChecked();
    await userEvent.click(within(bank).getByRole("checkbox", { name: "Vadesiz TL Vadesiz" }));
    expect(groupBox).toBePartiallyChecked();
    await userEvent.click(groupBox);
    expect(groupBox).toBeChecked();
    expect(screen.getByRole("button", { name: "Hesaplar: Tümü" })).toBeInTheDocument();
    await userEvent.click(groupBox);
    expect(screen.getByRole("button", { name: "Hesaplar: Vadesiz TL" })).toBeInTheDocument();
  });

  it("closes on Escape and gives the focus back to its button", async () => {
    render(<Harness />);
    await openIt();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hesaplar: Tümü" })).toHaveFocus();
  });

  it("lists options without a group on their own", async () => {
    render(<Harness options={[{ value: "a", label: "Market" }, { value: "b", label: "Ulaşım" }]} />);
    const panel = await openIt();
    // The one group is the panel's own fieldset, named after the filter.
    expect(within(panel).getAllByRole("group").map((group) => group.tagName)).toEqual(["FIELDSET"]);
    expect(within(panel).getAllByRole("checkbox")).toHaveLength(2);
  });
});

describe("FilterChips", () => {
  it("shows the filters that are set, each with a button that takes it off", async () => {
    const offCategory = vi.fn();
    const reset = vi.fn();
    render(
      <FilterChips
        chips={[{ key: "category", name: "Kategori", value: "Market", onRemove: offCategory }]}
        onReset={reset}
      />,
    );
    const chips = screen.getByRole("list", { name: "Etkin süzgeçler" });
    expect(within(chips).getByText("Market")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Kategori süzgecini kaldır" }));
    expect(offCategory).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: "Sıfırla" }));
    expect(reset).toHaveBeenCalledOnce();
  });

  it("shows nothing while no filter is set", () => {
    const { container } = render(<FilterChips chips={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
