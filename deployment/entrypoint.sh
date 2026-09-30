#!/bin/sh
# Set ownership on the mounted app directory, then drop privileges.
set -eu
APP_DATA_DIR=${APP_DATA_DIR:-/var/data/ip-sakti}
export APP_DATA_DIR
case "$APP_DATA_DIR" in
  /var/data/ip-sakti|/data/ip-sakti) ;;
  *) echo 'Unsupported APP_DATA_DIR mount path' >&2; exit 1 ;;
esac
mkdir -p "$APP_DATA_DIR"
chown 10001:10001 "$APP_DATA_DIR"
chmod 700 "$APP_DATA_DIR"
exec gosu 10001:10001 python -m deployment.start
