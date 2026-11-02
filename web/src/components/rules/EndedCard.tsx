// The payments the user knows ended (F15, `_biten`): a merchant and the month of its last payment, after which no
// payment of it is expected. One the user wrote is expected again from here; one shipped with the app stays. A new one
// is written under its merchant's name as the ledger has it: the service refuses a name no row has, naming the close
// ones.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import type { EndedPayment, Labels, RuleChange } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { ChangePanel, ChangePreview, MUTED, Notice, useNotice, useRuleEdit, useSavedText } from "./ChangePreview";
import { control, type Errors, Field, focusFirst } from "./fields";

// The Abonelikler screen as a whole: a series' link with no series named.
const SUBSCRIPTIONS = { screen: "subscription", id: "", query: {} } as const;
const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

interface EndedCardProps {
  ended: readonly EndedPayment[];
  labels: Labels;
}

export function EndedCard({ ended, labels }: EndedCardProps) {
  const { t } = useTranslation("rules");
  const flow = useRuleEdit();
  const notice = useNotice();
  const savedText = useSavedText();
  const [asked, setAsked] = useState<string | null>(null);

  function expectAgain(merchant: string) {
    notice.clear();
    flow.ask({ action: "not_ended", merchant });
    setAsked(merchant);
  }

  function close() {
    setAsked(null);
    flow.forget();
  }

  function saved(change: RuleChange) {
    close();
    notice.show(savedText(change));
  }

  const again = (payment: EndedPayment) =>
    payment.own ? (
      <Button
        variant="secondary"
        className="px-3"
        aria-label={`${t("ended.expectAgain")}: ${payment.merchant}`}
        onClick={() => expectAgain(payment.merchant)}
      >
        {t("ended.expectAgain")}
      </Button>
    ) : null;

  return (
    <Card title={t("ended.title")}>
      <Say next={{ link: SUBSCRIPTIONS, label: t("ended.next") }}>
        {ended.length > 0 ? t("ended.say", { count: ended.length }) : t("ended.sayNone")}
      </Say>
      <div className="flex flex-col gap-4">
        {ended.length === 0 ? (
          <Detailed>
            <p className={MUTED}>{t("ended.empty")}</p>
          </Detailed>
        ) : null}
        {ended.length > 0 ? (
          <>
            <Simple>
              <ul className="flex flex-col">
                {ended.map((payment) => (
                  <li
                    key={payment.merchant}
                    className={cn(
                      "flex flex-wrap items-center justify-between gap-2 py-1.5 text-sm",
                      "border-b border-zinc-100 last:border-b-0 dark:border-zinc-800",
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block font-medium break-words">{payment.merchant}</span>
                      <span className="block text-xs text-zinc-600 dark:text-zinc-300">
                        {t("ended.last", { month: payment.month })}
                        {payment.own ? null : ` · ${t("ended.shipped")}`}
                      </span>
                    </span>
                    {again(payment)}
                  </li>
                ))}
              </ul>
            </Simple>
            <Detailed>
              <Table>
                <caption className="sr-only">{t("ended.caption")}</caption>
                <thead>
                  <tr>
                    <Th>{t("ended.merchant")}</Th>
                    <Th>{t("ended.month")}</Th>
                    <Th>{t("ended.source")}</Th>
                    <Th>
                      <span className="sr-only">{t("ended.action")}</span>
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {ended.map((payment) => (
                    <tr key={payment.merchant}>
                      <Td className="break-words">{payment.merchant}</Td>
                      <Td className="whitespace-nowrap">{formatMonth(payment.month)}</Td>
                      <Td>{labelOf(labels, "RuleLayer", payment.own ? "own" : "shipped")}</Td>
                      <Td className="text-right">{again(payment)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Detailed>
          </>
        ) : null}
        <Notice notice={notice} />
        <EndedForm labels={labels} onSaved={(change) => notice.show(savedText(change))} onEdit={notice.clear} />
      </div>
      <ChangePanel
        open={asked !== null}
        title={t("panel.notEnded", { merchant: asked ?? "" })}
        text={t("panel.notEndedText")}
        flow={flow}
        labels={labels}
        onSaved={saved}
        onClose={close}
      />
    </Card>
  );
}

type EndedField = "merchant" | "month";
const ORDER: readonly EndedField[] = ["merchant", "month"];

interface EndedFormProps {
  labels: Labels;
  onSaved: (change: RuleChange) => void;
  onEdit: () => void; // a field changed: what was saved before is no longer the news
}

function EndedForm({ labels, onSaved, onEdit }: EndedFormProps) {
  const { t } = useTranslation("rules");
  const flow = useRuleEdit();
  const [merchant, setMerchant] = useState("");
  const [month, setMonth] = useState("");
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<Errors<EndedField>>({});
  const heading = useId();
  const ids: Record<EndedField | "note", string> = { merchant: useId(), month: useId(), note: useId() };

  function changed(field: EndedField | "note") {
    if (field !== "note" && errors[field]) {
      setErrors({ ...errors, [field]: undefined });
    }
    flow.forget();
    onEdit();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found: Errors<EndedField> = {};
    if (!merchant.trim()) {
      found.merchant = t("ended.needMerchant");
    }
    if (!month) {
      found.month = t("ended.needMonth");
    } else if (!MONTH.test(month)) {
      found.month = t("ended.badMonth");
    }
    setErrors(found);
    if (Object.keys(found).length > 0) {
      focusFirst(ORDER, found, ids);
      return;
    }
    flow.ask({ action: "ended", merchant: merchant.trim(), month, note: note.trim() });
  }

  function saved(change: RuleChange) {
    setMerchant("");
    setMonth("");
    setNote("");
    onSaved(change);
  }

  return (
    <div className="flex flex-col gap-3 border-t border-zinc-200 pt-4 dark:border-zinc-700">
      <form noValidate onSubmit={submit} aria-labelledby={heading} className="flex flex-col gap-3">
        <h3 id={heading} className="text-sm font-semibold">
          {t("ended.add")}
        </h3>
        <p className={MUTED}>{t("ended.addText")}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id={ids.merchant} label={t("ended.merchant")} error={errors.merchant}>
            <input
              type="text"
              value={merchant}
              maxLength={120}
              autoComplete="off"
              onChange={(event) => {
                setMerchant(event.target.value);
                changed("merchant");
              }}
              {...control(ids.merchant, { error: errors.merchant })}
            />
          </Field>
          <Field id={ids.month} label={t("ended.month")} hint={t("ended.monthHint")} error={errors.month}>
            {/* A browser without a month picker shows a text box: the hint and the check say how to write it. */}
            <input
              type="month"
              value={month}
              placeholder="2026-10"
              onChange={(event) => {
                setMonth(event.target.value);
                changed("month");
              }}
              {...control(ids.month, { hint: true, error: errors.month })}
            />
          </Field>
        </div>
        <Field id={ids.note} label={t("ended.note")}>
          <input
            type="text"
            value={note}
            maxLength={200}
            autoComplete="off"
            onChange={(event) => {
              setNote(event.target.value);
              changed("note");
            }}
            {...control(ids.note, {})}
          />
        </Field>
        <Button type="submit" variant="secondary" className="self-start" disabled={flow.preview.isPending}>
          {t("ended.preview")}
        </Button>
      </form>
      <ChangePreview flow={flow} labels={labels} onSaved={saved} />
    </div>
  );
}
