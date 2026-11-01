import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind classes joined, later ones winning over earlier ones of the same kind. */
export function cn(...classes: ClassValue[]): string {
  return twMerge(clsx(classes));
}
