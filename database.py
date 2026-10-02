import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

try:
    from sqlalchemy import create_engine
    from sqlalchemy.pool import QueuePool
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "warranty.db"

if not DB_DIR.exists():
    DB_DIR.mkdir(parents=True, exist_ok=True)

_engine = None

def get_connection_string():
    url = None
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            for k in ["DATABASE_URL", "database_url", "POSTGRES_URL", "postgres_url"]:
                if k in st.secrets:
                    url = st.secrets[k]
                    break
            if not url and "connections" in st.secrets and "postgresql" in st.secrets["connections"]:
                url = st.secrets["connections"]["postgresql"].get("url")
            if not url and "postgres" in st.secrets:
                url = st.secrets["postgres"].get("url")
    except Exception:
        pass
    if not url:
        url = os.environ.get("DATABASE_URL")
    if not url:
        return f"sqlite:///{DB_PATH}"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

def get_engine():
    global _engine
    if _engine is None:
        db_url = get_connection_string()
        if db_url.startswith("sqlite"):
            _engine = create_engine(db_url, connect_args={"check_same_thread": False})
        else:
            _engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=300,
            )
    return _engine

def is_postgres():
    return "postgresql" in get_connection_string()

class PostgresCompatibleCursor:
    def __init__(self, raw_cursor, is_pg=True):
        self._cursor = raw_cursor
        self._is_pg = is_pg

    def execute(self, query, params=None):
        if self._is_pg:
            if "?" in query:
                query = query.replace("?", "%s")
            if "INSERT OR IGNORE INTO companies (company_name)" in query:
                query = "INSERT INTO companies (company_name) VALUES (%s) ON CONFLICT (company_name) DO NOTHING"
        if params is not None:
            self._cursor.execute(query, params)
        else:
            self._cursor.execute(query)
        return self

    def executemany(self, query, params_list):
        if self._is_pg and "?" in query:
            query = query.replace("?", "%s")
        self._cursor.executemany(query, params_list)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size) if size else self._cursor.fetchmany()

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class PostgresCompatibleConnection:
    def __init__(self, raw_conn, is_pg=True):
        self._conn = raw_conn
        self._is_pg = is_pg

    def cursor(self):
        return PostgresCompatibleCursor(self._conn.cursor(), self._is_pg)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def validate_date_value(value, field_name="Date"):
    if value is None:
        raise ValueError(f"{field_name} is required.")

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{field_name} is required.")
        try:
            datetime.strptime(text, "%Y-%m-%d")
            return text
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid date in YYYY-MM-DD format.") from exc

    raise ValueError(f"{field_name} must be a valid date in YYYY-MM-DD format.")


def delete_customer(phone):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM customers
        WHERE phone = ?
        """,
        (phone,)
    )

    conn.commit()
    conn.close()


def get_connection():
    if HAS_SQLALCHEMY:
        try:
            engine = get_engine()
            raw_conn = engine.raw_connection()
            if is_postgres():
                raw_conn.autocommit = True
            return PostgresCompatibleConnection(raw_conn, is_postgres())
        except Exception:
            pass
    if not DB_DIR.exists():
        DB_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH))


def add_customer(customer_name, phone, email):
    conn = get_connection()
    cursor = conn.cursor()
    now = get_timestamp()

    cursor.execute(
        """
        INSERT INTO customers
        (phone, customer_name, email, created_at, last_updated)
        VALUES (?, ?, ?, ?, ?)
        """,
        (phone, customer_name, email, now, now)
    )

    conn.commit()
    conn.close()


def update_customer(phone, customer_name, email):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE customers
        SET customer_name = ?, email = ?, last_updated = ?
        WHERE phone = ?
        """,
        (customer_name, email, get_timestamp(), phone)
    )

    conn.commit()
    conn.close()


def get_customers():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            phone,
            customer_name,
            email,
            created_at,
            last_updated
        FROM customers
        ORDER BY customer_name
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return rows


LEGACY_COMPANY_NAMES = {"abc", "demo company"}


def is_legacy_company_name(company_name):
    return str(company_name or "").strip().lower() in LEGACY_COMPANY_NAMES


def cleanup_legacy_companies():
    conn = get_connection()
    cursor = conn.cursor()
    stale_rows = cursor.execute(
        "SELECT company_id, company_name FROM companies"
    ).fetchall()

    stale_ids = [
        company_id for company_id, company_name in stale_rows
        if is_legacy_company_name(company_name)
    ]

    for company_id in stale_ids:
        cursor.execute("DELETE FROM products WHERE company_id = ?", (company_id,))
        cursor.execute("DELETE FROM companies WHERE company_id = ?", (company_id,))

    conn.commit()
    conn.close()
    return len(stale_ids)


def get_company_id(company_name):
    if company_name is None:
        return None

    clean_name = str(company_name).strip()
    if is_legacy_company_name(clean_name):
        return None

    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT company_id FROM companies WHERE company_name = ?",
        (clean_name,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def add_company(company_name):
    clean_name = str(company_name or "").strip()
    if not clean_name or is_legacy_company_name(clean_name):
        return None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO companies (company_name) VALUES (?)",
        (clean_name,)
    )
    conn.commit()
    company_id = get_company_id(clean_name)
    conn.close()
    return company_id


def get_companies():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT company_id, company_name FROM companies ORDER BY company_name"
    ).fetchall()
    conn.close()
    return [
        (company_id, company_name)
        for company_id, company_name in rows
        if not is_legacy_company_name(company_name)
    ]


