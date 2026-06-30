# Upstream Mustache JSON Specs

These JSON fixtures are vendored from the upstream Mustache spec repository.

- Upstream URL: https://github.com/mustache/spec/tree/master/specs
- Pinned commit: `e8ec001db7f594521e773c34866aca2b5d6b0037`

Refresh command:

```bash
curl -L https://github.com/mustache/spec/archive/e8ec001db7f594521e773c34866aca2b5d6b0037.tar.gz -o /tmp/mustache-spec-e8ec001.tar.gz
tar -xzf /tmp/mustache-spec-e8ec001.tar.gz -C /tmp spec-e8ec001db7f594521e773c34866aca2b5d6b0037/specs
cp /tmp/spec-e8ec001db7f594521e773c34866aca2b5d6b0037/specs/*.json tests/fixtures/mustache-specs/
```
