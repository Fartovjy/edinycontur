"""Деплоит + пересчитывает маршруты для всех существующих заявок."""
import sys, time, paramiko

HOST = "5.42.122.25"; USER = "root"; PASS = "urQ-ww+L59@nDY"
APP_DIR = "/home/deploy/app"
DC = f"cd {APP_DIR} && docker compose --env-file .env.prod -f docker-compose.prod.yml"
YANDEX_KEY = "3ed6c779-70ab-4c98-bfc3-1033d57094a8"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

def run(cmd, timeout=180, allow_fail=False):
    print(f">>> {cmd[:100]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    for line in (out + err).strip().splitlines():
        sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
    print(f"[exit {code}]\n")
    if code != 0 and not allow_fail:
        client.close(); sys.exit(1)
    return out

# 1. Прописать ключ (удалить старую строку если есть, добавить правильную)
run(f"sed -i '/YANDEX_GEOCODER_API_KEY/d' {APP_DIR}/.env.prod && echo 'YANDEX_GEOCODER_API_KEY={YANDEX_KEY}' >> {APP_DIR}/.env.prod")

# 2. git pull + пересборка (нужна чтобы новый файл management command попал в образ)
run(f"cd {APP_DIR} && git pull")
run(f"{DC} build web")
run(f"{DC} up -d --no-deps --force-recreate web")
time.sleep(5)

# 3. Запустить пересчёт маршрутов
run(f"{DC} exec -T web python manage.py refresh_all_routes", timeout=600)

client.close()
print("Done!")
