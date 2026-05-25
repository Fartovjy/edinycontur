param(
    [string]$HostName = "77.221.142.125",
    [string]$User = "root",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\ediny_kontur_deploy"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Archive = Join-Path $env:TEMP "edinycontur-deploy.tar.gz"
$RemoteArchive = "/tmp/edinycontur-deploy.tar.gz"
$Target = "$User@$HostName"

if (Test-Path $Archive) {
    Remove-Item $Archive -Force
}

tar `
    --exclude='.git' `
    --exclude='__pycache__' `
    --exclude='*.pyc' `
    --exclude='media' `
    --exclude='staticfiles' `
    --exclude='archives' `
    --exclude='archive_work' `
    --exclude='.venv' `
    --exclude='venv' `
    --exclude='db.sqlite3' `
    -czf $Archive `
    -C $ProjectRoot .

scp -i $KeyPath $Archive "${Target}:$RemoteArchive"

ssh -i $KeyPath $Target @'
set -e
RELEASE=/srv/edinycontur/releases/$(date +%Y%m%d%H%M%S)
mkdir -p "$RELEASE"
tar -xzf /tmp/edinycontur-deploy.tar.gz -C "$RELEASE"
rm -rf /srv/edinycontur/current
ln -sT "$RELEASE" /srv/edinycontur/current
rm -rf /srv/edinycontur/current/media /srv/edinycontur/current/archives /srv/edinycontur/current/archive_work
ln -s /srv/edinycontur/shared/media /srv/edinycontur/current/media
ln -s /srv/edinycontur/shared/archives /srv/edinycontur/current/archives
ln -s /srv/edinycontur/shared/archive_work /srv/edinycontur/current/archive_work
chown -R ediny:www-data /srv/edinycontur
find /srv/edinycontur -type d -exec chmod 750 {} \;
find /srv/edinycontur -type f -exec chmod 640 {} \;
find /srv/edinycontur/current/staticfiles /srv/edinycontur/shared/media -type d -exec chmod 750 {} \; 2>/dev/null || true
find /srv/edinycontur/current/staticfiles /srv/edinycontur/shared/media -type f -exec chmod 640 {} \; 2>/dev/null || true
sudo -u ediny /srv/edinycontur/venv/bin/pip install -r /srv/edinycontur/current/requirements.txt
sudo -u ediny bash -lc 'set -a; source /etc/edinycontur.env; set +a; /srv/edinycontur/venv/bin/python /srv/edinycontur/current/manage.py migrate --noinput'
sudo -u ediny bash -lc 'set -a; source /etc/edinycontur.env; set +a; /srv/edinycontur/venv/bin/python /srv/edinycontur/current/manage.py collectstatic --noinput'
systemctl restart edinycontur
systemctl reload nginx
systemctl --no-pager --quiet is-active edinycontur nginx postgresql
echo "Deploy complete"
'@
