import os
import qrcode
from datetime import datetime

def ensure_dirs():
    os.makedirs("qrcodes", exist_ok=True)

def upi_qr_path(upi_id: str, amount: int, note: str = "ForwardX Premium") -> str:
    ensure_dirs()
    data = f"upi://pay?pa={upi_id}&am={amount}&tn={note}"
    path = os.path.join("qrcodes", f"{amount}.png")
    if not os.path.exists(path):
        img = qrcode.make(data)
        img.save(path)
    return path

def is_premium_row(row) -> bool:
    # row = (id, username, daily_count, premium_until)
    if not row or not row[3]:
        return False
    try:
        return datetime.fromisoformat(row[3]) > datetime.utcnow()
    except Exception:
        return False