def add_company_advance(company_name, advance_date, amount_paid, payment_mode="Cash", transaction_details="", remarks="", linked_customer_advance_id=None):
    clean_company_name = str(company_name or "").strip()
    if not clean_company_name:
        raise ValueError("Company name is required.")
    if payment_mode != "Cash" and str(transaction_details or "").strip() == "":
        raise ValueError("Transaction Details is required for non-cash payment modes.")

    valid_date = validate_date_value(advance_date, "Advance Date")
    company_id = get_company_id(clean_company_name)
    if company_id is None:
        company_id = add_company(clean_company_name)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO company_advances
        (company_id, company_name, advance_date, amount_paid, payment_mode, transaction_details, remarks, linked_customer_advance_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            clean_company_name,
            valid_date,
            float(amount_paid or 0),
            payment_mode,
            str(transaction_details or "").strip(),
            str(remarks or "").strip(),
            linked_customer_advance_id,
        ),
    )
    conn.commit()
    advance_id = cursor.lastrowid
    conn.close()
    return advance_id


def update_company_advance(advance_id, company_name, advance_date, amount_paid, payment_mode="Cash", transaction_details="", remarks="", linked_customer_advance_id=None):
    clean_company_name = str(company_name or "").strip()
    if not clean_company_name:
        raise ValueError("Company name is required.")
    if payment_mode != "Cash" and str(transaction_details or "").strip() == "":
        raise ValueError("Transaction Details is required for non-cash payment modes.")

    valid_date = validate_date_value(advance_date, "Advance Date")
    company_id = get_company_id(clean_company_name)
    if company_id is None:
        company_id = add_company(clean_company_name)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE company_advances
        SET company_id = ?,
            company_name = ?,
            advance_date = ?,
            amount_paid = ?,
            payment_mode = ?,
            transaction_details = ?,
            remarks = ?,
            linked_customer_advance_id = ?
        WHERE advance_id = ?
        """,
        (
            company_id,
            clean_company_name,
            valid_date,
            float(amount_paid or 0),
            payment_mode,
            str(transaction_details or "").strip(),
            str(remarks or "").strip(),
            linked_customer_advance_id,
            advance_id,
        ),
    )
    conn.commit()
    conn.close()
    return True


def delete_company_advance(advance_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM company_advances WHERE advance_id = ?", (advance_id,))
    conn.commit()
    conn.close()
    return True


def get_company_advances():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT
            advance_id,
            company_id,
            company_name,
            advance_date,
            amount_paid,
            payment_mode,
            transaction_details,
            remarks,
            linked_customer_advance_id
        FROM company_advances
        ORDER BY advance_date DESC, company_name
        """
    ).fetchall()
    conn.close()
    return rows


def add_customer_advance(customer_phone, customer_name, company_name, payment_to, advance_date, amount_paid, payment_mode="Cash", transaction_details="", remarks=""):
    clean_phone = str(customer_phone or "").strip()
    if not clean_phone:
        raise ValueError("Customer phone is required.")
    if payment_mode not in ("Cash", "Discount") and str(transaction_details or "").strip() == "":
        raise ValueError("Transaction Details is required for non-cash payment modes.")

    clean_payment_to = str(payment_to or "").strip()
    if payment_mode == "Discount" and clean_payment_to == "Company":
        raise ValueError("Discounts must be recorded as customer credits, not paid to a company.")
    if clean_payment_to == "Company":
        clean_company_name = str(company_name or "").strip()
        if not clean_company_name:
            raise ValueError("Company name is required when payment is made to the company.")
    else:
        clean_company_name = ""

    valid_date = validate_date_value(advance_date, "Advance Date")
    customer_display_name = str(customer_name or "").strip() or clean_phone

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO customer_advances
        (customer_phone, customer_name, company_name, payment_to, advance_date, amount_paid, payment_mode, transaction_details, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clean_phone,
            customer_display_name,
            clean_company_name,
            clean_payment_to,
            valid_date,
            float(amount_paid or 0),
            payment_mode,
            str(transaction_details or "").strip(),
            str(remarks or "").strip(),
        ),
    )
    customer_advance_id = cursor.lastrowid
    conn.commit()
    conn.close()

    if clean_payment_to == "Company":
        linked_company_advance_id = add_company_advance(
            clean_company_name,
            valid_date,
            amount_paid,
            payment_mode,
            transaction_details,
            remarks + " (Auto-created from customer advance)",
            linked_customer_advance_id=customer_advance_id,
        )

        follow_up_conn = get_connection()
        follow_up_cursor = follow_up_conn.cursor()
        follow_up_cursor.execute(
            "UPDATE customer_advances SET linked_company_advance_id = ? WHERE advance_id = ?",
            (linked_company_advance_id, customer_advance_id),
        )
        follow_up_conn.commit()
        follow_up_conn.close()

    return customer_advance_id


