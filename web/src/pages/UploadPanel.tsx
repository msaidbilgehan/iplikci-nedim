// Adding documents by hand (F02): the files go up into a batch the service keeps aside, the plan shows what would
// happen to each, and only the plan the user confirms is applied. A file that changed since the plan makes the
// service refuse; the plan is then made again and shown.

import { useQueryClient } from "@tanstack/react-query";
import { type DragEvent, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import { keys } from "../api/queries";
import type { Applied, Plan, Uploaded } from "../api/types";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { UploadIcon } from "../components/ui/Icons";
import { Table, Td, Th } from "../components/ui/Table";
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
  const [step, setStep] = useState<Step>({ kind: "idle" });
  const [over, setOver] = useState(false);
  const files = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement>(null);
  const client = useQueryClient();

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
    <Card title="Belge ekle">
      <div className="flex flex-col gap-3">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={dropped}
          className={`flex flex-col items-center gap-3 rounded-md border-2 border-dashed p-6 text-center ${
            over ? "border-teal-600 bg-teal-50 dark:bg-teal-950" : "border-zinc-300 dark:border-zinc-600"
          }`}
        >
          <UploadIcon className="size-6 text-zinc-500" />
          <p className="text-sm">
            Banka belgelerini buraya bırakın ya da seçin: PDF, Excel, HTML, ZIP, MBOX ve EML. Önce ne olacağı
            gösterilir; onaylamadan hiçbir şey arşive girmez.
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            <Button variant="secondary" onClick={() => files.current?.click()} disabled={busy}>
              Dosya seç
            </Button>
            <Button variant="secondary" onClick={() => folder.current?.click()} disabled={busy}>
              Klasör seç
            </Button>
          </div>
          <input
            ref={files}
            type="file"
            multiple
            accept={ACCEPTED}
            className="hidden"
            aria-label="Dosya seç"
            onChange={(e) => void send(Array.from(e.target.files ?? []))}
          />
          <input
            ref={folder}
            type="file"
            multiple
            // A whole folder: the browser hands over every file in it with its path.
            {...{ webkitdirectory: "" }}
            className="hidden"
            aria-label="Klasör seç"
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
  switch (step.kind) {
    case "idle":
      return null;
    case "uploading":
      return (
        <p role="status" className="text-sm">
          Dosyalar yükleniyor: {step.done}/{step.total}
        </p>
      );
    case "failed":
      return (
        <Alert tone="critical" title="Belgeler eklenemedi" live>
          <p>{step.message}</p>
          <Button variant="secondary" className="mt-2" onClick={onReset}>
            Yeniden başla
          </Button>
        </Alert>
      );
    case "applied":
      return (
        <div className="flex flex-col gap-2">
          <Alert tone="good" title={`${step.applied.stored} belge arşive alındı`} live>
            {step.applied.trash ? <p>Çöp kutusuna taşınanlar geri alınabilir.</p> : null}
          </Alert>
          <Refused refused={step.refused} />
          <Button variant="secondary" className="self-start" onClick={onReset}>
            Başka belge ekle
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
  return (
    <div className="flex flex-col gap-3">
      {renewed ? (
        <Alert tone="warning" title="Plan yenilendi" live>
          <p>Planı gösterdikten sonra bir dosya değişti; yeni plan aşağıda. Uygun görürseniz yeniden onaylayın.</p>
        </Alert>
      ) : null}
      <Refused refused={refused} />
      {plan.changes === 0 ? (
        <Alert tone="neutral" title="Alınacak belge yok" />
      ) : (
        <>
          <p className="text-sm font-medium">
            Plan: {Object.entries(plan.by_action).map(([label, n]) => `${label}: ${n}`).join(" · ")}
          </p>
          <Table>
            <caption className="sr-only">Her dosyaya ne olacağı</caption>
            <thead>
              <tr>
                <Th>Dosya</Th>
                <Th>Ne olacak</Th>
                <Th>Belge</Th>
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
            {applying ? "Uygulanıyor…" : "Planı uygula"}
          </Button>
        ) : null}
        <Button variant="secondary" onClick={onReset} disabled={applying}>
          Vazgeç
        </Button>
      </div>
    </div>
  );
}

function Refused({ refused }: { refused: Uploaded[] }) {
  if (refused.length === 0) {
    return null;
  }
  return (
    <Alert tone="warning" title={`${refused.length} dosya alınmadı`}>
      <ul>
        {refused.map((r) => (
          <li key={r.name}>
            {r.name}: {r.reason}
          </li>
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

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Beklenmeyen bir hata oldu.";
}
