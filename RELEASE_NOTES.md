# 发布说明

<!-- 发版前在此填写本次版本更新内容，作为 GitHub Release 的说明 -->

## v1.0.1

- 敏感变量（BOT_TOKEN / OWNER_ID）迁移到 `.env`，不再硬编码
- 新增 Docker + GitHub Actions 自动构建，镜像推送到 Docker Hub
- 骗子库改为 GitHub 远程只读源，启动时 + 每 5 分钟自动刷新
- 黑名单保持本地文件，重启/升级不丢失
- 新增 28 个骗子 ID

## v1.0.0

- 首个版本：双向传话筒、黑名单、骗子库。
