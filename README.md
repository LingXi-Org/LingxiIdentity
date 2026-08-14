# LingxiIdentity

Lingxi 系列统一身份认证与用户管理服务。LingxiIdentity 将 [Logto OSS](https://github.com/logto-io/logto) 作为 Headless Identity Core，通过标准 OIDC/OAuth2/JWT/JWKS 和 Management API 提供稳定的 Lingxi API，不 fork 或修改 Logto 源码。

## 快速启动

```powershell
Copy-Item .env.example .env
# 修改 .env 中的 POSTGRES_PASSWORD、SESSION_ENCRYPTION_KEY 等值
```

首次初始化时先只启动 PostgreSQL 与 Logto Core，避免 BFF 在凭据尚未生成时反复重启：

```powershell
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.bootstrap.yaml up -d --build postgres logto
```

开发 bootstrap profile 会把 Logto Admin Console 绑定到本机 `http://localhost:3002`。首次启动时，在该一次性入口创建 Logto 初始管理员与 seed M2M 应用，然后将 seed M2M 凭据填入 `.env`，执行：

```powershell
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.bootstrap.yaml run --rm --no-deps bootstrap
```

将输出文件中的 `OIDC_*` 与 `LOGTO_M2M_*` server-only 值写入 `.env` 后，再启动 BFF：

```powershell
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.bootstrap.yaml up -d --build bff
```

完成后，生产运行只使用核心 Compose 文件：

```powershell
docker compose --env-file .env -f deployment/compose.yaml up -d --build
```

核心服务已配置 `restart: unless-stopped`，服务器或 Docker 重启后会自动恢复；直接在项目根目录执行上面这一行即可启动。

生产配置不会发布 3002，并通过 `ADMIN_DISABLE_LOCALHOST=true` 且不设置 `ADMIN_ENDPOINT` 完全关闭 Logto Admin Console。生产 HTTPS 由外部反向代理提供，详见 [docs/deployment.md](docs/deployment.md)。

## SDK

The BFF exposes the user lifecycle under `/auth` and `/api/v1/me`: login, registration, password recovery, CSRF-protected refresh/logout, profile and email/password changes, device-session revocation, and self-service suspension. See [docs/account-api.md](docs/account-api.md) for the request contract.

```python
from lingxi_identity import AsyncIdentityClient, OidcVerifier

client = AsyncIdentityClient.from_logto(
    base_url="http://logto:3001",
    client_id="server-client",
    client_secret="server-secret",
)
users = await client.users.list()

verifier = OidcVerifier(
    issuer="https://identity.example.com/oidc",
    audience="https://graph.example.com/api",
)
principal = verifier.verify(access_token)
```

## 开发命令

```powershell
python -m pip install -e sdk/python -e server -e bootstrap -e ".[dev]"
make install
make lint
make typecheck
make test
make compose-config
```

项目许可证为 Apache-2.0。
