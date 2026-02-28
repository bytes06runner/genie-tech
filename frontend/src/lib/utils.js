/**
 * Utility module for class name merging.
 * Combines clsx (conditional classes) with tailwind-merge (deduplication)
 * to provide a single `cn()` helper used throughout shadcn-style components.
 *
 * @module utils
 */
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS class names intelligently.
 * Handles conditional classes and resolves Tailwind conflicts.
 *
 * @param {...(string|undefined|null|boolean|Record<string,boolean>)} inputs - Class values
 * @returns {string} Merged class string
 *
 * @example
 * cn("px-4 py-2", isActive && "bg-green-500", "px-8")
 * // => "py-2 px-8 bg-green-500" (px-8 overrides px-4)
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
