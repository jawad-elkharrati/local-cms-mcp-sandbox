from enum import StrEnum


class ArticleStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Role(StrEnum):
    READER = "reader"
    EDITOR = "editor"
    PUBLISHER = "publisher"
    ADMIN = "admin"
