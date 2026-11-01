import type { ComponentPropsWithoutRef } from "react";

import { cn } from "../../lib/cn";

export function Table({ className, ...rest }: ComponentPropsWithoutRef<"table">) {
  return (
    <div className="overflow-x-auto">
      <table className={cn("w-full border-collapse text-left text-sm", className)} {...rest} />
    </div>
  );
}

export function Th({ className, ...rest }: ComponentPropsWithoutRef<"th">) {
  return (
    <th
      scope="col"
      className={cn(
        "border-b border-zinc-200 px-2 py-2 font-medium text-zinc-600 dark:border-zinc-700 dark:text-zinc-300",
        className,
      )}
      {...rest}
    />
  );
}

export function Td({ className, ...rest }: ComponentPropsWithoutRef<"td">) {
  return (
    <td className={cn("border-b border-zinc-100 px-2 py-2 align-top dark:border-zinc-800", className)} {...rest} />
  );
}
