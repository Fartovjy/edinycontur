import subprocess, sys
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    import paramiko
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    import paramiko

HOST = "5.42.122.25"
USER = "root"
PASS = "urQ-ww+L59@nDY"
APP_DIR = "/home/deploy/app"
COMPOSE = f"docker compose -f {APP_DIR}/docker-compose.prod.yml --env-file {APP_DIR}/.env.prod"

def run(client, cmd):
    ch = client.get_transport().open_session()
    ch.set_combine_stderr(True)
    ch.exec_command(cmd)
    while True:
        d = ch.recv(8192)
        if not d: break
        sys.stdout.write(d.decode("utf-8", errors="replace")); sys.stdout.flush()
    return ch.recv_exit_status()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

ENV_FILE = f"{APP_DIR}/.env.prod"
NEW_VARS = {
    "TELEGRAM_BOT_TOKEN": "8838291209:AAE9pdutYlcePWcEkvNv_ZbOvpsUtbpG6O0",
    "TELEGRAM_BOT_NAME":  "biovetk_bot",
    "EMAIL_HOST":         "smtp.mail.ru",
    "EMAIL_PORT":         "465",
    "EMAIL_USE_SSL":      "1",
    "EMAIL_USE_TLS":      "0",
    "EMAIL_HOST_USER":    "a.leongardt@biovak-t.com",
    "EMAIL_HOST_PASSWORD":"oUnTYI32uua-",
    "DEFAULT_FROM_EMAIL": "a.leongardt@biovak-t.com",
}

print("==> Updating .env.prod with notification settings...")
for key, val in NEW_VARS.items():
    # Remove old line if exists, then append
    safe_val = val.replace("'", "'\\''")
    run(client, f"sed -i '/^{key}=/d' {ENV_FILE} && echo \"{key}={safe_val}\" >> {ENV_FILE}")

print("==> Pulling latest code from GitHub...")
run(client, f"cd {APP_DIR} && git fetch origin main && git reset --hard origin/main")

print("\n==> Rebuilding web container...")
run(client, f"cd {APP_DIR} && {COMPOSE} build --no-cache web 2>&1")

print("\n==> Restarting web and nginx...")
run(client, f"cd {APP_DIR} && {COMPOSE} up -d --no-deps web 2>&1")
run(client, f"cd {APP_DIR} && {COMPOSE} up -d --no-deps nginx 2>&1")

print("\n==> Applying migrations...")
run(client, f"cd {APP_DIR} && {COMPOSE} exec -T web python manage.py migrate --noinput 2>&1")

print("\n==> Collecting static files...")
run(client, f"cd {APP_DIR} && {COMPOSE} exec -T web python manage.py collectstatic --noinput --clear 2>&1")

print("\n==> Pruning old images...")
run(client, "docker image prune -f 2>&1")

print("\n==> Container status:")
run(client, f"cd {APP_DIR} && {COMPOSE} ps")

print("\n==> HTTP check:")
run(client, "curl -s -o /dev/null -w 'HTTP %{http_code}\\n' http://localhost/")

client.close()
print(f"\nSite: http://{HOST}/")
