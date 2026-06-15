"""Rebuild Docker image to persist code changes."""
import sys, time, paramiko

HOST = "5.42.122.25"; USER = "root"; PASS = "urQ-ww+L59@nDY"
APP_DIR = "/home/deploy/app"
DC = f"cd {APP_DIR} && docker compose --env-file .env.prod -f docker-compose.prod.yml"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

def run(cmd, timeout=180, allow_fail=False):
    print(f">>> {cmd[:80]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    for line in (out + err).strip().splitlines():
        sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    print(f"[exit {code}]\n")
    if code != 0 and not allow_fail:
        client.close(); sys.exit(1)
    return out

# First git pull to sync code
run(f"cd {APP_DIR} && git pull", allow_fail=True)
# Build new image
run(f"{DC} build web")
# Start with new image
run(f"{DC} up -d --no-deps --force-recreate web")
time.sleep(5)
run(f"{DC} logs --tail=10 web", allow_fail=True)
client.close()
print("Done!")
