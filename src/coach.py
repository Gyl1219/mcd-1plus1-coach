# -*- coding: utf-8 -*-
"""1+1 随心配组合教练 · 确定性决策引擎（零依赖，价格只认官方核价）。

输入来自官方 MCP 的真实返回（解析后的 dict），本模块只做纯计算：
不心算价格、不编造营养、不产生任何下单意图。
"""
from __future__ import annotations

# 人气经典桶 9900013304 = ¥14.9，精选超值桶 9900015568 = ¥13.9
# （实测 calculate-price：两桶价格恒定，diffPrice 仅为桶间展示差价）
BUCKET_FALLBACK_PRICE_FEN = {"9900013304": 1490, "9900015568": 1390}

# 官方营养表未收录的新品，禁止用同类目数据冒充
KNOWN_UNLISTED = {"521316": "高达吉士双牛堡", "521881": "马来咖喱风味薄皮肉骨鸡3块"}


def parse_bucket(detail: dict) -> dict:
    """Parse query-meal-detail payload into {bucket_code, name, rounds:{1:[...],2:[...]}}."""
    if not detail.get("success"):
        raise ValueError(f"upstream error {detail.get('code')}: {detail.get('message')}")
    data = detail.get("data") or {}
    rounds = {}
    for r in data.get("rounds", []):
        rounds[r["id"]] = [
            {"code": c["code"], "name": c["name"],
             "diff_price": c.get("diffPrice", "")}
            for c in r.get("choices", [])
        ]
    return {"bucket_code": data.get("code"), "name": data.get("name"), "rounds": rounds}


def parse_nutrition(payload: dict) -> dict[str, dict]:
    """Parse list-nutrition-foods payload.

    data is a CSV string: header line [N]{productName,...}: then rows
    'name,desc,kj,kcal,protein,fat,carb,sodium,calcium' (null allowed).
    """
    raw = payload.get("data")
    if isinstance(raw, dict):  # already unwrapped by caller
        raw = raw.get("data", "")
    if not isinstance(raw, str):
        return {}
    table: dict[str, dict] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("[") or line.startswith("{"):
            continue
        parts = line.split(",")
        if len(parts) < 9:
            continue
        name, _desc, kj, kcal, protein, fat, carb, sodium, calcium = parts[:9]
        def num(v):
            try:
                return float(v)
            except ValueError:
                return None
        table[name] = {
            "kj": num(kj), "kcal": num(kcal), "protein": num(protein),
            "fat": num(fat), "carb": num(carb), "sodium": num(sodium),
            "calcium": num(calcium),
        }
    return table


def lookup_nutrition(name: str, nutrition: dict) -> dict | None:
    """Match a menu name against the nutrition table.

    Menu names carry flavour suffixes ('那么大鸡排（椒盐风味）') that the
    nutrition table omits; match by longest contained table name. Returns
    None when nothing matches — callers must report that honestly.
    """
    if name in nutrition:
        return nutrition[name]
    best, best_len = None, 0
    for table_name, row in nutrition.items():
        if table_name and table_name in name and len(table_name) > best_len:
            best, best_len = row, len(table_name)
    return best


def combo_nutrition(bucket: dict, blue: str, pink: str, nutrition: dict) -> dict:
    """Nutrition for one combo; unlisted items are reported honestly as None."""
    name2 = {c["code"]: c["name"] for r in bucket["rounds"].values() for c in r}
    items = []
    total = {"kcal": 0.0, "sodium": 0.0, "protein": 0.0}
    complete = True
    for code in (blue, pink):
        nm = name2.get(code, code)
        row = lookup_nutrition(nm, nutrition)
        if row is None or row["kcal"] is None:
            complete = False
            items.append({"code": code, "name": nm, "kcal": None,
                          "note": "官方营养表暂未收录"})
        else:
            items.append({"code": code, "name": nm, "kcal": row["kcal"],
                          "sodium": row["sodium"], "protein": row["protein"]})
            total["kcal"] += row["kcal"]
            total["sodium"] += row["sodium"] or 0.0
            total["protein"] += row["protein"] or 0.0
    return {"items": items, "total": total, "complete": complete}


def rank_combos(bucket: dict, price_fen: int, nutrition: dict,
                budget_fen: int | None = None, max_kcal: float | None = None) -> list[dict]:
    """Enumerate blue×pink combos, attach official price, rank by kcal asc.

    price_fen MUST come from a real calculate-price call (one per bucket is
    enough — bucket price is constant across combos, verified 2026-10-25).
    Combos failing budget/calorie gates are filtered, not silently relaxed.
    """
    blues = bucket["rounds"].get(1, [])
    pinks = bucket["rounds"].get(2, [])
    out = []
    for b in blues:
        for p in pinks:
            nut = combo_nutrition(bucket, b["code"], p["code"], nutrition)
            if max_kcal is not None and nut["complete"] and nut["total"]["kcal"] > max_kcal:
                continue
            if budget_fen is not None and price_fen > budget_fen:
                continue
            out.append({
                "bucket": bucket["bucket_code"], "bucket_name": bucket["name"],
                "price_fen": price_fen, "blue": b, "pink": p,
                "kcal": nut["total"]["kcal"] if nut["complete"] else None,
                "sodium": round(nut["total"]["sodium"], 1) if nut["complete"] else None,
                "nutrition_complete": nut["complete"],
                "items": nut["items"],
            })
    out.sort(key=lambda x: (x["kcal"] is None, x["kcal"] if x["kcal"] is not None else 0))
    return out


def format_proposals(ranked: list[dict], top: int = 3) -> str:
    """Render top-N proposals; missing nutrition is stated, never faked."""
    lines = []
    for i, c in enumerate(ranked[:top], 1):
        kcal = f"{c['kcal']:.0f}" if c["kcal"] is not None else "?"
        lines.append(
            f"方案{i}：{c['blue']['name']} + {c['pink']['name']}"
            f" —— 官方实付 ¥{c['price_fen'] / 100:.1f}，热量 {kcal} kcal"
        )
        for it in c["items"]:
            if it.get("note"):
                lines.append(f"   ⚠️ {it['name']}：{it['note']}")
    if not lines:
        lines.append("（没有满足预算/热量条件的组合——条件未放宽，请调整门槛）")
    return "\n".join(lines)
