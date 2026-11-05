"""How well a row answers the term as it was typed, so the whole phrase outranks the pieces it was cut into."""

from sqlalchemy import Float, case, func, literal
from sqlalchemy.dialects.mysql import match as mysql_match
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement

from helpers.search import DICTIONARY, document_of


class TextRank(ColumnElement):
    inherit_cache = False
    type = Float()

    def __init__(self, columns, phrase):
        self.columns = list(columns)
        self.phrase = phrase


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
