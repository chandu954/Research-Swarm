"""Document upload, retrieval, signed downloads, and restore endpoints."""

import os
from datetime import datetime, timezone
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.common import (
    UPLOAD_DIR,
    log_audit,
    sign_document_download,
    verify_document_download,
)
from backend.auth.dependencies import get_current_user, get_optional_user
from backend.auth.tenant import (
    TenantContext,
    resolve_optional_tenant,
    resolve_tenant_dependencies,
)
from backend.core.ratelimit import limiter
from backend.db.models import Document, DocumentVersion, User
from backend.db.schemas import (
    DocumentDownloadUrlResponse,
    DocumentResponse,
    DocumentVersionResponse,
)
from backend.db.session import get_session

router = APIRouter(tags=["documents"])


# ═══════════════════════════════════════════════════════════════
# DOCUMENTS (tenant-aware)
# ═══════════════════════════════════════════════════════════════


@router.post("/upload")
@limiter.limit("30/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail="File too large. Maximum size is 50MB"
        )

    safe_name = os.path.basename(file.filename or "")
    if not safe_name:
        raise HTTPException(status_code=400, detail="Missing filename")

    file_id = f"{uuid.uuid4()}_{safe_name}"
    file_path = os.path.join(UPLOAD_DIR, file_id)
    try:
        content = await file.read()

        if not content[:4] == b"%PDF":
            raise HTTPException(
                status_code=400,
                detail="Invalid file format. Only PDF files are accepted",
            )

        with open(file_path, "wb") as f:
            f.write(content)

        doc = Document(
            user_id=current_user.id,
            organization_id=ctx.organization_id,
            workspace_id=ctx.workspace_id,
            project_id=ctx.project_id,
            filename=file_id,
            original_filename=file.filename,
            size_bytes=len(content),
            mime_type="application/pdf",
            storage_path=file_path,
            storage_backend="local",
        )
        session.add(doc)
        await session.flush()

        await log_audit(
            session,
            "document.uploaded",
            "document",
            doc.id,
            {"filename": file.filename, "size": len(content)},
            ctx,
        )

        _mirror_document_upload(
            user_id=str(current_user.id),
            document_id=str(doc.id),
            filename=file.filename,
            content=content,
        )

        return {
            "document_id": doc.id,
            "filename": file.filename,
            "size": len(content),
            "status": "uploaded",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail="Failed to upload document")


def _mirror_document_upload(
    *,
    user_id: str,
    document_id: str,
    filename: str,
    content: bytes,
) -> None:
    """Mirror an uploaded document to Supabase storage + rs_documents.

    Path layout `{legacy_user_id}/{document_id}/{filename}` inside the
    rs_documents bucket; the bucket policy scopes users to their own folder.
    """
    try:
        from backend.core.supabase import (
            get_profile,
            get_supabase,
            log_activity,
            save_document,
            update_document,
        )

        profile = get_profile(user_id)
        if not profile:
            return
        sb_user_id = profile["id"]
        storage_path = f"{sb_user_id}/{document_id}/{filename}"

        from storage3.types import FileOptions

        get_supabase().storage.from_("rs_documents").upload(
            storage_path,
            content,
            FileOptions(content_type="application/pdf", upsert="true"),
        )

        row = save_document(
            user_id=sb_user_id,
            name=filename,
            storage_path=storage_path,
            mime_type="application/pdf",
            size_bytes=len(content),
        )
        update_document(row["id"], status="ready")
        log_activity(
            user_id=sb_user_id,
            action="document.uploaded",
            entity_type="document",
            entity_id=row["id"],
            metadata={"name": filename},
        )
    except Exception as exc:  # pragma: no cover - resilience path
        logger.warning(f"supabase document mirror skipped for {document_id}: {exc}")


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    search: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    q = select(Document).where(Document.organization_id == ctx.organization_id)
    if not include_deleted:
        q = q.where(Document.is_deleted.is_(False))
    if ctx.project_id:
        q = q.where(Document.project_id == ctx.project_id)
    elif ctx.workspace_id:
        q = q.where(Document.workspace_id == ctx.workspace_id)
    if search:
        q = q.where(
            or_(
                Document.original_filename.ilike(f"%{search}%"),
                Document.filename.ilike(f"%{search}%"),
            )
        )
    q = q.order_by(Document.created_at.desc())

    result = await session.execute(q)
    return [DocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.organization_id == ctx.organization_id,
            Document.is_deleted.is_(False),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.get(
    "/documents/{doc_id}/versions", response_model=list[DocumentVersionResponse]
)
async def get_document_versions(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    doc_result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.organization_id == ctx.organization_id,
            Document.is_deleted.is_(False),
        )
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")
    result = await session.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.document_id == doc_id,
        )
        .order_by(DocumentVersion.version_number.desc())
    )
    return [DocumentVersionResponse.model_validate(v) for v in result.scalars().all()]


