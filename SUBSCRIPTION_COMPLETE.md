# Subscription System — Complete

## What was built

### Database
- Migration `005_subscriptions.sql` applied — `prompt_subscriptions` table with unique constraint on (prompt_id, agent_id)

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/prompts/{slug}/subscribe` | Subscribe (X-Agent-ID header, upsert) |
| DELETE | `/api/v1/prompts/{slug}/subscribe` | Unsubscribe |
| GET | `/api/v1/prompts/{slug}/subscribers` | List subscribers |
| GET | `/api/v1/agents/{agent_id}/subscriptions` | List agent's subscriptions |

### Auto-subscribe
When an agent fetches a version (`GET /api/v1/prompts/{slug}/versions/{version}`) with `X-Agent-ID` header, a subscription is automatically created/updated with `last_pulled_at` refreshed.

### Targeted Events
On version create, all subscribers receive a NATS event:
- Subject: `swarm.forge.agent.{agent_id}.prompt-updated`
- Payload includes slug, prompt_id, old/new version, change_note, priority
- Priority field supported in version create body (default "normal")

### TTL Cleanup
Background task runs every hour, removing subscriptions where `last_pulled_at` is older than 7 days.

### Subscriber Count
`GET /api/v1/prompts` response now includes `subscriber_count` per prompt.

### Tests
14 new tests covering all subscription features. 162 total tests passing.

### Files Changed
- `prompt_forge/db/migrations/005_subscriptions.sql`
- `prompt_forge/api/subscriptions.py` (new)
- `prompt_forge/api/agents.py` (new)
- `prompt_forge/api/router.py` (updated)
- `prompt_forge/api/versions.py` (updated — auto-subscribe + events)
- `prompt_forge/api/prompts.py` (updated — subscriber_count)
- `prompt_forge/api/models.py` (updated — priority, subscriber_count fields)
- `prompt_forge/main.py` (updated — TTL cleanup task)
- `tests/conftest.py` (updated — mock table)
- `tests/test_subscriptions.py` (new)
