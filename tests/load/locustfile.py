"""
TKYS QA-001 #186
Gercek HTTP + PostgreSQL performans olcumu.

Yalnizca yerel test sunucusunda calistirilir.
JWT ile kimlik dogrulamasi yapilir.
Veri degistiren endpoint kullanilmaz.
"""

import os
from urllib.parse import urlparse

from locust import HttpUser, between, task


class TKYSKullanicisi(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        hedef = urlparse(self.client.base_url)

        if hedef.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError(
                "Guvenlik: Yuk testi yalnizca yerel sunucuda yapilabilir."
            )

        if hedef.port != 8001:
            raise RuntimeError(
                "Guvenlik: Yuk testi icin port 8001 kullanilmalidir."
            )

        token = os.getenv("TKYS_LOAD_TOKEN")

        if not token:
            raise RuntimeError(
                "TKYS_LOAD_TOKEN tanimlanmamis."
            )

        self.headers = {
            "Authorization": f"Bearer {token}"
        }

    @task
    def odalari_listele(self):
        with self.client.get(
            "/api/odalar",
            headers=self.headers,
            name="GET /api/odalar",
            catch_response=True,
            timeout=10,
        ) as yanit:

            if yanit.status_code != 200:
                yanit.failure(
                    f"Beklenmeyen HTTP durumu: {yanit.status_code}"
                )
