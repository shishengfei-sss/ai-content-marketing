from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_active_tenant_id, get_current_user, get_token_payload
from app.models import User
from app.schemas import (
    ForgotPasswordResetRequest,
    ForgotPasswordSendRequest,
    LoginRequest,
    MeOut,
    RegisterRequest,
    SelectTenantRequest,
    SmsLoginRequest,
    SmsSendRequest,
    SmsSendResponse,
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
from app.services.membership_service import (
    assert_membership_access,
    get_membership,
    get_membership_permissions,
    is_platform_admin,
    list_active_memberships,
    pick_default_tenant_id,
)
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
    need_select = len(memberships) > 1 and not active_tenant_id
    active_tenant = None
    permissions: list[str] = []
    if active_tenant_id:
        membership = get_membership(db, user.id, active_tenant_id)
        if membership:
            active_tenant = TenantOut.model_validate(membership.tenant)
            permissions = get_membership_permissions(membership)
    return MeOut(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        active_tenant=active_tenant,
        permissions=permissions,
        tenants=tenants,
        need_select_tenant=need_select,
    )


def _token_for_user(db: Session, user: User) -> TokenResponse:
    active_tenant_id = pick_default_tenant_id(db, user)
    memberships = list_active_memberships(db, user.id)
    need_select = len(memberships) > 1 and not active_tenant_id
    extra: dict = {"role": user.role}
    if active_tenant_id:
        extra["active_tenant_id"] = str(active_tenant_id)
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
    return _token_for_user(db, user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, body.phone, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号或密码错误")
    return _token_for_user(db, user)


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
    return _token_for_user(db, user)


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
    db: Session = Depends(get_db),
):
    return _build_me(db, current_user, active_tenant_id)


@router.post("/select-tenant", response_model=TokenResponse)
def select_tenant(
    body: SelectTenantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_membership_access(db, current_user, body.tenant_id)
    token = create_access_token(
        str(current_user.id),
        {"role": current_user.role, "active_tenant_id": str(body.tenant_id)},
    )
    return TokenResponse(access_token=token, need_select_tenant=False)


@router.post("/switch-tenant", response_model=TokenResponse)
def switch_tenant(
    body: SelectTenantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_membership_access(db, current_user, body.tenant_id)
    token = create_access_token(
        str(current_user.id),
        {"role": current_user.role, "active_tenant_id": str(body.tenant_id)},
    )
    return TokenResponse(access_token=token, need_select_tenant=False)


@router.get("/me/legacy", response_model=UserOut, include_in_schema=False)
def me_legacy(current_user: User = Depends(get_current_user)):
    return current_user
