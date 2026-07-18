# HJ OBSERVE · 汇金宽基 ETF 监测

用**ETF 总份额**（日频）代理观察「国家队 / 汇金」行为，并与对应宽基指数收盘价双轴对比。

> **数据语义：** 总份额是场内申赎合计，**不是**汇金精确持仓。宽基上汇金占比很高，份额净变化常被用作行为代理。份额多为 **T+1**。

## 架构

- **OCI（或本机）：** Python 采集 → SQLite → 导出 JSON
- **GitHub Pages：** 托管 `docs/` 静态看板，读 `docs/data/*.json`

## 默认标的

| 组别 | ETF（SSE / SZSE） | 对比指数 |
|------|-------------------|----------|
| 沪深300 | 510300 / 510310 / 510330 / 510360 / **159919** | 000300 |
| 上证50 | 510050 | 000016 |
| 中证500 | 510500 / **159922** | 000905 |
| 中证1000 | 512100 / **159845** | 000852 |
| 科创50 | 588080 | 000688 |
| 创业板 | **159915** | 399006 |

粗体为深交所。在 [`collector/config.yaml`](collector/config.yaml) 中增删。

## 数据源说明（含开源调研）

| 市场 | 官方公开接口 | 历史能力 | 本项目用法 |
|------|--------------|----------|------------|
| 上交所 | `query.sse.com.cn` 按日 ETF 份额 | 可按日回溯多年 | `fetch_shares.py` |
| 深交所 | `www.szse.cn` 基金规模日频 xlsx（`CATALOGID=scsj_fund_jjgm`） | **单次查询窗口约 6 个月**，可分段拼接多年 | `fetch_szse.py` |
| 指数 | 新浪日线 K 线 | 约最近 1023 根 | `fetch_index.py` |

### 开源 / 公开渠道结论

1. **没有发现**「深市 ETF 每日份额多年完整 CSV 一键下载」的成熟开源数据集（GitHub 上同类项目如 `national-team-position`、`etf-national-tracker` 也明确只做上交所或自建归档）。
2. **开源库可用作接口封装，不是现成仓库：**
   - [AKShare](https://github.com/akfamily/akshare) `fund_etf_scale_sse(date=...)`、`fund_scale_daily_szse(start,end)`（深市窗口 ≤6 个月）
   - 本项目不依赖 AKShare 运行时，直接打交易所官方接口（深市逻辑对齐 AKShare 实现）
3. **要更省事的多年库：** [Tushare `etf_share_size`](https://tushare.pro/document/2?doc_id=408)（沪深，需约 8000 积分）、Wind / Choice 等付费源。
4. **季报/半年报**有份额，但频率不够做日频观测。

结论：深市**不是没有历史**，而是官网不提供「任意单日一键」归档；用日频规模接口按 ≤6 个月分段拉取即可回填（本仓库已验证约 2 年深市数据）。

## 本地快速开始

```bash
cd collector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 历史回填（SSE 按日请求较慢；SZSE 按窗口拉取较快）
python run.py backfill

# 或指定区间
python run.py backfill --start 20240701 --end 20260717

# 每日增量（SSE 单日 + SZSE 近两周窗口 + 指数）
python run.py daily

# 仅从 SQLite 再导出 JSON
python run.py export
```

本地预览看板：

```bash
cd docs
python3 -m http.server 8080
# 打开 http://127.0.0.1:8080/
```

## 目录

```
collector/          采集与导出
  config.yaml
  run.py            backfill | daily | export
  fetch_shares.py   上交所
  fetch_szse.py     深交所
  run_daily.sh      OCI cron 入口（可 PUSH_TO_GITHUB=1）
docs/               GitHub Pages 根目录
  index.html
  styles.css
  app.js
  data/             meta.json / etf_shares.json / indexes.json / shares/YYYY.json
```

权威数据在本地/OCI 的 SQLite（默认 `data/monitor.db`，已 gitignore）。推送到 GitHub 的是导出的紧凑 JSON。

## 部署

见 [`docs/DEPLOY.md`](docs/DEPLOY.md)：Pages 选 branch 的 `/docs`；OCI cron 示例与 Deploy Key 推送说明。

```cron
0 18 * * 1-5 cd /path/to/a-share-monitor && PUSH_TO_GITHUB=1 ./collector/run_daily.sh >> logs/daily.log 2>&1
```

## License

MIT
