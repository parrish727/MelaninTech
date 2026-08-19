# Integration Engine — Internal Setup

## Step 1: Google Cloud OAuth Credentials

You need a Google Cloud project with OAuth consent screen configured.

1. Go to https://console.cloud.google.com/
2. Create project: `melanin-tech-integrations`
3. Enable APIs:
   - Gmail API
   - Google Calendar API
4. Configure OAuth consent screen:
   - App name: `Melanin Tech Agent System`
   - User support email: `developer.integrator@melanin-tech.com`
   - Scopes: `gmail.readonly`, `gmail.send`, `gmail.modify`, `calendar`
   - Test users: `parrish.knowles@melanin-tech.com`, `developer.integrator@melanin-tech.com`
5. Create OAuth Client ID:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8089/oauth/callback`
   - Download the JSON → save as `integrations/credentials/google_oauth_client.json`

## Step 2: Get Initial Tokens

Run the auth flow for BOTH accounts:

```bash
cd /path/to/kiro-agents

# CEO account (client comms, calendar, strategy)
python3 integrations/auth_flow.py --provider google --client ceo

# System account (integrations, webhooks, vendor tools)
python3 integrations/auth_flow.py --provider google --client system
```

This saves tokens to:
- `integrations/credentials/ceo/gmail.json` (parrish.knowles@)
- `integrations/credentials/ceo/google_calendar.json`
- `integrations/credentials/system/gmail.json` (developer.integrator@)
- `integrations/credentials/system/google_calendar.json`

## Step 3: Test

```bash
python3 -c "
from integrations.gmail import GmailConnector
import json
creds = json.load(open('integrations/credentials/melanin-tech/gmail.json'))
gmail = GmailConnector('melanin-tech', creds)
print(gmail.health_check())
print(gmail.read_inbox(max_results=3))
"
```

## Step 4: Wire into Darius

Once credentials work, Darius can use:
```
/task melanin-tech: read my inbox and summarize unread emails
/task melanin-tech: schedule a meeting with HTC client next Tuesday 2pm
/task melanin-tech: draft a follow-up email to the OrthoFlow prospect
```

---

## Security Notes

- OAuth client secret → stored in Vaultwarden
- Refresh tokens → stored in `integrations/credentials/` (gitignored)
- Never log email content in traces
- Integration actions require same Slack approval as code changes
