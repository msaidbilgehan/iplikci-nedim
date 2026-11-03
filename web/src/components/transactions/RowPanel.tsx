// One row's detail (F04), in a panel over the list: what the row is, why it is what it is (the rule and its file, the
// necessity's source, how a transfer was resolved and its pair, the rate, the receipts and notices about it, the bill
// it paid), where it is printed with the row marked, and the corrections it may carry. ?satir=<fingerprint> opens it;
// a part of a split row opens its row, with every part.

import type { TFunction } from "i18next";
import { type ReactNode, useId } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useLabels, useTransaction } from "../../api/queries";
import type { Labels, Row, TransactionDetail } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney, formatRate } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { rateOrigin } from "../../lib/rateOrigin";
import { RowPreview } from "../documents/RowPreview";
import { useView } from "../Preferences";
import { Failure, Loading } from "../QueryState";
import { Facts } from "../ui/Card";
import { Money } from "../ui/Money";
import { Say, ScreenLink } from "../ui/Say";
import { SidePanel } from "../ui/SidePanel";
import { Table, Td, Th } from "../ui/Table";
import { Corrections, ownOf } from "./Corrections";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";

interface RowPanelProps {
  fingerprint: string; // "" while no row is open
  onClose: () => void;
  rowHref: (fingerprint: string) => string; // the address with another row open: the pair's
}

export function RowPanel({ fingerprint, onClose, rowHref }: RowPanelProps) {
  const { t } = useTranslation("transactions");
  const detail = useTransaction(fingerprint);
  const found = detail.data;
  return (
    <SidePanel
      open={fingerprint !== ""}
      onClose={onClose}
      title={found ? found.row.title : detail.isError ? t("row.title") : t("row.loading")}
      description={found ? <Summary row={found.row} /> : undefined}
    >
      {detail.isPending ? <Loading label={t("row.loading")} /> : null}
      {detail.isError ? <Failure error={detail.error} onRetry={() => void detail.refetch()} /> : null}
      {/* Keyed by the row: another row's detail starts with its own corrections, not this one's typing. */}
      {found ? <Body key={found.row.fingerprint} found={found} fingerprint={fingerprint} rowHref={rowHref} /> : null}
    </SidePanel>
  );
}

/** The line under the row's name: its amount with its certainty, its day and its account. */
function Summary({ row }: { row: Row }) {
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2">
      <Money value={row.amount} direction={row.direction} certainty={row.certainty} />
      <span>· {formatDay(row.day)}</span>
      <span>· {row.account.label}</span>
    </span>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="flex flex-col gap-2">
      <h3 id={heading} className="text-base font-semibold">
        {title}
      </h3>
      {children}
    </section>
  );
}

interface BodyProps {
  found: TransactionDetail;
  fingerprint: string;
  rowHref: (fingerprint: string) => string;
}

function Body({ found, fingerprint, rowHref }: BodyProps) {
  const { t } = useTranslation("transactions");
  const labels = useLabels().data ?? {};
  const { row, parts } = found;
  return (
    <div className="flex flex-col gap-6">
      <Say>
        {sayOf(found, labels, t)} {found.correctable ? <span>{t("row.next")}</span> : null}
      </Say>
      <Section title={t("row.details")}>
        <Facts items={factsOf(found, labels, t)} />
      </Section>
      {parts.length > 0 ? (
        <Section title={t("row.parts")}>
          <PartsTable parts={parts} labels={labels} />
        </Section>
      ) : null}
      <Section title={t("why.title")}>
        <Why found={found} labels={labels} rowHref={rowHref} />
      </Section>
      <Section title={t("printed.title")}>
        {found.printed ? (
          <RowPreview printed={found.printed} fingerprint={row.split_of || row.fingerprint} />
        ) : (
          <p className="text-sm">{t("printed.none")}</p>
        )}
      </Section>
      <Section title={t("correct.title")}>
        {found.correctable ? (
          <Corrections found={found} fingerprint={fingerprint} labels={labels} />
        ) : (
          <p className="text-sm">{t("row.notCounted")}</p>
        )}
      </Section>
    </div>
  );
}

/** The simple view's sentence: where the row counts and why. */
function sayOf(found: TransactionDetail, labels: Labels, t: TFunction<"transactions">): string {
  if (!found.correctable) {
    return t("row.sayExcluded");
  }
  if (found.parts.length > 0) {
    return t("row.saySplit", { count: found.parts.length });
  }
  const { why } = found;
  const reason = labelOf(labels, "CategoryReason", why.category);
  return t("row.say", {
    category: found.annotation?.category || found.row.category,
    reason: why.rule ? `${reason} (${why.rule})` : reason,
  });
}

