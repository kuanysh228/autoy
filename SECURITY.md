# Security Policy

## Supported versions

Only the latest release receives security fixes.

## Reporting a vulnerability

Please do not open a public issue. Report it privately through [GitHub security advisories](https://github.com/kuanysh228/autoy/security/advisories/new). Include the steps to reproduce and the affected version. You can expect an acknowledgement within a few days.

## Handling secrets

autoy works with credentials that grant control over a YouTube channel and a Telegram bot:

- Never commit `.env`, `credentials/`, `channels.toml` or `data/*.db`. They are git-ignored by default.
- `credentials/<channel>_token.pickle` is a serialized OAuth token. Only load files you generated yourself, and keep the directory readable by the service user only.
- The Telegram bot accepts commands only from `TELEGRAM_CHAT_ID`; keep that value and the bot token private.
- If a token or key leaks, revoke it at the provider and create a new one.
