from typing import Optional
from pydantic import BaseModel, Field


class SongCreate(BaseModel):
    performer_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=200)
    style_music: str = Field(..., min_length=1, max_length=200)
    album: Optional[str] = Field(None, max_length=200)  # ← ДОБАВЛЕНО
    genre: Optional[str] = Field(None, max_length=100)  # ← ДОБАВЛЕНО
    duration: Optional[int] = Field(None, gt=0)


class SongUpdate(BaseModel):
    performer_id: Optional[int] = Field(None, gt=0)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    style_music: Optional[str] = Field(None, min_length=1, max_length=200)
    album: Optional[str] = Field(None, max_length=200)  # ← ДОБАВЛЕНО
    genre: Optional[str] = Field(None, max_length=100)  # ← ДОБАВЛЕНО
    duration: Optional[int] = Field(None, gt=0)
