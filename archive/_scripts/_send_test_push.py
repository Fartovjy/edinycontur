"""Send a test FCM push to viewer1 via server."""
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
from django.contrib.auth import get_user_model
from apps.api.services import send_push_to_user

User = get_user_model()
user = User.objects.get(username='viewer1')
result = send_push_to_user(user, title='Test push', body='FCM test message - please check if you receive this', request_id=None)
print(f'Push result: {result}')
"""

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(python_code), "/tmp/send_push_shell.py")
sftp.close()

run(f"docker cp /tmp/send_push_shell.py {container}:/tmp/send_push_shell.py")

out, err = run(f"docker exec {container} sh -c 'python manage.py shell < /tmp/send_push_shell.py'")
print("OUTPUT:", out)
if err.strip():
    lines = [l for l in err.splitlines() if "INFO" not in l and "AXES" not in l and "axes" not in l]
    if lines:
        print("STDERR:", "\n".join(lines[:20]))

client.close()
