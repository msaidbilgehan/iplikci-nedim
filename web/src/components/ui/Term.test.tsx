import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import glossary from "../../locales/tr/glossary.json";
import { AppProviders } from "../AppProviders";
import { Term, type TermId } from "./Term";

function renderSentence(term = <Term id="kmh" />) {
  return render(
    <AppProviders>
      <p>Hesap {term} limitine dayandı.</p>
      <button type="button">Başka bir yer</button>
    </AppProviders>,
  );
}

describe("Term", () => {
  it("explains itself when the keyboard reaches it, as the word's description for screen readers", async () => {
    renderSentence();
    await userEvent.tab();
    const word = screen.getByRole("button", { name: "KMH" });
    expect(word).toHaveFocus();
    const tip = await screen.findByRole("tooltip");
    expect(tip).toHaveTextContent(glossary.kmh.text);
    expect(word).toHaveAccessibleDescription(glossary.kmh.text);
  });

  it("explains itself when the pointer rests on it, and goes when the pointer moves elsewhere", async () => {
    renderSentence();
    const user = userEvent.setup();
    // Coordinates of their own: in jsdom every box sits at 0,0, and Radix lets the pointer cross towards the hint.
    await user.pointer({ target: screen.getByRole("button", { name: "KMH" }), coords: { clientX: 10, clientY: 10 } });
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();
    const elsewhere = screen.getByRole("button", { name: "Başka bir yer" });
    await user.pointer({ target: elsewhere, coords: { clientX: 400, clientY: 300 } });
    await waitFor(() => expect(screen.queryByRole("tooltip")).not.toBeInTheDocument());
  });

  it("explains itself on a tap, where there is no hover", async () => {
    renderSentence();
    const user = userEvent.setup();
    await user.pointer({ keys: "[TouchA]", target: screen.getByRole("button", { name: "KMH" }) });
    expect(await screen.findByRole("tooltip")).toHaveTextContent(glossary.kmh.text);
  });

  it("goes away on Escape", async () => {
    renderSentence();
    await userEvent.tab();
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("tooltip")).not.toBeInTheDocument());
  });

  it("keeps the words of the sentence and names the term in its explanation", async () => {
    renderSentence(<Term id="statementDate">kesim tarihinde</Term>);
    await userEvent.click(screen.getByRole("button", { name: "kesim tarihinde" }));
    const visible = await screen.findAllByText(glossary.statementDate.term);
    expect(visible.length).toBeGreaterThan(0);
  });

  it("explains every term the screens use", () => {
    const required: TermId[] = [
      "kmh",
      "minimumPayment",
      "statementDate",
      "dueDate",
      "statement",
      "receipt",
      "bankNotice",
      "provisional",
      "notOnStatement",
      "infoOnly",
      "fxSpread",
      "completeMonth",
      "typicalMonth",
    ];
    expect(Object.keys(glossary).sort()).toEqual([...required].sort());
    for (const entry of Object.values(glossary)) {
      expect(entry.term.length).toBeGreaterThan(0);
      expect(entry.text).toMatch(/\.$/);
    }
  });
});
