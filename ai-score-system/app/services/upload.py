from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".ppt",
    ".pptx",
    ".doc",
    ".docx",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".zip",
    ".rar",
    ".7z",
}


def save_upload_file(upload: UploadFile, subdir: str) -> tuple[str, str, str, int]:
    settings = get_settings()
    original = Path(upload.filename or "").name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的文件类型：{suffix}")

    target_dir = (settings.upload_path / subdir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    if not str(target_dir).startswith(str(settings.upload_path)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法上传路径")

    stored_name = f"{uuid4().hex}{suffix}"
    target = target_dir / stored_name
    size = 0
    with target.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_size_bytes:
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件超过大小限制")
            out.write(chunk)
    return original, stored_name, str(target), size


def safe_file_path(file_path: str) -> Path:
    settings = get_settings()
    path = Path(file_path).resolve()
    if not str(path).startswith(str(settings.upload_path)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件路径")
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return path
