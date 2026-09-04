from fastapi import APIRouter, Depends, File, UploadFile, status

from enums.upload import UploadPurpose
from helpers.auth import get_administrator
from helpers.db import DatabaseSession
from schemas.common import BaseSchema
from services.upload import upload_service

# The account sends its own picture through its own route, so what is left here is an operator filling in a record.
router = APIRouter(prefix="/uploads", tags=["uploads"], dependencies=[Depends(get_administrator)])


class UploadResponse(BaseSchema):
    key: str
    url: str
    size: int


@router.post("/{purpose}", response_model=UploadResponse, status_code=status.HTTP_201_CREATED, summary="Store a file and answer its key")
async def upload(db: DatabaseSession, purpose: UploadPurpose, file: UploadFile = File(...)):
    """The key is what the resource stores, and the URL is what a screen renders while editing."""
    return UploadResponse(**await upload_service.store(db, purpose, file))
