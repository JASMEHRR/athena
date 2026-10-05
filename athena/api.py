"""FastAPI app: JSON API under /api/v1, slide images under /media, the web app at /.

Run with `python -m athena.server` (scripts\\start-athena.bat does this).
Listens on 127.0.0.1 only.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, config, db, planner, progress, services, srs

API = "/api/v1"


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = db.connect(config.DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ------------------------------------------------------------------ request bodies


class ChunkBody(BaseModel):
    chunk_id: str
    topic_id: str
    status: str = Field(pattern="^(seen|known)$")


class AnswerBody(BaseModel):
    question_id: str
    answer: str = Field(max_length=2000)
    context: str = Field(default="quiz", pattern="^(check|quiz|warmup|mock)$")


class CompleteBody(BaseModel):
    confidence: int = Field(ge=1, le=5)


class WrittenBody(BaseModel):
    kind: str = Field(pattern="^(explain_back|written)$")
    topic_id: str
    question_id: str = ""
    text: str = Field(min_length=1, max_length=20000)


class WrittenUpdate(BaseModel):
    ticks: list[bool] | None = None
    send_for_review: bool = False


class RatingBody(BaseModel):
    rating: int = Field(ge=1, le=4)


class ActivityBody(BaseModel):
    kind: str = Field(pattern="^(learn|review|practice)$")
    seconds: int = Field(ge=1, le=120)
    subject_id: str = ""
    topic_id: str = ""


class TaskStatusBody(BaseModel):
    status: str = Field(pattern="^(todo|done|skipped)$")


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found")


def create_app() -> FastAPI:
    app = FastAPI(title="Athena", version=__version__, docs_url=f"{API}/docs", openapi_url=f"{API}/openapi.json")

    @app.exception_handler(sqlite3.Error)
    async def _db_error(request: Request, exc: sqlite3.Error):
        return JSONResponse(status_code=500, content={"detail": f"database error: {exc}"})

    # ---------------------------------------------------------------- meta

    @app.get(f"{API}/health")
    def health(conn: sqlite3.Connection = Depends(get_conn)):
        topics = conn.execute("SELECT COUNT(*) FROM c_topics").fetchone()[0]
        return {"ok": True, "version": __version__, "topics": topics}

    @app.get(f"{API}/summary")
    def summary(conn: sqlite3.Connection = Depends(get_conn)):
        return services.summary(conn)

    @app.get(f"{API}/today")
    def today(conn: sqlite3.Connection = Depends(get_conn)):
        return services.today_view(conn)

    # ---------------------------------------------------------------- subjects and lessons

    @app.get(f"{API}/subjects")
    def subjects(conn: sqlite3.Connection = Depends(get_conn)):
        return services.subjects_overview(conn)

    @app.get(f"{API}/subjects/{{subject_id}}")
    def subject(subject_id: str, conn: sqlite3.Connection = Depends(get_conn)):
        data = services.subject_detail(conn, subject_id)
        if data is None:
            raise _not_found("subject")
        return data

    @app.get(f"{API}/topics/{{topic_id}}")
    def topic(topic_id: str, conn: sqlite3.Connection = Depends(get_conn)):
        data = services.lesson(conn, topic_id)
        if data is None:
            raise _not_found("topic")
        return data

    @app.get(f"{API}/slides/{{deck_id}}/{{n}}")
    def slide(deck_id: str, n: int, conn: sqlite3.Connection = Depends(get_conn)):
        data = services.slide(conn, deck_id, n)
        if data is None:
            raise _not_found("slide")
        return data

    @app.post(f"{API}/progress/chunk")
    def chunk_progress(body: ChunkBody, conn: sqlite3.Connection = Depends(get_conn)):
        topic = services.topic_json(conn, body.topic_id)
        if topic is None or body.chunk_id not in {c["id"] for c in topic["chunks"]}:
            raise _not_found("chunk")
        progress.set_chunk(conn, body.chunk_id, body.topic_id, topic["subject_id"], body.status)
        return {"ok": True}

    @app.post(f"{API}/topics/{{topic_id}}/complete")
    def complete(topic_id: str, body: CompleteBody, conn: sqlite3.Connection = Depends(get_conn)):
        topic = services.topic_json(conn, topic_id)
        if topic is None:
            raise _not_found("topic")
        cards = [r["id"] for r in conn.execute("SELECT id FROM c_cards WHERE topic_id = ? AND hidden = 0", (topic_id,))]
        added = progress.complete_topic(conn, topic_id, topic["subject_id"], body.confidence, cards)
        return {"ok": True, "cards_added": added, "mastery": progress.mastery(conn, topic_id)}

    @app.post(f"{API}/answer")
    def answer(body: AnswerBody, conn: sqlite3.Connection = Depends(get_conn)):
        try:
            return services.answer(conn, body.question_id, body.answer, body.context)
        except KeyError:
            raise _not_found("question")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post(f"{API}/written")
    def written(body: WrittenBody, conn: sqlite3.Connection = Depends(get_conn)):
        try:
            return services.written_start(conn, body.kind, body.topic_id, body.text, body.question_id)
        except KeyError:
            raise _not_found("topic or question")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.put(f"{API}/written/{{answer_id}}")
    def written_update(answer_id: str, body: WrittenUpdate, conn: sqlite3.Connection = Depends(get_conn)):
        try:
            return services.written_update(conn, answer_id, body.ticks, body.send_for_review)
        except KeyError:
            raise _not_found("answer")

    @app.get(f"{API}/written")
    def written_history(topic_id: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
        return services.written_history(conn, topic_id)

    # ---------------------------------------------------------------- review and quiz

    @app.get(f"{API}/review")
    def review_queue(limit: int = Query(30, ge=1, le=200), subject_id: str | None = None,
                     conn: sqlite3.Connection = Depends(get_conn)):
        return services.review_queue(conn, limit, subject_id)

    @app.post(f"{API}/review/{{card_id}}")
    def review_card(card_id: str, body: RatingBody, conn: sqlite3.Connection = Depends(get_conn)):
        try:
            return srs.review(conn, card_id, body.rating)
        except KeyError:
            raise _not_found("card")

    @app.get(f"{API}/quiz")
    def quiz(subject_id: str | None = None, topics: str | None = None, types: str | None = None,
             count: int = Query(10, ge=1, le=60), include_checks: bool = True,
             conn: sqlite3.Connection = Depends(get_conn)):
        topic_ids = [t for t in (topics or "").split(",") if t]
        type_list = [t for t in (types or "").split(",") if t] or None
        return services.quiz(conn, subject_id, topic_ids or None, type_list, count, include_checks)

    # ---------------------------------------------------------------- activity, settings, search

    @app.post(f"{API}/activity")
    def activity(body: ActivityBody, conn: sqlite3.Connection = Depends(get_conn)):
        progress.add_activity(conn, body.kind, body.seconds, body.subject_id, body.topic_id)
        return {"ok": True, "minutes_today": progress.minutes_today(conn)}

    @app.get(f"{API}/settings")
    def get_settings(conn: sqlite3.Connection = Depends(get_conn)):
        return {"settings": services.settings(conn), "content_exams": [dict(r) for r in conn.execute("SELECT * FROM c_exams")]}

    @app.put(f"{API}/settings")
    def put_settings(values: dict, conn: sqlite3.Connection = Depends(get_conn)):
        unknown = [k for k in values if k not in services.DEFAULT_SETTINGS]
        if unknown:
            raise HTTPException(status_code=400, detail=f"unknown settings: {unknown}")
        if "exams" in values and values["exams"] is not None:
            for e in values["exams"]:
                try:
                    date.fromisoformat(e["date"])
                except (KeyError, TypeError, ValueError):
                    raise HTTPException(status_code=400, detail="each exam needs subject_id and date YYYY-MM-DD")
        updated = services.update_settings(conn, values)
        planner.replan(conn)
        return {"settings": updated}

    @app.get(f"{API}/search")
    def search(q: str = Query(..., min_length=1, max_length=200), conn: sqlite3.Connection = Depends(get_conn)):
        return services.search(conn, q)

    # ---------------------------------------------------------------- plan

    @app.get(f"{API}/plan/today")
    def plan_today(conn: sqlite3.Connection = Depends(get_conn)):
        return planner.today_plan(conn)

    @app.post(f"{API}/plan/replan")
    def plan_replan(conn: sqlite3.Connection = Depends(get_conn)):
        return planner.replan(conn)

    @app.put(f"{API}/plan/tasks/{{task_id}}")
    def plan_task(task_id: str, body: TaskStatusBody, conn: sqlite3.Connection = Depends(get_conn)):
        try:
            planner.set_task_status(conn, task_id, body.status)
        except KeyError:
            raise _not_found("task")
        return {"ok": True}

    @app.get(f"{API}/plan/calendar")
    def plan_calendar(start: str | None = None, days: int = Query(42, ge=1, le=120),
                      conn: sqlite3.Connection = Depends(get_conn)):
        try:
            start_date = date.fromisoformat(start) if start else None
        except ValueError:
            raise HTTPException(status_code=400, detail="start must be YYYY-MM-DD")
        return planner.calendar(conn, start_date, days)

    @app.get(f"{API}/plan/export.ics")
    def plan_ics(conn: sqlite3.Connection = Depends(get_conn)):
        cal = planner.calendar(conn, None, 60)
        names = {sid: s["short_name"] for sid, s in services.subject_map(conn).items()}
        return PlainTextResponse(planner.to_ics(cal, names), media_type="text/calendar",
                                 headers={"Content-Disposition": 'attachment; filename="athena-plan.ics"'})

    # ---------------------------------------------------------------- static files

    slides_dir = config.DATA_DIR / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media/slides", StaticFiles(directory=str(slides_dir)), name="slides")

    @app.get("/")
    def index():
        return FileResponse(config.WEB_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True), name="web")
    return app
