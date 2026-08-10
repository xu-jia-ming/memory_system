"""Pydantic schemas for Memory Session API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    user_id: str = Field(min_length=1)


class CreateSessionResponse(BaseModel):
    session_id: str
    status: Literal["created"]
