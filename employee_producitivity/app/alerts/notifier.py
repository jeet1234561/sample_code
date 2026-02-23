"""Module D — Alert Notification Dispatcher.

Handles sending alert notifications via different channels.
Currently supports logging (console). Email and Teams webhook
can be plugged in by extending the base notifier.

This is a separate file so notification logic can be modified
independently of the alert evaluation engine.
"""

import logging
from abc import ABC, abstractmethod
from typing import List

from app.models.alert import AlertRecord

logger = logging.getLogger("epiap.notifier")


class BaseNotifier(ABC):
    """Abstract base for notification channels."""

    @abstractmethod
    async def send(self, alert: AlertRecord) -> bool:
        """Send a notification for an alert. Returns True on success."""
        ...


class LogNotifier(BaseNotifier):
    """Logs alerts to the console/log file. Always active."""

    async def send(self, alert: AlertRecord) -> bool:
        logger.info(
            f"[NOTIFICATION] [{alert.priority.upper()}] "
            f"{alert.metric_name}: {alert.message}"
        )
        return True


class EmailNotifier(BaseNotifier):
    """Sends alert emails. Stub — implement with SMTP or SendGrid.

    FRD Module E1:
    - Compose email based on templates and alert details
    - Email content: alert reason, metric values, link to dashboard
    """

    def __init__(self, smtp_host: str = "", smtp_port: int = 587):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    async def send(self, alert: AlertRecord) -> bool:
        # TODO: Implement with smtplib or an email service
        logger.info(
            f"[EMAIL STUB] Would send email for alert {alert.alert_id} "
            f"to targets: {alert.targets}"
        )
        return True


class TeamsNotifier(BaseNotifier):
    """Posts alerts to Microsoft Teams via webhook.

    FRD Module E2:
    - POST alert message to Teams webhook URL
    - Format JSON payload with actionable message card
    """

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url

    async def send(self, alert: AlertRecord) -> bool:
        # TODO: Implement with httpx POST to webhook_url
        logger.info(
            f"[TEAMS STUB] Would post to Teams for alert {alert.alert_id}"
        )
        return True


class NotificationDispatcher:
    """Dispatches alerts to all configured notification channels."""

    def __init__(self):
        self.notifiers: List[BaseNotifier] = [LogNotifier()]

    def add_notifier(self, notifier: BaseNotifier):
        self.notifiers.append(notifier)

    async def dispatch(self, alert: AlertRecord):
        """Send alert to all registered notifiers."""
        for notifier in self.notifiers:
            try:
                await notifier.send(alert)
            except Exception as e:
                logger.error(
                    f"Notifier {type(notifier).__name__} failed: {e}",
                    exc_info=True,
                )
