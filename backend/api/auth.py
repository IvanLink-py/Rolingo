from fastapi import APIRouter, Depends, HTTPException, status
from backend.database import get_db
from backend.models.schemas import (
    UserRegister, UserLogin, TokenResponse, RefreshTokenRequest
)
from backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister, conn=Depends(get_db)):
    try:
        user_id = await AuthService.register_user(conn, user_data)

        access_token = AuthService.create_access_token(user_id)
        refresh_token = AuthService.create_refresh_token()

        await AuthService.save_refresh_token(conn, user_id, refresh_token)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
    except Exception as e:
        if "users_email_unique" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, conn=Depends(get_db)):
    user_id = await AuthService.authenticate_user(conn, login_data)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    access_token = AuthService.create_access_token(user_id)
    refresh_token = AuthService.create_refresh_token()

    await AuthService.save_refresh_token(conn, user_id, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token_data: RefreshTokenRequest, conn=Depends(get_db)):
    user_id = await AuthService.verify_refresh_token(conn, token_data.refresh_token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    access_token = AuthService.create_access_token(user_id)
    new_refresh_token = AuthService.create_refresh_token()

    # Отзываем старый токен и создаем новый
    await AuthService.revoke_refresh_token(conn, token_data.refresh_token)
    await AuthService.save_refresh_token(conn, user_id, new_refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token
    )


@router.post("/logout")
async def logout(token_data: RefreshTokenRequest, conn=Depends(get_db)):
    await AuthService.revoke_refresh_token(conn, token_data.refresh_token)
    return {"message": "Successfully logged out"}