"""A HEAD is a GET whose body is dropped, which is what a crawler, a link checker and an uptime monitor ask with first."""

from fastapi import FastAPI

from helpers.answer_head_as_get import AnswerHeadAsGet


def setup(app: FastAPI) -> None:
    app.add_middleware(AnswerHeadAsGet)
