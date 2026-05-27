"""
dev_start.py — локальная разработка с продакшен-БД через SSH-тоннель.

Что делает:
  1. Читает POSTGRES_* из .env.prod на сервере (через SSH/paramiko)
  2. Записывает .env.dev с нужными кредами
  3. Открывает SSH-тоннель через paramiko: localhost:5433 → сервер:5432
  4. Поднимает docker-compose.dev.yml (runserver + volume mount кода)

Использование:
  python dev_start.py           # первый запуск — создаёт .env.dev автоматически
  python dev_start.py --reset   # перезаписать .env.dev из сервера заново
  python dev_start.py --no-pull # не тянуть .env с сервера, просто запустить
"""

import os
import sys
import time
import select
import socket
import threading
import socketserver
import subprocess
import argparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Настройки ──────────────────────────────────────────────────────────────
SSH_HOST    = "5.42.122.25"
SSH_USER    = "root"
SSH_PASS    = "urQ-ww+L59@nDY"
APP_DIR     = "/home/deploy/app"
LOCAL_PORT  = 15433  # на твоём ПК (5433 занят локальным postgres)
REMOTE_PORT = 5432   # postgres внутри Docker на сервере

ENV_DEV     = ".env.dev"
ENV_EXAMPLE = ".env.dev.example"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--reset",   action="store_true", help="Перезаписать .env.dev с сервера")
    p.add_argument("--no-pull", action="store_true", help="Не тянуть .env.prod, запустить как есть")
    return p.parse_args()


# ── paramiko: единожды подключаемся и держим соединение ────────────────────
def _get_paramiko():
    try:
        import paramiko
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
        import paramiko
    return paramiko


def connect_ssh():
    paramiko = _get_paramiko()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=15)
    return client


# ── Читаем .env.prod с сервера ──────────────────────────────────────────────
def fetch_env_from_server(ssh_client) -> dict:
    sftp = ssh_client.open_sftp()
    remote_env = f"{APP_DIR}/.env.prod"
    print(f"  Читаем {SSH_HOST}:{remote_env} ...")
    with sftp.open(remote_env, "r") as f:
        content = f.read().decode("utf-8")
    sftp.close()

    env = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env


def write_env_dev(prod_env: dict):
    with open(ENV_EXAMPLE, encoding="utf-8") as f:
        template = f.read()

    import re
    for key in ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_NAME",
                "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD", "DEFAULT_FROM_EMAIL"]:
        if key in prod_env:
            # Заменяем строку целиком (с любым уже существующим значением по умолчанию)
            template = re.sub(
                rf"^{re.escape(key)}=.*$",
                f"{key}={prod_env[key]}",
                template,
                flags=re.MULTILINE,
            )

    with open(ENV_DEV, "w", encoding="utf-8") as f:
        f.write(template)
    print(f"  ✓ {ENV_DEV} записан")


# ── SSH-тоннель через paramiko (без внешней команды ssh) ───────────────────
def _forward_handler(local_sock, transport, remote_host, remote_port):
    """Проксируем один TCP-коннект через SSH-канал."""
    try:
        peer = local_sock.getpeername()
        chan = transport.open_channel("direct-tcpip", (remote_host, remote_port), peer)
    except Exception as e:
        local_sock.close()
        return
    if chan is None:
        local_sock.close()
        return
    try:
        while True:
            r, _, _ = select.select([local_sock, chan], [], [], 5)
            if local_sock in r:
                data = local_sock.recv(4096)
                if not data:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(4096)
                if not data:
                    break
                local_sock.send(data)
    except Exception:
        pass
    finally:
        chan.close()
        local_sock.close()


def open_tunnel(ssh_client):
    transport = ssh_client.get_transport()
    transport.set_keepalive(30)

    # Локальный TCP-сервер, который слушает LOCAL_PORT
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        # 0.0.0.0 — нужно чтобы Docker-контейнер мог подключиться
        # через host.docker.internal (192.168.65.x), а не только localhost
        server_sock.bind(("0.0.0.0", LOCAL_PORT))
    except OSError:
        print(f"  ⚠  Порт {LOCAL_PORT} уже занят — тоннель, возможно, уже открыт")
        return

    server_sock.listen(10)
    server_sock.settimeout(1)

    def _serve():
        while True:
            try:
                conn, _ = server_sock.accept()
            except socket.timeout:
                if not transport.is_active():
                    break
                continue
            except Exception:
                break
            t = threading.Thread(
                target=_forward_handler,
                args=(conn, transport, "localhost", REMOTE_PORT),
                daemon=True,
            )
            t.start()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    print(f"  ✓ Тоннель открыт: localhost:{LOCAL_PORT} → {SSH_HOST}:{REMOTE_PORT}")


# ── Docker Compose ──────────────────────────────────────────────────────────
def start_docker():
    print("▶ Запускаем локальный Docker (авто-перезагрузка при изменении кода)...")
    print("  Адрес: http://localhost:8000\n")
    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.dev.yml", "up", "--build"],
        check=False,
    )


# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    args = parse_args()

    # ── Шаг 1: SSH-соединение ────────────────────────────────────────────
    print(f"▶ Подключаемся к {SSH_HOST}...")
    try:
        ssh = connect_ssh()
        print("  ✓ SSH подключён")
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")
        sys.exit(1)

    # ── Шаг 2: .env.dev ──────────────────────────────────────────────────
    if not args.no_pull:
        need_create = not os.path.exists(ENV_DEV) or args.reset
        if need_create:
            print("▶ Читаем конфиг с сервера...")
            try:
                prod_env = fetch_env_from_server(ssh)
                write_env_dev(prod_env)
            except Exception as e:
                print(f"  ! Не удалось прочитать .env.prod: {e}")
                if not os.path.exists(ENV_DEV):
                    sys.exit(1)
        else:
            print(f"  ✓ {ENV_DEV} уже есть (--reset для обновления)")
    else:
        if not os.path.exists(ENV_DEV):
            print(f"❌ {ENV_DEV} не найден. Запусти без --no-pull.")
            sys.exit(1)

    # ── Шаг 3: Тоннель ───────────────────────────────────────────────────
    print(f"▶ Открываем SSH-тоннель к БД...")
    open_tunnel(ssh)

    # ── Шаг 4: Docker ────────────────────────────────────────────────────
    start_docker()

    ssh.close()
