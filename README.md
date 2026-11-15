# customer-email-deep-search

给定一份客户清单（公司名 + 域名），从**公开网页**上尽可能地挖出这家公司自有域名下的邮箱地址，并给每个地址标上**来源证据**与**概率等级**。

为 B2B 冷启动找收件地址而写。不是爬虫框架，也不是“邮箱验证器”。

> **English**: Feed it a customer list (company + domain); it crawls the company's own pages and one `"@domain"` search per domain, returns every address it can see with evidence URLs and an A/B/C probability grade. No SMTP probing, no commercial verification API. Zero dependencies, Python 3.10+.

---

## 它做什么 / 不做什么

| 做 | 不做 |
| --- | --- |
| 爬官网首页 + Impressum / Kontakt / Team / Karriere / Presse 等页 | ❌ 不做 SMTP RCPT 探测、不建连对方 MX |
| 用 DeepSeek Search 做 `"@domain"` 全域检索 | ❌ 不调用任何商业邮箱验证 API |
| 一个域名能挖多少挖多少，不设下限与上限 | ❌ 不发现新客户（客户清单由上游给你） |
| 每个地址记下：来自哪个页面、被几个来源提到 | ❌ 不核验联系人是否仍在职 |
| 按证据强弱输出 A / B / C 概率等级 | ❌ 不保证地址真实存在 |

**一点必须先说清的事**：没有 SMTP 环节时，任何“真假判断”都只是**排序**，不是**验证**。程序能做的是——把在官网页面上真实出现过的地址排在前面，把由姓名推断拼出来的排在后面，把占位符和死域剔掉。真正的地面真值只有两个：**硬退信**（否）和**回信**（是）。所以输出里的 A 级不代表“已验证”，只代表“高概率”。

---

## 安装

零第三方依赖，Python 3.10+ 即可：

```bash
git clone https://github.com/G2E-Michael/customer-email-deep-search.git
cd customer-email-deep-search
python -m ceds run --customers examples/customers.sample.csv --out out/
```

