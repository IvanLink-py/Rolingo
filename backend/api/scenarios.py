from fastapi import APIRouter, Depends, HTTPException, status, Query
import uuid
from typing import Optional
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.schemas import ScenarioBase, ScenarioList, LanguageCode, DialogType, AgeGroup
from backend.services.scenario_service import ScenarioService

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

@router.get("", response_model=ScenarioList)
async def get_scenarios(
    language: Optional[LanguageCode] = Query(None),
    dialog_type: Optional[DialogType] = Query(None),
    age_group: Optional[AgeGroup] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: uuid.UUID = Depends(get_current_user),
    conn = Depends(get_db)
):
    return await ScenarioService.get_scenarios(
        conn, language, dialog_type, age_group, page, limit
    )

@router.get("/{scenario_id}", response_model=ScenarioBase)
async def get_scenario(
    scenario_id: uuid.UUID,
    current_user: uuid.UUID = Depends(get_current_user),
    conn = Depends(get_db)
):
    scenario = await ScenarioService.get_scenario_by_id(conn, scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    return scenario