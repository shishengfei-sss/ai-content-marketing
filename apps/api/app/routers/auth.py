from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_active_tenant_id, get_current_user, get_token_payload, get_workspace_mode
from app.models import User
from app.schemas import (
    ForgotPasswordResetRequest,
    ForgotPasswordSendRequest,
    LoginRequest,
    MeOut,
    MeUpdateRequest,
    RegisterRequest,
    SelectTenantRequest,
    SmsLoginRequest,
    SmsSendRequest,
    SmsSendResponse,
    SwitchWorkspaceRequest,
    TenantBriefOut,
    TenantOut,
    TokenResponse,
    UserOut,
)
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_active_user_by_phone,
    register_user,
    reset_user_password,
)
from app.services.auth_workspace import (
    WORKSPACE_MERCHANT,
    WORKSPACE_PLATFORM,
    build_token_extra,
    resolve_workspace_mode,
    validate_workspace_login,
)
from app.services.membership_service import (
    assert_membership_access,
    get_membership,
    get_membership_permissions,
    is_platform_admin,
    list_active_memberships,
)
from app.services.platform_shop_service import get_platform_shop_permissions, get_platform_shop_role
from app.services.sms_service import (
    send_login_code,
    send_reset_password_code,
    verify_login_code,
    verify_reset_password_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_me(
    db: Session,
    user: User,
    active_tenant_id: UUID | None,
    workspace_mode: str,
) -> MeOut:
    memberships = list_active_memberships(db, user.id)
    tenants = [
        TenantBriefOut(
            id=m.tenant.id,
            name=m.tenant.name,
            industry_code=m.tenant.industry_code,
            role_code=m.role.code,
            role_name=m.role.name,
        )
        for m in memberships
    ]
    need_select = (
        workspace_mode == WORKSPACE_MERCHANT
        and len(memberships) > 1
        and not active_tenant_id
    )
    active_tenant = None
    permissions: list[str] = []
    platform_shop_permissions: list[str] = []
    platform_shop_role: str | None = None
    if is_platform_admin(user):
        platform_shop_permissions = get_platform_shop_permissions(user)
        platform_shop_role = get_platform_shop_role(user)
    if workspace_mode == WORKSPACE_MERCHANT and active_tenant_id:
        membership = get_membership(db, user.id, active_tenant_id)
        if membership:
            active_tenant = TenantOut(
                id=membership.tenant.id,
                name=membership.tenant.name,
                industry_code=membership.tenant.industry_code,
                role_code=membership.role.code if membership.role else None,
            )
            permissions = get_membership_permissions(membership)
    return MeOut(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        active_tenant=active_tenant,
        permissions=permissions,
        platform_shop_permissions=platform_shop_permissions,
        platform_shop_role=platform_shop_role,
        tenants=tenants,
        need_select_tenant=need_select,
        workspace_mode=workspace_mode,
        has_merchant_workspace=len(memberships) > 0,
    )


def _token_for_user(
    db: Session,
    user: User,
    workspace_mode: str | None = None,
) -> TokenResponse:
    memberships = list_active_memberships(db, user.id)
    mode = resolve_workspace_mode(user, memberships, workspace_mode)
    validate_workspace_login(user, memberships, mode)
    extra, need_select = build_token_extra(db, user, mode)
    token = create_access_token(str(user.id), extra)
    return TokenResponse(
        access_token=token,
        need_select_tenant=need_select,
    )


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = register_user(
            db,
            phone=body.phone,
            password=body.password,
            tenant_name=body.tenant_name,
            industry_code=body.industry_code,
            display_name=body.display_name,
        )
    except ValueError as e:
        if str(e) == "PHONE_EXISTS":
            raise HTTPException(status_code=400, detail="该手机号已注册")
        raise
    return _token_for_user(db, user, WORKSPACE_MERCHANT)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    from app.services.login_guard import clear_failures, is_locked, record_failure

    if is_locked(body.phone):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录过于频繁，账号已临时锁定，请稍后重试或使用验证码登录",
        )
    user = authenticate_user(db, body.phone, body.password)
    if not user:
        locked, _ = record_failure(body.phone)
        if locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="登录失败次数过多，账号已临时锁定，请稍后重试",
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号或密码错误")
    clear_failures(body.phone)
    return _token_for_user(db, user, body.workspace_mode)


