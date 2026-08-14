# BFF account API

All endpoints below use the `lingxi_session` HttpOnly cookie. Call `GET /auth/csrf` first and send its value as `X-CSRF-Token` on every `POST`, `PATCH`, `PUT`, or `DELETE` request.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/auth/login` | Start OIDC sign-in |
| GET | `/auth/register` | Start registration (`first_screen=register`) |
| GET | `/auth/forgot-password` | Start password recovery (`first_screen=reset_password`) |
| POST | `/auth/refresh` | Explicitly rotate the encrypted provider tokens |
| POST | `/auth/logout` | Revoke the BFF session |
| GET | `/api/v1/me` | Current principal and latest Account API profile |
| PATCH | `/api/v1/me/profile` | Update name, avatar, username, profile, or custom data |
| POST | `/api/v1/me/verifications/password` | Create a short-lived identity verification record |
| POST | `/api/v1/me/verifications/email` | Send a permission-validation email code |
| POST | `/api/v1/me/verifications/email/verify` | Verify an email code |
| PATCH | `/api/v1/me/email` | Change primary email after both verifications |
| POST | `/api/v1/me/password` | Change password after recent verification |
| GET/DELETE | `/api/v1/me/sessions[/{id}]` | List or revoke Logto device sessions |
| POST | `/api/v1/me/deactivate` | Suspend the current account and revoke all BFF sessions |

The BFF proxies Account API and Verification API calls with the end-user access token. The interactive login flow requests the Logto Account API token without a `resource` indicator, as required by Logto's Account API; the validated ID token supplies the BFF session principal. It does not implement password hashing, email delivery, reset tokens, or verification-code storage. Configure Logto email templates (`Register`, `ForgotPassword`, `UserPermissionValidation`, and `BindNewIdentifier`) and enable Account API through bootstrap.
