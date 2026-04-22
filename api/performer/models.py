from typing import Optional
from pydantic import BaseModel, Field



class PerformerCreate(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=100, title="Nickname")
    style_music: str = Field(..., min_length=1, max_length=200, title="Style Music")


class PerformerUpdate(BaseModel):
    nickname: Optional[str] = Field(None, min_length=1, max_length=100, title="Nickname")
    style_music: Optional[str] = Field(None, min_length=1, max_length=200, title="Style Music")




