"""
seed.py — Demo catalogue and initial policy seed.

Products are fictional demo items. Prices are fixed in the database.
The AI may only recommend product IDs from this catalogue.
Run once at startup if the tables are empty.
"""
from sqlalchemy.orm import Session
from app.models import Policy, Product


# ── Demo merchants ────────────────────────────────────────────────────────────
MERCHANTS = {
    "techcore":   "TechCore Electronics",
    "homeplus":   "HomePlus Supplies",
    "officemate": "OfficeMate Pro",
}

# ── Demo catalogue (8-12 products across 3 merchants) ────────────────────────
DEMO_PRODUCTS = [
    # TechCore Electronics
    {
        "id": "tc-wireless-mouse",
        "name": "[DEMO] TechCore Wireless Mouse",
        "description": "Ergonomic wireless mouse, 2.4 GHz, 1600 DPI, 12-month battery.",
        "price_cents": 2999,   # $29.99
        "currency": "USD",
        "merchant_id": "techcore",
        "merchant_name": "TechCore Electronics",
        "features": ["Wireless 2.4 GHz", "1600 DPI", "Ergonomic design", "12-month battery"],
    },
    {
        "id": "tc-usb-hub",
        "name": "[DEMO] TechCore 7-Port USB-C Hub",
        "description": "USB-C hub with 4x USB-A, 1x HDMI, 1x SD, 1x PD charging.",
        "price_cents": 4499,   # $44.99
        "currency": "USD",
        "merchant_id": "techcore",
        "merchant_name": "TechCore Electronics",
        "features": ["4x USB-A 3.0", "HDMI 4K", "SD card reader", "100W PD pass-through"],
    },
    {
        "id": "tc-webcam-hd",
        "name": "[DEMO] TechCore 1080p Webcam",
        "description": "Full HD webcam with built-in noise-cancelling mic and auto-focus.",
        "price_cents": 5999,   # $59.99
        "currency": "USD",
        "merchant_id": "techcore",
        "merchant_name": "TechCore Electronics",
        "features": ["1080p 30fps", "Auto-focus", "Noise-cancelling mic", "Plug and play"],
    },
    {
        "id": "tc-keyboard-mech",
        "name": "[DEMO] TechCore Mechanical Keyboard",
        "description": "Compact TKL mechanical keyboard, brown switches, RGB backlight.",
        "price_cents": 7999,   # $79.99
        "currency": "USD",
        "merchant_id": "techcore",
        "merchant_name": "TechCore Electronics",
        "features": ["TKL layout", "Brown switches", "RGB backlight", "USB-C cable"],
    },
    # HomePlus Supplies
    {
        "id": "hp-desk-lamp",
        "name": "[DEMO] HomePlus LED Desk Lamp",
        "description": "Adjustable LED desk lamp, 3 colour temperatures, USB charging port.",
        "price_cents": 3499,   # $34.99
        "currency": "USD",
        "merchant_id": "homeplus",
        "merchant_name": "HomePlus Supplies",
        "features": ["3 colour temps", "5 brightness levels", "USB-A charging port", "Memory function"],
    },
    {
        "id": "hp-monitor-stand",
        "name": "[DEMO] HomePlus Monitor Stand",
        "description": "Ergonomic monitor riser with storage drawer and cable management.",
        "price_cents": 2799,   # $27.99
        "currency": "USD",
        "merchant_id": "homeplus",
        "merchant_name": "HomePlus Supplies",
        "features": ["Adjustable height", "Storage drawer", "Cable management", "Supports up to 27\""],
    },
    {
        "id": "hp-cable-organiser",
        "name": "[DEMO] HomePlus Cable Organiser Kit",
        "description": "10-piece cable management kit: clips, ties, sleeves, and box.",
        "price_cents": 1499,   # $14.99
        "currency": "USD",
        "merchant_id": "homeplus",
        "merchant_name": "HomePlus Supplies",
        "features": ["10-piece kit", "Adhesive cable clips", "Spiral wrap", "Cable box"],
    },
    # OfficeMate Pro
    {
        "id": "om-noise-headset",
        "name": "[DEMO] OfficeMate NC Headset",
        "description": "Over-ear noise-cancelling headset optimised for video calls.",
        "price_cents": 8999,   # $89.99 — intentionally over a $80 cap for demo scenario B
        "currency": "USD",
        "merchant_id": "officemate",
        "merchant_name": "OfficeMate Pro",
        "features": ["Active noise cancellation", "Boom mic", "USB + 3.5mm", "15h battery"],
    },
    {
        "id": "om-notebook-a5",
        "name": "[DEMO] OfficeMate Premium Notebook",
        "description": "A5 hardcover dotted notebook, 200 pages, lay-flat binding.",
        "price_cents": 1999,   # $19.99
        "currency": "USD",
        "merchant_id": "officemate",
        "merchant_name": "OfficeMate Pro",
        "features": ["A5 size", "Dotted grid", "200 pages", "Lay-flat binding"],
    },
    {
        "id": "om-pen-set",
        "name": "[DEMO] OfficeMate Gel Pen Set (12-pack)",
        "description": "Smooth-writing gel pens in 12 colours, 0.5 mm tip.",
        "price_cents": 1299,   # $12.99
        "currency": "USD",
        "merchant_id": "officemate",
        "merchant_name": "OfficeMate Pro",
        "features": ["12 colours", "0.5 mm tip", "Smear-resistant", "Refillable"],
    },
    # Unapproved merchant product (for demo scenario C)
    {
        "id": "shadow-gadget",
        "name": "[DEMO] ShadowTech Gadget",
        "description": "Demo product from a merchant NOT in the default approved list.",
        "price_cents": 2500,   # $25.00
        "currency": "USD",
        "merchant_id": "shadowtech",   # NOT in default approved list
        "merchant_name": "ShadowTech (unapproved demo merchant)",
        "features": ["Demo only", "Used to test merchant allowlist enforcement"],
    },
]

# ── Default policy ────────────────────────────────────────────────────────────
DEFAULT_POLICY = {
    "total_budget_cents": 10000,        # $100.00
    "max_per_order_cents": 4000,        # $40.00
    "currency": "USD",
    "approved_merchant_ids": ["techcore", "homeplus"],
    "require_approval": True,
    "successful_spend_cents": 0,
}


def seed_if_empty(db: Session) -> None:
    """Seed catalogue and policy only if the tables are empty."""
    if db.query(Product).count() == 0:
        for p in DEMO_PRODUCTS:
            product = Product(
                id=p["id"],
                name=p["name"],
                description=p["description"],
                price_cents=p["price_cents"],
                currency=p["currency"],
                merchant_id=p["merchant_id"],
                merchant_name=p["merchant_name"],
                active=True,
            )
            product.features = p["features"]
            db.add(product)
        db.commit()

    if db.query(Policy).count() == 0:
        policy = Policy(**{k: v for k, v in DEFAULT_POLICY.items() if k != "approved_merchant_ids"})
        policy.approved_merchant_ids = DEFAULT_POLICY["approved_merchant_ids"]
        db.add(policy)
        db.commit()
