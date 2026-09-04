"""The origins a browser is allowed to call this from."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from helpers.settings import settings


def setup(app: FastAPI):
    origins = settings.allowed_origins

    # Credentials cannot be combined with a wildcard origin under the cors spec.
    allow_credentials = origins != ["*"]

    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=allow_credentials, allow_methods=["*"], allow_headers=["*"])
