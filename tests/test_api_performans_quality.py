"""
TKYS QA-001 - API performans olcumu.
Gercek veritabani baglantisi kullanilmaz.
"""

import asyncio
import statistics
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from sunucu import app, mevcut_kullanici_id


ISTEK_SAYISI = 100
ESZAMANLILIK = 10


@pytest.fixture
def sahte_veritabani():
    eski_override = app.dependency_overrides.copy()

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 1

    def baglan(**kwargs):
        conn = MagicMock()
        conn.cursor.return_value.fetchall.return_value = []
        return conn

    try:
        with patch("sunucu.psycopg2.connect", side_effect=baglan):
            yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(eski_override)


async def olcum_yap(eszamanli):
    sureler = []
    durumlar = []

    semafor = asyncio.Semaphore(ESZAMANLILIK)

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:

        async def istek():
            async with semafor:
                baslangic = time.perf_counter()

                yanit = await client.get("/api/odalar")

                sureler.append(
                    (time.perf_counter() - baslangic) * 1000
                )
                durumlar.append(yanit.status_code)

        baslangic = time.perf_counter()

        if eszamanli:
            await asyncio.gather(
                *(istek() for _ in range(ISTEK_SAYISI))
            )
        else:
            for _ in range(ISTEK_SAYISI):
                await istek()

        toplam = time.perf_counter() - baslangic

    assert len(durumlar) == ISTEK_SAYISI
    assert all(kod == 200 for kod in durumlar)

    sirali = sorted(sureler)
    p95 = sirali[int(0.95 * (len(sirali) - 1))]

    print("\n--- QA-001 PERFORMANS RAPORU ---")
    print("Test:", "Eszamanli" if eszamanli else "Sirali")
    print("Istek sayisi:", ISTEK_SAYISI)
    print("Toplam sure:", round(toplam, 3), "saniye")
    print("Ortalama:", round(statistics.mean(sureler), 2), "ms")
    print("P95:", round(p95, 2), "ms")
    print("Istek/saniye:", round(ISTEK_SAYISI / toplam, 2))


def test_api_sirali_performans(sahte_veritabani):
    asyncio.run(olcum_yap(eszamanli=False))


def test_api_eszamanli_performans(sahte_veritabani):
    asyncio.run(olcum_yap(eszamanli=True))
