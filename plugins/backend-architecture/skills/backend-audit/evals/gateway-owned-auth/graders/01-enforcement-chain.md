---
type: llm
focus: trace
weight: 1
---

Follows gateway auth_request, trusted user header overwrite, lack of published API port and the user_id predicate. Does not report missing authentication solely because api.mjs has no JWT verification middleware.
