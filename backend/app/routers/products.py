"""
routers/products.py — GET /api/products

Returns authoritative catalogue. Prices and merchant IDs come from the
database — never from client input or AI output.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product
from app.schemas import ProductRead

router = APIRouter()


@router.get("/products", response_model=list[ProductRead], tags=["catalogue"])
def list_products(db: Session = Depends(get_db)):
    """Return all active products in the demo catalogue."""
    return db.query(Product).filter(Product.active == True).all()