def update_customer_advance(advance_id, customer_phone, customer_name, company_name, payment_to, advance_date, amount_paid, payment_mode="Cash", transaction_details="", remarks=""):
    clean_phone = str(customer_phone or "").strip()
    if not clean_phone:
        raise ValueError("Customer phone is required.")
    if payment_mode not in ("Cash", "Discount") and str(transaction_details or "").strip() == "":
        raise ValueError("Transaction Details is required for non-cash payment modes.")

    clean_payment_to = str(payment_to or "").strip()
    if payment_mode == "Discount" and clean_payment_to == "Company":
        raise ValueError("Discounts must be recorded as customer credits, not paid to a company.")
    clean_company_name = str(company_name or "").strip() if clean_payment_to == "Company" else ""
    if clean_payment_to == "Company" and not clean_company_name:
        raise ValueError("Company name is required when payment is made to the company.")

    valid_date = validate_date_value(advance_date, "Advance Date")
    customer_display_name = str(customer_name or "").strip() or clean_phone

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE customer_advances
        SET customer_phone = ?,
            customer_name = ?,
            company_name = ?,
            payment_to = ?,
            advance_date = ?,
            amount_paid = ?,
            payment_mode = ?,
            transaction_details = ?,
            remarks = ?
        WHERE advance_id = ?
        """,
        (
            clean_phone,
            customer_display_name,
            clean_company_name,
            clean_payment_to,
            valid_date,
            float(amount_paid or 0),
            payment_mode,
            str(transaction_details or "").strip(),
            str(remarks or "").strip(),
            advance_id,
        ),
    )
    conn.commit()
    conn.close()

    if clean_payment_to == "Company":
        current_link_conn = get_connection()
        current_link_cursor = current_link_conn.cursor()
        current_link = current_link_cursor.execute(
            "SELECT linked_company_advance_id FROM customer_advances WHERE advance_id = ?",
            (advance_id,),
        ).fetchone()
        current_link_conn.close()

        if current_link and current_link[0]:
            update_company_advance(
                current_link[0],
                clean_company_name,
                valid_date,
                amount_paid,
                payment_mode,
                transaction_details,
                str(remarks or "") + " (Updated from customer advance)",
                advance_id,
            )
        else:
            linked_company_advance_id = add_company_advance(
                clean_company_name,
                valid_date,
                amount_paid,
                payment_mode,
                transaction_details,
                str(remarks or "") + " (Auto-created from customer advance)",
                linked_customer_advance_id=advance_id,
            )
            follow_up_conn = get_connection()
            follow_up_cursor = follow_up_conn.cursor()
            follow_up_cursor.execute(
                "UPDATE customer_advances SET linked_company_advance_id = ? WHERE advance_id = ?",
                (linked_company_advance_id, advance_id),
            )
            follow_up_conn.commit()
            follow_up_conn.close()
    else:
        current_link_conn = get_connection()
        current_link_cursor = current_link_conn.cursor()
        current_link = current_link_cursor.execute(
            "SELECT linked_company_advance_id FROM customer_advances WHERE advance_id = ?",
            (advance_id,),
        ).fetchone()
        current_link_conn.close()

        if current_link and current_link[0]:
            delete_company_advance(current_link[0])
            follow_up_conn = get_connection()
            follow_up_cursor = follow_up_conn.cursor()
            follow_up_cursor.execute(
                "UPDATE customer_advances SET linked_company_advance_id = NULL WHERE advance_id = ?",
                (advance_id,),
            )
            follow_up_conn.commit()
            follow_up_conn.close()

    return True


def delete_customer_advance(advance_id):
    conn = get_connection()
    cursor = conn.cursor()
    linked_company_advance = cursor.execute(
        "SELECT linked_company_advance_id FROM customer_advances WHERE advance_id = ?",
        (advance_id,),
    ).fetchone()
    if linked_company_advance and linked_company_advance[0]:
        delete_company_advance(linked_company_advance[0])
    cursor.execute("DELETE FROM customer_advances WHERE advance_id = ?", (advance_id,))
    conn.commit()
    conn.close()
    return True


def get_customer_advances():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT
            advance_id,
            customer_phone,
            customer_name,
            company_name,
            payment_to,
            advance_date,
            amount_paid,
            payment_mode,
            transaction_details,
            remarks,
            linked_company_advance_id
        FROM customer_advances
        ORDER BY advance_date DESC, customer_name
        """
    ).fetchall()
    conn.close()
    return rows


def add_customer_outstanding(customer_phone, customer_name, month_start, outstanding_amount, remarks=""):
    clean_phone = str(customer_phone or "").strip()
    if not clean_phone:
        raise ValueError("Customer phone is required.")

    valid_month = validate_date_value(month_start, "Outstanding Month")
    clean_name = str(customer_name or "").strip() or clean_phone

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO customer_outstanding
        (customer_phone, customer_name, month_start, outstanding_amount, remarks)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            clean_phone,
            clean_name,
            valid_month,
            float(outstanding_amount or 0),
            str(remarks or "").strip(),
        ),
    )
    conn.commit()
    outstanding_id = cursor.lastrowid
    conn.close()
    return outstanding_id


def update_customer_outstanding(outstanding_id, customer_phone, customer_name, month_start, outstanding_amount, remarks=""):
    clean_phone = str(customer_phone or "").strip()
    if not clean_phone:
        raise ValueError("Customer phone is required.")

    valid_month = validate_date_value(month_start, "Outstanding Month")
    clean_name = str(customer_name or "").strip() or clean_phone

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE customer_outstanding
        SET customer_phone = ?,
            customer_name = ?,
            month_start = ?,
            outstanding_amount = ?,
            remarks = ?
        WHERE outstanding_id = ?
        """,
        (
            clean_phone,
            clean_name,
            valid_month,
            float(outstanding_amount or 0),
            str(remarks or "").strip(),
            outstanding_id,
        ),
    )
    conn.commit()
    conn.close()
    return True


def delete_customer_outstanding(outstanding_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM customer_outstanding WHERE outstanding_id = ?", (outstanding_id,))
    conn.commit()
    conn.close()
    return True


def get_customer_outstanding():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT
            outstanding_id,
            customer_phone,
            customer_name,
            month_start,
            outstanding_amount,
            remarks
        FROM customer_outstanding
        ORDER BY month_start DESC, customer_name
        """
    ).fetchall()
    conn.close()
    return rows


