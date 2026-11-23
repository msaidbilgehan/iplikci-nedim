// The sync folder on the Settings screen (ADR-0025, F22). A folder that Google Drive's desktop app (or iCloud Drive,
// Dropbox, OneDrive) mirrors carries each computer's documents and decisions (notes, rules, settings) to the user's
// other computers, and is the data's copy off the computer. The database never goes into it: each computer reads the
// documents itself. Off, the card lists the places on this computer the folder can go, checks a folder the user types,
// and says what turning the sync on in the chosen one does (begin a set of data there, or join the one another computer
// began) before it does it. On, it says where the folder is, this computer's name, how the last round went and what
// still moves, the computers in the set and which one sends Telegram's and e-mail's notifications (another one that
// can send takes a channel over after half an hour of silence), and offers a round now and turning the sync off, after
// asking. The rounds run without telling the event stream, so the card asks how they went (useSync).

import type { TFunction } from "i18next";
import { type FormEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  useInspectSyncFolder,
  useLabels,
  useRenameSyncComputer,
  useSendFromHere,
  useSync,
  useSyncPlaces,
  useSyncRound,
  useTurnOffSync,
  useTurnOnSync,
} from "../../api/queries";
import type { Labels, SyncDevice, SyncPlace, SyncState, SyncTurnOn } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatTime } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, useView } from "../Preferences";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, Facts } from "../ui/Card";
import { ConfirmDialog } from "../ui/Dialog";
import { Say } from "../ui/Say";
import { LINK } from "./MailFields";
import { HINT } from "./NameList";

// Google Drive for desktop's own download page, opened in the user's browser: the program itself never asks Google.
export const DRIVE_DOWNLOAD = "https://www.google.com/drive/download/";
// The channels whose notifications leave the computer: one computer of the set sends each (ADR-0025).
const CHANNELS = ["telegram", "email"] as const;
const WAIT_MS = 60_000; // how long the card follows a round it asked for, and says how it went
const NAME_MAX = 60; // the longest name the service takes (NameIn, TurnOnIn)
const FOLDER_MAX = 1000; // the longest folder the service takes (FolderIn)
const NAMES = new Intl.ListFormat("tr-TR", { style: "long", type: "conjunction" });

