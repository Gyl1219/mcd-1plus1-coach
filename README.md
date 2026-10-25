# 麦麦随心配教练 · McD 1+1 Coach

> 2026 麦当劳程序员创意开发大赛参赛作品（MCD Developer Innovation Challenge 2026）
> 用 McDonald's China 官方 MCP 的 6 个只读工具，把 1+1 随心配的红蓝区组合、营养和官方实付价一次算清楚。

## 一句话

**13.9 还是 14.9？哪个组合热量最低？——问一句，教练用官方 `calculate-price` 真核价，只算不买。**

## 解决什么问题

1+1 随心配有**两个桶**（人气经典 ¥14.9 / 精选超值 ¥13.9），红蓝两区 20+ 个选项，组合上百种。菜单页只给你看商品图和 diffPrice 标签，不告诉你：

- 两个桶里同名商品（如双层吉士汉堡）在哪个桶更便宜；
- 任意组合的真实到手价（展示的 `+¥1/-¥1` 是桶间差价，不是组合价格）；
- 每个组合的热量和钠含量——减脂期、控盐人群根本没法决策。

本技能把这条决策链压缩成一次对话：**门店 → 桶 → 组合 → 官方核价 → 营养对照**，每个价格都来自 `calculate-price` 的权威返回（单位分），绝不心算。

## 真实调用示例（2026-10-25，成都锦江区联升巷店 storeCode=3450410）

```
calculate-price · 人气经典随心配(9900013304) 双层吉士+可乐中杯
→ price: 1490 (¥14.9)   discount: 0

calculate-price · 精选超值随心配(9900015568) 同样双层吉士+可乐中杯
→ price: 1390 (¥13.9)   discount: 0   ← 同口味省 1 元

calculate-price · 精选超值随心配 那么大鸡排+可乐中杯
→ price: 1390 (¥13.9)，营养 385+147=532 kcal（8 个红区组合里蛋白质最高）
```

## 实测发现的坑（写给后来人）

| 坑 | 结论 |
|---|---|
| `query-meal-detail` 入参 | 参数名是 `code`，不是 `productCode`；`orderType`/`beType` 必传否则报 `400 缺少参数` |
| `diffPrice` 的含义 | 是桶间展示差价，**桶内任意组合实付价恒等于桶价**（已验证 4+ 组合，521316 标 `-¥1` 但实付仍是桶价） |
| 营养表 | `list-nutrition-foods` 的 `data` 是**转义 CSV 字符串**（160 条），要先 JSON 解析再 splitlines；新品（高达吉士双牛堡）不在表内，缺失必须如实标注 |
| 券生效时间 | 麦麦省券常为"明日 10:30 起"生效，提前用券核价报 `600012 此卡券不在使用日期内`——是业务规则不是故障，技能会提示生效时间 |
| 到店自取 | `beType=1` 时不传 `beCode`，传了反而可能 400 |

## MCP 接入

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_MCP_TOKEN" }
    }
  }
}
```

Token 申请：[open.mcd.cn/mcp](https://open.mcd.cn/mcp) → 手机号登录 → 控制台激活。

### 调用的工具（6 个，全部只读）

`query-nearby-stores` · `query-meals` · `query-meal-detail` · `calculate-price` · `list-nutrition-foods` · `available-coupons` / `query-my-coupons`

**明确不调用**：`create-order`、`cancel-order`、`party-order-create`、`mall-create-order`、`draw-lottery` 等一切写操作。支付永远在麦当劳官方 APP 完成。

## 使用

把 `SKILL.md` 放进 WorkBuddy（或其他支持 Skill 的 Agent 宿主）技能目录，配好上面的 MCP 连接即可。也可以直接阅读 `SKILL.md` 作为提示词工程参考，在任何 MCP Client 里手动复现工作流。

## 参赛声明

见 [CONTEST_DECLARATION.md](CONTEST_DECLARATION.md)。本项目个人非商业用途，与麦当劳中国无隶属关系；所有价格数据来自官方 MCP 实时返回，仅作决策参考。

## 目录结构

```
├── SKILL.md                 # 技能主文件（含业务事实与工作流）
├── CONTEST_DECLARATION.md   # 参赛声明
├── MCP_INTEGRATION.md       # MCP 接入实测记录（35 工具快照 + 6 工具实测台账）
├── workbuddy.md             # WorkBuddy 开发留痕
└── measured/measured_ledger.json  # 实测数据台账（组合、价格、营养）
```
