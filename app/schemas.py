"""Request and response schemas with strict input validation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskStatus = Literal["todo", "in_progress", "done"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus = "todo"

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title must not be blank")
        return cleaned


class TaskUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title must not be blank")
        return cleaned


class TaskRead(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    title: str
    description: str | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime


class TaskList(StrictModel):
    items: list[TaskRead]
    total: int
    limit: int
    offset: int


class HealthRead(StrictModel):
    status: str
    service: str
    version: str
    commit: str
    environment: str


class ReadyRead(StrictModel):
    status: str
    database: str


class InfoRead(StrictModel):
    service: str
    version: str
    commit: str
    environment: str
    otel_service_name: str
