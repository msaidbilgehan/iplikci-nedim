// Adding documents by hand (F02): the files go up into a batch the service keeps aside, the plan shows what would
// happen to each, and only the plan the user confirms is applied. A file that changed since the plan makes the
// service refuse; the plan is then made again and shown.

import { useQueryClient } from "@tanstack/react-query";
import { type DragEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api } from "../api/client";
import { keys } from "../api/queries";
import type { Applied, Plan, Uploaded } from "../api/types";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { UploadIcon } from "../components/ui/Icons";
import { Table, Td, Th } from "../components/ui/Table";
import { cn } from "../lib/cn";
import { formatPeriod } from "../lib/format";

const ACCEPTED = ".pdf,.xls,.xlsx,.html,.htm,.zip,.mbox,.eml";

type Step =
  | { kind: "idle" }
  | { kind: "uploading"; done: number; total: number }
  | { kind: "planned"; batch: string; plan: Plan; refused: Uploaded[]; renewed: boolean }
  | { kind: "applying"; batch: string; plan: Plan; refused: Uploaded[] }
  | { kind: "applied"; applied: Applied; refused: Uploaded[] }
  | { kind: "failed"; message: string };

export function UploadPanel() {
  const { t } = useTranslation("documents");
  const { t: tc } = useTranslation();
  const [step, setStep] = useState<Step>({ kind: "idle" });
  const [over, setOver] = useState(false);
  const files = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement>(null);
  const client = useQueryClient();
  const messageOf = (error: unknown) => (error instanceof Error ? error.message : tc("unexpected"));

  async function send(chosen: File[]) {
    if (chosen.length === 0) {
      return;
    }
    try {
      setStep({ kind: "uploading", done: 0, total: chosen.length });
      const { batch, refused } = await uploadAll(chosen, (done) =>
        setStep({ kind: "uploading", done, total: chosen.length }),
      );
      const plan = await api.post<Plan>("/api/inbox/plan", { upload: batch });
      setStep({ kind: "planned", batch, plan, refused, renewed: false });
    } catch (error) {
      setStep({ kind: "failed", message: messageOf(error) });
    }
  }

  async function apply(batch: string, plan: Plan, refused: Uploaded[]) {
    setStep({ kind: "applying", batch, plan, refused });
    try {
      const applied = await api.post<Applied>("/api/inbox/apply", { plan_id: plan.plan_id });
      setStep({ kind: "applied", applied, refused });
      void client.invalidateQueries({ queryKey: keys.allDocuments });
      void client.invalidateQueries({ queryKey: keys.system });
    } catch (error) {
      if (error instanceof ApiError && error.code === "plan_stale") {
        try {
          const again = await api.post<Plan>("/api/inbox/plan", { upload: batch });
          setStep({ kind: "planned", batch, plan: again, refused, renewed: true });
        } catch (renewing) {
          setStep({ kind: "failed", message: messageOf(renewing) });
        }
        return;
      }
      setStep({ kind: "failed", message: messageOf(error) });
    }
  }

  function dropped(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setOver(false);
    void send(Array.from(event.dataTransfer.files));
  }

  const busy = step.kind === "uploading" || step.kind === "applying";
  return (
    <Card title={t("upload.title")}>
      <div className="flex flex-col gap-3">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={dropped}
          className={cn(
            "flex flex-col items-center gap-3 rounded-md border-2 border-dashed p-6 text-center",
            over ? "border-teal-600 bg-teal-50 dark:bg-teal-950" : "border-zinc-300 dark:border-zinc-600",
          )}
        >
          <UploadIcon className="size-6 text-zinc-500" />
          <p className="text-sm">{t("upload.text")}</p>
          <div className="flex flex-wrap justify-center gap-2">
            <Button variant="secondary" onClick={() => files.current?.click()} disabled={busy}>
              {t("upload.files")}
            </Button>
            <Button variant="secondary" onClick={() => folder.current?.click()} disabled={busy}>
              {t("upload.folder")}
            </Button>
          </div>
          <input
            ref={files}
            type="file"
            multiple
            accept={ACCEPTED}
            className="hidden"
            aria-label={t("upload.files")}
            onChange={(e) => void send(Array.from(e.target.files ?? []))}
          />
          <input
            ref={folder}
            type="file"
            multiple
            // A whole folder: the browser hands over every file in it with its path.
            {...{ webkitdirectory: "" }}
            className="hidden"
            aria-label={t("upload.folder")}
            onChange={(e) => void send(Array.from(e.target.files ?? []))}
          />
        </div>
        <StepView step={step} onApply={apply} onReset={() => setStep({ kind: "idle" })} />
      </div>
    </Card>
  );
}

