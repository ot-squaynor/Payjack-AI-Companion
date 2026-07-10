# Session Memory

This package contains bounded, in-process session memory for short contextual
follow-ups. It is intentionally narrow: it does not create durable user memory
or long-term profiles.

Current behavior:

- Stores the last few user/assistant turns per `session_id`.
- Stores safe structured facts from the last tool-backed response.
- Resolves short follow-ups such as `so how many GHS` or `are you sure` from
  the last spend summary result.

Current limits:

- Memory is process-local and can be lost on app restart or Lambda cold start.
- It is not a replacement for durable chat history.
- It should stay deterministic and source follow-up answers from structured
  tool facts, not from free-form assistant text.

