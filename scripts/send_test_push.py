"""Send a real FCM push to the most-recently registered device.

Usage:
  FCM_SERVICE_ACCOUNT_FILE=/path/to/service-account.json \
    python -m scripts.send_test_push "Title" "Body"
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.db import async_session
from app.models.device import Device
from app.services.fcm_sender import FcmError, send_to_token


async def main() -> None:
    title = sys.argv[1] if len(sys.argv) > 1 else "Anchor Test"
    body = sys.argv[2] if len(sys.argv) > 2 else "Hello from Anchor push!"
    async with async_session() as db:
        device = (
            await db.execute(
                select(Device)
                .where(Device.push_token.isnot(None))
                .order_by(Device.last_seen_at.desc())
            )
        ).scalars().first()
    if not device:
        print("No device with a push token registered.")
        return
    print(f"Target device: {device.install_id} ({device.platform})")
    print(f"Token: {device.push_token[:30]}...{device.push_token[-10:]}")
    try:
        resp = send_to_token(device.push_token, title, body, {"source": "send_test_push"})
        print(f"✅ FCM delivered: {resp}")
    except FcmError as e:
        print(f"❌ {e}")


if __name__ == "__main__":
    asyncio.run(main())
