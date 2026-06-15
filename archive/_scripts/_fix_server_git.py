"""Fix server git state after manual docker cp patches."""
import paramiko

HOST = "5.42.122.25"; USER = "root"; PASS = "urQ-ww+L59@nDY"
APP_DIR = "/home/deploy/app"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=60):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f">>> {cmd[:80]}")
    if out.strip(): print(out.strip()[:300])
    if err.strip(): print("ERR:", err.strip()[:200])

run(f"cd {APP_DIR} && git checkout -- .")
run(f"cd {APP_DIR} && git pull")
run(f"cd {APP_DIR} && git log --oneline -3")

client.close()
print("Done.")
