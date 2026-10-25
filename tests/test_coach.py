# -*- coding: utf-8 -*-
"""Deterministic tests for the coach engine — fixtures are 2026-10-25 real
MCP responses (trimmed). No network access in tests."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcd_client import extract_json  # noqa: E402
from coach import (  # noqa: E402
    BUCKET_FALLBACK_PRICE_FEN, combo_nutrition, format_proposals,
    parse_bucket, parse_nutrition, rank_combos,
)

HERE = os.path.dirname(__file__)

BUCKET_DETAIL = {
    "success": True, "code": 200, "message": "请求成功",
    "data": {
        "code": "9900015568", "name": "精选超值随心配",
        "rounds": [
            {"id": 1, "name": "蓝区", "choices": [
                {"code": "521156", "name": "那么大鸡排（椒盐风味）", "diffPrice": "+ ¥0"},
                {"code": "1120", "name": "双层吉士汉堡", "diffPrice": "+ ¥1"},
            ]},
            {"id": 2, "name": "粉区", "choices": [
                {"code": "3050", "name": "可乐中杯", "diffPrice": "+ ¥0"},
                {"code": "4420", "name": "迷你草莓新地", "diffPrice": "+ ¥0"},
            ]},
        ],
    },
}

NUTRITION_PAYLOAD = {
    "success": True, "code": 200,
    "data": "[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n"
            "  那么大鸡排,null,1612,385,24,21,24,996,13\n"
            "  双层吉士汉堡,null,1796,429,27,22,31,1017,232\n"
            "  可乐中杯,null,616,147,0,0,36,0,10\n"
            "  迷你草莓新地,null,511,122,2,3,21,42,78\n"
            "  无糖可口可乐中杯,null,0,0,0,0,1,35,0\n"
}


class TestExtractJson(unittest.TestCase):
    def test_embedded_payload(self):
        text = "# API Response Information\n\n## Original Response\n\n" \
               '{"success":true,"code":200,"data":{"price":1390}} trailing text'
        self.assertEqual(extract_json(text)["data"]["price"], 1390)

    def test_no_payload(self):
        out = extract_json("没有 JSON 的错误说明")
        self.assertFalse(out["success"])
        self.assertEqual(out["code"], -1)


class TestParseBucket(unittest.TestCase):
    def test_rounds(self):
        b = parse_bucket(BUCKET_DETAIL)
        self.assertEqual(b["bucket_code"], "9900015568")
        self.assertEqual(len(b["rounds"][1]), 2)
        self.assertEqual(b["rounds"][2][0]["code"], "3050")

    def test_upstream_error_raises(self):
        with self.assertRaises(ValueError):
            parse_bucket({"success": False, "code": 400, "message": "缺少参数"})


class TestParseNutrition(unittest.TestCase):
    def test_rows(self):
        t = parse_nutrition(NUTRITION_PAYLOAD)
        self.assertEqual(t["可乐中杯"]["kcal"], 147.0)
        self.assertEqual(t["无糖可口可乐中杯"]["kcal"], 0.0)  # 0 是合法值，不是缺失
        self.assertNotIn("高达吉士双牛堡", t)  # 新品确实不在表内


class TestComboNutrition(unittest.TestCase):
    def setUp(self):
        self.bucket = parse_bucket(BUCKET_DETAIL)
        self.table = parse_nutrition(NUTRITION_PAYLOAD)

    def test_sum(self):
        nut = combo_nutrition(self.bucket, "521156", "3050", self.table)
        self.assertTrue(nut["complete"])
        self.assertAlmostEqual(nut["total"]["kcal"], 385 + 147)

    def test_unlisted_reported_not_faked(self):
        # 521316（高达吉士双牛堡）官方营养表未收录 → 如实标注
        # 注：parse_bucket 的 rounds 键是 int；JSON round-trip 会变 str，故手动重建
        bucket = parse_bucket(BUCKET_DETAIL)
        bucket["rounds"][1].append({"code": "521316", "name": "高达吉士双牛堡", "diff_price": ""})
        nut = combo_nutrition(bucket, "521316", "3050", self.table)
        self.assertFalse(nut["complete"])
        self.assertIn("官方营养表暂未收录", nut["items"][0]["note"])


class TestRank(unittest.TestCase):
    def setUp(self):
        self.bucket = parse_bucket(BUCKET_DETAIL)
        self.table = parse_nutrition(NUTRITION_PAYLOAD)

    def test_rank_by_kcal_and_price(self):
        ranked = rank_combos(self.bucket, 1390, self.table)
        self.assertEqual(len(ranked), 4)
        # 双层吉士+可乐 = 429+147=576；那么大鸡排+可乐 = 385+147=532 → 排第一
        self.assertEqual(ranked[0]["blue"]["code"], "521156")
        self.assertTrue(all(c["price_fen"] == 1390 for c in ranked))

    def test_budget_gate_filters_never_relaxes(self):
        ranked = rank_combos(self.bucket, 1390, self.table, budget_fen=1200)
        self.assertEqual(ranked, [])

    def test_kcal_gate(self):
        ranked = rank_combos(self.bucket, 1390, self.table, max_kcal=500)
        self.assertEqual(ranked, [])
        ranked2 = rank_combos(self.bucket, 1390, self.table, max_kcal=540)
        self.assertEqual(len(ranked2), 2)  # 两个鸡排组合（507 / 532）

    def test_fallback_prices_documented(self):
        self.assertEqual(BUCKET_FALLBACK_PRICE_FEN["9900015568"], 1390)
        self.assertEqual(BUCKET_FALLBACK_PRICE_FEN["9900013304"], 1490)


class TestFormat(unittest.TestCase):
    def test_output_mentions_official_price(self):
        bucket = parse_bucket(BUCKET_DETAIL)
        ranked = rank_combos(bucket, 1390, parse_nutrition(NUTRITION_PAYLOAD))
        text = format_proposals(ranked, top=1)
        self.assertIn("官方实付 ¥13.9", text)
        self.assertIn("507", text)  # 鸡排+草莓新地 = 385+122

    def test_empty_condition_message(self):
        self.assertIn("条件未放宽", format_proposals([], top=3))


if __name__ == "__main__":
    unittest.main(verbosity=2)