def add_customer_payment(customer_phone, customer_name, payment_date, amount_paid, payment_mode="Cash", transaction_details="", remarks=""):
    clean_phone = str(customer_phone or "").strip()
    if not clean_phone:
        raise ValueError("Customer phone is required.")

    valid_date = validate_date_value(payment_date, "Payment Date")
    payment_amount = float(amount_paid or 0)
    if payment_amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    conn = get_connection()
    cursor = conn.cursor()
    clean_name = str(customer_name or "").strip() or clean_phone

    if payment_mode != "Cash" and str(transaction_details or "").strip() == "":
        conn.close()
        raise ValueError("Transaction Details is required for non-cash payment modes.")

    cursor.execute(
        """
        INSERT INTO customer_outstanding
        (customer_phone, customer_name, month_start, outstanding_amount, remarks)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            clean_phone,
            clean_name,
            valid_date,
            -payment_amount,
            f"Payment: {remarks or payment_mode} | {transaction_details or 'Cash'}",
        ),
    )
    conn.commit()
    conn.close()
    return True


def get_customer_report():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT
            c.phone,
            c.customer_name,
            COALESCE(so.manual_outstanding, 0) AS manual_outstanding,
            COALESCE(s.sales_outstanding, 0) AS sales_outstanding,
            COALESCE(ca.customer_advances, 0) AS customer_advances,
            COALESCE(wc.warranty_credits, 0) AS warranty_credits,
            COALESCE(so.manual_outstanding, 0)
                + COALESCE(s.sales_outstanding, 0)
                - COALESCE(ca.customer_advances, 0)
                - COALESCE(wc.warranty_credits, 0) AS total_outstanding
        FROM customers c
        LEFT JOIN (
            SELECT
                customer_phone,
                SUM(outstanding_amount) AS manual_outstanding
            FROM customer_outstanding
            GROUP BY customer_phone
        ) so ON so.customer_phone = c.phone
        LEFT JOIN (
            SELECT
                customer_phone,
                SUM(
                    CASE
                        WHEN actual_price * COALESCE(quantity, 1) - paid_amount > 0
                        THEN actual_price * COALESCE(quantity, 1) - paid_amount
                        ELSE 0
                    END
                ) AS sales_outstanding
            FROM sales
            GROUP BY customer_phone
        ) s ON s.customer_phone = c.phone
        LEFT JOIN (
            SELECT
                customer_phone,
                SUM(amount_paid) AS customer_advances
            FROM customer_advances
            GROUP BY customer_phone
        ) ca ON ca.customer_phone = c.phone
        LEFT JOIN (
            SELECT
                customer_phone,
                SUM(warranty_value) AS warranty_credits
            FROM warranty_claims
            WHERE customer_phone IS NOT NULL
            GROUP BY customer_phone
        ) wc ON wc.customer_phone = c.phone
        WHERE so.customer_phone IS NOT NULL
            OR s.customer_phone IS NOT NULL
            OR ca.customer_phone IS NOT NULL
            OR wc.customer_phone IS NOT NULL
        ORDER BY total_outstanding DESC, c.customer_name
        """
    ).fetchall()
    conn.close()
    return rows


def _normalize_inventory_totals(qty_received, single_product_price):
    qty = float(qty_received or 0)
    unit_price = float(single_product_price or 0)
    total_price = qty * unit_price
    return qty, unit_price, total_price


def add_inventory_record(product_id, product_name, product_company, received_date, qty_received=0, single_product_price=0.0):
    valid_date = validate_date_value(received_date, "Purchase Date")
    qty, unit_price, total_price = _normalize_inventory_totals(qty_received, single_product_price)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO inventory_tracking
        (product_id, product_name, product_company, qty_received, received_date, single_product_price, overall_price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(product_id).strip(),
            product_name.strip(),
            product_company.strip(),
            int(qty),
            valid_date,
            float(unit_price),
            float(total_price),
        )
    )
    conn.commit()
    conn.close()


def update_inventory_record(inventory_id, product_id, product_name, product_company, received_date, qty_received=0, single_product_price=0.0):
    valid_date = validate_date_value(received_date, "Purchase Date")
    qty, unit_price, total_price = _normalize_inventory_totals(qty_received, single_product_price)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE inventory_tracking
        SET product_id = ?,
            product_name = ?,
            product_company = ?,
            qty_received = ?,
            received_date = ?,
            single_product_price = ?,
            overall_price = ?
        WHERE inventory_id = ?
        """,
        (
            str(product_id).strip(),
            product_name.strip(),
            product_company.strip(),
            int(qty),
            valid_date,
            float(unit_price),
            float(total_price),
            inventory_id,
        )
    )
    conn.commit()
    conn.close()


def delete_inventory_record(inventory_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM inventory_tracking WHERE inventory_id = ?",
        (inventory_id,)
    )
    conn.commit()
    conn.close()


def get_inventory_records():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT
            inventory_id,
            product_id,
            product_name,
            product_company,
            qty_received,
            received_date,
            single_product_price,
            overall_price
        FROM inventory_tracking
        ORDER BY received_date DESC, product_name
        """
    ).fetchall()
    conn.close()
    return rows


