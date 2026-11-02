import { render, screen, waitFor } from "@testing-library/react";
import userEvent, { PointerEventsCheckLevel } from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./Dialog";

const TITLE = "Belge çöp kutusuna taşınsın mı?";
const TEXT = "Belge kalıcı olarak silinmez; sistemin çöp kutusuna gider.";

function Harness({ onConfirm = () => {}, busy = false }: { onConfirm?: () => void; busy?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Kaldır
      </button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={TITLE}
        description={TEXT}
        confirmLabel="Çöp kutusuna taşı"
        variant="danger"
        onConfirm={onConfirm}
        busy={busy}
      />
    </>
  );
}

async function openIt() {
  await userEvent.click(screen.getByRole("button", { name: "Kaldır" }));
  return screen.findByRole("alertdialog", { name: TITLE });
}

describe("ConfirmDialog", () => {
  it("asks with its question and what will happen, the safe choice having the focus", async () => {
    render(<Harness />);
    const dialog = await openIt();
    expect(dialog).toHaveAccessibleDescription(TEXT);
    expect(screen.getByRole("button", { name: "Vazgeç" })).toHaveFocus();
  });

  it("keeps the focus inside while it asks", async () => {
    render(<Harness />);
    await openIt();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Çöp kutusuna taşı" })).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Vazgeç" })).toHaveFocus();
  });

  it("runs the action when it is confirmed", async () => {
    const onConfirm = vi.fn();
    render(<Harness onConfirm={onConfirm} />);
    await openIt();
    await userEvent.click(screen.getByRole("button", { name: "Çöp kutusuna taşı" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("goes away on Escape and gives the focus back to what opened it", async () => {
    render(<Harness />);
    await openIt();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Kaldır" })).toHaveFocus();
  });

  it("takes no press outside it as an answer", async () => {
    render(<Harness />);
    const dialog = await openIt();
    // Radix turns the page's pointer events off behind a modal dialog; the press is made anyway.
    const user = userEvent.setup({ pointerEventsCheck: PointerEventsCheckLevel.Never });
    await user.click(document.body);
    expect(dialog).toBeInTheDocument();
  });

  it("waits while the action runs", async () => {
    render(<Harness busy />);
    await openIt();
    expect(screen.getByRole("button", { name: "Çöp kutusuna taşı" })).toBeDisabled();
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("leaves the page behind inert while it asks: nothing there takes the focus or is read", async () => {
    const { container } = render(<Harness />);
    await openIt();
    expect(container).toHaveAttribute("inert");
    expect(screen.getByRole("alertdialog").closest("[inert]")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(container).not.toHaveAttribute("inert"));
  });

  it("holds the page behind still while it is open", async () => {
    render(<Harness />);
    await openIt();
    expect(document.documentElement.style.overflow).toBe("hidden");
    await userEvent.click(screen.getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(document.documentElement.style.overflow).toBe(""));
  });
});
