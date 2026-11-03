// What a chart's parts lead to (features.md, "İz": every number leads to the rows it rests on): a month's column or one
// series of it, a day of a line, a band of a flow. A mouse or a pen opens a part with a click. A touch first shows the
// part's values, as a pointer's rest does, and opens it with a second touch on the same part or with the link in its
// tip. The keyboard and screen readers reach the same places through the table view, whose names are links, so the
// drawing itself stays one image with no stops of its own.

import { type RefObject, useEffect, useRef } from "react";
import { useNavigate } from "react-router";

import type { Destination } from "../../api/types";
import { hrefOf } from "../../lib/links";

export interface ChartOpen<K> {
  link: (key: K) => Destination | null; // where a part leads; null for one that leads nowhere
  hint: string; // what a click opens, said under the drawing: "Bir aya tıklayın: o ayın giderleri listelenir."
}

/** Whether a press came from a finger: no pointer rests over a part before it, so its first touch shows the values. */
export function isTouch(event: { pointerType?: string }): boolean {
  return event.pointerType === "touch";
}

export interface Opener {
  /** A press on a part; again: the part was shown already, as a touch's second press on it. */
  press: (event: { pointerType?: string }, again: boolean) => void;
  /** The click after the press: opens the link, unless it was a touch's first press. */
  click: (link: Destination | null) => void;
}

/** Opens a chart's parts as their links say: at once for a mouse or a pen, at a touch's second press. */
export function useOpener(): Opener {
  const navigate = useNavigate();
  const pressed = useRef({ touch: false, again: false });
  return {
    press: (event, again) => {
      pressed.current = { touch: isTouch(event), again };
    },
    click: (link) => {
      const href = link ? hrefOf(link) : null;
      if (href && (!pressed.current.touch || pressed.current.again)) {
        void navigate(href);
      }
    },
  };
}

/** While a touch keeps a part shown, a press anywhere outside the chart puts it away. */
export function useDismiss(box: RefObject<HTMLElement | null>, shown: boolean, dismiss: () => void): void {
  useEffect(() => {
    if (!shown) {
      return undefined;
    }
    const away = (event: PointerEvent) => {
      if (!(event.target instanceof Node) || !box.current?.contains(event.target)) {
        dismiss();
      }
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [box, shown, dismiss]);
}
