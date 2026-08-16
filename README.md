<div align="center">

# LingxiIdentity

**LingXi 系列统一身份认证与用户管理服务。**

基于 Logto OSS 提供 OIDC / OAuth2 / JWT / JWKS、BFF 会话与用户生命周期能力。

[部署说明](docs/deployment.md) · [Account API](docs/account-api.md) · [LingXi Organization](https://github.com/LingXi-Org)

</div>

## 关于 LingxiIdentity

LingxiIdentity 将 Logto 作为 Headless Identity Core，在其上提供稳定的 LingXi 身份接口与 BFF 会话边界。

项目不 fork Logto 源码。浏览器侧使用 HttpOnly 会话，服务端通过标准 OIDC/OAuth2/JWT/JWKS 与 Management API 完成身份验证和用户管理。

```text
Browser / LingXi App
        │
        ▼
LingxiIdentity BFF
        │
        ▼
Logto OSS
        │
        ├── PostgreSQL
        └── OIDC / OAuth2 / JWT / JWKS
```

## 核心能力

- **统一登录与注册**：登录、注册、密码找回与会话刷新。
- **BFF Session**：使用 HttpOnly Cookie 隔离浏览器与服务端 Token。
- **OIDC / JWT**：提供标准 issuer、JWKS 与 Token 校验能力。
- **用户管理**：资料、邮箱、密码、设备会话与账号状态管理。
- **Python SDK**：提供 Management API Client 与 OIDC Verifier。

## 快速开始

```bash
cp .env.example .env
# 配置 POSTGRES_PASSWORD、SESSION_ENCRYPTION_KEY 等必要变量
```

首次初始化：

```bash
docker compose --env-file .env \
  -f deployment/compose.yaml \
  -f deployment/compose.bootstrap.yaml \
  up -d --build postgres logto
```

完成 Logto 初始管理员与 seed M2M 配置后执行 bootstrap：

```bash
docker compose --env-file .env \
  -f deployment/compose.yaml \
  -f deployment/compose.bootstrap.yaml \
  run --rm --no-deps bootstrap
```

生产运行：

```bash
docker compose --env-file .env -f deployment/compose.yaml up -d --build
```

更完整的首次初始化与生产配置见 [docs/deployment.md](docs/deployment.md)。

## Python SDK

```python
from lingxi_identity import OidcVerifier

verifier = OidcVerifier(
    issuer="https://identity.example.com/oidc",
    audience="https://example.com/api",
)

principal = verifier.verify(access_token)
```

## 仓库结构

```text
  experience/   Lingxi Custom Experience SPA（Logto v1.33.0 API）
  server/       BFF 与身份 API
sdk/python/   Python SDK
bootstrap/    首次初始化工具
deployment/   Docker Compose 部署配置
docs/         部署与接口文档
```

## 开发

```bash
make install
make lint
make typecheck
make test
make compose-config
```

## License

LingxiIdentity 采用 [Apache License 2.0](LICENSE)。
