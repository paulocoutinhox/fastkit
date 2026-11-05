"""The ceiling on a body this process parses into memory, because one request is otherwise enough to take a node down."""

from fastapi import FastAPI

from helpers.body_limit import BodyLimit
from helpers.settings import settings


def setup(app: FastAPI):
    app.add_middleware(BodyLimit, limit=settings.request_max_bytes)
