# scan-service

Flask REST API. Owns evidence upload, SHA-256 hashing, the keyword/hash
blacklist scan (`blacklist.py`), and the flagged-players feed. Calls back
into `tournament-service` to keep a registration's `scan_status` in sync,
and calls the `notify-function` (or falls back to generating the
certificate itself) once a verdict is reached.

## Run it standalone

```bash
pip install -r requirements.txt
python app.py            # dev server on :5002
```

## Environment variables

| Var | Default | What |
|---|---|---|
| `SCAN_DB_PATH` | `./scans.db` | sqlite file location |
| `EVIDENCE_CONTAINER_NAME` | `scan-evidence` | Azure Blob container for uploaded logs |
| `AZURE_STORAGE_CONNECTION_STRING` | *(empty)* | leave unset to use the local-disk fallback |
| `TOURNAMENT_SERVICE_URL` | `http://localhost:5001` | where to send scan-status callbacks |
| `NOTIFY_FUNCTION_URL` | *(empty)* | Azure Function URL; blank = generate certificates locally |
| `PORT` | `5002` | dev server port |

## Try it with the sample files

```bash
curl -X POST http://localhost:5002/api/scans \
  -F "registration_id=demo" -F "tournament_id=demo" -F "gamertag=tester" \
  -F "evidence=@../../docs/sample-uploads/suspicious-system-log.txt"
```

Elias
