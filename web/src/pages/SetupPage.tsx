// The setup wizard (F17): nine steps from the data folder to remote access, each with where it stands (the service's
// note) and what it asks. The step is in the address (?adim=), so the back button goes back a step; the list beside
// it shows every step's state and leads to any of them. Opened without a step, the wizard starts at the first required
// one still to do; with none left it shows where the setup stands (?adim=ozet), as "Bitir" on the last step does:
// done, or which steps wait, and the optional ones not used. Until v0.10.1 "Bitir" only went to the Pano and the
// wizard opened again at its last, optional step, as if nothing had been finished. An optional step can be skipped; a
// required one can be left for later, saying what it holds up. Every step can be come back to here or on the Settings
// screen. The first run opens here (useFirstRun).

import { type RefObject, useEffect, useId, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { useLabels, useSettings, useSetup } from "../api/queries";
import type { Labels, Settings, Setup, SetupStepState } from "../api/types";
import { Failure, Loading } from "../components/QueryState";
import { StepContent } from "../components/setup/StepContent";
import { Badge, type Tone } from "../components/ui/Badge";
import { Button, buttonClass } from "../components/ui/Button";
import { CheckIcon } from "../components/ui/Icons";
import { LinkButton } from "../components/ui/LinkButton";
import { PageHeader } from "../components/ui/PageHeader";
import { cn } from "../lib/cn";
import { labelOf } from "../lib/labels";

export default function SetupPage() {
  const { t } = useTranslation("setup");
  const setup = useSetup();
  const settings = useSettings();
  const labels = useLabels().data ?? {};
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      {setup.isPending || settings.isPending ? <Loading /> : null}
      {setup.isError ? <Failure error={setup.error} onRetry={() => void setup.refetch()} /> : null}
      {settings.isError ? <Failure error={settings.error} onRetry={() => void settings.refetch()} /> : null}
      {setup.data && settings.data ? <Wizard setup={setup.data} settings={settings.data} labels={labels} /> : null}
    </div>
  );
}

// The steps that say where they stand themselves, more fully than the service's note: the data folder's path, and the
// e-mail's way with its masked address and a refused login's reason.
const OWN_STATE: ReadonlySet<string> = new Set(["data_folder", "mail"]);

const PANEL = cn(
  "flex min-w-0 flex-col gap-4 rounded-lg border p-4 shadow-sm",
  "border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900",
);
const HEADING = cn(
  "rounded text-lg font-semibold",
  "focus:outline-none focus-visible:outline-2 focus-visible:outline-teal-600",
);
const CURRENT = cn(
  "border-teal-700 bg-teal-50 font-medium text-teal-900",
  "dark:border-teal-400 dark:bg-teal-950 dark:text-teal-100",
);
const OTHER = "border-transparent text-zinc-800 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-800";
const DONE = cn(
  "border-emerald-700 bg-emerald-700 text-white",
  "dark:border-emerald-400 dark:bg-emerald-400 dark:text-zinc-950",
);

const SUMMARY = "ozet"; // ?adim=ozet: where the setup stands, as "Bitir" leaves it

/** The required steps still to do, in their order. */
function requiredLeft(steps: readonly SetupStepState[]): SetupStepState[] {
  return steps.filter((step) => !step.done && !step.optional);
}

function stateOf(step: SetupStepState): { tone: Tone; key: "done" | "optional" | "todo" } {
  if (step.done) {
    return { tone: "good", key: "done" };
  }
  return step.optional ? { tone: "neutral", key: "optional" } : { tone: "warning", key: "todo" };
}

interface WizardProps {
  setup: Setup;
  settings: Settings;
  labels: Labels;
}

