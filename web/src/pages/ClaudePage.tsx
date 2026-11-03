// Claude's connection (K23, ADR-0011, F16): what anyone needs to add İplikçi Nedim to their Claude without a terminal.
// Claude Code reaches the service's /mcp with a headers helper that reads the token from the keyring, so the
// configuration carries no secret; claude-SAK imports the same JSON. Claude Desktop starts the stdio bridge. The token
// itself stays behind "Göster" (the user allowed it to be shown), and the user picks what MCP's answers hide.

import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  useMcpConnection,
  useRevealToken,
  useSetMasking,
} from "../api/queries";
import type { McpConnection, McpMasking } from "../api/types";
import { Failure, Loading } from "../components/QueryState";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Copyable } from "../components/ui/Copyable";
import { PageHeader } from "../components/ui/PageHeader";

export default function ClaudePage() {
  const { t } = useTranslation("claude");
  const connection = useMcpConnection();
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("page.title")} description={t("page.description")} />
      {connection.isPending ? <Loading /> : null}
      {connection.isError ? (
        <Failure
          error={connection.error}
          onRetry={() => void connection.refetch()}
        />
      ) : null}
      {connection.data ? <Connected connection={connection.data} /> : null}
    </div>
  );
}

function Connected({ connection }: { connection: McpConnection }) {
  const { t } = useTranslation("claude");
  return (
    <>
      {connection.development ? (
        <Alert tone="neutral" title={t("development")} />
      ) : null}
      <CodeCard connection={connection} />
      <DesktopCard connection={connection} />
      <AddressCard address={connection.address} />
      <MaskingCard masking={connection.masking} />
    </>
  );
}

/** Claude Code, through claude-SAK's MCP JSON import (its panel's own labels): the steps, the JSON and, folded, the
 *  command lines. */
function CodeCard({ connection }: { connection: McpConnection }) {
  const { t } = useTranslation("claude");
  return (
    <Card title={t("code.title")}>
      <div className="flex flex-col gap-3 text-sm">
        <p>{t("code.intro")}</p>
        <ol className="list-decimal pl-5">
          <li>{t("code.stepOpen")}</li>
          <li>{t("code.stepPaste")}</li>
          <li>{t("code.stepInstall")}</li>
          <li>{t("code.stepCheck")}</li>
        </ol>
        <Copyable
          label={t("code.config")}
          text={json(connection.claude_code)}
          block
        />
        <p className="text-zinc-600 dark:text-zinc-400">{t("code.token")}</p>
        <details className="flex flex-col gap-2">
          <summary className="min-h-8 cursor-pointer font-medium text-teal-800 dark:text-teal-300">
            {t("code.commands")}
          </summary>
          <div className="mt-2 flex flex-col gap-3">
            <Copyable label={t("code.sakAdd")} text={connection.sak_add} />
            <Copyable
              label={t("code.sakRemove")}
              text={connection.sak_remove}
            />
            <Copyable
              label={t("code.claudeAdd")}
              text={connection.claude_add}
            />
          </div>
        </details>
      </div>
    </Card>
  );
}

/** Claude Desktop starts the bridge itself: its configuration file's part. */
function DesktopCard({ connection }: { connection: McpConnection }) {
  const { t } = useTranslation("claude");
  return (
    <Card title={t("desktop.title")}>
      <div className="flex flex-col gap-3 text-sm">
        <p>{t("desktop.step")}</p>
        <Copyable
          label={t("desktop.config")}
          text={json(connection.claude_desktop)}
          block
        />
        <p className="text-zinc-600 dark:text-zinc-400">
          {t("desktop.offline")}
        </p>
      </div>
    </Card>
  );
}

/** The address any MCP client takes, and the token behind its button. */
function AddressCard({ address }: { address: string }) {
  const { t } = useTranslation("claude");
  const reveal = useRevealToken();
  const [shown, setShown] = useState(false);
  const token = shown ? reveal.data?.token : undefined;
  return (
    <Card title={t("address.title")}>
      <div className="flex flex-col gap-3 text-sm">
        <p>{t("address.intro")}</p>
        <Copyable label={t("address.label")} text={address} />
        {token ? (
          <div className="flex flex-col gap-2">
            <Copyable label={t("address.token")} text={token} />
            <Button
              variant="secondary"
              className="self-start"
              onClick={() => setShown(false)}
            >
              {t("address.hide")}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            <span className="text-zinc-600 dark:text-zinc-400">
              {t("address.token")}
            </span>
            <Button
              variant="secondary"
              className="self-start"
              disabled={reveal.isPending}
              onClick={() =>
                reveal.mutate(undefined, { onSuccess: () => setShown(true) })
              }
            >
              {t("address.show")}
            </Button>
          </div>
        )}
        {reveal.isError ? (
          <Alert tone="critical" title={t("address.failed")} live>
            <p>{reveal.error.message}</p>
          </Alert>
        ) : null}
        <p className="text-zinc-600 dark:text-zinc-400">
          {t("address.warning")}
        </p>
      </div>
    </Card>
  );
}

const LEVELS: readonly McpMasking[] = ["off", "accounts", "accounts_and_names"];

/** What MCP's answers hide: a choice of three, each with what it means. */
function MaskingCard({ masking }: { masking: McpMasking }) {
  const { t } = useTranslation("claude");
  const save = useSetMasking();
  const name = useId();
  return (
    <Card title={t("masking.title")}>
      <div className="flex flex-col gap-3 text-sm">
        <p>{t("masking.intro")}</p>
        <fieldset className="flex flex-col gap-2" disabled={save.isPending}>
          <legend className="sr-only">{t("masking.legend")}</legend>
          {LEVELS.map((level) => (
            <label
              key={level}
              className="flex min-h-11 cursor-pointer items-start gap-2"
            >
              <input
                type="radio"
                className="mt-1 size-4 accent-teal-700 dark:accent-teal-400"
                name={name}
                value={level}
                checked={masking === level}
                onChange={() => save.mutate(level)}
              />
              <span className="flex flex-col">
                <span className="font-medium">{t(`masking.${level}`)}</span>
                <span className="text-zinc-600 dark:text-zinc-400">
                  {t(`masking.${level}Hint`)}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
        <span aria-live="polite" className="text-zinc-700 dark:text-zinc-300">
          {save.isSuccess ? t("masking.saved") : ""}
        </span>
        {save.isError ? (
          <Alert tone="critical" title={t("masking.failed")} live>
            <p>{save.error.message}</p>
          </Alert>
        ) : null}
      </div>
    </Card>
  );
}

function json(value: unknown): string {
  return JSON.stringify(value, null, 2);
}
