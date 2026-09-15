from enum import StrEnum


class StorageProvider(StrEnum):
    FILESYSTEM = "filesystem"
    S3 = "s3"
