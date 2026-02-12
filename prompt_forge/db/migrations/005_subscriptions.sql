-- Migration 005_subscriptions.sql
CREATE TABLE prompt_subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  prompt_id UUID NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
  agent_id TEXT NOT NULL,
  subscribed_at TIMESTAMPTZ DEFAULT now(),
  last_pulled_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(prompt_id, agent_id)
);

CREATE INDEX idx_subscriptions_prompt ON prompt_subscriptions(prompt_id);
CREATE INDEX idx_subscriptions_agent ON prompt_subscriptions(agent_id);
