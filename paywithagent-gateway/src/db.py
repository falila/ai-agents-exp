import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Union

DB_PATH = Path(__file__).parent / "merchant_history.db"


def _open_connection(path: Union[str, Path] = DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path, timeout=10)


def initialize_history_db(path: Union[str, Path] = DB_PATH):
    conn = _open_connection(path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS merchant_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            thread_id TEXT,
            invoice_id TEXT,
            product_id TEXT,
            price_drops INTEGER,
            amount_xrp REAL,
            merchant_address TEXT,
            tx_hash TEXT,
            status TEXT,
            webhook_url TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def record_transaction(entry: dict, path: Union[str, Path] = DB_PATH):
    conn = _open_connection(path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO merchant_transactions (
            created_at, thread_id, invoice_id, product_id, price_drops, amount_xrp,
            merchant_address, tx_hash, status, webhook_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["created_at"],
            entry.get("thread_id"),
            entry.get("invoice_id"),
            entry.get("product_id"),
            entry.get("price_drops"),
            entry.get("amount_xrp"),
            entry.get("merchant_address"),
            entry.get("tx_hash"),
            entry.get("status"),
            entry.get("webhook_url"),
        ),
    )
    conn.commit()
    conn.close()


def fetch_transaction_history(path: Union[str, Path] = DB_PATH):
    conn = _open_connection(path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT created_at, thread_id, invoice_id, product_id, price_drops, amount_xrp, merchant_address, tx_hash, status, webhook_url"
        " FROM merchant_transactions ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def record_settlement_history(
    frozen: dict,
    tx_hash: str,
    webhook_url: str,
    thread_id: str,
    merchant_address: str,
    path: Union[str, Path] = DB_PATH,
):
    if not frozen:
        return

    entry = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "thread_id": thread_id,
        "invoice_id": frozen.get("invoice_id"),
        "product_id": frozen.get("target_product_id"),
        "price_drops": frozen.get("price_drops"),
        "amount_xrp": (frozen.get("price_drops", 0) or 0) / 1_000_000,
        "merchant_address": merchant_address,
        "tx_hash": tx_hash or "",
        "status": "SETTLED" if tx_hash else "RELEASED",
        "webhook_url": webhook_url or "",
    }
    record_transaction(entry, path=path)