function StepView({
  step,
  onApply,
  onReset,
}: {
  step: Step;
  onApply: (batch: string, plan: Plan, refused: Uploaded[]) => Promise<void>;
  onReset: () => void;
}) {
  const { t } = useTranslation("documents");
  switch (step.kind) {
    case "idle":
      return null;
    case "uploading":
      return (
        <p role="status" className="text-sm">
          {t("upload.uploading", { done: step.done, total: step.total })}
        </p>
      );
    case "failed":
      return (
        <Alert tone="critical" title={t("upload.failed")} live>
          <p>{step.message}</p>
          <Button variant="secondary" className="mt-2" onClick={onReset}>
            {t("upload.restart")}
          </Button>
        </Alert>
      );
    case "applied":
      return (
        <div className="flex flex-col gap-2">
          <Alert tone="good" title={t("upload.applied", { count: step.applied.stored })} live>
            {step.applied.trash ? <p>{t("upload.trash")}</p> : null}
          </Alert>
          <Refused refused={step.refused} />
          <Button variant="secondary" className="self-start" onClick={onReset}>
            {t("upload.another")}
          </Button>
        </div>
      );
    case "planned":
    case "applying":
      return (
        <PlanView
          plan={step.plan}
          refused={step.refused}
          renewed={step.kind === "planned" && step.renewed}
          applying={step.kind === "applying"}
          onApply={() => onApply(step.batch, step.plan, step.refused)}
          onReset={onReset}
        />
      );
  }
}

interface PlanViewProps {
  plan: Plan;
  refused: Uploaded[];
  renewed: boolean;
  applying: boolean;
  onApply: () => Promise<void>;
  onReset: () => void;
}

function PlanView({ plan, refused, renewed, applying, onApply, onReset }: PlanViewProps) {
  const { t } = useTranslation("documents");
  const actions = Object.entries(plan.by_action)
    .map(([label, count]) => t("upload.planAction", { label, count }))
    .join(" · ");
  return (
    <div className="flex flex-col gap-3">
      {renewed ? (
        <Alert tone="warning" title={t("upload.renewed")} live>
          <p>{t("upload.renewedText")}</p>
        </Alert>
      ) : null}
      <Refused refused={refused} />
      {plan.changes === 0 ? (
        <Alert tone="neutral" title={t("upload.nothing")} />
      ) : (
        <>
          <p className="text-sm font-medium">{t("upload.plan", { actions })}</p>
          <Table>
            <caption className="sr-only">{t("upload.caption")}</caption>
            <thead>
              <tr>
                <Th>{t("upload.file")}</Th>
                <Th>{t("upload.action")}</Th>
                <Th>{t("upload.document")}</Th>
              </tr>
            </thead>
            <tbody>
              {plan.items.map((item) => (
                <tr key={`${item.source}/${item.name}`}>
                  <Td>{item.target && item.target !== item.name ? `${item.name} → ${item.target}` : item.name}</Td>
                  <Td>
                    {item.label}
                    {item.reason ? <span className="block text-xs">{item.reason}</span> : null}
                  </Td>
                  <Td>
                    {item.document
                      ? `${item.document.account} · ${formatPeriod(item.document.start ?? "", item.document.end)}`
                      : "—"}
                    {item.document?.check ? <span className="block text-xs">{item.document.check}</span> : null}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      )}
      <div className="flex flex-wrap gap-2">
        {plan.changes > 0 ? (
          <Button onClick={() => void onApply()} disabled={applying}>
            {applying ? t("upload.applying") : t("upload.apply")}
          </Button>
        ) : null}
        <Button variant="secondary" onClick={onReset} disabled={applying}>
          {t("upload.cancel")}
        </Button>
      </div>
    </div>
  );
}

function Refused({ refused }: { refused: Uploaded[] }) {
  const { t } = useTranslation("documents");
  if (refused.length === 0) {
    return null;
  }
  return (
    <Alert tone="warning" title={t("upload.refused", { count: refused.length })}>
      <ul>
        {refused.map((r) => (
          <li key={r.name}>{t("upload.refusedItem", { name: r.name, reason: r.reason })}</li>
        ))}
      </ul>
    </Alert>
  );
}

async function uploadAll(
  chosen: File[],
  progress: (done: number) => void,
): Promise<{ batch: string; refused: Uploaded[] }> {
  let batch = "";
  const refused: Uploaded[] = [];
  for (const [i, file] of chosen.entries()) {
    const name = file.webkitRelativePath || file.name;
    const where = batch ? `/api/uploads?batch=${encodeURIComponent(batch)}` : "/api/uploads";
    const result = await api.send<Uploaded>(where, file, {
      "Content-Type": "application/octet-stream",
      "X-Filename": encodeURIComponent(name),
    });
    batch = result.batch;
    if (result.status === "reddedildi") {
      refused.push(result);
    }
    progress(i + 1);
  }
  return { batch, refused };
}
