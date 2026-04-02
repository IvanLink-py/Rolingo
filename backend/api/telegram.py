from fastapi import APIRouter, Depends, HTTPException, status
import uuid
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.schemas import TelegramLink, TelegramAuth, TokenResponse
from backend.services.user_service import UserService
from backend.services.auth_service import AuthService

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/link")
async def link_telegram_account(
        telegram_data: TelegramLink,
        current_user: uuid.UUID = Depends(get_current_user),
        conn=Depends(get_db)
):
    try:
        await UserService.link_telegram(
            conn, current_user, telegram_data.telegram_user_id, telegram_data.telegram_username
        )
        return {"message": "Telegram account linked successfully"}
    except Exception as e:
        if "telegram_accounts_tg_id_unique" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram account already linked to another user"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to link Telegram account"
        )


@router.post("/auth", response_model=TokenResponse)
async def authenticate_telegram_user(
        auth_data: TelegramAuth,
        conn=Depends(get_db)
):
    user_id = await UserService.get_user_by_telegram(conn, auth_data.telegram_user_id)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram account not linked"
        )

    access_token = AuthService.create_access_token(user_id)
    refresh_token = AuthService.create_refresh_token()

    await AuthService.save_refresh_token(conn, user_id, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )