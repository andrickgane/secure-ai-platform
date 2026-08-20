from __future__ import annotations

import io
import unicodedata
from pathlib import PurePosixPath

from pypdf import PdfReader


class AttachmentSecurityError(ValueError):
    pass


class AttachmentSecurityService:
    MAX_PDF_PAGES = 64

    TEXT_EXTENSIONS = frozenset(
        {
            ".txt", ".md", ".markdown", ".csv", ".json",
            ".yaml", ".yml", ".xml", ".html", ".css",
            ".py", ".sh", ".bash", ".js", ".jsx",
            ".ts", ".tsx", ".go", ".java", ".c", ".cpp",
            ".h", ".sql", ".tf", ".tfvars", ".hcl",
            ".ini", ".conf", ".log",
        }
    )

    IMAGE_MEDIA_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }

    ALLOWED_EXTENSIONS = frozenset(
        {
            *TEXT_EXTENSIONS,
            ".pdf",
            *IMAGE_MEDIA_TYPES.keys(),
        }
    )

    TEXT_MEDIA_TYPES = {
        ".csv": "text/csv",
        ".json": "application/json",
        ".xml": "application/xml",
        ".html": "text/html",
        ".css": "text/css",
    }

    @staticmethod
    def sanitize_filename(raw_filename: str) -> str:
        normalized = (raw_filename or "").replace("\\", "/")
        basename = PurePosixPath(normalized).name

        cleaned = "".join(
            "_"
            if unicodedata.category(character).startswith("C")
            else character
            for character in basename
        ).strip()

        if not cleaned or cleaned in {".", ".."}:
            raise AttachmentSecurityError(
                "Attachment filename is invalid"
            )

        cleaned = cleaned[:255]

        if not cleaned:
            raise AttachmentSecurityError(
                "Attachment filename is invalid"
            )

        return cleaned

    @classmethod
    def validate(
        cls,
        *,
        filename: str,
        content: bytes,
    ) -> str:
        if not content:
            raise AttachmentSecurityError(
                "Attachment is empty"
            )

        extension = PurePosixPath(filename.lower()).suffix

        if extension not in cls.ALLOWED_EXTENSIONS:
            raise AttachmentSecurityError(
                "Attachment extension is not allowed"
            )

        if extension in cls.TEXT_EXTENSIONS:
            cls._validate_text(content)
            return cls.TEXT_MEDIA_TYPES.get(
                extension,
                "text/plain",
            )

        if extension == ".pdf":
            cls._validate_pdf(content)
            return "application/pdf"

        cls._validate_image(
            extension=extension,
            content=content,
        )
        return cls.IMAGE_MEDIA_TYPES[extension]

    @staticmethod
    def _validate_text(content: bytes) -> None:
        if b"\x00" in content:
            raise AttachmentSecurityError(
                "Text attachment contains NUL bytes"
            )

        try:
            text = content.decode(
                "utf-8",
                errors="strict",
            )
        except UnicodeDecodeError as exc:
            raise AttachmentSecurityError(
                "Text attachment must be valid UTF-8"
            ) from exc

        for character in text:
            if (
                unicodedata.category(character).startswith("C")
                and character not in {"\n", "\r", "\t"}
            ):
                raise AttachmentSecurityError(
                    "Text attachment contains unsupported control characters"
                )

    @classmethod
    def _validate_pdf(
        cls,
        content: bytes,
    ) -> None:
        if not content.startswith(b"%PDF-"):
            raise AttachmentSecurityError(
                "PDF signature is invalid"
            )

        try:
            reader = PdfReader(
                io.BytesIO(content),
                strict=False,
            )

            if reader.is_encrypted:
                raise AttachmentSecurityError(
                    "Encrypted PDF attachments are not allowed"
                )

            page_count = len(reader.pages)

        except AttachmentSecurityError:
            raise
        except Exception as exc:
            raise AttachmentSecurityError(
                "PDF structure is invalid"
            ) from exc

        if page_count < 1:
            raise AttachmentSecurityError(
                "PDF contains no pages"
            )

        if page_count > cls.MAX_PDF_PAGES:
            raise AttachmentSecurityError(
                f"PDF exceeds the {cls.MAX_PDF_PAGES}-page limit"
            )

    @staticmethod
    def _validate_image(
        *,
        extension: str,
        content: bytes,
    ) -> None:
        valid = False

        if extension == ".png":
            valid = content.startswith(
                b"\x89PNG\r\n\x1a\n"
            )

        elif extension in {".jpg", ".jpeg"}:
            valid = (
                len(content) >= 3
                and content[:3] == b"\xff\xd8\xff"
            )

        elif extension == ".gif":
            valid = content.startswith(
                (b"GIF87a", b"GIF89a")
            )

        elif extension == ".webp":
            valid = (
                len(content) >= 12
                and content[:4] == b"RIFF"
                and content[8:12] == b"WEBP"
            )

        if not valid:
            raise AttachmentSecurityError(
                f"File content does not match {extension} format"
            )