const FIELD = cn(
  "min-h-11 w-full max-w-md rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const INVALID = "border-red-700 dark:border-red-400";
const ERROR = "text-sm text-red-800 dark:text-red-200";
const PART = "flex flex-col gap-2 text-sm";
const PART_TITLE = "text-sm font-semibold";
const BOX = "flex flex-col gap-2 rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700";
const PATH = "text-xs break-all text-zinc-700 dark:text-zinc-300";
// An element that takes the focus when what the user was on went away (a step changed the card).
const FOCUSED = "rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";

type TurnOn = ReturnType<typeof useTurnOnSync>;
type TurnOnStep = (body: SyncTurnOn) => void;
type TurnOff = ReturnType<typeof useTurnOffSync>;
type Rename = ReturnType<typeof useRenameSyncComputer>;
type Choose = (place: SyncPlace, opener: HTMLElement) => void;
/** A round the user asked for: not run yet, or run (and how it went is said until the card stops following it). */
type Asked = "waiting" | "ran" | null;

export function SyncCard() {
  const { t } = useTranslation("settings");
  // The last round's time when the user asked for a new one: the card asks every few seconds until it changes.
  const [askedAfter, setAskedAfter] = useState<string | null>(null);
  const sync = useSync(askedAfter);
  const found = sync.data;
  // Here rather than with their buttons, which go with the state they change: what they did is said after.
  const turnOn = useTurnOnSync();
  const turnOff = useTurnOffSync();
  useEffect(() => {
    if (askedAfter === null) {
      return undefined;
    }
    const stop = window.setTimeout(() => setAskedAfter(null), WAIT_MS);
    return () => window.clearTimeout(stop);
  }, [askedAfter]);
  // The service begins the first round as it turns the sync on: the card follows it as a round asked for.
  const onTurnOn = (body: SyncTurnOn) =>
    turnOn.mutate(body, { onSuccess: (state) => setAskedAfter(state.last_at) });
  return (
    <Card title={t("sync.title")} action={found ? <SyncBadge state={found} /> : undefined}>
      {found ? (
        <Say>
          <Sentence state={found} />
        </Say>
      ) : null}
      {sync.isPending ? <Loading /> : null}
      {sync.isError ? <Failure error={sync.error} onRetry={() => void sync.refetch()} /> : null}
      {found?.on ? (
        <SyncOn
          state={found}
          turnedOn={turnOn.isSuccess}
          turnOff={turnOff}
          asked={roundAsked(askedAfter, found)}
          onAsked={() => setAskedAfter(found.last_at)}
        />
      ) : null}
      {found && !found.on ? (
        <SyncOff state={found} turnOn={turnOn} onTurnOn={onTurnOn} turnedOff={turnOff.isSuccess} />
      ) : null}
    </Card>
  );
}

function roundAsked(askedAfter: string | null, state: SyncState): Asked {
  if (askedAfter === null) {
    return null;
  }
  return state.last_at === askedAfter ? "waiting" : "ran";
}

function SyncBadge({ state }: { state: SyncState }) {
  const { t } = useTranslation("settings");
  if (!state.on) {
    return <Badge tone="neutral">{t("sync.off")}</Badge>;
  }
  return state.problem ? (
    <Badge tone="warning">{t("sync.troubled")}</Badge>
  ) : (
    <Badge tone="good">{t("sync.on")}</Badge>
  );
}

/** The simple view's sentence: where the data is kept, and with how many computers it is shared. */
function Sentence({ state }: { state: SyncState }) {
  const { t } = useTranslation("settings");
  if (!state.on) {
    return t("sync.sayOff");
  }
  if (state.problem) {
    return t("sync.sayProblem");
  }
  const via = state.service || t("sync.theFolder");
  const computers = state.devices.filter((device) => !device.left).length;
  return computers > 1 ? t("sync.sayShared", { via, computers }) : t("sync.sayAlone", { via });
}

/** What a step just did, given the focus: the control that took the step went with the state it changed. */
function Told({ title, children }: { title: string; children?: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    box.current?.focus();
  }, []);
  return (
    <div ref={box} tabIndex={-1} className={FOCUSED}>
      <Alert tone="good" title={title}>
        {children}
      </Alert>
    </div>
  );
}

/** A folder's own name, the last part of its path on any system: "…/My Drive/İplikçi Nedim" → "İplikçi Nedim". */
function folderName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
}

// --- off: where the folder can go --------------------------------------------------------------------------------

interface OffProps {
  state: SyncState;
  turnOn: TurnOn; // how the step goes
  onTurnOn: TurnOnStep; // the step itself
  turnedOff: boolean; // turned off from this card just now
}

/** The places the folder can go, a folder the user types, and what turning the sync on in the chosen one does. */
function SyncOff({ state, turnOn, onTurnOn, turnedOff }: OffProps) {
  const { t } = useTranslation("settings");
  const [chosen, setChosen] = useState<SyncPlace | null>(null);
  const opener = useRef<HTMLElement | null>(null); // the button that chose the place: the focus goes back to it
  useEffect(() => {
    if (chosen === null && opener.current) {
      opener.current.focus();
      opener.current = null;
    }
  }, [chosen]);
  const choose: Choose = (place, button) => {
    opener.current = button;
    turnOn.reset();
    setChosen(place);
  };
  return (
    <div className="flex flex-col gap-4">
      {turnedOff ? (
        <Told title={t("sync.turnedOff")}>
          <p>{t("sync.turnedOffText")}</p>
        </Told>
      ) : null}
      <p className="text-sm">{t("sync.about")}</p>
      {/* Hidden, not gone, while a place is confirmed: a typed folder and what it holds are there after Vazgeç. */}
      <div hidden={chosen !== null} className="flex flex-col gap-4">
        <Places state={state} onChoose={choose} />
        <OtherFolder state={state} onChoose={choose} />
      </div>
      {chosen ? (
        <Confirm place={chosen} state={state} turnOn={turnOn} onTurnOn={onTurnOn} onCancel={() => setChosen(null)} />
      ) : null}
    </div>
  );
}

