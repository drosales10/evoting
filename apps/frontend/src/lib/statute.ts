export type StatuteArticle = {
  id: string;
  number: number;
  content: string;
  display_order: number;
  chapter_id: string;
};

export type StatuteChapter = {
  id: string;
  number: number;
  description: string;
  display_order: number;
  title_id: string;
  articles: StatuteArticle[];
};

export type StatuteTitleNode = {
  id: string;
  number: number;
  description: string;
  display_order: number;
  chapters: StatuteChapter[];
};

export type StatuteNamedResponse = {
  member_id: string;
  full_name: string;
  registry_code: string | null;
  approved: boolean;
  comment: string | null;
};

export type StatuteArticleResult = {
  article_id: string;
  number: number;
  content: string;
  title_number: number;
  title_description: string;
  chapter_number: number;
  chapter_description: string;
  approved_count: number;
  rejected_count: number;
  meets_threshold: boolean;
  responses: StatuteNamedResponse[];
};

export type FlatStatuteArticle = StatuteArticle & {
  titleNumber: number;
  titleDescription: string;
  chapterNumber: number;
  chapterDescription: string;
};

export function flattenStatute(titles: StatuteTitleNode[]): FlatStatuteArticle[] {
  const rows: FlatStatuteArticle[] = [];
  for (const title of titles) {
    for (const chapter of title.chapters) {
      for (const article of chapter.articles) {
        rows.push({
          ...article,
          titleNumber: title.number,
          titleDescription: title.description,
          chapterNumber: chapter.number,
          chapterDescription: chapter.description,
        });
      }
    }
  }
  return rows;
}
