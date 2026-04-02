import bcrypt
import jwt
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from backend.config import settings
from backend.models.schemas import UserRegister, UserLogin


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    @staticmethod
    def create_access_token(user_id: uuid.UUID) -> str:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        payload = {
            "user_id": str(user_id),
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def create_refresh_token() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            return payload
        except jwt.PyJWTError:
            raise ValueError("Invalid token")

    @staticmethod
    async def register_user(conn, user_data: UserRegister) -> uuid.UUID:
        hashed_password = AuthService.hash_password(user_data.password)

        user_id = await conn.fetchval("""
            INSERT INTO users (username, email, hashed_password, age_group)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, user_data.username, user_data.email, hashed_password, "adult")

        return user_id

    @staticmethod
    async def authenticate_user(conn, login_data: UserLogin) -> Optional[uuid.UUID]:
        user = await conn.fetchrow("""
            SELECT id, hashed_password
            FROM users 
            WHERE email = $1
        """, login_data.email)

        if user and AuthService.verify_password(login_data.password, user['hashed_password']):
            return user['id']
        return None

    @staticmethod
    async def save_refresh_token(conn, user_id: uuid.UUID, token: str):
        expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)

        await conn.execute("""
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
        """, user_id, token, expires_at)

    @staticmethod
    async def verify_refresh_token(conn, token: str) -> Optional[uuid.UUID]:
        user_id = await conn.fetchval("""
            SELECT user_id 
            FROM refresh_tokens 
            WHERE token_hash = $1 AND expires_at > $2 AND NOT revoked
        """, token, datetime.utcnow())

        return user_id

    @staticmethod
    async def revoke_refresh_token(conn, token: str):
        await conn.execute("""
            UPDATE refresh_tokens 
            SET revoked = TRUE 
            WHERE token_hash = $1
        """, token)