"""
setup_db.py — PharmaDash PostgreSQL Setup Script
=================================================
Run this ONCE before starting the dashboard:

    python setup_db.py

What it does:
  1. Reads DB credentials from .env
  2. Connects to PostgreSQL and creates the 'pharma_dash' database if missing
  3. Creates 5 tables (drops & recreates to stay idempotent)
  4. Imports all CSV data into the tables
  5. Creates indexes on high-cardinality filter columns
  6. Prints a row-count summary

Re-running is safe — tables are dropped and recreated each time.
"""

import os
import sys
# Configure stdout/stderr to use UTF-8 to prevent encoding errors on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import time
import psycopg2
import pandas as pd
from psycopg2 import sql
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# ── Load credentials from .env ─────────────────────────────────────────────────
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "pharma_dash")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── CSV file paths ─────────────────────────────────────────────────────────────
CSV_FILES = {
    "fact_sales":     "Fact_Sales_20k.csv",
    "fact_stock":     "Fact_Stock_20k.csv",
    "dim_products":   "Dim_Products_20k.csv",
    "dim_store":      "Dim_Store.csv",
    "dim_suppliers":  "Dim_Suppliers_20k.csv",
}

# ── DDL: Explicit table schemas with correct types ─────────────────────────────
TABLE_DDL = {
    "fact_sales": """
        CREATE TABLE fact_sales (
            "TransactionID"  VARCHAR(50)    PRIMARY KEY,
            "Date"           DATE           NOT NULL,
            "ProductID"      VARCHAR(50),
            "Store_ID"       VARCHAR(50),
            "Medicine_Name"  VARCHAR(255),
            "Category"       VARCHAR(100),
            "QuantitySold"   NUMERIC(10,2),
            "UnitPrice"      NUMERIC(10,4),
            "TotalAmount"    NUMERIC(12,4),
            "CustomerType"   VARCHAR(50)
        );
    """,
    "fact_stock": """
        CREATE TABLE fact_stock (
            "StockID"        VARCHAR(50)    PRIMARY KEY,
            "ProductID"      VARCHAR(50),
            "Store_ID"       VARCHAR(50),
            "SupplierID"     VARCHAR(50),
            "BatchNumber"    VARCHAR(100),
            "QuantityOnHand" NUMERIC(10,2),
            "ExpiryDate"     DATE,
            "DaysToExpiry"   NUMERIC(8,2),
            "ExpiryStatus"   VARCHAR(50)
        );
    """,
    "dim_products": """
        CREATE TABLE dim_products (
            "ProductID"    VARCHAR(50)  PRIMARY KEY,
            "ProductName"  VARCHAR(255),
            "Category"     VARCHAR(100),
            "UnitCost"     NUMERIC(10,4),
            "RetailPrice"  NUMERIC(10,4),
            "ReorderPoint" NUMERIC(10,2),
            "SafetyStock"  NUMERIC(10,2)
        );
    """,
    "dim_store": """
        CREATE TABLE dim_store (
            "Store_ID"   VARCHAR(50)  PRIMARY KEY,
            "Store_Name" VARCHAR(255),
            "Location"   VARCHAR(255),
            "Latitude"   NUMERIC(10,6),
            "Longitude"  NUMERIC(10,6)
        );
    """,
    "dim_suppliers": """
        CREATE TABLE dim_suppliers (
            "SupplierID"     VARCHAR(50)  PRIMARY KEY,
            "Supplier_Name"  VARCHAR(255),
            "QualityRating"  NUMERIC(4,2),
            "LeadTimeDays"   NUMERIC(5,1),
            "ContactInfo"    VARCHAR(255),
            "Category"       VARCHAR(100)
        );
    """,
}

# ── Indexes for fast dashboard filtering ───────────────────────────────────────
INDEXES = [
    'CREATE INDEX IF NOT EXISTS idx_sales_date       ON fact_sales ("Date");',
    'CREATE INDEX IF NOT EXISTS idx_sales_store      ON fact_sales ("Store_ID");',
    'CREATE INDEX IF NOT EXISTS idx_sales_product    ON fact_sales ("ProductID");',
    'CREATE INDEX IF NOT EXISTS idx_sales_category   ON fact_sales ("Category");',
    'CREATE INDEX IF NOT EXISTS idx_stock_store      ON fact_stock ("Store_ID");',
    'CREATE INDEX IF NOT EXISTS idx_stock_product    ON fact_stock ("ProductID");',
    'CREATE INDEX IF NOT EXISTS idx_stock_supplier   ON fact_stock ("SupplierID");',
    'CREATE INDEX IF NOT EXISTS idx_stock_expiry     ON fact_stock ("ExpiryStatus");',
]


def _banner(msg: str) -> None:
    print(f"\n{'─' * 60}\n  {msg}\n{'─' * 60}")


