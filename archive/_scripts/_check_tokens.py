"""Check FCM tokens in DB on server via SFTP + exec."""
import io, paramiko

HOST = "5.42.122.25"; USER = "root"; PASS = "urQ-ww+L59@nDY"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=60):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err

container = "app-web-1"

python_code = b"""
from apps.api.models import DeviceToken
tokens = list(DeviceToken.objects.select_related('user').all())
print(f'Total FCM tokens: {len(tokens)}')
for t in tokens:
    print(f'  user={t.user.username} platform={t.platform} created={str(t.created_at)[:16]} token=...{t.fcm_token[-50:]}')
"""

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(python_code), "/tmp/check_tokens_shell.py")
sftp.close()

run(f"docker cp /tmp/check_tokens_shell.py {container}:/tmp/check_tokens_shell.py")

out3, err3 = run(f"docker exec {container} sh -c 'python manage.py shell < /tmp/check_tokens_shell.py'")
print("OUTPUT:", out3)
if err3.strip():
    lines = [l for l in err3.splitlines() if "INFO" not in l and "AXES" not in l and "axes" not in l]
    if lines:
        print("STDERR:", "\n".join(lines[:10]))

client.close()
