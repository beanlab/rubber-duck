from typing import Optional, Any
from pydantic import BaseModel


class CanonicalCacheKey(BaseModel):
    dataset: str
    columns: list[str] = []
    analysis: Optional[str] = None
    parameters: dict[str, Any] = {}
    plot_type: Optional[str] = None
    special_requests: Optional[list[str]] = []