def ensure_database_exists() -> None:
    """Connect to the default 'postgres' DB and create pharma_dash if missing."""
    _banner("Step 1 — Ensuring database exists")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname="postgres",
        user=DB_USER, password=DB_PASS,
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
    if cur.fetchone():
        print(f"  ✅ Database '{DB_NAME}' already exists.")
    else:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
        print(f"  ✅ Database '{DB_NAME}' created.")
    cur.close()
    conn.close()


def build_engine():
    """Return a SQLAlchemy engine connected to pharma_dash."""
    from urllib.parse import quote_plus
    url = f"postgresql+psycopg2://{DB_USER}:{quote_plus(DB_PASS)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url, pool_pre_ping=True)


def create_tables(engine) -> None:
    """Drop existing tables (if any) and recreate with correct schema."""
    _banner("Step 2 — Creating tables")
    drop_order = [
        "fact_sales", "fact_stock",
        "dim_products", "dim_store", "dim_suppliers",
    ]
    with engine.connect() as conn:
        for tbl in drop_order:
            conn.execute(text(f'DROP TABLE IF EXISTS "{tbl}" CASCADE;'))
            print(f"  🗑️  Dropped (if existed): {tbl}")
        conn.commit()

        for tbl, ddl in TABLE_DDL.items():
            conn.execute(text(ddl))
            print(f"  ✅ Created: {tbl}")
        conn.commit()


def load_csv_to_table(engine, table: str, csv_file: str) -> int:
    """Read a CSV and bulk-insert into the given table. Returns row count."""
    fpath = os.path.join(BASE_DIR, csv_file)
    if not os.path.exists(fpath):
        print(f"  ❌ CSV not found: {fpath}")
        sys.exit(1)

    df = pd.read_csv(fpath)

    # ── Date coercion ────────────────────────────────────────────────────────
    for date_col in ["Date", "ExpiryDate", "LastDeliveryDate"]:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], dayfirst=False, errors="coerce")

    # ── Align columns to only those declared in DDL ──────────────────────────
    # Keeps only columns that exist in both the CSV and the table schema
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :tbl ORDER BY ordinal_position;"
            ),
            {"tbl": table},
        )
        db_cols = [row[0] for row in result]

    df = df[[c for c in df.columns if c in db_cols]]

    # ── Bulk insert via pandas to_sql ────────────────────────────────────────
    df.to_sql(
        table, engine,
        if_exists="append",   # table already empty; append = fast path
        index=False,
        method="multi",       # batched INSERT for speed
        chunksize=1000,
    )
    return len(df)


def import_all_csvs(engine) -> None:
    """Load all 5 CSV files into their corresponding tables."""
    _banner("Step 3 — Importing CSV data")
    total_rows = 0
    for table, csv_file in CSV_FILES.items():
        t0 = time.perf_counter()
        rows = load_csv_to_table(engine, table, csv_file)
        elapsed = time.perf_counter() - t0
        total_rows += rows
        print(f"  ✅ {table:<20}  {rows:>6,} rows  ({elapsed:.1f}s)")
    print(f"\n  📦 Total rows imported: {total_rows:,}")


def create_indexes(engine) -> None:
    """Create performance indexes on filtered columns."""
    _banner("Step 4 — Creating indexes")
    with engine.connect() as conn:
        for idx_sql in INDEXES:
            conn.execute(text(idx_sql))
            # Extract index name for display
            idx_name = idx_sql.split("INDEX IF NOT EXISTS ")[1].split(" ")[0]
            print(f"  ✅ {idx_name}")
        conn.commit()


def verify_counts(engine) -> None:
    """Print row counts for all tables as final verification."""
    _banner("Step 5 — Verification")
    with engine.connect() as conn:
        for table in CSV_FILES:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}";')).scalar()
            print(f"  📊 {table:<20}  {count:>6,} rows")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║       PharmaDash — PostgreSQL Database Setup             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"\n  Host    : {DB_HOST}:{DB_PORT}")
    print(f"  Database: {DB_NAME}")
    print(f"  User    : {DB_USER}")

    try:
        ensure_database_exists()
        engine = build_engine()
        create_tables(engine)
        import_all_csvs(engine)
        create_indexes(engine)
        verify_counts(engine)
        engine.dispose()
    except psycopg2.OperationalError as e:
        print(f"\n❌ Could not connect to PostgreSQL:\n   {e}")
        print("\n   Check that:")
        print("   • PostgreSQL is running  (pg_ctl status)")
        print("   • DB_HOST / DB_PORT are correct in .env")
        print("   • DB_USER / DB_PASSWORD are correct in .env")
        sys.exit(1)

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  ✅ Database ready — run  streamlit run pharma.py        ║")
    print("╚══════════════════════════════════════════════════════════╝\n")
