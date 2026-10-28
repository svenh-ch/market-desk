from fastapi import APIRouter, Query
from typing import Optional
from app.services.news_service import get_news

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
def news_feed(symbol: Optional[str] = Query(default=None), limit: int = Query(default=20, ge=1, le=50)):
    return get_news(symbol=symbol, limit=limit)


@router.get("/{symbol}")
def news_for_symbol(symbol: str, limit: int = Query(default=15, ge=1, le=50)):
    return get_news(symbol=symbol, limit=limit)