def get_inventory_products_for_sale():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT DISTINCT
            product_id,
            product_name,
            product_company
        FROM inventory_tracking
        ORDER BY product_name
        """
    ).fetchall()
    conn.close()
    return rows


def get_product_warranty_details(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT under_warranty, diameter, warranty_period_days FROM products WHERE product_id = ?",
        (str(product_id),)
    ).fetchone()
    conn.close()
    return (
        int(row[0]) if row else 0,
        float(row[1]) if row and row[1] is not None else 0.0,
        int(row[2]) if row and row[2] is not None else 0,
    )


def _calculate_sale_pending(actual_price, quantity, paid_amount):
    sale_total = float(actual_price or 0) * int(quantity or 1)
    return max(sale_total - float(paid_amount or 0), 0.0)


def add_sale(customer_phone, product_id, product_name, product_company, sale_date, actual_price, paid_amount, pending_amount,
             warranty_applicable=False, warranty_start_date=None, warranty_end_date=None, quantity=1, customer_name=None):
    valid_sale_date = validate_date_value(sale_date, "Sale Date")
    valid_warranty_start_date = validate_date_value(warranty_start_date, "Warranty Start Date") if warranty_applicable and warranty_start_date else None
    valid_warranty_end_date = validate_date_value(warranty_end_date, "Warranty End Date") if warranty_applicable and warranty_end_date else None
    valid_quantity = int(quantity or 1)
    valid_pending_amount = _calculate_sale_pending(actual_price, valid_quantity, paid_amount)

    clean_phone = str(customer_phone or "").strip()
    final_customer_name = str(customer_name or "").strip()
    conn = get_connection()
    cursor = conn.cursor()
    if not final_customer_name:
        customer_row = cursor.execute(
            "SELECT customer_name FROM customers WHERE phone = ?",
            (clean_phone,),
        ).fetchone()
        if customer_row:
            final_customer_name = str(customer_row[0] or "").strip()
    if not final_customer_name:
        final_customer_name = clean_phone

    cursor.execute(
        """
        INSERT INTO sales
        (customer_phone, customer_name, product_id, product_name, product_company, sale_date, actual_price, paid_amount, pending_amount,
         warranty_applicable, warranty_start_date, warranty_end_date, quantity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clean_phone,
            final_customer_name,
            str(product_id).strip(),
            product_name.strip(),
            product_company.strip(),
            valid_sale_date,
            float(actual_price or 0),
            float(paid_amount or 0),
            valid_pending_amount,
            int(bool(warranty_applicable)),
            valid_warranty_start_date,
            valid_warranty_end_date,
            valid_quantity,
        )
    )
    sale_id = cursor.lastrowid

    if warranty_applicable:
        cursor.execute(
            """
            INSERT INTO warranties
            (sale_id, start_date, expiry_date, status)
            VALUES (?, ?, ?, ?)
            """,
            (sale_id, valid_warranty_start_date, valid_warranty_end_date, "Active")
        )

    conn.commit()
    conn.close()


def update_sale(sale_id, customer_phone, product_id, product_name, product_company, sale_date, actual_price, paid_amount,
               pending_amount, warranty_applicable=False, warranty_start_date=None, warranty_end_date=None, quantity=1, customer_name=None):
    valid_sale_date = validate_date_value(sale_date, "Sale Date")
    valid_warranty_start_date = validate_date_value(warranty_start_date, "Warranty Start Date") if warranty_applicable and warranty_start_date else None
    valid_warranty_end_date = validate_date_value(warranty_end_date, "Warranty End Date") if warranty_applicable and warranty_end_date else None
    valid_quantity = int(quantity or 1)
    valid_pending_amount = _calculate_sale_pending(actual_price, valid_quantity, paid_amount)

    clean_phone = str(customer_phone or "").strip()
    final_customer_name = str(customer_name or "").strip()
    conn = get_connection()
    cursor = conn.cursor()
    if not final_customer_name:
        customer_row = cursor.execute(
            "SELECT customer_name FROM customers WHERE phone = ?",
            (clean_phone,),
        ).fetchone()
        if customer_row:
            final_customer_name = str(customer_row[0] or "").strip()
    if not final_customer_name:
        final_customer_name = clean_phone

    cursor.execute(
        """
        UPDATE sales
        SET customer_phone = ?,
            customer_name = ?,
            product_id = ?,
            product_name = ?,
            product_company = ?,
            sale_date = ?,
            actual_price = ?,
            paid_amount = ?,
            pending_amount = ?,
            warranty_applicable = ?,
            warranty_start_date = ?,
            warranty_end_date = ?,
            quantity = ?
        WHERE sale_id = ?
        """,
        (
            clean_phone,
            final_customer_name,
            str(product_id).strip(),
            product_name.strip(),
            product_company.strip(),
            valid_sale_date,
            float(actual_price or 0),
            float(paid_amount or 0),
            valid_pending_amount,
            int(bool(warranty_applicable)),
            valid_warranty_start_date,
            valid_warranty_end_date,
            valid_quantity,
            sale_id
        )
    )

    cursor.execute("DELETE FROM warranties WHERE sale_id = ?", (sale_id,))
    if warranty_applicable:
        cursor.execute(
            """
            INSERT INTO warranties
            (sale_id, start_date, expiry_date, status)
            VALUES (?, ?, ?, ?)
            """,
            (sale_id, valid_warranty_start_date, valid_warranty_end_date, "Active")
        )

    conn.commit()
    conn.close()


