"""Load the title → chapter → article tree for one consultation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StatuteArticle, StatuteChapter, StatuteTitle


async def load_statute_tree(
    session: AsyncSession,
    *,
    organization_id: UUID,
    consultation_id: UUID,
) -> list[dict[str, Any]]:
    titles = list(
        (
            await session.scalars(
                select(StatuteTitle)
                .where(
                    StatuteTitle.organization_id == organization_id,
                    StatuteTitle.consultation_id == consultation_id,
                )
                .order_by(StatuteTitle.number.asc(), StatuteTitle.display_order.asc())
            )
        ).all()
    )
    chapters = list(
        (
            await session.scalars(
                select(StatuteChapter)
                .where(
                    StatuteChapter.organization_id == organization_id,
                    StatuteChapter.consultation_id == consultation_id,
                )
                .order_by(StatuteChapter.number.asc(), StatuteChapter.display_order.asc())
            )
        ).all()
    )
    articles = list(
        (
            await session.scalars(
                select(StatuteArticle)
                .where(
                    StatuteArticle.organization_id == organization_id,
                    StatuteArticle.consultation_id == consultation_id,
                )
                .order_by(StatuteArticle.number.asc(), StatuteArticle.display_order.asc())
            )
        ).all()
    )
    chapters_by_title: dict[UUID, list[StatuteChapter]] = {}
    for chapter in chapters:
        chapters_by_title.setdefault(chapter.title_id, []).append(chapter)
    articles_by_chapter: dict[UUID, list[StatuteArticle]] = {}
    for article in articles:
        articles_by_chapter.setdefault(article.chapter_id, []).append(article)

    tree: list[dict[str, Any]] = []
    for title in titles:
        chapter_rows = []
        for chapter in chapters_by_title.get(title.id, []):
            chapter_rows.append(
                {
                    "id": chapter.id,
                    "number": chapter.number,
                    "description": chapter.description,
                    "display_order": chapter.display_order,
                    "title_id": chapter.title_id,
                    "articles": [
                        {
                            "id": article.id,
                            "number": article.number,
                            "content": article.content,
                            "display_order": article.display_order,
                            "chapter_id": article.chapter_id,
                        }
                        for article in articles_by_chapter.get(chapter.id, [])
                    ],
                }
            )
        tree.append(
            {
                "id": title.id,
                "number": title.number,
                "description": title.description,
                "display_order": title.display_order,
                "chapters": chapter_rows,
            }
        )
    return tree


def flatten_article_ids(tree: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for title in tree:
        for chapter in title["chapters"]:
            for article in chapter["articles"]:
                ids.append(str(article["id"]))
    return ids


def tree_as_json(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stringify UUID values so public and voter payloads stay JSON-native."""

    def convert(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, list):
            return [convert(item) for item in value]
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        return value

    converted = convert(tree)
    return converted if isinstance(converted, list) else []
