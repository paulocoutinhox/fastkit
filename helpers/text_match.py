"""The rows a term reaches, said in the language the database has for saying it."""

from sqlalchemy import Boolean, and_, func, literal, or_
from sqlalchemy.dialects.mysql import match as mysql_match
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement

from helpers.search import DICTIONARY, document_of


class TextMatch(ColumnElement):
    inherit_cache = False
    type = Boolean()

    # Already a predicate, so a dialect with no native boolean must not compare it against one of its own.
    _is_implicitly_boolean = True

    def __init__(self, columns, tokens):
        self.columns = list(columns)
        self.tokens = list(tokens)


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
