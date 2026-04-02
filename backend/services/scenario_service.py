import uuid
from typing import List, Optional
from backend.models.schemas import ScenarioBase, ScenarioList, LanguageCode, DialogType, AgeGroup


class ScenarioService:
    @staticmethod
    async def get_scenarios(conn, language: Optional[LanguageCode] = None,
                      dialog_type: Optional[DialogType] = None,
                      age_group: Optional[AgeGroup] = None,
                      page: int = 1, limit: int = 20) -> ScenarioList:

        conditions = []
        params = []
        param_num = 1

        if language:
            conditions.append(f"language = ${param_num}")
            params.append(language)
            param_num += 1

        if dialog_type:
            conditions.append(f"dialog_type = ${param_num}")
            params.append(dialog_type)
            param_num += 1

        if age_group:
            conditions.append(f"(age_group = ${param_num} OR age_group = 'all')")
            params.append(age_group)
            param_num += 1

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Получаем общее количество
        total_query = f"SELECT COUNT(*) FROM scenarios {where_clause}"
        total = await conn.fetchval(total_query, *params)

        # Получаем сценарии с пагинацией
        offset = (page - 1) * limit
        params.extend([limit, offset])

        scenarios_query = f"""
            SELECT id, title, description, language, dialog_type, goal, 
                   character_name, character_role, character_traits, age_group, min_level
            FROM scenarios {where_clause}
            ORDER BY title
            LIMIT ${param_num} OFFSET ${param_num + 1}
        """

        scenarios_data = await conn.fetch(scenarios_query, *params)
        scenarios = [ScenarioBase(**dict(row)) for row in scenarios_data]

        pages = (total + limit - 1) // limit

        return ScenarioList(
            scenarios=scenarios,
            total=total,
            page=page,
            pages=pages
        )

    @staticmethod
    async def get_scenario_by_id(conn, scenario_id: uuid.UUID) -> Optional[ScenarioBase]:
        scenario = await conn.fetchrow("""
            SELECT id, title, description, language, dialog_type, goal, 
                   character_name, character_role, character_traits, age_group, min_level
            FROM scenarios 
            WHERE id = $1
        """, scenario_id)

        return ScenarioBase(**dict(scenario)) if scenario else None