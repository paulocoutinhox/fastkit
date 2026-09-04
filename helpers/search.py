"""What a search term matches, said once and expressed by each database with what it has."""

import re
from functools import reduce

from sqlalchemy import Boolean, Float, Index, and_, case, func, literal, or_
from sqlalchemy.dialects.mysql import match as mysql_match
from sqlalchemy.ext.compiler import compiles
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


class TextMatch(ColumnElement):
    """The rows a term reaches, said in the language the database has for saying it."""

    inherit_cache = False
    type = Boolean()

    # Already a predicate, so a dialect with no native boolean must not compare it against one of its own.
    _is_implicitly_boolean = True

    def __init__(self, columns, tokens):
        self.columns = list(columns)
        self.tokens = list(tokens)


class TextRank(ColumnElement):
    """How well a row answers the term as it was typed, so the whole phrase outranks the pieces it was cut into."""

    inherit_cache = False
    type = Float()

    def __init__(self, columns, phrase):
        self.columns = list(columns)
        self.phrase = phrase


@compiles(TextMatch)
def compile_text_match(element, compiler, **kw):
    """A word matches from its start, which is the only prefix every dialect agrees on."""
    document = document_of(element.columns)
    conditions = [or_(document.ilike(token + "%"), document.ilike("% " + token + "%")) for token in element.tokens]

    return compiler.process(and_(*conditions), **kw)


@compiles(TextMatch, "mysql")
def compile_mysql_text_match(element, compiler, **kw):
    """Builds the boolean mode term MySQL matches by, where the trailing star is what makes a word answer from its start."""
    against = " ".join("+" + token + "*" for token in element.tokens)

    return compiler.process(mysql_match(*element.columns, against=against, in_boolean_mode=True), **kw)


@compiles(TextMatch, "postgresql")
def compile_postgresql_text_match(element, compiler, **kw):
    query = " & ".join(token + ":*" for token in element.tokens)
    document = func.to_tsvector(literal(DICTIONARY), document_of(element.columns))

    return compiler.process(document.op("@@")(func.to_tsquery(literal(DICTIONARY), query)), **kw)


@compiles(TextRank)
def compile_text_rank(element, compiler, **kw):
    document = document_of(element.columns)

    return compiler.process(case((document.ilike("%" + element.phrase + "%"), 1.0), else_=0.0), **kw)


@compiles(TextRank, "mysql")
def compile_mysql_text_rank(element, compiler, **kw):
    return compiler.process(mysql_match(*element.columns, against='"' + element.phrase + '"', in_boolean_mode=True), **kw)


@compiles(TextRank, "postgresql")
def compile_postgresql_text_rank(element, compiler, **kw):
    document = func.to_tsvector(literal(DICTIONARY), document_of(element.columns))

    return compiler.process(func.ts_rank(document, func.phraseto_tsquery(literal(DICTIONARY), element.phrase)), **kw)


def search_index(name: str, *columns: str) -> Index:
    """MySQL answers a text search only where a fulltext index covers exactly the columns asked for, so the two are declared together."""
    return Index(name, *columns, mysql_prefix="FULLTEXT")
