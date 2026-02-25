# app/api/routes_health.py
# 2026-02-25
#
"""Purpose: /health for ECS health checks, maybe /ready for readiness.
Audit notes:

Health should be cheap and not depend on Bedrock.

If you add readiness: verify vector store reachable, KB index loaded, etc."""