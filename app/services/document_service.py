import io
import uuid
import logging
from pypdf import PdfReader
from app.core.config import get_settings
from app.domain.chunker import chunk_text
from app.models.document import UserDocument
from app.core.exceptions import NotFoundError
from app.core.vector_db import get_qdrant_client
from app.services.embedding_service import get_embedding_service
from app.schemas.document import DocumentChunkResult, DocumentResponse
from qdrant_client.models import (
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
)

logger = logging.getLogger(__name__)


def _to_response(doc: UserDocument) -> DocumentResponse:
    return DocumentResponse(
        id=str(doc.id),
        filename=doc.filename,
        content_type=doc.content_type,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _chunk_point_id(document_id: str, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{index}"))


def _extract_text(filename: str, content_type: str, raw: bytes) -> str:
    is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")

    if is_pdf:
        reader = PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    return raw.decode("utf-8", errors="ignore")


class DocumentService:
    async def ingest(
        self,
        user_id: str,
        filename: str,
        content_type: str,
        raw: bytes,
    ) -> DocumentResponse:
        doc = UserDocument(
            user_id=user_id,
            filename=filename,
            content_type=content_type or "application/octet-stream",
        )
        await doc.insert()

        try:
            text = _extract_text(filename, doc.content_type, raw)
            chunks = chunk_text(text)

            if not chunks:
                doc.status = "failed"
                doc.error_message = "No extractable text found"
                await doc.save()
                return _to_response(doc)

            embedding_service = get_embedding_service()
            vectors = await embedding_service.embed_batch(chunks)

            settings = get_settings()
            client = get_qdrant_client()

            points = [
                PointStruct(
                    id=_chunk_point_id(str(doc.id), i),
                    vector=vectors[i],
                    payload={
                        "document_id": str(doc.id),
                        "user_id": user_id,
                        "filename": filename,
                        "chunk_index": i,
                        "text": chunks[i],
                    },
                )
                for i in range(len(chunks))
            ]

            await client.upsert(
                collection_name=settings.qdrant_document_collection_name,
                points=points,
            )

            doc.status = "ready"
            doc.chunk_count = len(chunks)
            await doc.save()

        except Exception as exc:
            logger.warning(f"Document ingestion failed for {doc.id}: {exc}")
            doc.status = "failed"
            doc.error_message = str(exc)
            await doc.save()

        return _to_response(doc)

    async def list_documents(self, user_id: str) -> list[DocumentResponse]:
        docs = (
            await UserDocument.find(UserDocument.user_id == user_id)
            .sort(-UserDocument.created_at)
            .to_list()
        )
        return [_to_response(d) for d in docs]

    async def delete(self, user_id: str, document_id: str) -> None:
        doc = await UserDocument.get(document_id)
        if not doc or doc.user_id != user_id:
            raise NotFoundError("Document", document_id)

        settings = get_settings()
        client = get_qdrant_client()
        try:
            await client.delete(
                collection_name=settings.qdrant_document_collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                    )
                ),
            )
        except Exception as exc:
            logger.warning(f"Failed to delete vectors for document {document_id}: {exc}")

        await doc.delete()

    async def search(self, user_id: str, query_text: str, limit: int = 5) -> list[DocumentChunkResult]:
        try:
            settings = get_settings()
            embedding_service = get_embedding_service()
            client = get_qdrant_client()

            query_vector = await embedding_service.embed(query_text)

            result = await client.query_points(
                collection_name=settings.qdrant_document_collection_name,
                query=query_vector,
                query_filter=Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                ),
                limit=limit,
                score_threshold=settings.document_relevance_threshold,
            )

            return [
                DocumentChunkResult(
                    document_id=point.payload["document_id"],
                    filename=point.payload["filename"],
                    chunk_text=point.payload["text"],
                    score=point.score,
                )
                for point in result.points
            ]
        except Exception as exc:
            logger.warning(f"Document search failed for user {user_id}: {exc}")
            return []