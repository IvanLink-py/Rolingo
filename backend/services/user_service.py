import uuid
from typing import Optional
from backend.models.schemas import UserProfile, UserUpdate


class UserService:
    @staticmethod
    async def get_user_by_id(conn, user_id: uuid.UUID) -> Optional[UserProfile]:
        user = await conn.fetchrow("""
            SELECT id, username, email, interface_language, target_language, 
                   lang_level, age_group, onboarding_completed, created_at
            FROM users 
            WHERE id = $1
        """, user_id)

        if user:
            return UserProfile(**dict(user))
        return None

    @staticmethod
    async def update_user(conn, user_id: uuid.UUID, update_data: UserUpdate) -> Optional[UserProfile]:
        update_fields = []
        values = []
        param_num = 1

        for field, value in update_data.model_dump(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ${param_num}")
                values.append(value)
                param_num += 1

        if not update_fields:
            return await UserService.get_user_by_id(conn, user_id)

        values.append(user_id)

        query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}
            WHERE id = ${param_num}
            RETURNING id, username, email, interface_language, target_language, 
                      lang_level, age_group, onboarding_completed, created_at
        """

        user = await conn.fetchrow(query, *values)
        return UserProfile(**dict(user)) if user else None

    @staticmethod
    async def complete_onboarding(conn, user_id: uuid.UUID):
        await conn.execute("""
            UPDATE users 
            SET onboarding_completed = TRUE 
            WHERE id = $1
        """, user_id)

    @staticmethod
    async def check_level_up_recommendation(conn, user_id: uuid.UUID) -> bool:
        """Проверяет, выполнил ли пользователь 3 Mission/Challenge подряд"""
        recent_sessions = await conn.fetch("""
            SELECT result, dialog_type, difficulty
            FROM sessions 
            WHERE user_id = $1 AND status = 'finished'
            ORDER BY finished_at DESC 
            LIMIT 3
        """, user_id)

        if len(recent_sessions) < 3:
            return False

        return all(
            session['result'] == 'success' and
            session['dialog_type'] == 'mission' and
            session['difficulty'] == 'challenge'
            for session in recent_sessions
        )

    @staticmethod
    async def link_telegram(conn, user_id: uuid.UUID, telegram_user_id: int, telegram_username: str = None):
        await conn.execute("""
            INSERT INTO telegram_accounts (user_id, telegram_user_id, telegram_username)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE SET 
                telegram_user_id = $2, 
                telegram_username = $3
        """, user_id, telegram_user_id, telegram_username)

    @staticmethod
    async def get_user_by_telegram(conn, telegram_user_id: int) -> Optional[uuid.UUID]:
        user_id = await conn.fetchval("""
            SELECT user_id 
            FROM telegram_accounts 
            WHERE telegram_user_id = $1
        """, telegram_user_id)

        return user_id