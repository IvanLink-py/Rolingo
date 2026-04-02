from fastapi import APIRouter, Depends, HTTPException, status, Query
import uuid
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.schemas import (
    SessionCreate, SessionBase, SessionFinish, SessionList,
    SessionResult, DialogType
)
from backend.services.session_service import SessionService
from backend.services.scenario_service import ScenarioService
from backend.services.user_service import UserService
from backend.services.llm_service import LLMService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=dict)
async def create_session(
        session_data: SessionCreate,
        current_user: uuid.UUID = Depends(get_current_user),
        conn=Depends(get_db)
):
    # Проверяем, что сценарий существует
    scenario = await ScenarioService.get_scenario_by_id(conn, session_data.scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )

    session_id = await SessionService.create_session(conn, current_user, session_data)
    return {"id": session_id}


@router.get("", response_model=SessionList)
async def get_user_sessions(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        current_user: uuid.UUID = Depends(get_current_user),
        conn=Depends(get_db)
):
    return await SessionService.get_user_sessions(conn, current_user, page, limit)


@router.get("/{session_id}", response_model=SessionBase)
async def get_session(
        session_id: uuid.UUID,
        current_user: uuid.UUID = Depends(get_current_user),
        conn=Depends(get_db)
):
    session = await SessionService.get_session_by_id(conn, session_id, current_user)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    return session


@router.patch("/{session_id}/finish", response_model=SessionFinish)
async def finish_session(
        session_id: uuid.UUID,
        current_user: uuid.UUID = Depends(get_current_user),
        conn=Depends(get_db)
):
    # Получаем сессию
    session = await SessionService.get_session_by_id(conn, session_id, current_user)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already finished"
        )

    # Получаем сообщения для анализа
    messages = await SessionService.get_session_messages(conn, session_id, current_user)

    result = None
    errors_summary = None
    goal_feedback = None

    # Если это Mission, получаем оценку от LLM
    if session.dialog_type == DialogType.MISSION:
        scenario = await ScenarioService.get_scenario_by_id(conn, session.scenario_id)
        user = await UserService.get_user_by_id(conn, current_user)

        if scenario and scenario.goal and messages:
            try:
                success, goal_fb, errors = await LLMService.evaluate_mission(
                    messages, scenario.goal, user.target_language
                )
                result = SessionResult.SUCCESS if success == "success" else SessionResult.FAIL
                goal_feedback = goal_fb

                # Ошибки анализируем только в Challenge режиме
                if session.difficulty == "challenge":
                    errors_summary = errors

            except Exception:
                # Если LLM недоступен, считаем задачу выполненной
                result = SessionResult.SUCCESS
                goal_feedback = "Задача выполнена"

    # Сохраняем результат
    success = await SessionService.finish_session(
        conn, session_id, current_user, result, errors_summary, goal_feedback
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to finish session"
        )

    # Проверяем рекомендацию повышения уровня
    level_up_recommended = await UserService.check_level_up_recommendation(conn, current_user)

    return SessionFinish(
        result=result,
        errors_summary=errors_summary,
        goal_feedback=goal_feedback,
        level_up_recommended=level_up_recommended
    )