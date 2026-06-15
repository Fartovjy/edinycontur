"""Patch logistics/views.py into running container."""
import paramiko

HOST = "5.42.122.25"; USER = "root"; PASS = "urQ-ww+L59@nDY"
APP_DIR = "/home/deploy/app"
container = "app-web-1"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=60):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f">>> {cmd[:80]}")
    if out.strip(): print("OUT:", out.strip()[:300])
    if err.strip(): print("ERR:", err.strip()[:300])
    return out

# Upload views.py to server
sftp = client.open_sftp()
sftp.put(r"C:\Users\Home\Documents\biovak\apps\logistics\views.py",
         f"{APP_DIR}/apps/logistics/views.py")
sftp.close()
print("Uploaded views.py to server")

# Copy into container
run(f"docker cp {APP_DIR}/apps/logistics/views.py {container}:/app/apps/logistics/views.py")

# Remove __pycache__
run(f"docker exec {container} find /app/apps/logistics -name __pycache__ -type d -exec rm -rf {{}} + 2>/dev/null || true")

# Restart container
run(f"cd {APP_DIR} && docker compose --env-file .env.prod -f docker-compose.prod.yml restart web", timeout=30)

import time; time.sleep(4)

# Check logs
run(f"cd {APP_DIR} && docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=8 web")

client.close()
print("Done!")
