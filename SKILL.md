---
name: customer-email-deep-search
description: 给定客户清单（公司名 + 域名），从公开网页与搜索引擎批量挖出该域名下的邮箱地址，输出带来源证据与 A/B/C 概率分级的清单。只在需要为客户清单找收件地址、或核对某公司现有邮箱是否真实时使用；不做 SMTP 验证、不做在职核验、不负责发现新客户。
---

# customer-email-deep-search

输入一份客户清单，输出每家公司在自有域名下能公开找到的全部邮箱地址，带证据与分级。

## 何时用

- 手里已有客户清单（公司 + 域名），需要一批可发信的收件地址。
- 怀疑清单里某个地址是当年瞎猜拼出来的，想用「真实存在的地址挖不挖得到」来交叉验证。

## 何时不用

- 要发现新客户 → 用上游的客户挖掘技能。
- 要确认地址一定能送达 → 本技能不做 SMTP，做不到。
- 要确认某人还在职 → 本技能不查。

## 跑法

技能装在 `~/.dsh/skills/customer-email-deep-search/`（Windows：`C:\Users\<你>\.dsh\skills\customer-email-deep-search\`），
**不依赖当前目录**，从任何项目里都能直接调：

```powershell
$skill = "$env:USERPROFILE\.dsh\skills\customer-email-deep-search\run.py"

python -X utf8 $skill run --customers customers.csv --out out\            # 官网 + 搜索
python -X utf8 $skill run --customers customers.csv --out out\ --local-only   # 只爬官网，零成本
python -X utf8 $skill dns --domains a.com,b.de                            # 只看域名健康
```

在仓库目录里开发时，`python -m ceds ...` 与 `python run.py ...` 等价。

参数：`--max-pages`（每域最多抓几页，默认 12）、`--workers`（并发，默认 6）、`--limit`（只跑前 N 家，调试）、`--api-key`。

Key 从环境变量 `DEEPSEEK_API_KEY` 或 `~/.dsh/.env` 读取；没有 key 时自动跳过搜索通道，只爬官网。

## 流程

1. **域名健康**：先查 MX/A，死域直接标掉，省得白爬。
2. **官网爬取**：首页 + 最多 N 个关键词页（impressum / kontakt / team / about / karriere / presse / service / haendler / mentions 等），提取页面里出现的本域邮箱，记录来源 URL。
3. **搜索通道**（可选）：每个域名一条 `"@domain"` 检索，从结果摘要里再捞一批，标为 third_party。
4. **清洗**：`[at]`/`(at)`/`&#64;`/`%40` 归一化；剔除占位符（`john.doe`、`max.mustermann`、`youremail`）、图片名、退信箱。
5. **评分**：证据形态 + 具名程度 + 独立来源数 + 域名健康 → 0–100 → A/B/C。
6. **输出**：`addresses.csv`（全量）、`report.md`（按公司分组）、`summary.json`。

## 硬规则

- **不构造地址**。只有页面里真实出现过才算。带 `inferred` 标记的，仅在确有必要时人工补，且一律 C 级。
- **不跨域移植格式**。A 公司的 `vorname.nachname@` 不能套到 B 公司头上。
- **不抓个人隐私页**，不绕登录。`robots.txt` 默认遵守。
- **域名健康只用 DNS**，绝不与对方 MX 建连。
- **A 级 ≠ 已验证**。对外表述必须写「高概率」，不写「已验证」。

## 输出怎么用

- 先发 A 级具名地址；没有具名就发 A 级 role 箱，并在正文第一句请求转交。
- 硬退信回流：把退信地址记下来，同域其他地址一并降分——没有这条回流，分数永远不可校准。

## 已知失真

- 大型机构（遗产机构、连锁餐饮）会挖出几十个分店/场馆箱，真实但不掌采购。
- “邮箱格式示例”站（prospeo 一类）会吐出占位符，黑名单已覆盖常见形态，仍需人工抽查。
- 展会主办方名录多为 JS 渲染，`site:` 搜不到，别指望从展商索引页批量刮邮箱。
