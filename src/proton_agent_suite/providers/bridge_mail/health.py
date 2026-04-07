from __future__ import annotations

import socket


def tcp_check(host: str, port: int, timeout: float = 2.0) -> dict[str, object]:
    result: dict[str, object] = {"host": host, "port": port, "ok": False}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        result["ok"] = True
    except ConnectionRefusedError:
        result["reason"] = "connection_refused"
    except OSError as exc:
        result["reason"] = str(exc)
    finally:
        sock.close()
    return result
