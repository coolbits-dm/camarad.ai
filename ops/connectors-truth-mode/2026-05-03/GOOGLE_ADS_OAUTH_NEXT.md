# Google Ads Connector — OAuth Phase 2 Next Steps

**Prerequisite**: Phase 1 (truth mode) must be deployed and confirmed stable.

---

## Phase 2: Google Ads OAuth Connection

### Goals
- Add real OAuth 2.0 flow for Google Ads (no mock bypass)
- Store `refresh_token` in `provider_credentials` table
- Validate token on connect
- Set `connected_live: true` only after successful API validation

### Required Env Vars (to configure before Phase 2)
- `GOOGLE_ADS_CLIENT_ID` — OAuth2 client ID from Google Cloud Console
- `GOOGLE_ADS_CLIENT_SECRET` — OAuth2 client secret
- `GOOGLE_ADS_DEVELOPER_TOKEN` — from Google Ads Manager Account
- `GOOGLE_ADS_REDIRECT_URI` — e.g. `https://app.camarad.ai/api/connectors/google-ads/oauth/callback`

### Routes to Add
- `GET /api/connectors/google-ads/oauth/start` — redirect to Google consent screen
- `GET /api/connectors/google-ads/oauth/callback` — handle code, exchange for token, store in `provider_credentials`

### Routes to Update
- `GET /api/connectors/google-ads/reality/status` — set `connected_live: true` when token valid + API validated
- `GET /api/connectors/google-ads/accounts` — use Coolbits gateway with real OAuth credentials

### UI to Update
- `gadsConnect()` — initiate real OAuth flow (redirect or popup)
- `gadsInit()` — display `reality/status` `ui_label='Live Data'` and `ui_badge_class='success'` only when `connected_live: true`

### Token Storage
- Table: `provider_credentials` (already exists, 0 rows)
- Columns: `user_id`, `provider_slug='google-ads'`, `access_token` (encrypt), `refresh_token` (encrypt), `expires_at`

### Security Requirements
- Tokens must be stored encrypted at rest
- `refresh_token` must never be returned in any API response
- `reality/status` must continue to return only booleans
- `GOOGLE_ADS_CLIENT_SECRET` must never appear in any response

### Coolbits Gateway
- Phase 2 delegates live calls through Coolbits gateway with forwarded OAuth token
- Gateway path: `/api/connectors/googleads/customers`
- `COOLBITS_GATEWAY_ENABLED=true` required

### Test Plan (Phase 2)
1. OAuth start redirects to accounts.google.com
2. Callback with valid code stores refresh_token in DB
3. Callback with invalid code returns 400
4. reality/status returns `connected_live: true` after valid token stored
5. Accounts endpoint returns `source: coolbits` after OAuth connection
6. Token refresh happens automatically on expiry
7. Disconnect clears token from DB
8. No token value in any API response
9. State parameter validated in callback (CSRF protection)
10. Only current user's token is accessible

---

## Phase 3: Live Data + MCC Multi-Account

- Real-time Google Ads data via Coolbits gateway
- MCC account listing with real child accounts
- Campaign creation and bid management (write access)
- Billing integration
