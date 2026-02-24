"""
Refresh analytics cache: call backend refresh endpoint (used by DAG) or run in-process for local testing.
Cache is in-memory in the API process; warmup on API startup also runs do_refresh. For DAG, set
REFRESH_CACHE_URL to the API base URL (e.g. https://api.example.com) and this script will POST to
/api/v1/admin/refresh-cache.
"""
from __future__ import annotations

import argparse
import os
import sys

# Add repo root to path so we can import backend.app when running in-process (e.g. from DAG with cwd=repo)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_SCRIPT_DIR)
_REPO = os.path.dirname(_BACKEND)
for _p in (_REPO, _BACKEND):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh analytics cache")
    parser.add_argument("--url", default=os.environ.get("REFRESH_CACHE_URL"), help="API base URL (e.g. https://api.example.com). If set, POST to /api/v1/admin/refresh-cache")
    parser.add_argument("--org", default="default", help="Organization ID")
    parser.add_argument("--client", type=int, default=1, help="Client ID")
    parser.add_argument("--in-process", action="store_true", help="Run do_refresh in-process (updates only this process's memory; use for local testing)")
    args = parser.parse_args()

    if args.url:
        try:
            import urllib.request
            req = urllib.request.Request(
                args.url.rstrip("/") + "/api/v1/admin/refresh-cache",
                data=b"{}",
                headers={"Content-Type": "application/json", "X-Organization-Id": args.org},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                print(resp.read().decode())
        except Exception as e:
            print("Error calling refresh endpoint:", e, file=sys.stderr)
            return 1
        return 0

    if args.in_process:
        # Run in-process: only updates this process's cache (script), not the running API
        from backend.app.refresh_analytics_cache import do_refresh
        result = do_refresh(organization_id=args.org, client_id=args.client)
        print("Refresh result:", result)
        return 0 if not result.get("error") else 1

    print("Set REFRESH_CACHE_URL to API base URL for DAG, or use --in-process for local test.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
