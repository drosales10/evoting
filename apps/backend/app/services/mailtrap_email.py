from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from email.utils import parseaddr

import mailtrap as mt  # type: ignore[import-untyped]

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_mailtrap_configured() -> bool:
    return bool(
        settings.mailtrap_api_token
        and settings.mailtrap_api_mode == "sending"
        and settings.smtp_from
    )


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
    client = mt.MailtrapClient(token=settings.mailtrap_api_token)
    login_url = f"{settings.app_public_url.rstrip('/')}/vote/login"
    mail = mt.Mail(
        sender=_build_sender(),
        to=[mt.Address(email=recipient)],
        subject="Código de acceso electoral",
        text=(
            f"Tu código OTP es: {code}\n\n"
            f"Expira el {expires_at.isoformat()}.\n"
            f"Acceso: {login_url}\n"
        ),
        html=(
            "<p>Tu código OTP para acceder a la votación es:</p>"
            f"<p><strong>{code}</strong></p>"
            f"<p>Expira el {expires_at.isoformat()}.</p>"
            f'<p><a href="{login_url}">Abrir acceso del elector</a></p>'
        ),
    )
    client.send(mail)


async def send_voter_otp_email(
    recipient: str,
    code: str,
    expires_at: datetime,
) -> None:
    await asyncio.to_thread(_send_voter_otp_sync, recipient, code, expires_at)