function Wizard({ setup, settings, labels }: WizardProps) {
  const { t } = useTranslation("setup");
  const [params, setParams] = useSearchParams();
  const steps = setup.steps;
  const asked = steps.findIndex((step) => step.step === params.get("adim"));
  const left = requiredLeft(steps);
  // Without a step: the first required one to do, else where the setup stands.
  const isSummary = params.get("adim") === SUMMARY || (asked < 0 && left.length === 0);
  const firstLeft = steps.findIndex((step) => !step.done && !step.optional);
  const index = asked >= 0 ? asked : isSummary ? -1 : firstLeft;
  const current = steps[index];
  const heading = useRef<HTMLHeadingElement>(null);
  const headingId = useId();
  const shown = useRef(isSummary ? SUMMARY : current?.step);

  // A step chosen, or the summary, moves the focus to its heading, as a new page would; the first one shown leaves it
  // where it is.
  const showing = isSummary ? SUMMARY : current?.step;
  useEffect(() => {
    if (showing && shown.current !== showing) {
      shown.current = showing;
      heading.current?.focus();
    }
  }, [showing]);

  if (steps.length === 0) {
    return null; // a service with no steps: nothing to set up
  }
  if (isSummary || !current) {
    return (
      <div className="grid items-start gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <StepList steps={steps} current={-1} labels={labels} isSummary />
        <Summary steps={steps} labels={labels} headingRef={heading} />
      </div>
    );
  }
  const go = (to: number) => {
    const next = steps[to];
    if (next) {
      setParams({ adim: next.step });
    }
  };
  const last = index === steps.length - 1;
  const state = stateOf(current);
  let forward = t("next");
  if (last) {
    forward = t("finish");
  } else if (!current.done) {
    forward = current.optional ? t("skip") : t("later");
  }
  const label = labelOf(labels, "SetupStep", current.step);

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <StepList steps={steps} current={index} labels={labels} />
      <section aria-labelledby={headingId} className={PANEL}>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h2 ref={heading} id={headingId} tabIndex={-1} className={HEADING}>
            {t("stepOf", { number: index + 1, total: steps.length, step: label })}
          </h2>
          <Badge tone={state.tone}>{t(`status.${state.key}`)}</Badge>
        </div>
        {current.note && !OWN_STATE.has(current.step) ? <p className="text-sm font-medium">{current.note}</p> : null}
        <StepContent step={current.step} done={current.done} settings={settings} />
        <div className="flex flex-col gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-700">
          {!current.done && !current.optional && !last ? (
            <p className="text-sm text-zinc-700 dark:text-zinc-300">{t("laterHint")}</p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {index > 0 ? (
              <Button variant="secondary" onClick={() => go(index - 1)}>
                {t("back")}
              </Button>
            ) : null}
            <Button
              variant={current.done || last ? "primary" : "secondary"}
              onClick={() => (last ? setParams({ adim: SUMMARY }) : go(index + 1))}
            >
              {forward}
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

interface StepListProps {
  steps: readonly SetupStepState[];
  current: number; // -1 while the summary is shown
  labels: Labels;
  isSummary?: boolean;
}

/** Every step with its state, the one shown marked; each leads to its step, and the summary under them. */
function StepList({ steps, current, labels, isSummary = false }: StepListProps) {
  const { t } = useTranslation("setup");
  return (
    <nav aria-label={t("steps")} className="flex flex-col gap-2">
      <ol className="flex flex-col gap-1">
        {steps.map((step, index) => {
          const state = stateOf(step);
          return (
            <li key={step.step}>
              <Link
                to={{ search: `?${new URLSearchParams({ adim: step.step }).toString()}` }}
                aria-current={index === current ? "step" : undefined}
                className={cn(
                  "flex min-h-11 items-center gap-3 rounded-md border-l-[3px] px-3 text-sm",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
                  index === current ? CURRENT : OTHER,
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "inline-flex size-6 shrink-0 items-center justify-center rounded-full border text-xs",
                    step.done ? DONE : "border-zinc-400 dark:border-zinc-500",
                  )}
                >
                  {step.done ? <CheckIcon className="size-3.5" /> : index + 1}
                </span>
                <span className="flex min-w-0 flex-col">
                  <span>{labelOf(labels, "SetupStep", step.step)}</span>
                  <span className="text-xs text-zinc-600 dark:text-zinc-300">{t(`status.${state.key}`)}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
      <Link
        to={{ search: `?${new URLSearchParams({ adim: SUMMARY }).toString()}` }}
        aria-current={isSummary ? "page" : undefined}
        className={cn(
          "flex min-h-11 items-center gap-3 rounded-md border-l-[3px] px-3 text-sm",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
          isSummary ? CURRENT : OTHER,
        )}
      >
        {t("summary.link")}
      </Link>
    </nav>
  );
}

interface SummaryProps {
  steps: readonly SetupStepState[];
  labels: Labels;
  headingRef: RefObject<HTMLHeadingElement | null>;
}

/**
 * Where the setup stands once it is walked through: done, or the required steps that wait, each leading to itself;
 * the optional steps not used, with what they would give; the way to the Pano and to the Settings screen.
 */
function Summary({ steps, labels, headingRef }: SummaryProps) {
  const { t } = useTranslation("setup");
  const headingId = useId();
  const left = requiredLeft(steps);
  const unused = steps.filter((step) => !step.done && step.optional);
  const done = steps.filter((step) => step.done).length;
  const item = (step: SetupStepState) => (
    <li key={step.step} className="flex flex-col gap-0.5">
      <Link
        to={{ search: `?${new URLSearchParams({ adim: step.step }).toString()}` }}
        className="font-medium text-teal-800 underline underline-offset-2 hover:no-underline dark:text-teal-300"
      >
        {labelOf(labels, "SetupStep", step.step)}
      </Link>
      <span className="text-zinc-700 dark:text-zinc-300">{step.note}</span>
    </li>
  );
  return (
    <section aria-labelledby={headingId} className={PANEL}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 ref={headingRef} id={headingId} tabIndex={-1} className={HEADING}>
          {left.length === 0 ? t("summary.title") : t("summary.titleLeft", { count: left.length })}
        </h2>
        <Badge tone={left.length === 0 ? "good" : "warning"}>
          {t("summary.count", { done, total: steps.length })}
        </Badge>
      </div>
      <p className="text-sm">{left.length === 0 ? t("summary.text") : t("summary.textLeft")}</p>
      {left.length > 0 ? (
        <div className="flex flex-col gap-1 text-sm">
          <h3 className="font-semibold">{t("summary.left")}</h3>
          <ul className="flex flex-col gap-2">{left.map(item)}</ul>
        </div>
      ) : null}
      {unused.length > 0 ? (
        <div className="flex flex-col gap-1 text-sm">
          <h3 className="font-semibold">{t("summary.unused")}</h3>
          <ul className="flex flex-col gap-2">{unused.map(item)}</ul>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-700">
        <Link to="/" className={buttonClass("primary")}>
          {t("summary.dashboard")}
        </Link>
        <LinkButton to="/ayarlar">{t("summary.settings")}</LinkButton>
      </div>
    </section>
  );
}
