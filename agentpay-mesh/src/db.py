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


def initialize_orders_db(path: Union[str, Path] = DB_PATH):
    conn = _open_connection(path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            invoice_id TEXT UNIQUE,
            product_id TEXT,
            quantity INTEGER,
            buyer_agent_id TEXT,
            thread_id TEXT,
            shipping_address TEXT,
            payment_payload TEXT,
            price_drops INTEGER,
            amount_xrp REAL,
            merchant_address TEXT,
            tx_hash TEXT,
            status TEXT,
            note TEXT
        )
        """
    )
    cursor.execute("PRAGMA table_info(pending_orders)")
    columns = [row[1] for row in cursor.fetchall()]
    if "thread_id" not in columns:
        cursor.execute("ALTER TABLE pending_orders ADD COLUMN thread_id TEXT")
    if "payment_payload" not in columns:
        cursor.execute("ALTER TABLE pending_orders ADD COLUMN payment_payload TEXT")
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


def insert_pending_order(entry: dict, path: Union[str, Path] = DB_PATH):
    conn = _open_connection(path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO pending_orders (
            created_at, invoice_id, product_id, quantity, buyer_agent_id, thread_id,
            shipping_address, payment_payload, price_drops, amount_xrp, merchant_address, status, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["created_at"],
            entry["invoice_id"],
            entry["product_id"],
            entry["quantity"],
            entry["buyer_agent_id"],
            entry.get("thread_id"),
            entry["shipping_address"],
            entry.get("payment_payload", ""),
            entry["price_drops"],
            entry["amount_xrp"],
            entry["merchant_address"],
            entry["status"],
            entry.get("note", ""),
        ),
    )
    conn.commit()
    conn.close()


def fetch_order_by_invoice(invoice_id: str, path: Union[str, Path] = DB_PATH):
    conn = _open_connection(path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT invoice_id, product_id, quantity, buyer_agent_id, shipping_address, payment_payload, price_drops, amount_xrp, merchant_address, tx_hash, status, note, created_at, thread_id FROM pending_orders WHERE invoice_id = ?",
        (invoice_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "invoice_id": row[0],
        "product_id": row[1],
        "quantity": row[2],
        "buyer_agent_id": row[3],
        "shipping_address": row[4],
        "payment_payload": row[5],
        "price_drops": row[6],
        "amount_xrp": row[7],
        "merchant_address": row[8],
        "tx_hash": row[9],
        "status": row[10],
        "note": row[11],
        "created_at": row[12],
        "thread_id": row[13],
    }


def fetch_pending_orders(path: Union[str, Path] = DB_PATH):
    conn = _open_connection(path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT invoice_id, product_id, quantity, buyer_agent_id, shipping_address, payment_payload, price_drops, amount_xrp, merchant_address, tx_hash, status, note, created_at, thread_id FROM pending_orders ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "invoice_id": row[0],
            "product_id": row[1],
            "quantity": row[2],
            "buyer_agent_id": row[3],
            "shipping_address": row[4],
            "payment_payload": row[5],
            "price_drops": row[6],
            "amount_xrp": row[7],
            "merchant_address": row[8],
            "tx_hash": row[9],
            "status": row[10],
            "note": row[11],
            "created_at": row[12],
            "thread_id": row[13],
        }
        for row in rows
    ]


def update_order_status(invoice_id: str, status: str, tx_hash: str | None = None, note: str | None = None, path: Union[str, Path] = DB_PATH):
    conn = _open_connection(path)
    cursor = conn.cursor()
    fields = ["status"]
    params = [status]
    if tx_hash is not None:
        fields.append("tx_hash")
        params.append(tx_hash)
    if note is not None:
        fields.append("note")
        params.append(note)
    params.append(invoice_id)

    cursor.execute(
        f"UPDATE pending_orders SET {', '.join(field + ' = ?' for field in fields)} WHERE invoice_id = ?",
        tuple(params),
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
