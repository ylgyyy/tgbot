# Telegram 双向传话筒机器人

匿名双向消息转发，支持所有消息类型。

## 功能

- **双向传话** — 陌生人发消息 → 转发给主人；主人发消息 → 转发给当前对话对象
- **多对话切换** — 支持最近 5 个联系人快速切换
- **🚫 黑名单** — 拉黑 / 解封骚扰用户
- **⚠️ 骗子库** — 标记、管理可疑用户
- **多类型消息** — 文字、图片、视频、语音、贴图等全部支持

---

## 配置准备

部署前，先在 `docker-compose.yml` **同目录**下创建 `.env` 文件，存放密钥。

```bash
cp .env.example .env
```

然后编辑 `.env`，填入真实值：

| 字段 | 说明 |
|------|------|
| `BOT_TOKEN` | Telegram 机器人 Token，找 [@BotFather](https://t.me/BotFather) |
| `OWNER_ID` | 你的 Telegram 数字 ID，找 [@userinfobot](https://t.me/userinfobot) |
| `TG_PROXY` | 代理地址，直连可留空（如 `http://127.0.0.1:7897`） |
| `TZ` | 时区，建议 `Asia/Shanghai` |

> ⚠️ `.env` 不进版本库、不进镜像，只留在服务器上。

---

## Docker 运行

镜像由 GitHub Actions 自动构建并推送到 Docker Hub 公开仓库 `ylgy007/tgbot`，部署时直接拉取即可，**无需本地构建、无需登录**。

### 方式一：docker-compose（推荐）

```bash
docker compose up -d
```

### 方式二：纯 docker 命令

```bash
docker run -d --name tgbot \
  --env-file .env \
  -e DATA_DIR=/app/data \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  ylgy007/tgbot:latest
```

> 常用命令：`docker compose restart`（重启）、`docker compose down`（停止）、`docker compose logs -f`（看日志）。

---

## 数据持久化

黑名单 (`blacklist.json`) 和骗子库 (`scammers.json`) 保存在 `./data/` 目录，重启/升级不丢失。

---

## 命令列表（管理员）

| 命令 | 功能 |
|------|------|
| `/switch` | 切换对话对象 |
| `/block` | 拉黑用户 |
| `/unblock` | 解除拉黑 |
| `/blacklist` | 查看黑名单 |
| `/addscam` | 添加骗子 |
| `/delscam` | 删除骗子 |
| `/scamlist` | 查看骗子库 |

---

## 版本与发布

发版前，先在 [`RELEASE_NOTES.md`](RELEASE_NOTES.md) 里写好本次版本的更新说明，然后打标签并推送（或直接 `upload.bat v1.0.1`）：

```bash
git tag v1.0.1
git push origin v1.0.1
```

GitHub Actions 会自动：

1. 构建镜像并打上版本号 tag（`ylgy007/tgbot:v1.0.1`，`latest` 同步更新）
2. 在 GitHub 创建 Release，把 `RELEASE_NOTES.md` 的内容作为**版本说明**

想**固定版本**部署（不追 `latest`），把 `docker-compose.yml` 里的镜像改成具体版本号：

```yaml
image: ylgy007/tgbot:v1.0.1
```
