from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import auth
from app.api.routes.requests import router as requests_router
from app.api.routes.instances import router as instances_router
from app.api.routes.dumps import router as dumps_router
from app.api.routes.exports import router as exports_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.sse import router as sse_router
from app.api.routes.notifications_settings import (
    notifications_router,
    settings_router,
)
from app.api.routes.rollback import router as rollback_router
from app.api.routes.users import router as users_router
from app.api.routes.master_odd import router as master_odd_router

app = FastAPI(title="ODD Automation API", version="1.0.0")

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routes under /api prefix (nginx proxies /api/ to this service)
API_PREFIX = "/api"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(requests_router, prefix=API_PREFIX)
app.include_router(instances_router, prefix=API_PREFIX)
app.include_router(dumps_router, prefix=API_PREFIX)
app.include_router(exports_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)
app.include_router(sse_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=API_PREFIX)
app.include_router(settings_router, prefix=API_PREFIX)
app.include_router(rollback_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(master_odd_router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}