def delete_sale(sale_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM warranties WHERE sale_id = ?", (sale_id,))
    cursor.execute("DELETE FROM sales WHERE sale_id = ?", (sale_id,))
    conn.commit()
    conn.close()


def get_sales():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT
            sale_id,
            customer_phone,
            customer_name,
            product_id,
            product_name,
            product_company,
            sale_date,
            actual_price,
            paid_amount,
            CASE
                WHEN actual_price * COALESCE(quantity, 1) - paid_amount > 0
                THEN actual_price * COALESCE(quantity, 1) - paid_amount
                ELSE 0
            END AS pending_amount,
            warranty_applicable,
            warranty_start_date,
            warranty_end_date,
            quantity
        FROM sales
        ORDER BY sale_date DESC, product_name
        """
    ).fetchall()
    conn.close()
    return rows


def update_company(company_id, company_name):
    clean_name = (company_name or "").strip()
    if not clean_name:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE companies SET company_name = ? WHERE company_id = ?",
        (clean_name, company_id)
    )
    conn.commit()
    conn.close()
    return True


def delete_company(company_id):
    conn = get_connection()
    cursor = conn.cursor()
    linked_products = cursor.execute(
        "SELECT COUNT(*) FROM products WHERE company_id = ?",
        (company_id,)
    ).fetchone()[0]

    if linked_products > 0:
        conn.close()
        return False

    cursor.execute(
        "DELETE FROM companies WHERE company_id = ?",
        (company_id,)
    )
    conn.commit()
    conn.close()
    return True


def add_product(company_name, product_name, sold_by_product_name, product_type, diameter, under_warranty, warranty_period_days, sale_price=0.0):
    company_id = get_company_id(company_name)
    if company_id is None:
        company_id = add_company(company_name)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO products
        (company_id, product_name, sold_by_product_name, product_type, diameter, under_warranty, warranty_period_days, sale_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (company_id, product_name, sold_by_product_name, product_type, diameter, int(bool(under_warranty)), int(warranty_period_days or 0), float(sale_price or 0))
    )

    conn.commit()
    conn.close()


def update_product(product_id, company_name, product_name, sold_by_product_name, product_type, diameter, under_warranty, warranty_period_days, sale_price=0.0):
    company_id = get_company_id(company_name)
    if company_id is None:
        company_id = add_company(company_name)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE products
        SET company_id = ?,
            product_name = ?,
            sold_by_product_name = ?,
            product_type = ?,
            diameter = ?,
            under_warranty = ?,
            warranty_period_days = ?,
            sale_price = ?
        WHERE product_id = ?
        """,
        (company_id, product_name, sold_by_product_name, product_type, diameter, int(bool(under_warranty)), int(warranty_period_days or 0), float(sale_price or 0), product_id)
    )

    conn.commit()
    conn.close()


def delete_product(product_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM products
        WHERE product_id = ?
        """,
        (product_id,)
    )

    conn.commit()
    conn.close()


def get_products():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            p.product_id,
            c.company_name,
            p.product_name,
            p.sold_by_product_name,
            p.product_type,
            p.diameter,
            p.under_warranty,
            p.warranty_period_days,
            p.sale_price
        FROM products p
        JOIN companies c ON c.company_id = p.company_id
        ORDER BY p.product_name
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return rows


def get_product_sale_price(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT sale_price FROM products WHERE product_id = ?",
        (str(product_id),)
    ).fetchone()
    conn.close()
    return float(row[0]) if row and row[0] is not None else 0.0


def add_warranty_claim(product_id, product_name, company_name, initial_mm, current_mm, sale_price, warranty_limit_mm, warranty_value, claim_date=None, customer_phone=None, customer_name=None):
    valid_date = validate_date_value(claim_date or datetime.now().date(), "Claim Date")
    clean_customer_phone = str(customer_phone or "").strip()
    if not clean_customer_phone:
        raise ValueError("Customer is required.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO warranty_claims
        (product_id, product_name, company_name, initial_mm, current_mm, sale_price, warranty_limit_mm, warranty_value, claim_date, customer_phone, customer_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(product_id).strip(),
            str(product_name or "").strip(),
            str(company_name or "").strip(),
            float(initial_mm or 0),
            float(current_mm or 0),
            float(sale_price or 0),
            float(warranty_limit_mm or 0),
            float(warranty_value or 0),
            valid_date,
            clean_customer_phone,
            str(customer_name or "").strip(),
        ),
    )
    conn.commit()
    claim_id = cursor.lastrowid
    conn.close()
    return claim_id


def get_warranty_claims():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT
            claim_id,
            product_id,
            product_name,
            company_name,
            initial_mm,
            current_mm,
            sale_price,
            warranty_limit_mm,
            warranty_value,
            claim_date,
            customer_phone,
            customer_name
        FROM warranty_claims
        ORDER BY claim_date DESC, product_name
        """
    ).fetchall()
    conn.close()
    return rows


