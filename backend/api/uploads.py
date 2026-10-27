"""Bounded image upload reading shared by prediction endpoints."""
from fastapi import HTTPException, UploadFile
from backend.config.settings import MAX_UPLOAD_BYTES


def read_upload(file: UploadFile) -> bytes:
    try:
        if file.size is not None and file.size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Ảnh vượt quá giới hạn 10 MB.")
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if not data:
            raise HTTPException(422, "File ảnh rỗng. Hãy chọn một ảnh khác.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Ảnh vượt quá giới hạn 10 MB.")
        return data
    finally:
        file.file.close()

