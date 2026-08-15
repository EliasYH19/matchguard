# tournament-service

Flask REST API. Owns tournaments, the package catalogue, purchases and
player registrations. SQLite for storage, Azure Blob Storage (with a local
disk fallback) for tournament banner images.

## Run it standalone

```bash
pip install -r requirements.txt
python app.py            # dev server on :5001
# or, closer to how the container runs it:
gunicorn --bind 0.0.0.0:5001 app:app
```

## Environment variables

| Var | Default | What |
|---|---|---|
| `TOURNAMENT_DB_PATH` | `./tournaments.db` | sqlite file location |
| `BANNER_CONTAINER_NAME` | `tournament-banners` | Azure Blob container for banner images |
| `AZURE_STORAGE_CONNECTION_STRING` | *(empty)* | leave unset to use the local-disk fallback |
| `PORT` | `5001` | dev server port |

Elias
