#!/usr/bin/env bash
set -euo pipefail

BASE="http://localhost:8083"
FAIL=0

pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1 — $2"; FAIL=1; }

echo "=== PromptForge E2E Smoke Tests ==="

# 1. Health
echo "--- Health ---"
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' "$BASE/health")
if [ "$HTTP" = "200" ]; then
  pass "GET /health → 200"
else
  fail "GET /health" "expected 200, got $HTTP"
fi

# 2. List prompts (empty)
echo "--- Prompts CRUD ---"
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' "$BASE/api/v1/prompts")
if [ "$HTTP" = "200" ]; then
  pass "GET /api/v1/prompts → 200"
else
  fail "GET /api/v1/prompts" "expected 200, got $HTTP"
fi

# 3. Create prompt
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' -X POST \
  -H "Content-Type: application/json" \
  -d '{"slug":"e2e-test","name":"E2E Test Prompt","type":"persona","description":"Test prompt","tags":["e2e"]}' \
  "$BASE/api/v1/prompts")
if [ "$HTTP" = "201" ]; then
  pass "POST /api/v1/prompts → 201"
else
  fail "POST /api/v1/prompts" "expected 201, got $HTTP (body: $(cat /tmp/e2e_body))"
fi

# 4. Get prompt by slug
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' "$BASE/api/v1/prompts/e2e-test")
if [ "$HTTP" = "200" ]; then
  pass "GET /api/v1/prompts/e2e-test → 200"
else
  fail "GET /api/v1/prompts/e2e-test" "expected 200, got $HTTP"
fi

# 5. Create version
echo "--- Versions ---"
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' -X POST \
  -H "Content-Type: application/json" \
  -d '{"content":{"sections":[{"id":"identity","label":"Identity","content":"You are an E2E test agent."}]},"message":"v1","author":"e2e-runner"}' \
  "$BASE/api/v1/prompts/e2e-test/versions")
if [ "$HTTP" = "201" ]; then
  pass "POST /api/v1/prompts/e2e-test/versions → 201"
else
  fail "POST /api/v1/prompts/e2e-test/versions" "expected 201, got $HTTP (body: $(cat /tmp/e2e_body))"
fi

# 6. Get latest version
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' "$BASE/api/v1/prompts/e2e-test/versions/latest")
if [ "$HTTP" = "200" ]; then
  pass "GET /api/v1/prompts/e2e-test/versions/latest → 200"
else
  fail "GET versions/latest" "expected 200, got $HTTP"
fi

# 7. List versions
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' "$BASE/api/v1/prompts/e2e-test/versions")
if [ "$HTTP" = "200" ]; then
  pass "GET /api/v1/prompts/e2e-test/versions → 200"
else
  fail "GET versions" "expected 200, got $HTTP"
fi

# 8. Subscribe
echo "--- Subscriptions ---"
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' -X POST \
  -H "X-Agent-ID: e2e-agent" \
  "$BASE/api/v1/prompts/e2e-test/subscribe")
if [ "$HTTP" = "201" ]; then
  pass "POST /api/v1/prompts/e2e-test/subscribe → $HTTP"
else
  fail "POST subscribe" "expected 201, got $HTTP (body: $(cat /tmp/e2e_body))"
fi

# 9. List subscribers
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' "$BASE/api/v1/prompts/e2e-test/subscribers")
if [ "$HTTP" = "200" ]; then
  pass "GET /api/v1/prompts/e2e-test/subscribers → 200"
  if grep -q "e2e-agent" /tmp/e2e_body; then
    pass "e2e-agent in subscriber list"
  else
    fail "subscriber check" "e2e-agent not found"
  fi
else
  fail "GET subscribers" "expected 200, got $HTTP"
fi

# 10. Audit log
echo "--- Audit ---"
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' "$BASE/api/v1/audit")
if [ "$HTTP" = "200" ]; then
  pass "GET /api/v1/audit → 200"
else
  fail "GET /api/v1/audit" "expected 200, got $HTTP"
fi

# 11. Delete prompt (archive returns 204)
echo "--- Cleanup ---"
HTTP=$(curl -s -o /tmp/e2e_body -w '%{http_code}' -X DELETE "$BASE/api/v1/prompts/e2e-test")
if [ "$HTTP" = "204" ]; then
  pass "DELETE /api/v1/prompts/e2e-test → $HTTP"
else
  fail "DELETE prompt" "expected 204, got $HTTP (body: $(cat /tmp/e2e_body))"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "All PromptForge E2E tests passed."
else
  echo "Some PromptForge E2E tests FAILED."
  exit 1
fi
