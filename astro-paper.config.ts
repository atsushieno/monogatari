import { defineAstroPaperConfig } from "./src/types/config";

const siteUrl =
  process.env.SITE_URL ?? "http://monogatari.audiopluginlab.com/";

export default defineAstroPaperConfig({
  site: {
    url: siteUrl,
    title: "ものがたり",
    description: "the daily little nothings by atsushieno",
    author: "atsushieno",
    profile: "https://github.com/atsushieno",
    ogImage: "og.png",
    lang: "ja",
    timezone: "Asia/Tokyo",
    dir: "ltr",
  },
  posts: {
    perPage: 4,
    perIndex: 4,
    scheduledPostMargin: 15 * 60 * 1000,
  },
  features: {
    lightAndDarkMode: true,
    dynamicOgImage: true,
    showArchives: true,
    showBackButton: true,
    editPost: {
      enabled: false,
    },
    search: "pagefind",
  },
  socials: [
    { name: "github", url: "https://github.com/atsushieno" },
  ],
  shareLinks: [
    { name: "hatena",   url: "https://b.hatena.ne.jp/add?mode=confirm&url=" },
    { name: "bluesky",  url: "https://bsky.app/intent/compose?text=" },
    { name: "mastodon", url: "https://toot.kytta.dev/?text=" },
  ],
});
