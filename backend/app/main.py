from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.neis import (
    MealSearchRequest,
    MealSearchResponse,
    NoMealDataError,
    NoSearchResultsError,
    NeisServiceError,
    SchoolSearchResponse,
    search_sample_schools,
    search_meals,
    search_schools,
)

app = FastAPI(title="School Lunch API", version="1.0.0")
STATIC_INDEX = Path(__file__).with_name("static") / "index.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(STATIC_INDEX.read_text(encoding="utf-8"))


@app.get("/api/schools", response_model=SchoolSearchResponse)
async def search_school_candidates(query: str) -> SchoolSearchResponse:
    try:
        return await search_schools(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NoSearchResultsError as exc:
        return SchoolSearchResponse(schools=[], message=str(exc))
    except NeisServiceError as exc:
        return SchoolSearchResponse(schools=search_sample_schools(query), message=str(exc))


@app.post("/api/meals", response_model=MealSearchResponse)
async def search_lunch_meals(payload: MealSearchRequest) -> MealSearchResponse:
    try:
        return await search_meals(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NoMealDataError as exc:
        return MealSearchResponse(
            schoolName=payload.schoolName,
            startDate=payload.startDate.isoformat(),
            endDate=payload.endDate.isoformat(),
            meals=[],
            hasData=False,
            message=str(exc),
        )
    except NeisServiceError as exc:
        fallback = await search_meals(payload, api_key="")
        return MealSearchResponse(
            schoolName=fallback.schoolName,
            startDate=fallback.startDate,
            endDate=fallback.endDate,
            meals=fallback.meals,
            hasData=fallback.hasData,
            message=str(exc),
        )
