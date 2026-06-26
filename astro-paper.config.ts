import { defineAstroPaperConfig } from "./src/types/config";

const siteUrl = process.env.SITE_URL ?? "https://atsushieno.github.io/";

export default defineAstroPaperConfig({
  site: {
    url: siteUrl,
    title: "ものがたり",
    description: "atsushieno の開発記録。MIDI 2.0、オーディオプラグイン、Android、.NET/mono などの話題。",
    author: "atsushieno",
    profile: "https://github.com/atsushieno",
    ogImage: "default-og.jpg",
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
