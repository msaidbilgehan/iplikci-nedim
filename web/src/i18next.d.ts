// The keys t() accepts are the keys of the Turkish files: a missing or misspelt one fails the typecheck.

import "i18next";

import type { defaultNS, resources } from "./i18n";

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: typeof defaultNS;
    resources: (typeof resources)["tr"];
  }
}
