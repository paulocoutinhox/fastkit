from fastapi import APIRouter, Depends, File, UploadFile, status

from enums.upload import UploadPurpose
from helpers.auth import CurrentUser
from helpers.db import DatabaseSession
from helpers.errors import PermissionError
from models.user import User
from schemas.upload import UploadResponse
from services.crud import roles_storing
from services.upload import upload_service

# The account sends its own picture through its own route, so what is left here is an operator filling in a record.
router = APIRouter(prefix="/uploads", tags=["uploads"])


async def uploader(purpose: UploadPurpose, user: CurrentUser) -> User:
    """Whoever may write a record may put its file in, so an editor fills a banner and a product file stays with the administrator."""
    if user.role not in roles_storing(purpose):
        raise PermissionError("error.role-not-allowed")

    return user


@router.post("/{purpose}", response_model=UploadResponse, status_code=status.HTTP_201_CREATED, summary="Store a file and answer its key", dependencies=[Depends(uploader)])
async def upload(db: DatabaseSession, purpose: UploadPurpose, file: UploadFile = File(...)):
    """The key is what the resource stores, and the URL is what a screen renders while editing."""
    return UploadResponse(**await upload_service.store(db, purpose, file))