只有走搜索通道时需要一个 DeepSeek API key（[申请](https://platform.deepseek.com/)）：

```bash
export DEEPSEEK_API_KEY=sk-...        # Windows: set DEEPSEEK_API_KEY=sk-...
# 或者写进 ~/.dsh/.env，程序会自动读取其中的 DEEPSEEK_API_KEY
```

加 `--local-only` 就完全离线：只爬官网，不花钱。不加时默认会走搜索通道（每个域名一条检索，约 $0.00075）。

## 作为 DSH 技能安装（一次装好，所有项目通用）

DSH 在每次会话启动时扫描用户级技能目录 `~/.dsh/skills/<name>/SKILL.md`（Windows：`C:\Users\<你>\.dsh\skills\`），按 `SKILL.md` 里 `name` / `description` 决定何时调用。

```powershell
# 1) 复制到全局技能目录
$dst = "$env:USERPROFILE\.dsh\skills\customer-email-deep-search"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -Recurse -Force .\customer-email-deep-search\* $dst

# 2) 从任意项目调用：不用 cd、不用 PYTHONPATH、不用 pip install
python -X utf8 "$dst\run.py" run --customers .\customers.csv --out .\out
```

- 装好的目录就是本仓库的完整副本（去掉 `.git`），`run.py` 负责把 `ceds/` 加进 `sys.path`。
- 技能名与目录名一致：`customer-email-deep-search`。DSH 只在会话启动时扫描，装完要新开一个会话；当前会话的技能列表不会热加载。
- 更新：重新覆盖目录即可，无版本锁定；也可以 `git pull` 到仓库再复制一次。
- 想只在当前项目生效，就放到 `<项目>/.dsh/skills/customer-email-deep-search/`（项目级优先于用户级）。

装好之后，直接对 agent 说「按这份客户清单挖邮箱」，它会去调用本技能，而不是临时写脚本。

## 输入

`customers.csv`，UTF-8，表头固定：

```csv
id,name,domains,country,notes
D01,Lumos Experiences,lumos-experiences.com;curategroup.co.uk,UK,活动制作
D02,Velas y Candelas,velasycandelas.com,ES,蜡烛零售
```

- `domains` 用分号分隔，一家公司可以有多域（集团域 + 本地品牌域），多域往往能把地址数量翻一倍。
- 只有公司名没有域名时，先用别的办法把域名补上——本工具不负责猜域名。

## 输出

`out/addresses.csv`：

| 字段 | 说明 |
| --- | --- |
| `id` / `company` / `domain` | 归属 |
| `email` | 地址（小写） |
| `local` | @ 前的部分 |
| `kind` | `role`（info/kontakt/sales…）或 `named`（疑似具名） |
| `evidence` | `official`（该域自己的页面）/ `third_party`（他站提及）/ `inferred` |
| `sources` | 出现过的页面 URL，多个用 ` \| ` 分隔 |
| `source_count` | 独立来源数 |
| `dns` | `mx` / `a_only`（RFC 5321 隐式 MX）/ `null_mx` / `dead` |
| `score` / `grade` | 0–100 与 A/B/C |

`out/report.md` 是按公司分组、可直接贴进邮件的版本；`out/summary.json` 是计数汇总。

## 分级规则

评分是**启发式**，权重集中在一处（`ceds/score.py`），可以自己调：

| 维度 | 分值 |
| --- | --- |
| 证据形态 | official +40 / third_party +30 / inferred +10 |
| 具名程度 | named +10 / role +5 |
| 独立来源数 | 每多一个 +5，上限 +20 |
| 域名健康 | mx +10 / a_only +3 / dead −40 |
| 免费邮箱域（gmail 等） | −10 |
| 占位符 / 图片名 / 退信箱 | 直接丢弃 |

`A ≥ 70`，`B 45–69`，`C < 45`。

域名健康只查 DNS，不碰 SMTP：

- 有 MX → 正常。
- 无 MX 但有 A → 按 RFC 5321 §5.1 仍可投递，降一档。
- 无 MX 且无 A → 死域。
- `MX .`（NULL MX，RFC 7505）→ 明确拒收。

## 实测成色（18 家真实客户，2026-11）

- 20 个域名 → **156 个地址**，16/18 家有产出，单家中位数 3。
- 其中 **11/16 家**把清单里原有的首选发信地址原样挖了回来。
- 5 家没挖回来：3 家原地址是当年**按姓名格式推断构造**的，2 家来自招标文件署名。**真实存在的地址能挖到，构造出来的挖不到**——这套流程本身就是一台“构造地址过滤器”，不需要 SMTP。
- 两个失败模式：① 大型机构会挖出一堆分店/场馆前台箱（某遗产机构 81 个、某连锁餐饮 26 个），数量 ≠ 采购决策人；② “邮箱格式示例”网站（prospeo 一类）会污染结果，吐出 `john.doe@domain`、`j.doe@domain` 这种占位符——已内置黑名单，但仍建议人工扫一眼。

## 合规与边界

- 只读公开页面，遵守 `robots.txt`（默认开启，`--no-robots` 可关）。
- 不绕登录、不碰付费墙、不抓取个人隐私页。
- 抓来的地址用于 B2B 联络时，注意 GDPR 的合法利益基础、退订要求与来源留痕——`sources` 列就是给你留痕用的。
- 别拿它当“邮箱验证器”用：它不做任何 SMTP 交互。

## 目录

```
run.py          入口脚本（把 ceds/ 加进 sys.path，任意目录可跑）
ceds/
  cli.py       命令行入口
  extract.py   邮箱正则、[at]/[dot] 归一化、占位符过滤
  fetch.py     HTTP 抓取（UA、超时、编码、robots）
  crawl.py     站点爬取与页面挑选
  search.py    DeepSeek Search / Fetch 通道
  dnsx.py      纯 stdlib 的 MX/A 查询
  score.py     评分与分级
  pipeline.py  串起整条流水线
  report.py    CSV / Markdown 输出
examples/      样例输入
tests/         unittest
```

MIT License.
