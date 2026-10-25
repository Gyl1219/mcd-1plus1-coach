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

### 可运行参考引擎（Python ≥3.11，零依赖）

```bash
# 确定性决策引擎 + MCP 薄客户端，全程只读 allowlist，写操作在代码层被拒绝
python demo.py YOUR_MCP_TOKEN 成都市 春熙路
```

真实运行输出（2026-10-25，成都锦江区联升巷店）见 [measured/demo_output_2026-10-25.txt](measured/demo_output_2026-10-25.txt)：

```
方案1：小薯条 + 无糖可口可乐中杯 —— 官方实付 ¥14.9，热量 210 kcal
方案2：小薯条 + 无糖可口可乐中杯 —— 官方实付 ¥13.9，热量 210 kcal   ← 同样吃法省 1 元
方案3：小薯条 + 锡兰红茶 —— 官方实付 ¥14.9，热量 212 kcal
```

引擎设计原则：
- **价格只认官方核价**——每桶一次 `calculate-price`（桶价恒定已实测验证），绝不心算；
- **营养缺失如实标注**——新品（高达吉士双牛堡）不在官方营养表，输出"官方营养表暂未收录"，不用同类目冒充；
- **门槛只过滤不放宽**——预算/热量条件不满足时输出"条件未放宽"提示，绝不偷偷降级条件。

### 测试与 CI

13 个确定性单元测试（fixture 为真实 MCP 响应裁剪版，离线可跑）：

```bash
python -m unittest discover -s tests -v   # 13 tests, OK
```

GitHub Actions 矩阵（Ubuntu/Windows × Python 3.11/3.13）+ 仓库凭据泄露扫描，见 [.github/workflows/ci.yml](.github/workflows/ci.yml)。

## 参赛声明

见 [CONTEST_DECLARATION.md](CONTEST_DECLARATION.md)。本项目个人非商业用途，与麦当劳中国无隶属关系；所有价格数据来自官方 MCP 实时返回，仅作决策参考。

## 目录结构

```
├── SKILL.md                 # 技能主文件（含业务事实与工作流）
├── demo.py                  # 可运行 demo（真实 Token，端到端只读链路）
├── src/
│   ├── mcd_client.py        # MCP 薄客户端（stdlib，只读 allowlist，写操作在代码层被拒）
│   └── coach.py             # 确定性决策引擎（解析/营养/排序/门槛，纯函数）
├── tests/test_coach.py      # 13 个离线确定性单元测试
├── .github/workflows/ci.yml # CI：4 矩阵测试 + 凭据泄露扫描
├── CONTEST_DECLARATION.md   # 参赛声明
├── MCP_INTEGRATION.md       # MCP 接入实测记录（35 工具快照 + 15 项实测台账）
├── workbuddy.md             # WorkBuddy 开发留痕
└── measured/                # 实测台账 JSON + demo 真实输出（脱敏）
```
