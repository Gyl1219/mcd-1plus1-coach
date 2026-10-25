# MCP 接入实测记录（MCP_INTEGRATION）

> 测试时间：2026-10-25 21:17–21:32 (GMT+8) · 协议：Streamable HTTP · 端点：`https://mcp.mcd.cn`
> 服务器版本：`mcd-mcp 1.0.0`（`tools/list` 返回 35 个工具）

## 1. 连接握手

```
POST /  initialize  protocolVersion=2025-03-26
→ 200 {"capabilities":{"tools":{}},"serverInfo":{"name":"mcd-mcp","version":"1.0.0"}}
```

## 2. 实测台账（7 项服务全部真实 Token 调用）

| # | 工具 | 入参 | 结果 | 关键返回 |
|---|---|---|---|---|
| 1 | `now-time-info` | `{}` | ✅ 200 | 服务器时间 2026-10-25 21:20:36 |
| 2 | `query-my-account` | `{}` | ✅ 200 | accountId=E C99…（脱敏），availablePoint=0，expiredPoint=82 |
| 3 | `available-coupons` | `{}` | ✅ 200 | 3 张可领：免费脆薯饼 / 11.9元麦辣鸡腿堡 / 19.9元王牌炸鸡任选2 |
| 4 | `query-my-coupons` | `{page:"1"}` | ✅ 200 | 领券后券包 2 张（脆薯饼券未入列表，疑似到店专项） |
| 5 | `query-nearby-stores` | `{beType:1,searchType:2,city:"成都市",keyword:"春熙路"}` | ✅ 200 | 返回联升巷店 storeCode=3450410 等，含 reservationTimeOptions |
| 6 | `query-meals` | `{storeCode:"3450410",orderType:1,beType:1}` | ✅ 200 | 分类菜单；两个随心配桶 9900013304 / 9900015568 在售 |
| 7 | `query-meal-detail` | `{storeCode,code:"9900015568",orderType:1,beType:1}` | ✅ 200 | 红区 8 项 + 蓝区 16 项，含 diffPrice、modification 特调 |
| 8 | `calculate-price` | 桶 5568 组合 521156+3050 | ✅ 200 | **price=1390 分**，discount=0，takeWayList 堂食/外带 |
| 9 | `calculate-price` | 桶 5568 组合 1450+4437 / 521316+4420 / 1120+3050 | ✅ 200 | 全部 **price=1390 分** → 证实"桶内组合实付=桶价" |
| 10 | `calculate-price` | 桶 3304 组合 1120+3050 | ✅ 200 | **price=1490 分** → 两桶价差证实 |
| 11 | `calculate-price` | 双桶合并（5568+3304 各 1 份） | ✅ 200 | price=2880，productList 分项 1390/1490 |
| 12 | `calculate-price` | 单品 1440（麦辣鸡腿汉堡） | ✅ 200 | price=2250 分（¥22.5） |
| 13 | `calculate-price` | 单品 1440 + 麦辣券 | ❌ 600012 | "此卡券不在使用日期内"——券 10-26 10:30 才生效，业务规则非故障 |
| 14 | `list-nutrition-foods` | `{}` | ✅ 200 | data 为转义 CSV 字符串，160 条，含 kcal/protein/sodium/calcium |
| 15 | `order-list` | `{}` | ✅ 200 | `data:{}` 空列表（新账号无历史订单） |

> 注：#4 的 `auto-bind-coupons`（一键领券）亦已实测成功（3/3 张领取成功），属于对用户账户有利且可弃用的操作；技能运行时默认**不自动领券**，仅在用户明示时调用。

## 3. 关键入参 Schema 摘录（verbatim）

### query-nearby-stores
```json
{"properties":{"beType":{"enum":[1,5],"type":"integer"},"city":{"type":"string"},
"keyword":{"type":"string"},"searchType":{"default":1,"enum":[1,2],"type":"integer"}},
"required":["beType","searchType"],"type":"object"}
```

### query-meal-detail
入参名是 **`code`**（非 productCode）；`storeCode`、`orderType`、`beType` 均必传，缺任一项返回：
```json
{"success":false,"code":400,"message":"beType1-到店取餐，2-麦乐送到家…code不得为空白"}
```

### calculate-price（随心配组合最小入参）
```json
{"storeCode":"3450410","orderType":1,"beType":1,
 "items":[{"productCode":"9900015568","quantity":1,
   "choiceList":[{"roundId":1,"code":"521156","quantity":1},
                 {"roundId":2,"code":"3050","quantity":1}]}]}
```
返回金额字段单位均为**分**：`price / originalPrice / discount / productPrice / deliveryPrice / packingPrice`。

## 4. 营养表解析要点

`list-nutrition-foods` 的 `data` 是**双重编码**：MCP text → JSON → `data` 字段内是含 `\n` 的 CSV 字符串：

```
[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  小薯条,null,877,210,3,9,28,120,13
  双层吉士汉堡,null,1796,429,27,22,31,1017,232
```

- 必须先 `json.loads` 整个响应，再对 `data` 字段 `splitlines()`。
- 新品可能缺行（如"高达吉士双牛堡"521316 未收录）——技能侧如实标注"官方营养表暂未收录"，禁止用同类目数据冒充。

## 5. 业务规则发现

1. **桶价恒定**：随心配桶内任意红+蓝组合的实付价 = 桶价（13.9 / 14.9），`diffPrice` 仅为桶间展示差价。这意味着"选哪个桶"比"选哪个组合"更影响价格。
2. **券生效窗口**：麦麦省券普遍次日 10:30 生效；`600012` 报错属于正常业务规则，技能会解析券有效期并提示用户。
3. **到店自取不传 beCode**：`beType=1` 时 calculate-price / query-meals 均无需 beCode；外送(beType=2)/得来速(5)/团餐(6) 才需要。
4. **限流**：600 req/min（官方 README），本技能每次决策 ≤10 次调用，余量充足。
