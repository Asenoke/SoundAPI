from typing import Optional
from pydantic import BaseModel, Field


class PlaylistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    is_public: bool = Field(True)


class PlaylistUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = Field(None)


class AddTrackToPlaylist(BaseModel):
    song_id: int = Field(..., gt=0)


class UpdateTrackPosition(BaseModel):
    position: int = Field(..., ge=0)