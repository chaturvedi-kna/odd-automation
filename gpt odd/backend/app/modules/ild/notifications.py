from app.models.notification import Notification


async def create_notification(db, message, req_id=None):
    notif = Notification(
        message=message,
        type="INFO",
        related_request_id=req_id,
    )
    db.add(notif)