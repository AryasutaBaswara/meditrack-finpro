import csv
import asyncio
import logging
import os
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text, insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 💡 Import Configuration & Model from the app
from app.core.config import settings
from app.db.models.drug import Drug

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bulk_seeder")

# 💡 Path relatif ke folder root/data
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_FILE = os.path.join(
    os.path.dirname(os.path.dirname(BASE_DIR)), "data", "drugs-dataset.csv"
)


async def bulk_seed():
    """Mengimpor 50.000 data obat dari CSV ke PostgreSQL dengan gaya High-Performance."""

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    logger.info("🚀 Memulai proses seeding 50.000 data...")

    try:
        async with async_session() as session:
            # 1. 🛡️ MATIKAN TRIGGER (Agar tidak 50k HTTP Requests ke Edge Function)
            logger.info("🛡️ Mematikan trigger database sementara...")
            await session.execute(
                text("ALTER TABLE drugs DISABLE TRIGGER tr_audit_drug_stock_sync;")
            )

            # 2. BACA CSV
            drugs_to_insert = []
            with open(CSV_FILE, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 🧩 Gabungkan Name + Strength untuk nama obat yang lengkap
                    full_name = f"{row['Name']} {row['Strength']}"

                    # 📝 Buat deskripsi yang kaya informasi
                    description = f"Indication: {row['Indication']}. Form: {row['Dosage Form']}. Classification: {row['Classification']}"

                    drug_id = uuid.uuid4()

                    drugs_to_insert.append(
                        {
                            "id": drug_id,
                            "name": full_name,
                            "generic_name": row["Name"],
                            "category": row["Category"],
                            "description": description,
                            "stock": random.randint(10, 500),
                            "price": Decimal(random.randint(5000, 75000)),
                            "unit": row["Dosage Form"].lower(),
                            "manufacturer": row["Manufacturer"],
                            "min_stock_alert": 10,
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )

                    # Batch Insert every 5000 rows to optimize memory
                    if len(drugs_to_insert) >= 5000:
                        await session.execute(insert(Drug), drugs_to_insert)
                        drugs_to_insert = []
                        logger.info("→ Berhasil mengimpor 5000 data...")

            # Insert remaining data
            if drugs_to_insert:
                await session.execute(insert(Drug), drugs_to_insert)

            # 3. 🛡️ NYALAKAN TRIGGER KEMBALI
            logger.info("🛡️ Menyalakan kembali trigger database...")
            await session.execute(
                text("ALTER TABLE drugs ENABLE TRIGGER tr_audit_drug_stock_sync;")
            )

            await session.commit()
            logger.info("✅ Database Seeding Sukses!")

    except Exception as e:
        logger.error(f"❌ Terjadi kesalahan saat seeding: {e}")
        # Jangan lupa nyalakan trigger lagi meski error
        async with async_session() as session:
            await session.execute(
                text("ALTER TABLE drugs ENABLE TRIGGER tr_audit_drug_stock_sync;")
            )
            await session.commit()
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(bulk_seed())
