import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.push_campaign import CampaignStatusEnum, PushCampaign
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)


@celery_app.task(name="app.workers.tasks.push_delivery.send_push_campaign")
def send_push_campaign(campaign_id: str) -> dict[str, str]:
    """Send push notifications for a campaign. Mocks FCM/APNs delivery."""
    with Session(sync_engine) as db:
        campaign = db.execute(
            select(PushCampaign).where(PushCampaign.id == campaign_id)
        ).scalar_one_or_none()
        if not campaign:
            return {"status": "error", "detail": "Campaign not found"}

        # Get target devices
        stmt = select(Device).where(
            Device.project_id == campaign.project_id,
            Device.mode_id == campaign.mode_id,
            Device.push_token.isnot(None),
        )
        if campaign.target_type == "device" and campaign.target_value:
            stmt = stmt.where(Device.install_id == campaign.target_value)

        devices = list(db.execute(stmt).scalars().all())
        sent_count = 0
        failures: list[str] = []

        from app.services.fcm_sender import FcmError, send_to_token

        for device in devices:
            try:
                resp = send_to_token(device.push_token, campaign.title, campaign.body, campaign.data)
                logger.info(f"FCM sent to {device.push_token[:20]}...: {resp}")
                sent_count += 1
            except FcmError as e:
                failures.append(str(e))
                logger.error(f"FCM send failed: {e}")

        # Update campaign
        campaign.status = CampaignStatusEnum.sent if sent_count else CampaignStatusEnum.failed
        campaign.sent_at = datetime.now(timezone.utc)
        campaign.total_sent = sent_count
        db.commit()

        result: dict[str, str] = {"status": "sent" if sent_count else "failed", "total_sent": str(sent_count)}
        if failures:
            result["error"] = failures[0]
        return result