/** The sync services' folders on this computer, Google Drive's first; how to get Google Drive when there are none. */
function Places({ state, onChoose }: { state: SyncState; onChoose: Choose }) {
  const { t } = useTranslation("settings");
  const places = useSyncPlaces();
  const heading = useId();
  const found = places.data;
  return (
    <section aria-labelledby={heading} className={PART}>
      <h3 id={heading} className={PART_TITLE}>
        {t("sync.placesTitle")}
      </h3>
      {places.isPending ? <Loading /> : null}
      {places.isError ? <Failure error={places.error} onRetry={() => void places.refetch()} /> : null}
      {found?.length === 0 ? <NoDrive /> : null}
      {found && found.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {found.map((place) => (
            <li key={place.folder}>
              <PlaceItem place={place} state={state} onChoose={onChoose} />
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

/** No sync service's folder here: Google Drive for desktop's own download page, opened in a new tab. Its name says so
 * after the visible words (WCAG's label in name), as EvdsLink's does. */
function NoDrive() {
  const { t } = useTranslation("settings");
  return (
    <div className="flex flex-col gap-1">
      <p>{t("sync.noPlaces")}</p>
      <a
        href={DRIVE_DOWNLOAD}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`${t("sync.download")} ${t("sync.newTab")}`}
        className={cn(LINK, "inline-flex min-h-11 items-center self-start")}
      >
        {t("sync.download")}
      </a>
      <p>{t("sync.orType")}</p>
    </div>
  );
}

/** A place as the user knows it: its service and account, "Google Drive (ad@example.com)", or a folder they typed. */
function placeName(place: SyncPlace, t: TFunction<"settings">): string {
  if (!place.service) {
    return t("sync.typed");
  }
  return place.account ? t("sync.placeAccount", { service: place.service, account: place.account }) : place.service;
}

/** What turning the sync on in a usable place does: join the data of the computers there, or begin with this one's. */
function happens(place: SyncPlace, state: SyncState, t: TFunction<"settings">): string {
  if (!place.exists) {
    return t("sync.begins");
  }
  // This computer, if it was in the set before, is no other computer: it goes on where it left off.
  const others = place.devices.filter((device) => !state.device || device.id !== state.device);
  if (others.length === 0) {
    return place.devices.length > 0 ? t("sync.rejoins") : t("sync.joinsSomeone");
  }
  return t("sync.joins", { names: NAMES.format([...new Set(others.map((device) => device.name))]) });
}

/** What follows once it is on: the data merged, or this computer's copied into the folder for its app to upload. */
function follows(place: SyncPlace, t: TFunction<"settings">): string {
  if (place.exists) {
    return t("sync.joinText");
  }
  return place.service ? t("sync.beginText", { service: place.service }) : t("sync.beginTextPlain");
}

interface PlaceProps {
  place: SyncPlace;
  state: SyncState;
  onChoose: Choose;
}

/** A place the folder can go: whose it is, where, and what turning the sync on there would do, or why it cannot. */
function PlaceItem({ place, state, onChoose }: PlaceProps) {
  const { t } = useTranslation("settings");
  const name = placeName(place, t);
  return (
    <div className={BOX}>
      <span className="font-medium">{name}</span>
      <code className={PATH}>{place.folder}</code>
      <p>{place.usable ? happens(place, state, t) : t("sync.unusable", { problem: place.problem })}</p>
      {place.usable && !place.service ? <p className={HINT}>{t("sync.unknownService")}</p> : null}
      {place.usable ? (
        <Button
          variant="secondary"
          className="self-start"
          aria-label={t("sync.useNamed", { place: name })}
          onClick={(event) => onChoose(place, event.currentTarget)}
        >
          {t("sync.use")}
        </Button>
      ) : null}
    </div>
  );
}

/** A folder the user types: the service says what turning the sync on there would do, as for the places it found. */
function OtherFolder({ state, onChoose }: { state: SyncState; onChoose: Choose }) {
  const { t } = useTranslation("settings");
  const inspect = useInspectSyncFolder();
  const [folder, setFolder] = useState("");
  const [problem, setProblem] = useState("");
  const id = useId();
  const said = problem || (inspect.isError ? inspect.error.message : "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const typed = folder.trim();
    if (!typed) {
      setProblem(t("sync.needFolder"));
      document.getElementById(id)?.focus();
      return;
    }
    inspect.mutate(typed);
  }

  return (
    <div className="flex flex-col gap-3">
      <form noValidate onSubmit={submit} className="flex flex-col gap-1 text-sm">
        <label htmlFor={id} className="font-medium">
          {t("sync.otherLabel")}
        </label>
        <div className="flex flex-wrap items-start gap-2">
          <input
            id={id}
            type="text"
            value={folder}
            maxLength={FOLDER_MAX}
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            aria-describedby={said ? `${id}-ipucu ${id}-hata` : `${id}-ipucu`}
            aria-invalid={said ? true : undefined}
            onChange={(event) => {
              setFolder(event.target.value);
              setProblem("");
              inspect.reset(); // what the service said was of the folder typed before
            }}
            className={cn(FIELD, "flex-1", said && INVALID)}
          />
          <Button type="submit" variant="secondary" disabled={inspect.isPending}>
            {inspect.isPending ? t("sync.inspecting") : t("sync.inspect")}
          </Button>
        </div>
        <p id={`${id}-ipucu`} className={HINT}>
          {t("sync.otherHint")}
        </p>
        {said ? (
          <p id={`${id}-hata`} className={ERROR}>
            {said}
          </p>
        ) : null}
      </form>
      <div aria-live="polite">
        {inspect.data ? <PlaceItem place={inspect.data} state={state} onChoose={onChoose} /> : null}
      </div>
    </div>
  );
}

interface ConfirmProps {
  place: SyncPlace;
  state: SyncState;
  turnOn: TurnOn;
  onTurnOn: TurnOnStep;
  onCancel: () => void;
}

/** What turning the sync on in the chosen place does, this computer's name as the others will show it, and the step. */
function Confirm({ place, state, turnOn, onTurnOn, onCancel }: ConfirmProps) {
  const { t } = useTranslation("settings");
  const [name, setName] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  const ids = { heading: useId(), name: useId(), hint: useId() };
  useEffect(() => {
    heading.current?.focus(); // the button that opened it is hidden now
  }, []);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // An empty field keeps the name its placeholder shows: sent empty, it would give up a name the user chose before.
    onTurnOn({ folder: place.folder, name: name.trim() || state.name });
  }

  return (
    <section
      aria-labelledby={ids.heading}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !turnOn.isPending) {
          onCancel();
        }
      }}
      className={cn(BOX, "gap-3 p-4")}
    >
      <h3 id={ids.heading} ref={heading} tabIndex={-1} className={cn(PART_TITLE, FOCUSED)}>
        {t("sync.confirmTitle")}
      </h3>
      <div className="flex flex-col gap-1">
        <span className="font-medium">{placeName(place, t)}</span>
        <code className={PATH}>{place.folder}</code>
      </div>
      <p>{happens(place, state, t)}</p>
      <p>{follows(place, t)}</p>
      <form noValidate onSubmit={submit} className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.name}>{t("sync.nameLabel")}</label>
          <input
            id={ids.name}
            type="text"
            value={name}
            placeholder={state.name}
            maxLength={NAME_MAX}
            autoComplete="off"
            aria-describedby={ids.hint}
            onChange={(event) => setName(event.target.value)}
            className={FIELD}
          />
          <p id={ids.hint} className={HINT}>
            {t("sync.nameHint", { name: state.name })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={turnOn.isPending}>
            {turnOn.isPending ? t("sync.turningOn") : t("sync.turnOn")}
          </Button>
          <Button variant="secondary" disabled={turnOn.isPending} onClick={onCancel}>
            {t("sync.cancel")}
          </Button>
        </div>
        {turnOn.isError ? (
          <Alert tone="critical" title={t("sync.refused")} live>
            <p>{turnOn.error.message}</p>
          </Alert>
        ) : null}
      </form>
    </section>
  );
}

// --- on: how it goes -----------------------------------------------------------------------------------------------

interface OnProps {
  state: SyncState;
  turnedOn: boolean; // turned on from this card just now
  turnOff: TurnOff;
  asked: Asked;
  onAsked: () => void;
}

/** Where the folder is and how the rounds go, the computers in the set, who sends the notifications, and the steps. */
function SyncOn({ state, turnedOn, turnOff, asked, onAsked }: OnProps) {
  const { t } = useTranslation("settings");
  const labels = useLabels().data ?? {};
  return (
    <div className="flex flex-col gap-4">
      {turnedOn ? (
        <Told title={t("sync.turnedOn")}>
          <p>{t("sync.turnedOnText")}</p>
        </Told>
      ) : null}
      <SyncFacts state={state} />
      {state.problem ? <Problem state={state} /> : null}
      <Computers state={state} labels={labels} />
      <Senders state={state} labels={labels} />
      <SyncSteps state={state} turnOff={turnOff} asked={asked} onAsked={onAsked} />
    </div>
  );
}

/** The folder, this computer's name (changed in place), the last round and the documents, with what still moves. The
 * detailed view adds the folder's path, the last round that did its work and this computer's id. */
function SyncFacts({ state }: { state: SyncState }) {
  const { t } = useTranslation("settings");
  const detailed = useView().view === "detailed";
  const rename = useRenameSyncComputer();
  const [renaming, setRenaming] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const formId = useId();
  const close = () => {
    setRenaming(false);
    toggle.current?.focus();
  };
  const path = <code className="break-all">{state.folder}</code>;
  const items: Array<[string, ReactNode]> = [
    [
      t("sync.folder"),
      state.service ? t("sync.folderValue", { name: folderName(state.folder), service: state.service }) : path,
    ],
    [
      t("sync.computer"),
      // The name on its label's line, the button under it: beside it, the button's height pushed the name down.
      <span className="flex flex-col items-start">
        <span>{state.name}</span>
        <Button
          ref={toggle}
          variant="quiet"
          className="-ml-2 px-2"
          aria-expanded={renaming}
          aria-controls={renaming ? formId : undefined}
          onClick={() => {
            rename.reset();
            setRenaming(!renaming);
          }}
        >
          {t("sync.rename")}
        </Button>
      </span>,
    ],
    [t("sync.last"), state.last_at ? formatTime(state.last_at) : t("sync.never")],
    [t("sync.documents"), <Documents state={state} />],
  ];
  if (detailed) {
    if (state.service) {
      items.push([t("sync.path"), path]);
    }
    items.push(
      [t("sync.lastOk"), state.ok_at ? formatTime(state.ok_at) : t("sync.neverOk")],
      [t("sync.deviceId"), <code className="break-all">{state.device}</code>],
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <Facts items={items} />
      {renaming ? <RenameForm id={formId} name={state.name} rename={rename} onDone={close} /> : null}
      <Said text={rename.isSuccess && !renaming ? t("sync.saved") : ""} />
    </div>
  );
}

/** A live region for what a step did: always on the page, so screen readers hear it change; taking no room empty. */
function Said({ text }: { text: string }) {
  return (
    <span aria-live="polite" className={text ? HINT : "sr-only"}>
      {text}
    </span>
  );
}

/** The documents in the shared data, and those whose originals still go one way or the other. */
function Documents({ state }: { state: SyncState }) {
  const { t } = useTranslation("settings");
  return (
    <span className="flex flex-col">
      <span>{t("sync.documentsValue", { count: state.documents })}</span>
      {state.waiting_down > 0 ? <span>{t("sync.down", { count: state.waiting_down })}</span> : null}
      {state.waiting_up > 0 ? <span>{t("sync.up", { count: state.waiting_up })}</span> : null}
    </span>
  );
}

interface RenameProps {
  id: string;
  name: string;
  rename: Rename;
  onDone: () => void; // saved or given up: the form closes
}

/** This computer's name as the others show it; an empty one gives the computer's own name back. */
function RenameForm({ id, name, rename, onDone }: RenameProps) {
  const { t } = useTranslation("settings");
  const [draft, setDraft] = useState(name);
  const input = useRef<HTMLInputElement>(null);
  const field = useId();
  useEffect(() => {
    input.current?.focus();
    input.current?.select();
  }, []);
  const refused = rename.isError ? rename.error.message : "";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    rename.mutate(draft.trim(), { onSuccess: onDone });
  }

  return (
    <form
      id={id}
      noValidate
      onSubmit={submit}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !rename.isPending) {
          event.preventDefault();
          onDone();
        }
      }}
      className={BOX}
    >
      <label htmlFor={field} className="font-medium">
        {t("sync.nameLabel")}
      </label>
      <input
        ref={input}
        id={field}
        type="text"
        value={draft}
        maxLength={NAME_MAX}
        autoComplete="off"
        aria-describedby={refused ? `${field}-ipucu ${field}-hata` : `${field}-ipucu`}
        aria-invalid={refused ? true : undefined}
        onChange={(event) => {
          setDraft(event.target.value);
          rename.reset();
        }}
        className={cn(FIELD, refused && INVALID)}
      />
      <p id={`${field}-ipucu`} className={HINT}>
        {t("sync.renameHint")}
      </p>
      {refused ? (
        <p id={`${field}-hata`} className={ERROR}>
          {refused}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={rename.isPending || draft.trim() === name}>
          {t("sync.save")}
        </Button>
        <Button variant="secondary" disabled={rename.isPending} onClick={onDone}>
          {t("sync.cancel")}
        </Button>
      </div>
    </form>
  );
}

