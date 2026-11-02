// A screen's heading: its name as the page's one h1 and in the window's title (WCAG 2.4.2; React puts the <title> in
// the document's head), a sentence on what the screen shows, and the screen's own actions beside it.

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  const { t } = useTranslation("shell");
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <title>{`${title} · ${t("appName")}`}</title>
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold">{title}</h1>
        {description ? <p className="mt-1 max-w-3xl text-sm text-zinc-700 dark:text-zinc-300">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
