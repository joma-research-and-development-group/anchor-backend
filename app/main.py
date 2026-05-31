from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import rate_limit_ip, rate_limit_key
from app.models.user import User
from app.schemas.auth import UserResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
        redirect_slashes=False,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.admin.analytics import router as admin_analytics_router
    from app.api.admin.announcements import router as admin_announcements_router
    from app.api.admin.api_keys import router as api_keys_router
    from app.api.admin.audit import router as audit_router
    from app.api.admin.auth import router as auth_router
    from app.api.admin.banners import router as admin_banners_router
    from app.api.admin.config import router as config_router
    from app.api.admin.crashes import router as admin_crashes_router
    from app.api.admin.deep_links import router as admin_deep_links_router
    from app.api.admin.devices import router as admin_devices_router
    from app.api.admin.experiments import router as admin_experiments_router
    from app.api.admin.invitations import router as invitations_router
    from app.api.admin.legal import router as admin_legal_router
    from app.api.admin.localization import router as admin_localization_router
    from app.api.admin.maintenance import router as maintenance_router
    from app.api.admin.members import router as members_router
    from app.api.admin.onboarding import router as admin_onboarding_router
    from app.api.admin.orgs import router as orgs_router
    from app.api.admin.projects import router as projects_router
    from app.api.admin.push_campaigns import router as push_campaigns_router
    from app.api.admin.push_credentials import router as push_credentials_router
    from app.api.admin.rating import router as admin_rating_router
    from app.api.admin.support import router as admin_support_router
    from app.api.admin.version_policy import router as version_policy_router
    from app.api.admin.versions import router as versions_router
    from app.api.health import router as health_router
    from app.api.v1.announcements import router as v1_announcements_router
    from app.api.v1.banners import router as v1_banners_router
    from app.api.v1.crashes import router as v1_crashes_router
    from app.api.v1.deep_links import router as v1_deep_links_router
    from app.api.v1.devices import router as v1_devices_router
    from app.api.v1.events import router as v1_events_router
    from app.api.v1.experiments import router as v1_experiments_router
    from app.api.v1.handshake import router as handshake_router
    from app.api.v1.legal import router as v1_legal_router
    from app.api.v1.localization import router as v1_localization_router
    from app.api.v1.onboarding import router as v1_onboarding_router
    from app.api.v1.push import router as v1_push_router
    from app.api.v1.rating import router as v1_rating_router
    from app.api.v1.sdk import router as sdk_router
    from app.api.v1.support import router as v1_support_router

    # /admin/me endpoint
    admin_router = APIRouter(prefix="/admin", tags=["auth"])

    @admin_router.get("/me", response_model=UserResponse)
    async def me(current_user: User = Depends(get_current_user)) -> User:
        return current_user

    app.include_router(health_router, tags=["health"])
    app.include_router(admin_router)
    app.include_router(auth_router, prefix="/admin/auth", tags=["auth"])
    app.include_router(orgs_router, prefix="/admin/orgs", tags=["organizations"])
    app.include_router(members_router, prefix="/admin/orgs", tags=["members"])
    app.include_router(invitations_router, prefix="/admin/orgs", tags=["invitations"])
    app.include_router(invitations_router, prefix="/admin", tags=["invitations"])
    app.include_router(projects_router, prefix="/admin/orgs", tags=["projects"])
    app.include_router(audit_router, prefix="/admin/orgs", tags=["audit"])
    app.include_router(versions_router, prefix="/admin/orgs", tags=["versions"])
    app.include_router(api_keys_router, prefix="/admin/orgs", tags=["api-keys"])
    app.include_router(version_policy_router, prefix="/admin/orgs", tags=["version-policy"])
    app.include_router(maintenance_router, prefix="/admin/orgs", tags=["maintenance"])
    app.include_router(config_router, prefix="/admin/orgs", tags=["config"])
    app.include_router(push_credentials_router, prefix="/admin/orgs", tags=["push-credentials"])
    app.include_router(admin_devices_router, prefix="/admin/orgs", tags=["devices"])
    app.include_router(push_campaigns_router, prefix="/admin/orgs", tags=["push-campaigns"])
    app.include_router(admin_announcements_router, prefix="/admin/orgs", tags=["announcements"])
    app.include_router(admin_localization_router, prefix="/admin/orgs", tags=["localization"])
    app.include_router(admin_legal_router, prefix="/admin/orgs", tags=["legal"])
    app.include_router(admin_onboarding_router, prefix="/admin/orgs", tags=["onboarding"])
    app.include_router(admin_banners_router, prefix="/admin/orgs", tags=["banners"])
    app.include_router(admin_rating_router, prefix="/admin/orgs", tags=["rating"])
    app.include_router(admin_support_router, prefix="/admin/orgs", tags=["support"])
    app.include_router(admin_analytics_router, prefix="/admin/orgs", tags=["analytics"])
    app.include_router(admin_crashes_router, prefix="/admin/orgs", tags=["crashes"])
    app.include_router(admin_experiments_router, prefix="/admin/orgs", tags=["experiments"])
    app.include_router(admin_deep_links_router, prefix="/admin/orgs", tags=["deep-links"])

    # SDK routes with rate limiting
    handshake_router.dependencies.append(Depends(rate_limit_ip(60, 60)))
    app.include_router(handshake_router, prefix="/v1", tags=["sdk"])
    app.include_router(sdk_router, prefix="/v1", tags=["sdk"])
    app.include_router(v1_devices_router, prefix="/v1", tags=["sdk-devices"])
    app.include_router(v1_push_router, prefix="/v1", tags=["sdk-push"])
    app.include_router(v1_announcements_router, prefix="/v1", tags=["sdk-announcements"])
    app.include_router(v1_localization_router, prefix="/v1", tags=["sdk-localization"])
    app.include_router(v1_legal_router, prefix="/v1", tags=["sdk-legal"])
    app.include_router(v1_onboarding_router, prefix="/v1", tags=["sdk-onboarding"])
    app.include_router(v1_banners_router, prefix="/v1", tags=["sdk-banners"])
    app.include_router(v1_rating_router, prefix="/v1", tags=["sdk-rating"])
    app.include_router(v1_support_router, prefix="/v1", tags=["sdk-support"])

    # Events with key-based rate limiting (100/min/key)
    v1_events_router.dependencies.append(Depends(rate_limit_key(100, 60)))
    app.include_router(v1_events_router, prefix="/v1", tags=["sdk-events"])
    app.include_router(v1_crashes_router, prefix="/v1", tags=["sdk-crashes"])
    app.include_router(v1_experiments_router, prefix="/v1", tags=["sdk-experiments"])
    app.include_router(v1_deep_links_router, tags=["sdk-deep-links"])

    return app


app = create_app()
