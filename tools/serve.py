"""
Development serveri — `localhost` adının HƏR İKİ ünvanında işləyir.

PROBLEM ÖLÇÜLDÜ, uydurulmadı. Windows-da adi `uvicorn` çağırışları belə davranır:

    --host 127.0.0.1   ->  127.0.0.1 açıq,  [::1] BAĞLI
    --host ::          ->  [::1] açıq,      127.0.0.1 BAĞLI

Səbəb: Windows-da IPv6 soketinin `IPV6_V6ONLY` seçimi standart olaraq AÇIQDIR,
yəni «::» ünvanı IPv4-ü ƏHATƏ ETMİR. Brauzer isə `localhost` yazanda əvvəlcə
`::1`-i sınayır - və bəzi quraşdırmalarda geri `127.0.0.1`-ə keçmir. Nəticədə
server işləyir, terminalda `curl 127.0.0.1` cavab verir, brauzerdə isə
«bağlantı yoxdur» görünür. Səhv sakit olduğu üçün adama serverin ölü olduğunu
düşündürür.

HƏLL: soketi ÖZÜMÜZ yaradırıq. `socket.create_server(..., dualstack_ipv6=True)`
`IPV6_V6ONLY`-ni söndürür, yəni tək soket həm `::1`-ə, həm `127.0.0.1`-ə cavab
verir. Hazır soket uvicorn-a ötürülür.

NİYƏ `--fd` YOX? Uvicorn-un `--fd` seçimi `socket.fromfd()` işlədir, o isə
Windows-da mövcud deyil. Soketi obyekt kimi ötürmək (`Server.run(sockets=[...])`)
hər iki platformada işləyir.

İSTİFADƏ:
    python tools/serve.py                 # http://localhost:8000
    python tools/serve.py --port 8080
    python tools/serve.py --no-reload
    python tools/serve.py --admin         # admin paneli açıq

Yalnız DEVELOPMENT üçündür. İstehsalda `deploy/` altındakı konfiqurasiya işləyir.
"""

import argparse
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows konsolu bəzən cp1252-dir - Azərbaycan hərfləri onu qırır
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def dual_stack_socket(port: int) -> socket.socket:
    """
    Həm IPv4, həm IPv6 dinləyən tək soket.

    Maşında IPv6 yoxdursa (nadir, amma mümkün), sakitcə IPv4-ə düşürük -
    o zaman `localhost` yenə işləyir, sadəcə `[::1]` yazmaqla yox.
    """
    if socket.has_ipv6 and socket.has_dualstack_ipv6():
        return socket.create_server(
            ("::", port), family=socket.AF_INET6, dualstack_ipv6=True, reuse_port=False
        )
    print("XƏBƏRDARLIQ: dual-stack mümkün deyil, yalnız IPv4 açılır.")
    return socket.create_server(("0.0.0.0", port), reuse_port=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="BasketIQ development serveri")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-reload", action="store_true", help="fayl dəyişəndə yenidən başlatma")
    ap.add_argument("--admin", action="store_true", help="admin panelini aç (ADMIN_ENABLED=1)")
    args = ap.parse_args()

    if args.admin:
        os.environ["ADMIN_ENABLED"] = "1"

    import uvicorn

    # --reload AYRI PROSES qaldırır və ona hazır soket ötürmək olmur: yenidən
    # başlayan proses soketi miras almır. Ona görə reload rejimində adi yol
    # işlədilir - o zaman `localhost` yalnız IPv4-də olur, amma inkişaf
    # dövründə fayl izləmək daha vacibdir. Seçim istifadəçidədir.
    if not args.no_reload:
        print(f"reload AÇIQ  ->  http://127.0.0.1:{args.port}")
        print("           `localhost` adının hər iki ünvanı üçün: --no-reload")
        uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, reload=True)
        return

    sock = dual_stack_socket(args.port)
    print(f"dual-stack   ->  http://localhost:{args.port}")
    print(f"                 http://127.0.0.1:{args.port}")
    print(f"                 http://[::1]:{args.port}")
    config = uvicorn.Config("app.main:app", log_level="info")
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    main()
