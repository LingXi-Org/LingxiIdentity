# Bootstrap

首次启动只需要一次临时人工步骤：在开发 Compose profile 的 `http://localhost:3002` 创建 Logto 初始管理员和一个拥有内置 `Logto Management API access` 角色的 M2M 应用。

然后在 `.env` 中设置：

```text
BOOTSTRAP_SEED_CLIENT_ID=...
BOOTSTRAP_SEED_CLIENT_SECRET=...
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=use-a-temporary-strong-password
```

先启动 `postgres` 与 `logto`，再运行：

```powershell
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.bootstrap.yaml run --rm bootstrap
```

脚本会幂等创建 API resources/scopes、global role、organization role、默认组织及初始管理员 membership、BFF Web 应用、BFF Management M2M、claims customizer 与 branding，并把生成的 server-only credentials 写入 `BOOTSTRAP_OUTPUT_FILE` 指定文件。不要把该文件提交到 Git。

Logto 只在首次创建应用时返回 client secret；重复执行不会轮换已有 secret。重复 bootstrap 时请继续保留 `.env` 中已有的 `OIDC_CLIENT_SECRET` 和 `LOGTO_M2M_CLIENT_SECRET`。

确认 BFF 使用新 M2M 正常工作后，应在一次性本机 Console 或 Management API 中撤销 seed M2M 的 Management API 角色，并从 `.env`/secret store 删除 seed 凭据。