@router.post("/sms/send", response_model=SmsSendResponse)
def send_sms_code(body: SmsSendRequest, db: Session = Depends(get_db)):
    result = send_login_code(db, body.phone)
    return SmsSendResponse(**result)


@router.post("/sms/login", response_model=TokenResponse)
def login_by_sms(body: SmsLoginRequest, db: Session = Depends(get_db)):
    verify_login_code(body.phone, body.code)
    user = get_active_user_by_phone(db, body.phone)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号未注册或已禁用")
    return _token_for_user(db, user, body.workspace_mode)


@router.post("/password/forgot/send-code", response_model=SmsSendResponse)
def forgot_password_send(body: ForgotPasswordSendRequest, db: Session = Depends(get_db)):
    result = send_reset_password_code(db, body.phone)
    return SmsSendResponse(**result)


@router.post("/password/forgot/reset")
def forgot_password_reset(body: ForgotPasswordResetRequest, db: Session = Depends(get_db)):
    verify_reset_password_code(body.phone, body.code)
    user = get_active_user_by_phone(db, body.phone)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户不存在")
    reset_user_password(db, user.id, body.password)
    return {"message": "密码已重置，请使用新密码登录"}


@router.get("/me", response_model=MeOut)
def me(
    current_user: User = Depends(get_current_user),
    active_tenant_id: UUID | None = Depends(get_active_tenant_id),
    workspace_mode: str = Depends(get_workspace_mode),
    db: Session = Depends(get_db),
):
    return _build_me(db, current_user, active_tenant_id, workspace_mode)


@router.patch("/me", response_model=MeOut)
def update_me(
    body: MeUpdateRequest,
    current_user: User = Depends(get_current_user),
    active_tenant_id: UUID | None = Depends(get_active_tenant_id),
    workspace_mode: str = Depends(get_workspace_mode),
    db: Session = Depends(get_db),
):
    """S-ACCOUNT：更新昵称。"""
    name = (body.display_name or "").strip()
    if len(name) < 2 or len(name) > 30:
        raise HTTPException(status_code=422, detail="昵称须为 2–30 字")
    current_user.display_name = name
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _build_me(db, current_user, active_tenant_id, workspace_mode)


@router.post("/select-tenant", response_model=TokenResponse)
def select_tenant(
    body: SelectTenantRequest,
    current_user: User = Depends(get_current_user),
    workspace_mode: str = Depends(get_workspace_mode),
    db: Session = Depends(get_db),
):
    if workspace_mode != WORKSPACE_MERCHANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先使用商家登录入口 /login",
        )
    assert_membership_access(db, current_user, body.tenant_id)
    token = create_access_token(
        str(current_user.id),
        {
            "role": current_user.role,
            "workspace_mode": WORKSPACE_MERCHANT,
            "active_tenant_id": str(body.tenant_id),
        },
    )
    return TokenResponse(access_token=token, need_select_tenant=False)


@router.post("/switch-tenant", response_model=TokenResponse)
def switch_tenant(
    body: SelectTenantRequest,
    current_user: User = Depends(get_current_user),
    workspace_mode: str = Depends(get_workspace_mode),
    db: Session = Depends(get_db),
):
    if workspace_mode != WORKSPACE_MERCHANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先使用商家登录入口 /login",
        )
    assert_membership_access(db, current_user, body.tenant_id)
    token = create_access_token(
        str(current_user.id),
        {
            "role": current_user.role,
            "workspace_mode": WORKSPACE_MERCHANT,
            "active_tenant_id": str(body.tenant_id),
        },
    )
    return TokenResponse(access_token=token, need_select_tenant=False)


@router.post("/switch-workspace", response_model=TokenResponse)
def switch_workspace(
    body: SwitchWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.workspace_mode not in (WORKSPACE_PLATFORM, WORKSPACE_MERCHANT):
        raise HTTPException(status_code=400, detail="workspace_mode 须为 platform 或 merchant")
    return _token_for_user(db, current_user, body.workspace_mode)


@router.get("/me/legacy", response_model=UserOut, include_in_schema=False)
def me_legacy(current_user: User = Depends(get_current_user)):
    return current_user
