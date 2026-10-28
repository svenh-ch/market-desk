from fastapi import APIRouter
from app.services import supply_chain

router = APIRouter(prefix="/api/relationships", tags=["relationships"])


@router.get("/{symbol}")
def get_relationships(symbol: str):
    """
    Lieferkette aus offiziellen Berichten (nur belegte Verbindungen).
    Beim ersten Aufruf wird im Hintergrund ausgewertet (status 'running').
    """
    return supply_chain.get_or_start(symbol)
