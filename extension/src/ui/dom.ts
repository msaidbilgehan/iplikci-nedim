/**
 * What the extension's window (popup.html) and its settings page (options.html) share: their elements, the requests
 * to the service worker, the status card and "İplikçi Nedim'i aç". The pages carry no inline script or style: they
 * change only text, attributes and the `hidden` property.
 */

import type { Request, Status } from "../bridge/messages";
import type { PanelAnswer, PanelOutcome } from "../bridge/panel";
import { type Saying, asSaying } from "../bridge/service";
import { ICON_PATHS, SILENT, type Shown } from "./status";

export function element<T extends Element>(id: string, type: new () => T): T {
  const found = document.getElementById(id);
  if (!(found instanceof type)) {
    throw new Error(`the page has no #${id}`);
  }
  return found;
}

/** Set an element's text only when it changed: a live region says again what is set again. */
export function say(target: HTMLElement, text: string): void {
  if (target.textContent !== text) {
    target.textContent = text;
  }
}

export function version(): string {
  return chrome.runtime.getManifest().version;
}

/** Ask the service worker; where the bridge stands after it, or null when it did not answer. */
export async function ask(request: Request): Promise<Status | null> {
  const answer = await send(request);
  return isStatus(answer) ? answer : null;
}

/** İplikçi Nedim's lines on the money, from the service worker (bridge/sayings.ts); none when it has none. */
export async function askSayings(): Promise<Saying[]> {
  const answer = await send({ kind: "sayings" });
  return Array.isArray(answer) ? answer.flatMap(asSaying) : [];
}

/** Whether anything answers on the service's address, as the service worker finds; null when it did not answer. */
export async function askService(): Promise<boolean | null> {
  const answer = await send({ kind: "service" });
  if (typeof answer !== "object" || answer === null) {
    return null;
  }
  const found = (answer as Record<string, unknown>)["answers"];
  return typeof found === "boolean" ? found : null;
}

async function send(request: Request): Promise<unknown> {
  try {
    return (await chrome.runtime.sendMessage(request)) as unknown;
  } catch {
    return null;
  }
}

function isStatus(value: unknown): value is Status {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const { paired, account, problem } = value as Record<string, unknown>;
  return typeof paired === "boolean" && typeof account === "number" && typeof problem === "string";
}

const OUTCOMES: ReadonlySet<string> = new Set<PanelOutcome>([
  "shown",
  "signed-in",
  "opened",
  "service-down",
  "not-the-service",
]);
/** The outcomes after which a tab of the service is in front. */
export const IN_FRONT: ReadonlySet<PanelOutcome> = new Set<PanelOutcome>(["shown", "signed-in", "opened"]);

function isPanelAnswer(value: unknown): value is PanelAnswer {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const { outcome, detail } = value as Record<string, unknown>;
  return typeof outcome === "string" && OUTCOMES.has(outcome) && typeof detail === "string";
}

/** The status card: its tone, the icon, the word and the sentences (ids shared by the two pages). */
export interface StatusCard {
  readonly card: HTMLElement;
  readonly icon: SVGPathElement;
  readonly word: HTMLElement;
  readonly detail: HTMLElement;
  readonly when: HTMLElement;
}

export function statusCard(): StatusCard {
  return {
    card: element("status", HTMLElement),
    icon: element("status-icon", SVGPathElement),
    word: element("status-word", HTMLElement),
    detail: element("status-detail", HTMLElement),
    when: element("status-when", HTMLElement),
  };
}

export function draw(card: StatusCard, shown: Shown): void {
  card.card.dataset["tone"] = shown.tone;
  card.icon.setAttribute("d", ICON_PATHS[shown.icon]);
  say(card.word, shown.word);
  say(card.detail, shown.detail);
  say(card.when, shown.when);
}

/**
 * "İplikçi Nedim'i aç": the service worker opens the interface (bridge/panel.ts); what it did, said beside the
 * button, or null when it did not answer. The button keeps the focus it had.
 */
export async function openInterface(button: HTMLButtonElement, answer: HTMLElement): Promise<PanelAnswer | null> {
  const focused = document.activeElement === button;
  button.disabled = true;
  say(answer, "İplikçi Nedim açılıyor…");
  const found = await send({ kind: "open-panel" });
  const result = isPanelAnswer(found) ? found : null;
  button.disabled = false;
  if (focused) {
    button.focus();
  }
  say(answer, result === null ? SILENT : result.detail);
  return result;
}
