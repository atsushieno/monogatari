import type { UIStrings } from "../types";

export default {
  nav: {
    home: "ホーム",
    posts: "記事",
    tags: "タグ",
    about: "このブログについて",
    archives: "アーカイブ",
    search: "検索",
  },
  post: {
    publishedAt: "公開日",
    updatedAt: "更新日",
    sharePostIntro: "この記事を共有:",
    sharePostOn: "{{platform}}で共有",
    sharePostViaEmail: "メールで共有",
    tagLabel: "タグ",
    backToTop: "ページ先頭へ",
    goBack: "戻る",
    editPage: "ページを編集",
    previousPost: "前の記事",
    nextPost: "次の記事",
  },
  pagination: {
    prev: "前へ",
    next: "次へ",
    page: "ページ",
  },
  home: {
    socialLinks: "ソーシャルリンク",
    featured: "注目の記事",
    recentPosts: "最近の記事",
    allPosts: "すべての記事",
  },
  footer: {
    copyright: "Copyright",
    allRightsReserved: "無断転載を禁じます。",
  },
  pages: {
    tagTitle: "タグ",
    tagDesc: "次のタグが付いた記事",

    tagsTitle: "タグ",
    tagsDesc: "記事で使われているすべてのタグ。",

    postsTitle: "記事",
    postsDesc: "これまでに投稿したすべての記事。",

    archivesTitle: "アーカイブ",
    archivesDesc: "これまでの記事の一覧。",

    searchTitle: "検索",
    searchDesc: "記事を検索 ...",
  },
  a11y: {
    skipToContent: "コンテンツへスキップ",
    openMenu: "メニューを開く",
    closeMenu: "メニューを閉じる",
    toggleTheme: "テーマを切り替え",
    searchPlaceholder: "記事を検索...",
    noResults: "該当する記事がありません",
    goToPreviousPage: "前のページへ",
    goToNextPage: "次のページへ",
  },
  notFound: {
    title: "404 Not Found",
    message: "ページが見つかりません",
    goHome: "ホームへ戻る",
  },
} satisfies UIStrings;
