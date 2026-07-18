# GitHub Pages / OCI 部署说明

## GitHub Pages

1. 将本仓库推送到 GitHub。
2. Settings → Pages → Source: **Deploy from a branch**
3. Branch: `main`（或你的默认分支），Folder: **/docs**
4. 保存后站点地址形如：`https://<user>.github.io/<repo>/`

前端从相对路径 `./data/*.json` 读取数据，与 Pages 同源，无需 CORS。

## OCI 每日任务

在 OCI 机器上：

```bash
git clone <repo-url> a-share-monitor
cd a-share-monitor/collector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 首次回填（约 2 年，份额按日请求，可能需 10+ 分钟）
python run.py backfill

# 验证导出
ls ../docs/data/
```

配置 cron（交易日 18:00 CST，份额多为 T+1）：

```cron
0 18 * * 1-5 cd /path/to/a-share-monitor && PUSH_TO_GITHUB=1 ./collector/run_daily.sh >> logs/daily.log 2>&1
```

### 用 Deploy Key 推送

1. 在 OCI 生成只用于本仓库的 key：`ssh-keygen -t ed25519 -f ~/.ssh/hj_observe_deploy -N ""`
2. GitHub 仓库 → Settings → Deploy keys → 添加 **公钥**，勾选 Allow write
3. 配置 git remote 使用该 key，例如 `~/.ssh/config`：

```
Host github.com-hj
  HostName github.com
  User git
  IdentityFile ~/.ssh/hj_observe_deploy
```

然后将 remote 改为 `git@github.com-hj:<user>/<repo>.git`。

`run_daily.sh` 在 `PUSH_TO_GITHUB=1` 时会 `git add docs/data`、commit、push。

可选环境变量：

- `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL`：提交作者（默认 hj-bot）
