# -*- coding: utf-8 -*-
"""McProbe - McDonald's China MCP readonly tool probe (contest entry)."""
import json, sys, time
import urllib.request

URL = "https://mcp.mcd.cn"
TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
_id = [0]

def rpc(method, params=None):
    _id[0] += 1
    payload = {"jsonrpc": "2.0", "id": _id[0], "method": method}
    if params is not None:
        payload["params"] = params
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + TOKEN,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        body = r.read().decode()
    for line in body.splitlines():
        if line.startswith("data:"):
            body = line[5:].strip()
            break
    try:
        return json.loads(body)
    except Exception:
        return {"raw": body[:500]}

rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "mcprobe", "version": "0.1.0"}})

def call_tool(name, args=None):
    out = rpc("tools/call", {"name": name, "arguments": args or {}})
    if "error" in out:
        return {"ok": False, "err": str(out["error"])[:200]}
    content = out.get("result", {}).get("content", [])
    text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
    try:
        return {"ok": True, "data": json.loads(text)}
    except Exception:
        return {"ok": True, "data": text[:1200]}

if __name__ == "__main__":
    result = {}
    tools_to_probe = [
        ("now-time-info", {}),
        ("query-my-account", {}),
        ("query-my-coupons", {}),
        ("available-coupons", {}),
        ("campaign-calendar", {}),
        ("list-nutrition-foods", {}),
        ("query-nearby-stores", {"latitude": 30.57, "longitude": 104.06}),
        ("order-list", {}),
        ("query-lottery-info", {}),
        ("mall-points-products", {}),
    ]
    for name, args in tools_to_probe:
        t0 = time.time()
        r = call_tool(name, args)
        dt = round(time.time() - t0, 2)
        if r.get("ok"):
            d = r["data"]
            if isinstance(d, dict):
                keys = list(d.keys())[:8]
                print(f"[OK  {dt:>5}s] {name}: keys={keys}")
            else:
                print(f"[OK  {dt:>5}s] {name}: {str(d)[:150]}")
        else:
            print(f"[FAIL{dt:>5}s] {name}: {r.get('err','')[:150]}")
        result[name] = r
        time.sleep(0.4)
    with open("probe_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
