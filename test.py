import sys
import json
import time
from typing import Optional

try:
    import requests
except Exception:  # pragma: no cover
    print("Requests library is not installed, please run: pip install requests", file=sys.stderr)
    sys.exit(1)


BASE = "http://127.0.0.1:8000/api"


def post_json(path: str, params: Optional[dict] = None, payload: Optional[dict] = None, timeout: int = 30):
    url = f"{BASE.rstrip('/')}/{path.lstrip('/')}"
    try:
        resp = requests.post(url, params=params, json=payload, timeout=timeout)
        resp.raise_for_status()
        try:
            return True, resp.json()
        except Exception:
            return True, {"raw": resp.text}
    except requests.RequestException as e:
        return False, {"error": str(e)}


def main():
    print("[1/3] Reset group and mentor assignments (delete all groups)...")
    ok, data = post_json("reset_groups/", params={"mode": "delete_all", "reset_seq": "1"})
    print(json.dumps({"ok": ok, "result": data}, ensure_ascii=False, indent=2))
    if not ok:
        sys.exit(1)

    '''
    # Wait for database transactions to be flushed
    time.sleep(0.5)

    print("\n[2/3] Generate Group(auto_group)...")
    ok, data = post_json("auto_group/")
    print(json.dumps({"ok": ok, "result": data}, ensure_ascii=False, indent=2))
    if not ok:
        sys.exit(1)

    print("\n[Optional] Perform a fallback grouping for students who have not yet been grouped(auto_group_fallback)...")
    ok_fallback, data_fallback = post_json("auto_group_fallback/")
    print(json.dumps({"ok": ok_fallback, "result": data_fallback}, ensure_ascii=False, indent=2))

    print("\n[3/3] Assign a mentor(assign_mentors)...")
    ok, data = post_json("assign_mentors/")
    print(json.dumps({"ok": ok, "result": data}, ensure_ascii=False, indent=2))
    if not ok:
        sys.exit(1)

    print("\nAll done. You can also access it in your browser:")
    print(" - http://127.0.0.1:8000/api/auto_group/")
    print(" - http://127.0.0.1:8000/api/assign_mentors/")
    '''

if __name__ == "__main__":
    main()


