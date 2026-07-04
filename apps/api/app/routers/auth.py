from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    LoginRequest,
    RegisterRequest,
    SmsLoginRequest,
    SmsSendRequest,
    SmsSendResponse,
    TokenResponse,
    UserOut,
)
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_active_user_by_phone,
    register_user,
)
from app.services.sms_service import send_login_code, verify_login_code

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_for_user(user: User) -> TokenResponse:
    token = create_access_token(
        str(user.id),
        {"tenant_id": str(user.tenant_id), "role": user.role},
    )
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = register_user(
            db,
            phone=body.phone,
            password=body.password,
            industry_code=body.industry_code,
            display_name=body.display_name,
        )
    except ValueError as e:
        if str(e) == "PHONE_EXISTS":
            raise HTTPException(status_code=400, detail="该手机号已注册")
        raise
    return _token_for_user(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, body.phone, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号或密码错误")
    return _token_for_user(user)


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
    return _token_for_user(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
