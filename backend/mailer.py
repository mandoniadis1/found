"""Outgoing email.
  MAIL_MODE=outbox  (default) saves each message to output/outbox/ instead of sending, so testing never emails anyone.
  MAIL_MODE=smtp    sends through SMTP_HOST with SMTP_USER / SMTP_PASSWORD.
  MAIL_MODE=outlook sends from the signed-in Outlook account through Microsoft Graph (reuses the token cache of
                    mcp_servers/mcp_outlook_server.py). Messages also appear in that account's Sent Items.
"""

from __future__ import annotations

import html
import json
import re
import smtplib
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import certifi

import config

# python.org builds of Python on macOS don't use the system certificates, so HTTPS fails with
# CERTIFICATE_VERIFY_FAILED unless we point at a CA bundle explicitly.
TLS = ssl.create_default_context(cafile=certifi.where())

OUTBOX = config.ROOT / "output" / "outbox"


def _html(heading: str, body: str, button_text: str, link: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:#f4efe6;font-family:Helvetica,Arial,sans-serif;color:#1a1917">
<div style="max-width:520px;margin:40px auto;background:#fbf8f2;border:1px solid #e2d9c9;border-radius:16px;padding:32px">
  <div style="font-family:Georgia,serif;font-size:28px">found<span style="color:#b8643f">.</span></div>
  <h2 style="font-family:Georgia,serif;font-weight:400;font-size:24px;margin:24px 0 8px">{html.escape(heading)}</h2>
  <p style="font-size:15px;line-height:1.55;color:#3a3733">{html.escape(body)}</p>
  <p style="margin:28px 0"><a href="{html.escape(link)}" style="background:#1a1917;color:#f4efe6;padding:12px 22px;border-radius:999px;text-decoration:none;font-size:14px">{html.escape(button_text)}</a></p>
  <p style="font-size:12px;color:#7a746a">Or paste this link into your browser:<br>{html.escape(link)}</p>
  <p style="font-size:12px;color:#7a746a">The link expires in 24 hours. If you didn't ask for this, you can ignore this email.</p>
</div></body></html>"""


class MailError(RuntimeError):
    pass


def _outlook_token() -> str:
    import msal  # only needed in outlook mode

    if not (config.OUTLOOK_CLIENT_ID and config.OUTLOOK_TENANT_ID):
        raise MailError("MAIL_MODE=outlook needs OUTLOOK_CLIENT_ID and OUTLOOK_TENANT_ID in the .env.")
    cache = msal.SerializableTokenCache()
    if config.OUTLOOK_TOKEN_CACHE.exists():
        cache.deserialize(config.OUTLOOK_TOKEN_CACHE.read_text())
    app = msal.PublicClientApplication(config.OUTLOOK_CLIENT_ID, token_cache=cache,
                                       authority=f"https://login.microsoftonline.com/{config.OUTLOOK_TENANT_ID}")
    accounts = app.get_accounts()
    result = app.acquire_token_silent(["Mail.Send"], account=accounts[0]) if accounts else None
    if cache.has_state_changed:
        config.OUTLOOK_TOKEN_CACHE.write_text(cache.serialize())
        config.OUTLOOK_TOKEN_CACHE.chmod(0o600)
    if not result or "access_token" not in result:
        raise MailError("Outlook isn't signed in. Run: cd mcp_servers && .venv/bin/python mcp_outlook_server.py")
    return result["access_token"]


def _send_outlook(to: str, subject: str, html_body: str) -> None:
    payload = {"message": {"subject": subject, "body": {"contentType": "HTML", "content": html_body},
                           "toRecipients": [{"emailAddress": {"address": to}}]},
               "saveToSentItems": True}
    req = urllib.request.Request("https://graph.microsoft.com/v1.0/me/sendMail", data=json.dumps(payload).encode(),
                                 headers={"Authorization": f"Bearer {_outlook_token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=TLS) as resp:
            if resp.status != 202:
                raise MailError(f"Microsoft Graph returned {resp.status}.")
    except urllib.error.HTTPError as exc:
        raise MailError(f"Microsoft Graph returned {exc.code}: {exc.read()[:300]!r}") from exc
    except urllib.error.URLError as exc:
        raise MailError(f"Couldn't reach Microsoft Graph: {exc.reason}") from exc


def send(to: str, subject: str, heading: str, body: str, button_text: str, link: str) -> Path | None:
    """Send (or, in outbox mode, save) a one-button email. Returns the saved file in outbox mode."""
    msg = EmailMessage()
    msg["From"] = config.MAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(f"{heading}\n\n{body}\n\n{button_text}: {link}\n\nThe link expires in 24 hours.")
    msg.add_alternative(_html(heading, body, button_text, link), subtype="html")

    if config.MAIL_MODE == "outlook":
        _send_outlook(to, subject, _html(heading, body, button_text, link))
        print(f"[mailer] sent '{subject}' to {to} via Outlook", flush=True)
        return None

    if config.MAIL_MODE == "smtp":
        if not config.SMTP_HOST:
            raise MailError("MAIL_MODE=smtp but SMTP_HOST is not set.")
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as smtp:
            smtp.starttls(context=TLS)
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)
        return None

    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OUTBOX / f"{stamp}_{re.sub(r'[^a-zA-Z0-9.@_-]', '_', to)}.html"
    path.write_text(_html(heading, body, button_text, link))
    print(f"[mailer] outbox mode: email to {to} saved to {path}", flush=True)
    return path
