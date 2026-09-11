"""
MEDIA QOVLUĞU — yüklənən şəkillər deploy yeniləməsində itməsin (2026-09-11).

Tapıntı (ilk deploy-dan əvvəl): reklam kreativi, məhsul fotosu və kataloq
kəsiyi `app/static`-in altına yazılırdı. Konteynerdə bu, image-in öz fayl
sistemidir: hər `docker compose build` + `up` onları silirdi, baza isə hələ də
onlara istinad edirdi - reklamın şəkli 404 olurdu. İndi üçü də
`settings.media_dir`-dədir; Docker-də o, `/data/media`-dır - bazanın volume-u.
URL-lər dəyişmir: `/static` mount-u əvvəl koda, sonra media qovluğuna baxır.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.main import NO_CACHE, STATIC_DIR, RevalidatedStaticFiles

ROOT = Path(__file__).resolve().parent.parent


def _client(media: Path) -> TestClient:
    app = FastAPI()
    app.mount(
        "/static",
        RevalidatedStaticFiles(directory=STATIC_DIR, media_directory=media),
        name="static",
    )
    return TestClient(app)


# ------------------------------------------------------------- yazan tərəf


def test_üç_yazıcı_da_media_qovluğuna_yazır():
    """Biri köhnə yolda qalsa, həmin şəkillər deploy yeniləməsində yenə itər."""
    from app.api.ads import CREATIVE_DIR
    from app.services.product_images import IMAGE_DIR
    from ingestion.images import PRODUCT_IMAGE_DIR

    assert CREATIVE_DIR == settings.media_dir / "images" / "ads"
    assert IMAGE_DIR == settings.media_dir / "product_images"
    assert PRODUCT_IMAGE_DIR == settings.media_dir / "images" / "products"


# ------------------------------------------------------------- verən tərəf


def test_media_faylı_köhnə_url_ilə_verilir(tmp_path):
    (tmp_path / "images" / "ads").mkdir(parents=True)
    (tmp_path / "images" / "ads" / "abc.webp").write_bytes(b"RIFF-test")

    r = _client(tmp_path).get("/static/images/ads/abc.webp")

    assert r.status_code == 200 and r.content == b"RIFF-test"
    assert r.headers["cache-control"] == NO_CACHE


def test_kod_faylı_mediadan_üstündür(tmp_path):
    """Media qovluğundakı eyni adlı fayl saytın öz CSS/JS-ini əvəz edə bilməz."""
    # Unikal işarə: adi söz ("saxta") style.css-in öz şərhlərində də var.
    (tmp_path / "style.css").write_text("/* MEDIA-KOLGE-7f3a */", encoding="utf-8")

    r = _client(tmp_path).get("/static/style.css")

    assert r.status_code == 200 and "MEDIA-KOLGE-7f3a" not in r.text


def test_repodakı_nümunə_bannerlər_media_başqa_yerdə_olanda_da_verilir(tmp_path):
    for fayl in ("sample-banner.svg", "sample-rail.svg"):
        assert _client(tmp_path).get(f"/static/images/ads/{fayl}").status_code == 200


def test_media_qovluğu_hələ_yoxdursa_sayt_qırılmır(tmp_path):
    client = _client(tmp_path / "hələ-yoxdur")

    assert client.get("/static/images/ads/yox.webp").status_code == 404
    assert client.get("/static/style.css").status_code == 200


def test_media_qovluğundan_kənara_çıxmaq_olmur(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    (tmp_path / "sirr.txt").write_text("gizli", encoding="utf-8")

    r = _client(media).get("/static/%2e%2e/sirr.txt")

    assert r.status_code == 404 and "gizli" not in r.text


# ------------------------------------------------------------------ Docker


def test_docker_da_media_bazanın_volume_undadır():
    """Ayrı volume YOX: ehtiyat nüsxə bazanı götürüb şəkilləri unutmasın."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "MEDIA_DIR=/data/media" in dockerfile
    assert "MEDIA_DIR: /data/media" in compose
    assert "basketiq_data:/data" in compose


def test_lokal_şəkillər_image_ə_düşmür_nümunələr_isə_düşür():
    """Image-ə düşən lokal şəkil volume-dakı eyni adlı faylı kölgələyərdi."""
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    for sətir in ("app/static/images/ads/*", "app/static/product_images/", "app/static/images/products/"):
        assert sətir in ignore
    for nümunə in ("sample-banner.svg", "sample-rail.svg"):
        assert f"!app/static/images/ads/{nümunə}" in ignore


def test_nümunə_bannerlərin_ikisi_də_repoya_düşür():
    """sample-rail.svg `.gitignore`-da qalmışdı - təmiz clone-da tapılmırdı."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "!app/static/images/ads/sample-banner.svg" in gitignore
    assert "!app/static/images/ads/sample-rail.svg" in gitignore
