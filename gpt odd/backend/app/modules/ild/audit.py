from app.models.audit_log import AuditLog


async def log_audit(db, message, level="INFO", request_id=None, instance=None, entry_type=None):
    log = AuditLog(
        message=message,
        level=level,
        entry_type=entry_type,
        request_id=request_id,
        instance_label=instance.get("instance_label") if instance else None,
        dra_type=instance.get("dra_type") if instance else None,
    )
    db.add(log)