import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from elasticsearch import AsyncElasticsearch

from app.core.config import settings
from app.db.session import create_database_engine
from app.db.models.drug import Drug
from app.services.search_service import SearchService

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("search_indexer")


async def bootstrap_index(es: AsyncElasticsearch, index_name: str):
    """Membangun skema index Elasticsearch dengan Best Practices."""

    # 💡 Definisi Analisis (Filter typo & Bahasa)
    settings_body = {
        "analysis": {
            "analyzer": {
                "drug_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding", "stop", "snowball"],
                }
            }
        }
    }

    # 💡 Mapping Data (Tipenya apa & Pentingnya seberapa)
    mappings_body = {
        "properties": {
            "id": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "drug_analyzer",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "generic_name": {"type": "text", "analyzer": "drug_analyzer"},
            "category": {"type": "keyword"},
            "description": {"type": "text", "analyzer": "drug_analyzer"},
            "stock": {"type": "integer"},
            "price": {"type": "double"},
            "unit": {"type": "keyword"},
            "manufacturer": {"type": "keyword"},
        }
    }

    # Hapus index lama jika ada (Fresh Reset)
    if await es.indices.exists(index=index_name):
        logger.info(f"→ Menghapus index lama: {index_name}")
        await es.indices.delete(index=index_name)

    logger.info(f"→ Membuat index baru: {index_name}")
    await es.indices.create(
        index=index_name, settings={"index": settings_body}, mappings=mappings_body
    )


async def sync_all_drugs():
    """Initial Sync: Memindahkan semua data dari Postgres ke Elasticsearch."""

    engine = create_database_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    es = AsyncElasticsearch(settings.elasticsearch_url)
    search_service = SearchService(es)

    try:
        async with async_session() as session:
            # 1. Bangun Index
            await bootstrap_index(es, settings.elasticsearch_index_drugs)

            # 2. Ambil semua obat dari DB
            result = await session.execute(
                select(Drug).where(Drug.deleted_at.is_(None))
            )
            drugs = result.scalars().all()

            if not drugs:
                logger.warning("! Tidak ada obat ditemukan di database untuk di-index.")
                return

            logger.info(f"→ Meng-index {len(drugs)} obat...")

            # 3. Bulk Indexing via SearchService
            await search_service.bulk_index_drugs(drugs)

            logger.info("✅ Elasticsearch Indexing Sukses!")

    except Exception as e:
        logger.error(f"❌ Terjadi kesalahan saat indexing: {e}")
        raise
    finally:
        await es.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(sync_all_drugs())
