import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.database import get_db
from backend.services.auth_service import AuthService
from backend.services.user_service import UserService

security = HTTPBearer()


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        conn=Depends(get_db)
) -> uuid.UUID:
    try:
        payload = AuthService.decode_token(credentials.credentials)
        user_id = uuid.UUID(payload.get("user_id"))

        user = await UserService.get_user_by_id(conn, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        return user_id
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )