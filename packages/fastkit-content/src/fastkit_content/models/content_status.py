from enum import Enum


class ContentStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"
