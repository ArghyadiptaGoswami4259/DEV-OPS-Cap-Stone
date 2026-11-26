"""TaskFlow API factory, routes and process entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from logging import getLogger

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import Settings
from .db import Database
from .logging import configure_logging
from .metrics import TASK_OPERATIONS, render_metrics, set_build_info, set_ready
from .middleware import ObservabilityMiddleware
from .models import Task
from .schemas import (
    HealthRead,
    InfoRead,
    ReadyRead,
    TaskCreate,
    TaskList,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)
from .ui import render_index

logger = getLogger("taskflow")


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def _task_or_404(db: Session, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    db = database or Database(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if settings.auto_create_schema:
            db.create_schema()
        try:
            set_ready(db.check())
            logger.info(
                "service.started",
                extra={
                    "context": {
                        "version": settings.version,
                        "commit": settings.git_sha,
                        "environment": settings.environment,
                    }
                },
            )
        except SQLAlchemyError:
            set_ready(False)
            logger.exception("service.startup_database_unavailable")
        yield
        db.dispose()
        set_ready(False)

    production_docs = None if settings.is_production else "/docs"
    app = FastAPI(
        title="TaskFlow API",
        version=settings.version,
        description="Reference application for the end-to-end DevOps automation capstone.",
        lifespan=lifespan,
        docs_url=production_docs,
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings
    app.state.db = db
    app.add_middleware(ObservabilityMiddleware, settings=settings)
    set_build_info(settings.version, settings.git_sha, settings.environment)

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            extra={
                "context": {
                    "path": request.url.path,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> HTMLResponse:
        return HTMLResponse(render_index(settings))

    @app.get("/healthz", response_model=HealthRead, tags=["health"])
    def healthz() -> HealthRead:
        return HealthRead(
            status="ok",
            service=settings.app_name,
            version=settings.version,
            commit=settings.git_sha,
            environment=settings.environment,
        )

    @app.get("/readyz", response_model=ReadyRead, tags=["health"])
    def readyz(response: Response, db_session: Session = Depends(get_db)) -> ReadyRead:
        try:
            db_session.execute(select(func.count()).select_from(Task))
            set_ready(True)
            return ReadyRead(status="ready", database="ok")
        except SQLAlchemyError:
            set_ready(False)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            logger.exception("readiness.database_failed")
            return ReadyRead(status="unavailable", database="failed")

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        content, media_type = render_metrics()
        return Response(content=content, media_type=media_type)

    @app.get("/api/v1/info", response_model=InfoRead, tags=["metadata"])
    def info() -> InfoRead:
        return InfoRead(
            service=settings.app_name,
            version=settings.version,
            commit=settings.git_sha,
            environment=settings.environment,
            otel_service_name=settings.otel_service_name,
        )

    @app.get("/api/v1/tasks", response_model=TaskList, tags=["tasks"])
    def list_tasks(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        task_status: TaskStatus | None = Query(None, alias="status"),
        db_session: Session = Depends(get_db),
    ) -> TaskList:
        query = select(Task).order_by(Task.created_at.desc(), Task.id)
        count_query = select(func.count()).select_from(Task)
        if task_status is not None:
            query = query.where(Task.status == task_status)
            count_query = count_query.where(Task.status == task_status)
        total = int(db_session.scalar(count_query) or 0)
        rows = db_session.scalars(query.limit(limit).offset(offset)).all()
        items = [TaskRead.model_validate(row) for row in rows]
        return TaskList(items=items, total=total, limit=limit, offset=offset)

    @app.post(
        "/api/v1/tasks",
        response_model=TaskRead,
        status_code=status.HTTP_201_CREATED,
        tags=["tasks"],
    )
    def create_task(
        payload: TaskCreate,
        response: Response,
        db_session: Session = Depends(get_db),
    ) -> Task:
        task = Task(**payload.model_dump())
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        TASK_OPERATIONS.labels("create").inc()
        response.status_code = status.HTTP_201_CREATED
        return task

    @app.get("/api/v1/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
    def get_task(task_id: str, db_session: Session = Depends(get_db)) -> Task:
        return _task_or_404(db_session, task_id)

    @app.patch("/api/v1/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
    def update_task(
        task_id: str,
        payload: TaskUpdate,
        db_session: Session = Depends(get_db),
    ) -> Task:
        task = _task_or_404(db_session, task_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        db_session.commit()
        db_session.refresh(task)
        TASK_OPERATIONS.labels("update").inc()
        return task

    @app.delete("/api/v1/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tasks"])
    def delete_task(task_id: str, db_session: Session = Depends(get_db)) -> Response:
        task = _task_or_404(db_session, task_id)
        db_session.delete(task)
        db_session.commit()
        TASK_OPERATIONS.labels("delete").inc()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


app = create_app()


def run() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips=settings.forwarded_allow_ips,
        log_config=None,
        access_log=False,
        server_header=False,
        date_header=False,
    )
