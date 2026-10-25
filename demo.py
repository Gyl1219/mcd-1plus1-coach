# -*- coding: utf-8 -*-
"""Live demo: run the full coach chain against the official MCP with a real
token, and print measured proposals. Run locally:

    python demo.py YOUR_MCP_TOKEN [city] [keyword]

Never commit the token. Output includes only public menu/price data.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mcd_client import McdMcpClient  # noqa: E402
from coach import parse_bucket, parse_nutrition, rank_combos, format_proposals  # noqa: E402

# 实测锚点（2026-10-25 成都）：两个随心配桶
TARGET_BUCKETS = ("9900013304", "9900015568")


def main() -> None:
    token = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MCD_MCP_TOKEN", "")
    if not token:
        sys.exit("usage: python demo.py YOUR_MCP_TOKEN [city] [keyword]")
    city = sys.argv[2] if len(sys.argv) > 2 else "成都市"
    keyword = sys.argv[3] if len(sys.argv) > 3 else "春熙路"

    cli = McdMcpClient(token)

    print(f"[1/4] now-time-info:", cli.call("now-time-info").get("data", {}).get("datetime", "?"))

    print(f"[2/4] query-nearby-stores {city}/{keyword}")
    stores = cli.call("query-nearby-stores", {"beType": 1, "searchType": 2, "city": city, "keyword": keyword})
    data = stores.get("data") or []
    if not data:
        sys.exit("no stores found")
    store = data[0]
    print(f"      -> {store['storeName']} (storeCode={store['storeCode']}, {store.get('distance','?')}m)")

    print("[3/4] query-meals + query-meal-detail x2")
    meals = cli.call("query-meals", {"storeCode": store["storeCode"], "orderType": 1, "beType": 1})
    on_sale = {m["code"] for cat in (meals.get("data", {}).get("categories") or [])
               for m in cat.get("meals", [])}
    nutrition = parse_nutrition(cli.call("list-nutrition-foods", {}))
    print(f"      -> nutrition rows: {len(nutrition)}")

    proposals = []
    for bucket_code in TARGET_BUCKETS:
        if bucket_code not in on_sale:
            print(f"      -> bucket {bucket_code} not on sale at this store, skip")
            continue
        detail = cli.call("query-meal-detail",
                          {"storeCode": store["storeCode"], "code": bucket_code,
                           "orderType": 1, "beType": 1})
        bucket = parse_bucket(detail)
        # 桶价恒定（实测）：每桶一次 calculate-price 即得全部组合的实付价
        first_blue = bucket["rounds"][1][0]["code"]
        first_pink = bucket["rounds"][2][0]["code"]
        price = cli.call("calculate-price", {
            "storeCode": store["storeCode"], "orderType": 1, "beType": 1,
            "items": [{"productCode": bucket_code, "quantity": 1,
                       "choiceList": [{"roundId": 1, "code": first_blue, "quantity": 1},
                                      {"roundId": 2, "code": first_pink, "quantity": 1}]}],
        }).get("data", {}).get("price")
        print(f"      -> {bucket['name']} official price: {price} fen")
        proposals.extend(rank_combos(bucket, price, nutrition, max_kcal=600))

    proposals.sort(key=lambda c: (c["kcal"] is None, c["kcal"] or 0))
    print("\n[4/4] Top proposals (≤600 kcal gate, official prices only):\n")
    print(format_proposals(proposals, top=5))
    print("\n※ 只算不买：下单请到麦当劳 APP/小程序完成支付。")


if __name__ == "__main__":
    main()
