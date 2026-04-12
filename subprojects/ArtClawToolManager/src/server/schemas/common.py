# Ref: docs/api/api-design.md#ResponseFormat
"""
Common response schemas: SuccessResponse, ErrorResponse, PaginationMeta.

Every API endpoint wraps its payload in one of these envelopes.
"""
from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata included with list responses."""
    page: int = 1
    limit: int = 20
    total: int = 0


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseModel, Generic[T]):
    """Uniform success envelope."""
    success: bool = True
    data: T
    meta: Optional[PaginationMeta] = None


class ErrorResponse(BaseModel):
    """Uniform error envelope."""
    success: bool = False
    error: ErrorDetail


class SuccessListResponse(BaseModel, Generic[T]):
    """Uniform success envelope for lists."""
    success: bool = True
    data: List[T]
    meta: PaginationMeta


# --- helpers ---

def ok(data: Any, meta: Optional[PaginationMeta] = None) -> Dict:
    """Shortcut to build a success dict."""
    resp: Dict[str, Any] = {"success": True, "data": data}
    if meta is not None:
        resp["meta"] = meta.model_dump()
    return resp


def ok_list(items: List, *, page: int, limit: int, total: int) -> Dict:
    """Shortcut for paginated list responses."""
    return {
        "success": True,
        "data": items,
        "meta": {"page": page, "limit": limit, "total": total},
    }


def err(code: str, message: str, details: Optional[Dict] = None) -> Dict:
    """Shortcut to build an error dict."""
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
    }
