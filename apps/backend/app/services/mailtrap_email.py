from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from email.utils import parseaddr

import mailtrap as mt  # type: ignore[import-untyped]

from app.core.config import settings

logger = logging.getLogger(__name__)

# Formato mínimo entregable (no RFC completo): local@dominio.tld
_EMAIL_RE = re.compile(
    r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.IGNORECASE,
)


def is_mailtrap_configured() -> bool:
    return bool(
        settings.mailtrap_api_token
        and settings.mailtrap_api_mode == "sending"
        and settings.smtp_from
    )


def is_deliverable_email(value: str | None) -> bool:
    """True if the address is worth sending (rejects padrón placeholders without @)."""
    if not value:
        return False
    candidate = value.strip()
    if len(candidate) < 6 or len(candidate) > 254 or " " in candidate:
        return False
    return bool(_EMAIL_RE.match(candidate))


def _build_sender() -> mt.Address:
    name, email = parseaddr(settings.smtp_from or "")
    if not email:
        raise ValueError("SMTP_FROM must contain a valid sender email address")
    return mt.Address(email=email, name=name or None)


def _send_voter_otp_sync(
    recipient: str,
    code: str,
    expires_at: datetime,
) -> None:
    if not settings.mailtrap_api_token:
        raise RuntimeError("MAILTRAP_API_TOKEN is not configured")
    if not is_deliverable_email(recipient):
        raise ValueError(f"Recipient address is not deliverable: {recipient!r}")

    client = mt.MailtrapClient(token=settings.mailtrap_api_token)
    login_url = f"{settings.app_public_url.rstrip('/')}/vote/login"
    expires_local = expires_at.isoformat()
    subject = "Tu código de acceso a eVoting"
    text = (
        "Hola,\n\n"
        "Recibimos una solicitud de acceso a la votación electrónica.\n\n"
        f"Tu código de verificación es: {code}\n\n"
        f"Este código caduca a las {expires_local} (UTC).\n"
        "Si no solicitaste este código, puedes ignorar este mensaje.\n\n"
        f"Acceso seguro: {login_url}\n\n"
        "— eVoting (mensaje transaccional automático)\n"
    )
    html = (
        "<div style='font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:16px;"
        "line-height:1.5;color:#111'>"
        "<p>Hola,</p>"
        "<p>Recibimos una solicitud de acceso a la votación electrónica.</p>"
        "<p>Tu código de verificación es:</p>"
        f"<p style='font-size:28px;font-weight:700;letter-spacing:0.12em'>{code}</p>"
        f"<p>Este código caduca a las <strong>{expires_local}</strong> (UTC).</p>"
        "<p>Si no solicitaste este código, puedes ignorar este mensaje.</p>"
        f'<p><a href="{login_url}">Abrir acceso del elector</a></p>'
        "<p style='font-size:12px;color:#666'>— eVoting · mensaje transaccional automático</p>"
        "</div>"
    )
    mail = mt.Mail(
        sender=_build_sender(),
        to=[mt.Address(email=recipient.strip().lower())],
        subject=subject,
        text=text,
        html=html,
        category="voter-otp",
    )
    client.send(mail)


async def send_voter_otp_email(
    recipient: str,
    code: str,
    expires_at: datetime,
) -> None:
    await asyncio.to_thread(_send_voter_otp_sync, recipient, code, expires_at)
