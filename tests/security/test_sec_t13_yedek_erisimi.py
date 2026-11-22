"""SEC-T13 - Backup Security: normal kullanıcı yedek dosyasına erişememelidir.

Uygulama tarafı: hiçbir API ucu dosya sunmaz (yedek indirilemez); yedek hakkında bilgi veren tek uç olan Sistem Durumu yalnızca
yetkili kullanıcıya açıktır ve dosya yolu ya da içerik değil, yalnızca tarih/adet/boyut döndürür. Sunucudaki klasör izni
(yalnızca sistem sorumlusu ve SYSTEM) canlı ortamda elle doğrulanır (bkz. docs/test-reports/SEC-001_Guvenlik_Test_Raporu.md)."""
import inspect
from datetime import datetime

from fastapi.responses import FileResponse, StreamingResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import Mount

from server import sistem_durumu
from server.sunucu import app


def test_hicbir_uc_dosya_sunmaz_ve_statik_klasor_baglanmamis():
    for yol in app.routes:
        assert not isinstance(yol, Mount), f"Statik dosya klasörü bağlanmış: {yol.path}"
        if isinstance(yol, APIRoute):
            assert yol.response_class not in (FileResponse, StreamingResponse), yol.path
            kaynak = inspect.getsource(yol.endpoint)
            assert "FileResponse" not in kaynak and "StreamingResponse" not in kaynak, yol.path


def test_yedek_bilgisi_dosya_yolu_ya_da_dosya_adi_icermez(tmp_path):
    (tmp_path / "tkys_20261122_050000_000000.dump").write_bytes(b"x" * 2048)
    bilgi = sistem_durumu.son_yedek_bilgisi(tmp_path, "tkys", simdi=datetime(2026, 11, 22, 9, 0))
    assert set(bilgi) == {"var", "tarih", "gecen_saat", "eski", "adet", "boyut_mb"}
    metin = str(bilgi)
    assert str(tmp_path) not in metin and ".dump" not in metin and "tkys_" not in metin


def test_sistem_durumu_ucu_kimlik_dogrulamasi_ister():
    yanit = TestClient(app).get("/api/sistem-durumu")
    assert yanit.status_code == 401
