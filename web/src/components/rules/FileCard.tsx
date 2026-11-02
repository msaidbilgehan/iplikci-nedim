// The user's rule file as it is (F15), for the detailed view: edited whole, previewed against the ledger and written
// only when the program can build the rules from it. The rules shipped with the app are not in it. The earlier
// versions are listed beside it, newest first.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../api/client";
import type { Labels, RuleChange } from "../../api/types";
import { Detailed } from "../Preferences";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { ChangePreview, MUTED, Notice, useNotice, useRuleEdit, useSavedText } from "./ChangePreview";
import { errorIdOf, HINT } from "./fields";

const LIMIT = 1_000_000; // the service's (WriteRulesIn)
// An example for an empty file: a group, a category under it and a merchant with its pattern.
const EXAMPLE = "Yeme & İçme:\n  Kafe & Kahve:\n    Örnek Kafe: [ORNEK KAFE]\n";

interface FileCardProps {
  content: string; // the user's rule file; "" before the first change
  labels: Labels;
}

export function FileCard({ content, labels }: FileCardProps) {
  const { t } = useTranslation("rules");
  const flow = useRuleEdit();
  const notice = useNotice();
  const savedText = useSavedText();
  const [draft, setDraft] = useState(content);
  const [base, setBase] = useState(content); // the file the draft started from
  const id = useId();
  const hintId = `${id}-ipucu`;
  // The program could not build the rules from the draft: the field is what is wrong, and the message says where.
  const refused = flow.preview.error instanceof ApiError && flow.preview.error.code === "rules_refused";

  // The file changed on the service (a change saved from another card or screen): an untouched draft follows it, an
  // edited one stays and says it is behind.
  if (content !== base && draft === base) {
    setBase(content);
    setDraft(content);
  }
  const behind = content !== base;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    notice.clear();
    flow.ask({ action: "write", content: draft });
  }

  function saved(change: RuleChange) {
    setDraft(change.content);
    setBase(change.content);
    notice.show(savedText(change));
  }

  return (
    <Detailed>
      <Card title={t("file.title")}>
        <div className="flex flex-col gap-3">
          <p className={MUTED}>{t("file.intro")}</p>
          <form noValidate onSubmit={submit} className="flex flex-col gap-2">
            <label htmlFor={id} className="text-sm">
              {t("file.label")}
            </label>
            <textarea
              id={id}
              value={draft}
              rows={16}
              maxLength={LIMIT}
              spellCheck={false}
              autoCapitalize="off"
              autoComplete="off"
              placeholder={EXAMPLE}
              aria-describedby={refused ? `${hintId} ${errorIdOf(id)}` : hintId}
              aria-invalid={refused ? true : undefined}
              onChange={(event) => {
                setDraft(event.target.value);
                flow.forget();
                notice.clear();
              }}
              className={[
                "w-full rounded-md border p-3 font-mono text-xs leading-5",
                "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
              ].join(" ")}
            />
            <p id={hintId} className={HINT}>
              {t("file.hint")}
            </p>
            {behind ? (
              <Alert tone="warning" title={t("file.changedMeanwhile")}>
                <Button
                  variant="secondary"
                  className="mt-2"
                  onClick={() => {
                    setDraft(content);
                    setBase(content);
                    flow.forget();
                  }}
                >
                  {t("file.reload")}
                </Button>
              </Alert>
            ) : null}
            <Button type="submit" variant="secondary" className="self-start" disabled={flow.preview.isPending}>
              {t("file.preview")}
            </Button>
          </form>
          <ChangePreview flow={flow} labels={labels} onSaved={saved} errorId={errorIdOf(id)} />
          <Notice notice={notice} />
        </div>
      </Card>
    </Detailed>
  );
}

const STAMP = /(\d{4})-(\d{2})-(\d{2}) (\d{2})\.(\d{2})\.(\d{2})/;

/** When a version was put aside, from its name ("personal 2026-11-02 10.00.00.yaml"); the name itself otherwise. */
export function versionTime(name: string): string {
  const found = STAMP.exec(name);
  return found ? `${found[3]}.${found[2]}.${found[1]} ${found[4]}:${found[5]}` : name;
}

interface HistoryCardProps {
  history: readonly string[]; // the rule file's earlier versions, newest first
  hasFile: boolean;
}

export function HistoryCard({ history, hasFile }: HistoryCardProps) {
  const { t } = useTranslation("rules");
  let sentence = t("history.say", { count: history.length });
  if (!hasFile) {
    sentence = t("history.noFile");
  } else if (history.length === 0) {
    sentence = t("history.none");
  }
  return (
    <Card title={t("history.title")}>
      <Say>{sentence}</Say>
      {history.length > 0 ? (
        <ol aria-label={t("history.list")} className="flex flex-col gap-1 text-sm">
          {history.map((name) => (
            <li key={name} className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span>{t("history.version", { when: versionTime(name) })}</span>
              <Detailed>
                <code className="text-xs break-all text-zinc-600 dark:text-zinc-300">{name}</code>
              </Detailed>
            </li>
          ))}
        </ol>
      ) : (
        <Detailed>
          <p className={MUTED}>{hasFile ? t("history.none") : t("history.noFile")}</p>
        </Detailed>
      )}
    </Card>
  );
}
