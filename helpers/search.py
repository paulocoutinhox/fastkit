"""What a search term matches, said once and expressed by each database with what it has."""

import re
from functools import reduce

from sqlalchemy import Index, func, literal
from sqlalchemy.sql.expression import ColumnElement

# What a dialect reads as syntax, and what a reader who types it means literally.
OPERATORS = re.compile(r"[+\-<>()~*\"@:&|!\\%_]+")


# The configuration every dialect is asked to parse the term under, so a stemmer never changes the answer between two of them.
DICTIONARY = "simple"


# InnoDB never indexes a word below `innodb_ft_min_token_size`, so requiring one asks the index for what it does not hold.
MIN_TOKEN_SIZE = 3


def words_of(term: str) -> list[str]:
    """A term is the words it carries, because the operators of every dialect are stripped before it reaches one."""
    return [word for word in OPERATORS.sub(" ", term).split() if word]


def tokens_of(term: str) -> list[str]:
    """A word an index cannot hold is dropped instead of required, or `machado de assis` would answer nothing at all."""
    return [word for word in words_of(term) if len(word) >= MIN_TOKEN_SIZE]


def phrase_of(term: str) -> str:
    """The phrase is what was typed, short words included, because it ranks and never filters."""
    return " ".join(words_of(term))


def contains(column, term: str):
    """What a reader typed is a piece of an identifier and never a pattern, so `%` and `_` match themselves."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    return column.ilike(f"%{escaped}%", escape="\\")


def document_of(columns) -> ColumnElement:
    """The columns a search reads are one document, so a term spread across two of them still answers."""
    return reduce(lambda left, right: left.concat(literal(" ")).concat(right), [func.coalesce(column, literal("")) for column in columns])


def search_index(name: str, *columns: str) -> Index:
    """MySQL answers a text search only where a fulltext index covers exactly the columns asked for, so the two are declared together."""
    return Index(name, *columns, mysql_prefix="FULLTEXT")
