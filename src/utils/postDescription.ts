import type { CollectionEntry } from "astro:content";

const IMPORTED_HATENA_PREFIXES = ["hatenablog/", "hatenadiary/"];

export function getPostDescription(
  post: Pick<CollectionEntry<"posts">, "id" | "data">
): string | undefined {
  if (IMPORTED_HATENA_PREFIXES.some(prefix => post.id.startsWith(prefix))) {
    return undefined;
  }

  const description = post.data.description?.trim();
  return description || undefined;
}
