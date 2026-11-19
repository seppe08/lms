from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession
from app.common.rate_limit import enforce_auth_rate_limit
from app.schemas.auth import AuthResponse, LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_auth_rate_limit)],
    summary="Register a new student account",
    description=(
        "Creates a new user with the `student` role (always assigned server-side) "
        "and returns the created profile along with access and refresh JWT tokens."
    ),
)
async def register(payload: RegisterRequest, db: DbSession) -> AuthResponse:
    user, tokens = await auth_service.register_user(db, payload)
    return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.post(
    "/login",
    response_model=TokenPair,
    dependencies=[Depends(enforce_auth_rate_limit)],
    summary="Authenticate and obtain JWT tokens",
    description=(
        "Validates email/password credentials and returns short-lived access and refresh tokens."
    ),
)
async def login(payload: LoginRequest, db: DbSession) -> TokenPair:
    return await auth_service.authenticate_user(db, payload)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Refresh JWT token pair",
    description="Exchanges a valid refresh token for a fresh access and refresh token pair.",
)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    return await auth_service.refresh_tokens(db, payload.refresh_token)
