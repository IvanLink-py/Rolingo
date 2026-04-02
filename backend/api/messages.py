from fastapi import APIRouter, Depends, HTTPException, status
import uuid
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.schemas import MessageSend, MessageResponse, MessageList, Message, MessageRole
from backend.services.session_service import SessionService
from backend.services.scenario_service import ScenarioService
from backend.services.user_service import UserService
from backend.services.llm_service import LLMService

router = APIRouter(tags=["messages"])


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
        session_id: uuid.UUID,
        message_data: MessageSend,
        current_user: uuid.UUID = Depends(get_current_user),
        conn=Depends(get_db)
):
    # Проверяем сессию
    session = await SessionService.get_session_by_id(conn, session_id, current_user)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active"
        )

    # Добавляем сообщение пользователя
    await SessionService.add_message(conn, session_id, MessageRole.USER, message_data.content)

    # Получаем информацию для LLM
    scenario = await ScenarioService.get_scenario_by_id(conn, session.scenario_id)
    user = await UserService.get_user_by_id(conn, current_user)

    if not scenario or not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session context"
        )

    # Получаем историю сообщений
    messages = await SessionService.get_session_messages(conn, session_id, current_user)

    try:
        # Получаем ответ от LLM
        scenario_dict = {
            'character_name': scenario.character_name,
            'character_role': scenario.character_role,
            'character_traits': scenario.character_traits,
            'goal': scenario.goal
        }

        character_response, hint = await LLMService.get_character_response(
            scenario_dict, messages, user.lang_level, session.dialog_type,
            session.difficulty, user.target_language
        )

        # Сохраняем ответ персонажа
        await SessionService.add_message(
            conn, session_id, MessageRole.ASSISTANT, character_response, hint
        )

        return MessageResponse(
            user_message=message_data.content,
            assistant_message=character_response,
            hint=hint
        )

    except Exception as e:
        # В случае ошибки LLM возвращаем стандартный ответ
        fallback_response = "I'm having trouble responding right now. Please try again." if user.target_language == "en" else "У меня проблемы с ответом. Попробуйте еще раз."

        await SessionService.add_message(
            conn, session_id, MessageRole.ASSISTANT, fallback_response
        )

        return MessageResponse(
            user_message=message_data.content,
            assistant_message=fallback_response,
            hint=None
        )


@router.get("/sessions/{session_id}/messages", response_model=MessageList)
async def get_session_messages(
        session_id: uuid.UUID,
        current_user: uuid.UUID = Depends(get_current_user),
        conn=Depends(get_db)
):
    # Проверяем сессию
    session = await SessionService.get_session_by_id(conn, session_id, current_user)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    messages_data = await SessionService.get_session_messages(conn, session_id, current_user)
    messages = [Message(**msg) for msg in messages_data]

    return MessageList(messages=messages)
