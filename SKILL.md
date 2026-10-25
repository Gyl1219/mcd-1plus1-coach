---
name: 麦麦随心配教练
description: 麦当劳中国 1+1 随心配红蓝区组合教练。给一句"今天想吃啥/预算/热量要求"，输出红蓝两区全部可点组合的营养对照与官方实付核价，告诉你 13.9 还是 14.9、哪个组合更划算。基于麦当劳中国官方 MCP（35 工具中的 6 个只读工具），零下单、零代付。
---

# 麦麦随心配教练 (McD 1+1 Coach)

帮用户用麦当劳 1+1 随心配吃得最值。核心能力：**红蓝区组合×营养×官方核价**三维对照，只算不买。

## 何时使用

用户提到以下任何一种情况时使用本技能：
- "1+1 随心配怎么点" / "随心配有哪些组合"
- "13.9 的随心配有什么" / "14.9 和 13.9 差在哪"
- "随心配哪个热量最低" / "减脂期能点啥随心配"
- "帮我算算这单随心配多少钱"
- 给出任意红区+蓝区两个单品名，要求核价

## MCP 工具链（全部只读，零下单）

| 工具 | 用途 |
|---|---|
| `query-nearby-stores` | 定门店（拿 storeCode） |
| `query-meals` | 拉菜单，定位两个随心配桶 |
| `query-meal-detail` | 拉桶的红区/蓝区选项与 diffPrice |
| `calculate-price` | 官方实付核价（唯一权威价格来源，单位分） |
| `list-nutrition-foods` | 营养对照（kcal/蛋白/钠） |
| `available-coupons` / `query-my-coupons` | 提醒可用券（可选） |

## 关键业务事实（2026-10-25 成都实测）

1. **两个随心配桶**：
   - `9900013304` 人气经典随心配 = **14.9 元**（1490 分）
   - `9900015568` 精选超值随心配 = **13.9 元**（1390 分）
   - 两桶的红蓝区选项高度重叠；`diffPrice` 是桶间展示差价，**桶内任意组合实付价 = 桶价**（已用 calculate-price 验证 4+ 种组合）。
2. **算价入参结构**（calculate-price）：
   ```json
   {"storeCode":"...","orderType":1,"beType":1,
    "items":[{"productCode":"9900015568","quantity":1,
      "choiceList":[{"roundId":1,"code":"521156","quantity":1},
                    {"roundId":2,"code":"3050","quantity":1}]}]}
   ```
   - 到店自取 beType=1 不传 beCode；query-meal-detail 的入参名是 `code` 不是 `productCode`。
3. **营养表**：`list-nutrition-foods` 返回 160 条 CSV 行（productName,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium），data 字段是转义字符串，需先 JSON 解析再 splitlines。新品（如高达吉士双牛堡）可能不在表内——缺失就明说，禁止拿同类目数据冒充。
4. **券的时间坑**：麦麦省券常为"明日 10:30 起"生效，提前用券核价会报 `600012 此卡券不在使用日期内`——这不是故障，要在输出里提示用户生效时间。

## 工作流

1. 问用户城市/门店（或用默认门店），`query-nearby-stores {beType:1,searchType:2,city:"...",keyword:"..."}` 取 storeCode。
2. `query-meals {storeCode,orderType:1,beType:1}` 确认两个随心配桶 code 当日在售。
3. `query-meal-detail` 逐桶拉红区(roundId=1)/蓝区(roundId=2)选项。
4. 按用户诉求（预算/热量/忌口）筛组合，给最多 3 个方案，**每个方案都用 calculate-price 真实核价**，报"官方实付 X 元"。
5. 附营养对照表（kcal+钠），标注"营养表未收录"的项。
6. 结尾固定提醒：只算价不代下单，下单请到麦当劳 APP/小程序。

## 输出格式

```
🍗 方案一：那么大鸡排 + 可乐中杯 —— 官方实付 ¥13.9
   热量 385+147=532 kcal | 钠 996mg（偏高，今天其他餐少盐）
...
⚠️ 你有 1 张 11.9 元麦辣鸡腿堡券明日 10:30 生效，明天点更省
```

## 边界（硬性）

- **绝不调用 create-order / cancel-order / party-order-create / mall-create-order**。只算不买。
- 价格只认 calculate-price 返回（单位分），不心算、不用菜单展示价代替。
- Token 不落盘、不输出到对话。
- 营养数据缺失时如实说"官方营养表暂未收录"，不编造。
