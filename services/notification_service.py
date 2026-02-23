"""
Notification service — sends review alerts via Azure Communication Services (ACS) Email.

Auth: DefaultAzureCredential (passwordless) — works with both managed identity (production)
and az login (local dev).

Fallback: Slack webhook if ACS is not configured.
"""

import asyncio
import logging
from azure.communication.email import EmailClient
from azure.identity import DefaultAzureCredential
from config.settings import settings

logger = logging.getLogger(__name__)

# Singleton client
_email_client: EmailClient | None = None


def _get_email_client() -> EmailClient:
    """Lazily create and cache the ACS Email client."""
    global _email_client
    if _email_client is None:
        if settings.ACS_CONNECTION_STRING:
            _email_client = EmailClient.from_connection_string(settings.ACS_CONNECTION_STRING)
        else:
            _email_client = EmailClient(
                endpoint=settings.ACS_ENDPOINT,
                credential=DefaultAzureCredential(managed_identity_client_id=settings.AZURE_CLIENT_ID),
            )
    return _email_client


class NotificationService:
    """Send notifications to the human reviewer via ACS Email (primary) or Slack (fallback)."""

    async def notify_new_review(self, item: dict) -> None:
        """Notify the human that a new item is pending review."""
        if settings.ACS_ENDPOINT and settings.ACS_SENDER_EMAIL and settings.REVIEWER_EMAIL:
            await self._send_acs_email(item)
        elif settings.SLACK_WEBHOOK_URL:
            await self._send_slack(item)
        else:
            logger.info(
                f"[REVIEW NEEDED] New content pending: {item['id']} - {item['topic']}"
            )

    async def _send_acs_email(self, item: dict) -> None:
        """Send a rich HTML review notification via Azure Communication Services Email."""
        subject = f"📸 Review Needed: {item.get('topic', 'Instagram Post')}"

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">📸 New Instagram Content Ready for Review</h2>
            </div>
            <div style="border: 1px solid #e0e0e0; border-top: none; padding: 20px;
                        border-radius: 0 0 8px 8px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; font-weight: bold; color: #555;">ID:</td>
                        <td style="padding: 8px;"><code>{item.get('id', 'N/A')}</code></td>
                    </tr>
                    <tr style="background: #f9f9f9;">
                        <td style="padding: 8px; font-weight: bold; color: #555;">Type:</td>
                        <td style="padding: 8px;">{item.get('content_type', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold; color: #555;">Topic:</td>
                        <td style="padding: 8px;">{item.get('topic', 'N/A')}</td>
                    </tr>
                    <tr style="background: #f9f9f9;">
                        <td style="padding: 8px; font-weight: bold; color: #555;">Caption Preview:</td>
                        <td style="padding: 8px;"><em>{item.get('caption', '')[:200]}...</em></td>
                    </tr>
                </table>

                <div style="margin-top: 16px; text-align: center;">
                    <a href="{item.get('media_url', '#')}"
                       style="display: inline-block; background: #667eea; color: white;
                              padding: 12px 24px; text-decoration: none; border-radius: 6px;
                              font-weight: bold;">
                        🖼️ View Media
                    </a>
                </div>

                <p style="margin-top: 20px; color: #888; font-size: 12px; text-align: center;">
                    This is an automated notification from InstaAgent.
                    Review and approve/reject via the DevUI or by replying to this email.
                </p>
            </div>
        </body>
        </html>
        """

        plain_text = (
            f"New Instagram content pending review.\n\n"
            f"ID: {item.get('id', 'N/A')}\n"
            f"Type: {item.get('content_type', 'N/A')}\n"
            f"Topic: {item.get('topic', 'N/A')}\n"
            f"Caption: {item.get('caption', '')[:200]}...\n"
            f"Media: {item.get('media_url', 'N/A')}\n"
        )

        message = {
            "senderAddress": settings.ACS_SENDER_EMAIL,
            "recipients": {
                "to": [{"address": addr.strip()} for addr in settings.REVIEWER_EMAIL.split(",") if addr.strip()],
            },
            "content": {
                "subject": subject,
                "plainText": plain_text,
                "html": html_body,
            },
        }

        try:
            client = _get_email_client()
            # begin_send() and poller.result() are synchronous — run in a thread
            # to avoid blocking the async event loop.
            poller = await asyncio.to_thread(client.begin_send, message)
            result = await asyncio.to_thread(poller.result)
            logger.info(f"[OK] ACS email sent — message ID: {result.get('id', 'unknown')}")
        except Exception as e:
            logger.error(f"[FAIL] ACS email failed: {e}")
            # Fall back to Slack if available
            if settings.SLACK_WEBHOOK_URL:
                logger.info("[FALLBACK] Trying Slack notification...")
                await self._send_slack(item)

    async def _send_slack(self, item: dict) -> None:
        """Send a Slack notification with a summary of the queued content (fallback)."""
        import httpx

        message = {
            "text": ":camera: *New Instagram Content Pending Review*",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "New Instagram Content Ready for Review",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*ID:* `{item['id']}`"},
                        {"type": "mrkdwn", "text": f"*Type:* {item['content_type']}"},
                        {"type": "mrkdwn", "text": f"*Topic:* {item['topic']}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Preview:* {item['caption'][:100]}...",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Media:* <{item['media_url']}|View Image/Video>",
                    },
                },
            ],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(settings.SLACK_WEBHOOK_URL, json=message)
                resp.raise_for_status()
            logger.info("[OK] Slack notification sent")
        except Exception as e:
            logger.error(f"[FAIL] Slack notification failed: {e}")