def delete_warranty_claim(claim_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM warranty_claims WHERE claim_id = ?",
        (claim_id,)
    )
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()
    if is_postgres():
        conn.close()
        return

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        phone TEXT PRIMARY KEY,
        customer_name TEXT NOT NULL,
        email TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("PRAGMA table_info(customers)")
    columns = [row[1] for row in cursor.fetchall()]

    if columns and ("customer_id" in columns or "created_at" not in columns or "last_updated" not in columns):
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers_migration (
            phone TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            email TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        INSERT OR IGNORE INTO customers_migration
        (phone, customer_name, email, created_at, last_updated)
        SELECT
            COALESCE(phone, 'TEMP_' || customer_id),
            customer_name,
            email,
            datetime('now'),
            datetime('now')
        FROM customers
        """)

        cursor.execute("DROP TABLE customers")
        cursor.execute("ALTER TABLE customers_migration RENAME TO customers")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        company_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_advances (
        advance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        company_name TEXT NOT NULL,
        advance_date TEXT NOT NULL,
        amount_paid REAL NOT NULL DEFAULT 0,
        payment_mode TEXT NOT NULL DEFAULT 'Cash',
        transaction_details TEXT,
        remarks TEXT,
        linked_customer_advance_id INTEGER,
        FOREIGN KEY (company_id) REFERENCES companies(company_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_advances (
        advance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_phone TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        company_name TEXT,
        payment_to TEXT NOT NULL CHECK(payment_to IN ('Us', 'Company')),
        advance_date TEXT NOT NULL,
        amount_paid REAL NOT NULL DEFAULT 0,
        payment_mode TEXT NOT NULL DEFAULT 'Cash',
        transaction_details TEXT,
        remarks TEXT,
        linked_company_advance_id INTEGER,
        FOREIGN KEY (customer_phone) REFERENCES customers(phone)
    )
    """)

    cleanup_legacy_companies()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_tracking (
        inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        product_company TEXT NOT NULL,
        qty_received INTEGER NOT NULL DEFAULT 0,
        received_date TEXT NOT NULL,
        single_product_price REAL NOT NULL DEFAULT 0,
        overall_price REAL NOT NULL DEFAULT 0
    )
    """)

    cursor.execute("PRAGMA table_info(inventory_tracking)")
    inventory_columns = cursor.fetchall()
    if inventory_columns:
        column_names = [col[1] for col in inventory_columns]
        has_received_date = "received_date" in column_names
        has_incoming_date = "incoming_date" in column_names
        has_qty_received = "qty_received" in column_names
        has_single_product_price = "single_product_price" in column_names
        has_overall_price = "overall_price" in column_names
        has_incoming_price = "incoming_price" in column_names
        has_product_id_text_type = next((col[2] for col in inventory_columns if col[1] == "product_id"), "").upper().startswith("INT")

        if (not has_received_date and has_incoming_date) or (not has_qty_received or not has_single_product_price or not has_overall_price) or has_product_id_text_type:
            cursor.execute("ALTER TABLE inventory_tracking RENAME TO inventory_tracking_old")
            old_columns = [col[1] for col in cursor.execute("PRAGMA table_info(inventory_tracking_old)").fetchall()]
            qty_expr = "qty_received" if "qty_received" in old_columns else "1"
            date_expr = "received_date" if "received_date" in old_columns else ("incoming_date" if "incoming_date" in old_columns else "CURRENT_DATE")
            unit_price_expr = "single_product_price" if "single_product_price" in old_columns else ("incoming_price" if "incoming_price" in old_columns else "0")
            total_expr = "overall_price" if "overall_price" in old_columns else f"(COALESCE({qty_expr}, 1) * COALESCE({unit_price_expr}, 0))"
            if "overall_price" not in old_columns and "single_product_price" not in old_columns and "incoming_price" not in old_columns:
                total_expr = "0"

            cursor.execute("""
            CREATE TABLE inventory_tracking (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_company TEXT NOT NULL,
                qty_received INTEGER NOT NULL DEFAULT 0,
                received_date TEXT NOT NULL,
                single_product_price REAL NOT NULL DEFAULT 0,
                overall_price REAL NOT NULL DEFAULT 0
            )
            """)
            cursor.execute(f"""
            INSERT INTO inventory_tracking
            (inventory_id, product_id, product_name, product_company, qty_received, received_date, single_product_price, overall_price)
            SELECT
                inventory_id,
                CAST(product_id AS TEXT),
                product_name,
                product_company,
                CAST(COALESCE({qty_expr}, 1) AS INTEGER),
                {date_expr},
                CAST(COALESCE({unit_price_expr}, 0) AS REAL),
                CAST(COALESCE({total_expr}, 0) AS REAL)
            FROM inventory_tracking_old
            """)
            cursor.execute("DROP TABLE inventory_tracking_old")

    cursor.execute("PRAGMA table_info(products)")
    product_columns = [row[1] for row in cursor.fetchall()]

    if product_columns and "sale_price" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN sale_price REAL NOT NULL DEFAULT 0")

    if product_columns and "company_id" not in product_columns:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products_new (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            sold_by_product_name TEXT,
            product_type TEXT CHECK(product_type IN ('Normal', 'Special', 'Drilling')),
            diameter TEXT,
            under_warranty INTEGER NOT NULL DEFAULT 0,
            warranty_period_days INTEGER DEFAULT 0,
            sale_price REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
        """)

        old_rows = cursor.execute(
            "SELECT product_id, company_name, product_name, sold_by_product_name, diameter FROM products"
        ).fetchall()

        for _, company_name, product_name, sold_by_product_name, diameter in old_rows:
            company_id = get_company_id(company_name)
            if company_id is None:
                company_id = add_company(company_name)
            cursor.execute(
                """
                INSERT INTO products_new
                (company_id, product_name, sold_by_product_name, product_type, diameter, under_warranty, warranty_period_days, sale_price)
                VALUES (?, ?, ?, 'Normal', ?, 0, 0, 0)
                """,
                (company_id, product_name, sold_by_product_name, diameter)
            )

        cursor.execute("DROP TABLE products")
        cursor.execute("ALTER TABLE products_new RENAME TO products")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        sold_by_product_name TEXT,
        product_type TEXT CHECK(product_type IN ('Normal', 'Special', 'Drilling')),
        diameter TEXT,
        under_warranty INTEGER NOT NULL DEFAULT 0,
        warranty_period_days INTEGER DEFAULT 0,
        sale_price REAL NOT NULL DEFAULT 0,
        FOREIGN KEY (company_id) REFERENCES companies(company_id)
    )
    """)

    cursor.execute("PRAGMA table_info(products)")
    product_columns = [row[1] for row in cursor.fetchall()]
    if product_columns and "sale_price" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN sale_price REAL NOT NULL DEFAULT 0")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_outstanding (
        outstanding_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_phone TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        month_start TEXT NOT NULL,
        outstanding_amount REAL NOT NULL DEFAULT 0,
        remarks TEXT,
        FOREIGN KEY (customer_phone) REFERENCES customers(phone)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_phone TEXT NOT NULL,
        customer_name TEXT NOT NULL DEFAULT '',
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        product_company TEXT NOT NULL,
        sale_date TEXT NOT NULL,
        actual_price REAL NOT NULL DEFAULT 0,
        paid_amount REAL NOT NULL DEFAULT 0,
        pending_amount REAL NOT NULL DEFAULT 0,
        warranty_applicable INTEGER NOT NULL DEFAULT 0,
        warranty_start_date TEXT,
        warranty_end_date TEXT,
        quantity INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (customer_phone) REFERENCES customers(phone)
    )
    """)

    cursor.execute("PRAGMA table_info(sales)")
    sales_columns = [row[1] for row in cursor.fetchall()]
    if sales_columns and "customer_name" not in sales_columns:
        cursor.execute("ALTER TABLE sales ADD COLUMN customer_name TEXT NOT NULL DEFAULT ''")
    if sales_columns and "quantity" not in sales_columns:
        cursor.execute("ALTER TABLE sales ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")

    if sales_columns and not all(column in sales_columns for column in [
        "product_name",
        "product_company",
        "actual_price",
        "paid_amount",
        "pending_amount",
        "warranty_applicable",
        "warranty_start_date",
        "warranty_end_date"
    ]):
        cursor.execute("ALTER TABLE sales RENAME TO sales_old")
        cursor.execute("""
        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone TEXT NOT NULL,
            customer_name TEXT NOT NULL DEFAULT '',
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            product_company TEXT NOT NULL,
            sale_date TEXT NOT NULL,
            actual_price REAL NOT NULL DEFAULT 0,
            paid_amount REAL NOT NULL DEFAULT 0,
            pending_amount REAL NOT NULL DEFAULT 0,
            warranty_applicable INTEGER NOT NULL DEFAULT 0,
            warranty_start_date TEXT,
            warranty_end_date TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (customer_phone) REFERENCES customers(phone)
        )
        """)

        cursor.execute("PRAGMA table_info(sales_old)")
        old_sales_columns = [row[1] for row in cursor.fetchall()]

        if "customer_phone" in old_sales_columns:
            old_rows = cursor.execute(
                """
                SELECT
                    sale_id,
                    customer_phone,
                    product_id,
                    sale_date,
                    sale_price
                FROM sales_old
                """
            ).fetchall()
        else:
            old_rows = cursor.execute(
                """
                SELECT
                    sale_id,
                    product_id,
                    sale_date,
                    sale_price
                FROM sales_old
                """
            ).fetchall()

        for row in old_rows:
            if len(row) == 5:
                sale_id, customer_phone, product_id, sale_date, sale_price = row
            else:
                sale_id, product_id, sale_date, sale_price = row
                customer_phone = ""

            customer_name = ""
            if customer_phone:
                customer_name_row = cursor.execute(
                    "SELECT customer_name FROM customers WHERE phone = ?",
                    (customer_phone,),
                ).fetchone()
                if customer_name_row:
                    customer_name = customer_name_row[0]

            product_name = ""
            product_company = ""
            product_row = cursor.execute(
                "SELECT product_name, company_id FROM products WHERE product_id = ?",
                (str(product_id),)
            ).fetchone()
            if product_row:
                product_name = product_row[0]
                company_row = cursor.execute(
                    "SELECT company_name FROM companies WHERE company_id = ?",
                    (product_row[1],)
                ).fetchone()
                if company_row:
                    product_company = company_row[0]

            cursor.execute(
                """
                INSERT INTO sales
                (sale_id, customer_phone, customer_name, product_id, product_name, product_company, sale_date, actual_price, paid_amount,
                 pending_amount, warranty_applicable, warranty_start_date, warranty_end_date, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 0, NULL, NULL, 1)
                """,
                (
                    sale_id,
                    customer_phone,
                    customer_name,
                    str(product_id),
                    product_name,
                    product_company,
                    sale_date,
                    float(sale_price or 0),
                    float(sale_price or 0)
                )
            )

        cursor.execute("DROP TABLE sales_old")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warranties (
        warranty_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER,
        start_date TEXT,
        expiry_date TEXT,
        status TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warranty_claims (
        claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        company_name TEXT NOT NULL,
        initial_mm REAL NOT NULL DEFAULT 0,
        current_mm REAL NOT NULL DEFAULT 0,
        sale_price REAL NOT NULL DEFAULT 0,
        warranty_limit_mm REAL NOT NULL DEFAULT 0,
        warranty_value REAL NOT NULL DEFAULT 0,
        claim_date TEXT NOT NULL,
        customer_phone TEXT,
        customer_name TEXT
    )
    """)

    warranty_claim_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(warranty_claims)").fetchall()
    }
    if "customer_phone" not in warranty_claim_columns:
        cursor.execute("ALTER TABLE warranty_claims ADD COLUMN customer_phone TEXT")
    if "customer_name" not in warranty_claim_columns:
        cursor.execute("ALTER TABLE warranty_claims ADD COLUMN customer_name TEXT")

    cursor.execute("SELECT COUNT(*) FROM companies")
    if cursor.fetchone()[0] == 0:
        pass

    conn.commit()
    conn.close()


if __name__ == "__main__":
    initialize_database()
    print("Database Created Successfully")