/** What the row is: the simple view's few facts, and the bank's own words and the fingerprint in the detailed one. */
function factsOf(found: TransactionDetail, labels: Labels, t: TFunction<"transactions">): Array<[string, ReactNode]> {
  const { row, bill } = found;
  const own = ownOf(found);
  const category = found.annotation?.category || row.category;
  const facts: Array<[string, ReactNode]> = [];
  if (row.description && row.description !== row.title) {
    facts.push([t("row.description"), row.description]);
  }
  facts.push([t("row.category"), [category, category === row.category ? row.group : ""].filter(Boolean).join(" · ")]);
  if (row.necessity !== null) {
    facts.push([t("row.necessity"), labelOf(labels, "Necessity", found.annotation?.necessity || row.necessity)]);
  }
  facts.push([t("row.kind"), labelOf(labels, "TransactionKind", row.kind)]);
  facts.push([t("row.account"), row.account.label]);
  facts.push([t("row.day"), formatDay(row.day)]);
  if (row.installment) {
    facts.push([t("row.installment"), row.installment]);
  }
  if (row.original) {
    facts.push([t("row.original"), row.original]);
  }
  if (own.tags.length > 0) {
    facts.push([t("row.tags"), own.tags.map((tag) => `#${tag}`).join(" ")]);
  }
  if (own.note) {
    facts.push([t("row.note"), own.note]);
  }
  if (bill) {
    facts.push([
      t("row.bill"),
      <ScreenLink key="bill" link={{ screen: "invoice", id: bill.key, query: {} }}>
        {t("row.billText", { seller: bill.seller, day: formatDay(bill.issued), total: formatMoney(bill.total) })}
      </ScreenLink>,
    ]);
  }
  return facts;
}

/** The row's parts in order, each with its share and its own category. */
function PartsTable({ parts, labels }: { parts: readonly Row[]; labels: Labels }) {
  const { t } = useTranslation("transactions");
  return (
    <Table>
      <caption className="sr-only">{t("row.parts")}</caption>
      <thead>
        <tr>
          <Th>{t("row.part")}</Th>
          <Th>{t("row.category")}</Th>
          <Th>{t("row.necessity")}</Th>
          <Th className="text-right">{t("table.amount")}</Th>
        </tr>
      </thead>
      <tbody>
        {parts.map((part, index) => (
          <tr key={part.fingerprint}>
            <Td className="tabular-nums">{t("row.partNumber", { number: index + 1, total: parts.length })}</Td>
            <Td>
              {part.category}
              {part.group ? <span className={cn("block", SMALL)}>{part.group}</span> : null}
            </Td>
            <Td>{part.necessity ? labelOf(labels, "Necessity", part.necessity) : "—"}</Td>
            <Td className="text-right">
              <Money value={part.amount} direction={part.direction} className="justify-end" />
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

interface WhyProps {
  found: TransactionDetail;
  labels: Labels;
  rowHref: (fingerprint: string) => string;
}

/** Why the row is what it is; the detailed view adds where each rule stands and the evidence behind the row. */
function Why({ found, labels, rowHref }: WhyProps) {
  const { t } = useTranslation("transactions");
  const { t: tc } = useTranslation("common");
  const { view } = useView();
  const detailed = view === "detailed";
  const { why, told } = found;
  const layer = (code: string | null) => (code ? labelOf(labels, "RuleLayer", code) : "");
  const facts: Array<[string, ReactNode]> = [
    [
      t("why.category"),
      [
        labelOf(labels, "CategoryReason", why.category),
        why.rule ? t("why.categoryRule", { rule: why.rule }) : "",
        layer(why.layer),
      ]
        .filter(Boolean)
        .join(" · "),
    ],
  ];
  if (why.necessity) {
    facts.push([
      t("why.necessity"),
      [labelOf(labels, "NecessityReason", why.necessity), layer(why.necessity_layer)].filter(Boolean).join(" · "),
    ]);
  }
  if (why.transfer) {
    facts.push([t("why.transfer"), labelOf(labels, "TransferStep", why.transfer)]);
  }
  if (why.pair) {
    facts.push([t("why.pair"), <Pair key="pair" pair={why.pair} href={rowHref(why.pair.fingerprint)} />]);
  }
  if (why.rate) {
    facts.push([
      t("why.rate"),
      why.rate_day
        ? t("why.rateText", { rate: formatRate(why.rate), origin: rateOrigin(tc, why.rate_source, why.rate_day, "by") })
        : t("why.rateOnly", { rate: formatRate(why.rate) }),
    ]);
  }
  return (
    <div className="flex flex-col gap-3">
      <Facts items={facts} />
      {told.length > 0 || detailed ? (
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium">{t("why.told")}</p>
          {told.length > 0 ? (
            <ul className="flex flex-col gap-1 text-sm">
              {told.map((item) => (
                <li key={item.fingerprint}>
                  {t("why.toldItem", {
                    status: labelOf(labels, "EvidenceStatus", item.status),
                    day: formatDay(item.day),
                    amount: formatMoney(item.amount),
                  })}
                  {item.printed ? (
                    <span className={cn("block wrap-break-word", SMALL)}>
                      <ScreenLink
                        link={{ screen: "document", id: item.printed.document, query: { satir: item.fingerprint } }}
                      >
                        {item.printed.name}
                      </ScreenLink>
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className={SMALL}>{t("why.noTold")}</p>
          )}
        </div>
      ) : null}
      {detailed ? (
        <Facts
          items={[[t("row.fingerprint"), <code key="fp" className="break-all text-xs">{found.row.fingerprint}</code>]]}
        />
      ) : null}
    </div>
  );
}

/** The opposite row in another of the user's accounts, or the named payment the row is like; it opens in the panel. */
function Pair({ pair, href }: { pair: Row; href: string }) {
  return (
    <span className="flex flex-col">
      <Link to={href} className={cn("self-start rounded font-medium underline underline-offset-2", FOCUS)}>
        {pair.title}
      </Link>
      <span className={SMALL}>
        {[formatDay(pair.day), pair.account.label, formatMoney(pair.amount)].join(" · ")}
      </span>
    </span>
  );
}