/** Why the last round could not do its work, since when, and where to look. */
function Problem({ state }: { state: SyncState }) {
  const { t } = useTranslation("settings");
  return (
    <Alert tone="warning" title={t("sync.problemTitle")}>
      <div className="flex flex-col gap-1">
        <p>{state.problem}</p>
        {state.since ? <p>{t("sync.problemSince", { time: formatTime(state.since) })}</p> : null}
        <p>{state.service ? t("sync.problemHelp", { service: state.service }) : t("sync.problemHelpPlain")}</p>
      </div>
    </Alert>
  );
}

/** The computers in the set, this one first: what runs on each, when it was last seen, and whether it left. */
function Computers({ state, labels }: { state: SyncState; labels: Labels }) {
  const { t } = useTranslation("settings");
  const heading = useId();
  if (state.devices.length === 0) {
    return null;
  }
  return (
    <section aria-labelledby={heading} className={PART}>
      <h3 id={heading} className={PART_TITLE}>
        {t("sync.computers")}
      </h3>
      <ul className="flex flex-col divide-y divide-zinc-100 dark:divide-zinc-800">
        {state.devices.map((device) => (
          <li key={device.id} className="flex flex-col gap-0.5 py-2">
            <Computer device={device} labels={labels} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function Computer({ device, labels }: { device: SyncDevice; labels: Labels }) {
  const { t } = useTranslation("settings");
  const runs = [device.system, device.app ? t("sync.version", { app: device.app }) : ""].filter(Boolean).join(" · ");
  const channels = device.channels.map((channel) => labelOf(labels, "Channel", channel));
  return (
    <>
      <span className="font-medium">
        {device.name}
        {device.me ? <span className="font-normal"> {t("sync.me")}</span> : null}
      </span>
      {runs ? <span className={HINT}>{runs}</span> : null}
      {device.seen_at ? <span className={HINT}>{t("sync.seen", { time: formatTime(device.seen_at) })}</span> : null}
      {device.left ? (
        <span>
          <Badge tone="neutral">{t("sync.left")}</Badge>
        </span>
      ) : null}
      <Detailed>
        <span className={HINT}>
          {channels.length > 0 ? t("sync.canSend", { channels: channels.join(", ") }) : t("sync.cannotSend")}
        </span>
        <code className="text-xs break-all">{device.id}</code>
      </Detailed>
    </>
  );
}

/** Who sends a channel's notifications (channel: its name, "Telegram"): this computer, another one by its name, or the
 * one the next round chooses. */
function senderSaid(state: SyncState, channel: string, holder: string | undefined, t: TFunction<"settings">): string {
  if (holder === undefined) {
    return t("sync.sentByNone", { channel });
  }
  if (holder === state.device) {
    return t("sync.sentHere", { channel });
  }
  const device = state.devices.find((one) => one.id === holder);
  return t("sync.sentBy", { channel, name: device ? device.name : t("sync.someone") });
}

/** Which computer sends Telegram's and e-mail's notifications; this one takes over a channel it can send on. */
function Senders({ state, labels }: { state: SyncState; labels: Labels }) {
  const { t } = useTranslation("settings");
  const send = useSendFromHere();
  const heading = useId();
  const shown = CHANNELS.filter((channel) => state.senders[channel] !== undefined || state.ready.includes(channel));
  if (shown.length === 0) {
    return null;
  }
  // The channels just taken over that this computer still sends.
  const taken = send.isSuccess ? send.variables.filter((channel) => state.senders[channel] === state.device) : [];
  return (
    <section aria-labelledby={heading} className={PART}>
      <h3 id={heading} className={PART_TITLE}>
        {t("sync.sendersTitle")}
      </h3>
      <p className={HINT}>{t("sync.sendersAbout")}</p>
      <ul className="flex flex-col gap-2">
        {shown.map((channel) => {
          const name = labelOf(labels, "Channel", channel);
          const holder = state.senders[channel];
          return (
            <li key={channel} className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>{senderSaid(state, name, holder, t)}</span>
              {state.ready.includes(channel) && holder !== state.device ? (
                <Button
                  variant="secondary"
                  disabled={send.isPending}
                  aria-label={t("sync.claimNamed", { channel: name })}
                  onClick={() => send.mutate([channel])}
                >
                  {t("sync.claim")}
                </Button>
              ) : null}
            </li>
          );
        })}
      </ul>
      {taken.length > 0 ? (
        <Told
          title={t("sync.claimed", {
            channels: NAMES.format(taken.map((channel) => labelOf(labels, "Channel", channel))),
          })}
        />
      ) : null}
      {send.isError ? (
        <Alert tone="critical" title={t("sync.claimRefused")} live>
          <p>{send.error.message}</p>
        </Alert>
      ) : null}
    </section>
  );
}

function roundSaid(asked: Asked, state: SyncState, t: TFunction<"settings">): string {
  if (asked === "waiting") {
    return t("sync.roundWaiting");
  }
  if (asked === "ran") {
    return state.problem ? t("sync.roundProblem") : t("sync.roundDone");
  }
  return "";
}

interface StepsProps {
  state: SyncState;
  turnOff: TurnOff;
  asked: Asked;
  onAsked: () => void;
}

/** A round now, followed until it ran, and turning the sync off after saying what stays. */
function SyncSteps({ state, turnOff, asked, onAsked }: StepsProps) {
  const { t } = useTranslation("settings");
  const round = useSyncRound();
  const [asking, setAsking] = useState(false);
  return (
    <div className="flex flex-col gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-700">
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          disabled={round.isPending || asked === "waiting"}
          onClick={() => round.mutate(undefined, { onSuccess: onAsked })}
        >
          {asked === "waiting" ? t("sync.rounding") : t("sync.round")}
        </Button>
        <Button
          variant="secondary"
          disabled={turnOff.isPending}
          onClick={() => {
            turnOff.reset();
            setAsking(true);
          }}
        >
          {t("sync.turnOff")}
        </Button>
      </div>
      <Said text={roundSaid(asked, state, t)} />
      {round.isError ? (
        <Alert tone="critical" title={t("sync.roundFailed")} live>
          <p>{round.error.message}</p>
        </Alert>
      ) : null}
      {turnOff.isError ? (
        <Alert tone="critical" title={t("sync.turnOffFailed")} live>
          <p>{turnOff.error.message}</p>
        </Alert>
      ) : null}
      <ConfirmDialog
        open={asking}
        onOpenChange={setAsking}
        title={t("sync.turnOffTitle")}
        description={t("sync.turnOffText")}
        confirmLabel={t("sync.turnOff")}
        busy={turnOff.isPending}
        onConfirm={() => turnOff.mutate(undefined, { onSettled: () => setAsking(false) })}
      />
    </div>
  );
}
