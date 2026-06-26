export const UNTITLED_HATENA_POST_TITLE = "■";

export function getDisplayPostTitle(title: string | null | undefined): string {
  return title?.trim() || UNTITLED_HATENA_POST_TITLE;
}
