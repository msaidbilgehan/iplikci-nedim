// Links that stand among buttons look like the secondary button (ui/Button): a screen to go on to, or a file the
// service sends. They stay links, so the browser opens, copies and downloads them as links.

import type { ComponentProps } from "react";
import { Link } from "react-router";

import { cn } from "../../lib/cn";
import { buttonClass } from "./Button";

/** A screen of the interface to go on to, looking like a button. */
export function LinkButton({ className, ...rest }: ComponentProps<typeof Link>) {
  return <Link className={cn(buttonClass("secondary"), className)} {...rest} />;
}

/** A file the service sends (a CSV, a report, a document's original), downloaded, looking like a button. */
export function DownloadLink({ className, ...rest }: ComponentProps<"a">) {
  return <a download className={cn(buttonClass("secondary"), className)} {...rest} />;
}
