# notify-function (serverless)

Azure Function, Python v2 model - satisfies the "at least one serverless
component" requirement from the project brief. Same folder shape as the
Lab Session 06 blob storage exercise (`host.json`, `local.settings.json`,
`requirements.txt`).

## What it's for

`scan-service` POSTs a finished scan verdict to this function. The function
renders a short text "verification certificate" and drops it into the
`certificates` container in Blob Storage, then returns the blob URL. This
keeps certificate generation off the always-on containers and lets it scale
to zero between tournaments.

## Run it locally

```bash
cd serverless/notify-function
cp local.settings.json.example local.settings.json
# edit local.settings.json and paste your Azure Storage connection string
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
func start
```

(Needs the Azure Functions Core Tools - `npm i -g azure-functions-core-tools@4`.)

Test it:

```bash
curl -X POST http://localhost:7071/api/notify \
  -H "Content-Type: application/json" \
  -d '{"scan_id":"demo-1","gamertag":"xX_ShadowFrag_Xx","tournament_id":"t1","verdict":"clear","sha256":"abc123","created_at":"2026-08-15T10:00:00Z"}'
```

## Deploy to Azure

```bash
az functionapp create \
  --resource-group matchguard-rg \
  --consumption-plan-location westeurope \
  --runtime python --runtime-version 3.11 \
  --functions-version 4 \
  --name matchguard-notify \
  --storage-account <your-storage-account-name>

func azure functionapp publish matchguard-notify
```

Then point `scan-service` at it by setting `NOTIFY_FUNCTION_URL` to
`https://matchguard-notify.azurewebsites.net/api/notify?code=<function-key>`.

If `NOTIFY_FUNCTION_URL` is left empty, `scan-service` generates the same
certificate itself and uploads it directly - handy for local testing before
you've deployed the function, but the whole point of the assignment is to
actually stand this up on Azure once you've got your student subscription
connection string plugged in.

Elias
