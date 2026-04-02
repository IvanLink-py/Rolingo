import uuid
from typing import Optional
from datetime import datetime
from backend.models.schemas import (
    SessionCreate, SessionBase, SessionFinish, SessionList,
    SessionStatus, SessionResult, DialogType
)


class SessionService:
    @staticmethod
    async def create_session(conn, user_id: uuid.UUID, session_data: SessionCreate) -> uuid.UUID:
        session_id = await conn.fetchval("""
            INSERT INTO sessions (user_id, scenario_id, dialog_type, difficulty)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, user_id, session_data.scenario_id, session_data.dialog_type, session_data.difficulty)

        return session_id

    @staticmethod
    async def get_session_by_id(conn, session_id: uuid.UUID, user_id: uuid.UUID) -> Optional[SessionBase]:
        session = await conn.fetchrow("""
            SELECT id, scenario_id, dialog_type, difficulty, status, result, started_at, finished_at
            FROM sessions 
            WHERE id = $1 AND user_id = $2
        """, session_id, user_id)

        return SessionBase(**dict(session)) if session else None

    @staticmethod
    async def get_user_sessions(conn, user_id: uuid.UUID, page: int = 1, limit: int = 20) -> SessionList:
        offset = (page - 1) * limit

        total = await conn.fetchval("""
            SELECT COUNT(*) FROM sessions WHERE user_id = $1
        """, user_id)

        sessions_data = await conn.fetch("""
            SELECT id, scenario_id, dialog_type, difficulty, status, result, started_at, finished_at
            FROM sessions 
            WHERE user_id = $1
            ORDER BY started_at DESC
            LIMIT $2 OFFSET $3
        """, user_id, limit, offset)

        sessions = [SessionBase(**dict(row)) for row in sessions_data]
        pages = (total + limit - 1) // limit

        return SessionList(
            sessions=sessions,
            total=total,
            page=page,
            pages=pages
        )

    @staticmethod
    async def finish_session(conn, session_id: uuid.UUID, user_id: uuid.UUID,
                             result: Optional[SessionResult], errors_summary: Optional[str],
                             goal_feedback: Optional[str]) -> bool:
        rows_updated = await conn.fetchval("""
            UPDATE sessions 
            SET status = 'finished', 
                finished_at = $3,
                result = $4,
                errors_summary = $5,
                goal_feedback = $6
            WHERE id = $1 AND user_id = $2 AND status = 'active'
            RETURNING 1
        """, session_id, user_id, datetime.utcnow(), result, errors_summary, goal_feedback)

        return rows_updated is not None

    @staticmethod
    async def add_message(conn, session_id: uuid.UUID, role: str, content: str,
                          hint: Optional[str] = None) -> uuid.UUID:
        message_id = await conn.fetchval("""
            INSERT INTO messages (session_id, role, content, hint)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, session_id, role, content, hint)

        return message_id

    @staticmethod
    async def get_session_messages(conn, session_id: uuid.UUID, user_id: uuid.UUID):
        # Проверяем, что сессия принадлежит пользователю
        session_exists = await conn.fetchval("""
            SELECT 1 FROM sessions WHERE id = $1 AND user_id = $2
        """, session_id, user_id)

        if not session_exists:
            return []

        messages_data = await conn.fetch("""
            SELECT id, role, content, hint, created_at
            FROM messages 
            WHERE session_id = $1
            ORDER BY created_at ASC
        """, session_id)

        return [dict(row) for row in messages_data]