@router.delete("/documents/{doc_id}")
async def soft_delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.organization_id == ctx.organization_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_deleted = True
    doc.deleted_at = datetime.now(timezone.utc)
    await session.flush()
    await log_audit(session, "document.deleted", "document", doc_id, {}, ctx)
    return {"status": "deleted"}


@router.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
    ctx: Optional[TenantContext] = Depends(resolve_optional_tenant),
    sig: Optional[str] = Query(
        None, description="HMAC signature for signed download URLs"
    ),
    exp: Optional[int] = Query(None, description="Signature expiry epoch seconds"),
):
    from fastapi.responses import FileResponse

    # Signed (short-lived) download path: no bearer token in the URL, and no
    # token can be attached by a plain browser tab — the HMAC is the auth.
    # The signature binds doc_id + owning organization + expiry, so it can
    # never be replayed against another tenant's document.
    if sig and exp is not None:
        sig_result = await session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.is_deleted.is_(False),
            )
        )
        doc_for_sig = sig_result.scalar_one_or_none()
        if doc_for_sig is None or not verify_document_download(
            doc_id, doc_for_sig.organization_id, exp, sig
        ):
            raise HTTPException(
                status_code=403, detail="Invalid or expired download link"
            )
        doc = doc_for_sig
    else:
        if current_user is None:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if ctx is None:
            raise HTTPException(status_code=403, detail="organization_required")
        result = await session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.organization_id == ctx.organization_id,
                Document.is_deleted.is_(False),
            )
        )
        doc = result.scalar_one_or_none()
        if not doc or not doc.storage_path:
            raise HTTPException(status_code=404, detail="Document not found")
    if not doc.storage_path or not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        doc.storage_path,
        media_type="application/pdf",
        filename=doc.original_filename,
    )


@router.post(
    "/documents/{doc_id}/download-url", response_model=DocumentDownloadUrlResponse
)
async def create_document_download_url(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    """Issue a short-lived, cryptographically signed download URL.

    The signature binds the document id, the owning organization, and an
    expiry timestamp (HMAC-SHA256 over a server-only secret) — never a JWT.
    Signed URLs are valid for 5 minutes and cannot be replayed across
    tenants or documents.
    """
    result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.organization_id == ctx.organization_id,
            Document.is_deleted.is_(False),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc or not doc.storage_path:
        raise HTTPException(status_code=404, detail="Document not found")
    if not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    expires = int(time.time()) + 300
    sig = sign_document_download(doc_id, doc.organization_id, expires)
    return DocumentDownloadUrlResponse(
        url=f"/documents/{doc_id}/download?sig={sig}&exp={expires}",
        expires_in=300,
    )


@router.post("/documents/{doc_id}/restore")
async def restore_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.organization_id == ctx.organization_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_deleted = False
    doc.deleted_at = None
    await session.flush()
    return {"status": "restored"}
