from enum import Enum


class StorageFileKind(str, Enum):
    file = "file"
    image = "image"
    video = "video"
    audio = "audio"
    document = "document"
    other = "other"
