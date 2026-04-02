from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid

# Enums
class LanguageCode(str, Enum):
    EN = "en"
    RU = "ru"

class LangLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class AgeGroup(str, Enum):
    TEEN = "teen"
    ADULT = "adult"
    ALL = "all"

class DialogType(str, Enum):
    MISSION = "mission"
    HANGOUT = "hangout"

class Difficulty(str, Enum):
    RELAX = "relax"
    CHALLENGE = "challenge"

class SessionStatus(str, Enum):
    ACTIVE = "active"
    FINISHED = "finished"

class SessionResult(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

# Auth schemas
class UserRegister(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# User schemas
class UserProfile(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    interface_language: LanguageCode
    target_language: LanguageCode
    lang_level: LangLevel
    age_group: AgeGroup
    onboarding_completed: bool
    created_at: datetime

class UserUpdate(BaseModel):
    username: Optional[str] = None
    interface_language: Optional[LanguageCode] = None
    target_language: Optional[LanguageCode] = None
    lang_level: Optional[LangLevel] = None
    age_group: Optional[AgeGroup] = None

# Telegram schemas
class TelegramLink(BaseModel):
    telegram_user_id: int
    telegram_username: Optional[str] = None

class TelegramAuth(BaseModel):
    telegram_user_id: int

# Scenario schemas
class ScenarioBase(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    language: LanguageCode
    dialog_type: DialogType
    goal: Optional[str]
    character_name: str
    character_role: str
    character_traits: str
    age_group: AgeGroup
    min_level: LangLevel

class ScenarioList(BaseModel):
    scenarios: List[ScenarioBase]
    total: int
    page: int
    pages: int

# Session schemas
class SessionCreate(BaseModel):
    scenario_id: uuid.UUID
    dialog_type: DialogType
    difficulty: Difficulty

class SessionBase(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    dialog_type: DialogType
    difficulty: Difficulty
    status: SessionStatus
    result: Optional[SessionResult]
    started_at: datetime
    finished_at: Optional[datetime]

class SessionFinish(BaseModel):
    result: Optional[SessionResult]
    errors_summary: Optional[str]
    goal_feedback: Optional[str]
    level_up_recommended: bool = False

class SessionList(BaseModel):
    sessions: List[SessionBase]
    total: int
    page: int
    pages: int

# Message schemas
class MessageSend(BaseModel):
    content: str

class MessageResponse(BaseModel):
    user_message: str
    assistant_message: str
    hint: Optional[str] = None

class Message(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    hint: Optional[str]
    created_at: datetime

class MessageList(BaseModel):
    messages: List[Message]