# CNB sync gateway

`cnb-sync-gateway` is the first local/cloud sync layer for CNB companion clients.  It is deliberately small:

- SQLite append-only event log at `cnb-sync.db`
- HTTP JSON pull endpoint for reconnect/backfill
- Server-Sent Events endpoint for live streaming
- optional Bearer token auth
- encrypted Git backup script for cloud instances that may disappear

## Local run

```bash
bin/cnb-sync-gateway --host 127.0.0.1 --port 8765 --data-dir /tmp/cnb-sync
```

Post an event:

```bash
curl -sS http://127.0.0.1:8765/v1/events \
  -H 'Content-Type: application/json' \
  -H 'X-CNB-Device-ID: mac-local' \
  -d '{"stream":"chat","type":"message.created","payload":{"text":"hello"}}'
```

Pull missed events:

```bash
curl -sS 'http://127.0.0.1:8765/v1/events?after=0'
```

Follow live events:

```bash
curl -N 'http://127.0.0.1:8765/v1/stream?after=0'
```

## Event contract

Clients send either one event object, an array of event objects, or `{ "events": [...] }`.

```json
{
  "stream": "chat",
  "type": "message.delta",
  "source_id": "macbook",
  "payload": {
    "conversation_id": "local",
    "text": "partial reply"
  }
}
```

The server assigns a monotonic integer `id`, UTC `ts`, and `payload_sha256`.  Clients should store the last seen `id` and reconnect with `/v1/events?after=<id>` before reopening `/v1/stream?after=<id>`.

## Linux install

On the server, copy or clone this checkout, then run:

```bash
sudo tools/cnb-sync-gateway/install-linux.sh
sudo editor /etc/cnb-sync/env
sudo systemctl restart cnb-sync-gateway.service
```

For public binds, keep `CNB_SYNC_TOKEN` set and put HTTPS in front of the service with Caddy, nginx, Tailscale Funnel, or a cloud load balancer.  iOS clients should use HTTPS outside local development.

## Encrypted Git backup

The cloud server should not hold the private decryption key.  Import only the local public GPG key on the server, then set:

```bash
CNB_SYNC_BACKUP_GIT_REMOTE=git@github.com:your-org/cnb-sync-backups.git
CNB_SYNC_BACKUP_GPG_RECIPIENT=your-key-id-or-email
```

Enable the timer:

```bash
sudo systemctl enable --now cnb-sync-backup.timer
```

Each run creates a consistent SQLite snapshot, packages attachments, encrypts the tarball with GPG, commits it to the private Git repo, and pushes it.

Restore on a fresh machine:

```bash
tools/cnb-sync-gateway/restore_from_backup.sh snapshots/cnb-sync-YYYYMMDDTHHMMSSZ.tar.gz.gpg /var/lib/cnb-sync
```

## Next integration points

- Mac companion: post local user input immediately, append assistant deltas as streaming events, and persist last seen event id.
- Bonjour + QR pairing: advertise local gateway URL and token fingerprint, then exchange the full token through QR.
- Cloud relay + APNs: use this gateway as the authoritative event log; push notifications carry only wake-up metadata.
- Feishu, `ADMIN_TO_DO`, and project state: project each source into separate streams rather than creating separate sync stores.
