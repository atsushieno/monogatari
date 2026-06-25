import type { CollectionEntry } from "astro:content";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";
import config from "@/config";

dayjs.extend(utc);
dayjs.extend(timezone);

/**
 * Posts-per-page for the year archive listing.
 *
 * Invariant: this must be large enough that no single year spans 10+ pages.
 * Year pages use bare numeric URLs (/archives/2005/2 …) that share the same URL
 * depth as the zero-padded month pages (/archives/2005/01). As long as the page
 * count per year stays single-digit, "2".."9" never collide with "01".."12".
 * The busiest year currently has ~530 posts, so 75 keeps it at <=9 pages with
 * plenty of margin. Raise the size (do not lower) if a year ever grows past 675.
 */
export const ARCHIVE_PAGE_SIZE = 75;

/** Resolve a post's publish time in its own (or the site default) timezone. */
function inZone(post: CollectionEntry<"posts">) {
  return dayjs(post.data.pubDatetime).tz(
    post.data.timezone ?? config.site.timezone
  );
}

/** Four-digit year, e.g. "2005", honoring the post timezone (JST by default). */
export function getPostYear(post: CollectionEntry<"posts">) {
  return inZone(post).format("YYYY");
}

/** Zero-padded month, e.g. "01".."12", honoring the post timezone. */
export function getPostMonth(post: CollectionEntry<"posts">) {
  return inZone(post).format("MM");
}

/** Localized full month name for a "01".."12" string. */
export function monthName(month: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { month: "long" }).format(
    new Date(2000, Number(month) - 1, 1)
  );
}
