from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

NEIS_BASE_URL = "https://open.neis.go.kr/hub"
NEIS_API_KEY = os.getenv("NEIS_API_KEY", "").strip()
MAX_RANGE_DAYS = int(os.getenv("MAX_RANGE_DAYS", "31"))

app = FastAPI(title="School Lunch API", version="1.0.0")
STATIC_INDEX = Path(__file__).with_name("static") / "index.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class School(BaseModel):
    atptOfcdcScCode: str
    atptOfcdcScNm: str
    sdSchulCode: str
    schulNm: str
    schulKndScNm: str | None = None
    lctnScNm: str | None = None


class SchoolSearchResponse(BaseModel):
    schools: list[School]
    message: str | None = None


class MealDay(BaseModel):
    date: str
    menus: list[str]


class MealSearchRequest(BaseModel):
    atptOfcdcScCode: str = Field(min_length=1)
    sdSchulCode: str = Field(min_length=1)
    schoolName: str = Field(min_length=1)
    startDate: date
    endDate: date


class MealSearchResponse(BaseModel):
    schoolName: str
    startDate: str
    endDate: str
    meals: list[MealDay]
    hasData: bool
    message: str | None = None


SAMPLE_SCHOOLS: list[School] = [
    School(
        atptOfcdcScCode="B10",
        atptOfcdcScNm="서울특별시교육청",
        sdSchulCode="7010893",
        schulNm="서울급식배틀고등학교",
        schulKndScNm="고등학교",
        lctnScNm="서울특별시",
    ),
    School(
        atptOfcdcScCode="C10",
        atptOfcdcScNm="경기도교육청",
        sdSchulCode="7240154",
        schulNm="경기미래중학교",
        schulKndScNm="중학교",
        lctnScNm="경기도",
    ),
    School(
        atptOfcdcScCode="J10",
        atptOfcdcScNm="세종특별자치시교육청",
        sdSchulCode="3030033",
        schulNm="세종행복초등학교",
        schulKndScNm="초등학교",
        lctnScNm="세종특별자치시",
    ),
    School(
        atptOfcdcScCode="D10",
        atptOfcdcScNm="충청북도교육청",
        sdSchulCode="4100123",
        schulNm="청주미래고등학교",
        schulKndScNm="고등학교",
        lctnScNm="충청북도",
    ),
    School(
        atptOfcdcScCode="F10",
        atptOfcdcScNm="부산광역시교육청",
        sdSchulCode="8090456",
        schulNm="부산해운대중학교",
        schulKndScNm="중학교",
        lctnScNm="부산광역시",
    ),
]


def parse_menu(raw: str) -> list[str]:
    cleaned = re.sub(r"\([^)]*\)", "", raw)
    cleaned = cleaned.replace("<br/>", "\n").replace("<br>", "\n")
    parts = [part.strip() for part in cleaned.split("\n") if part.strip()]
    return parts


def date_range(start: date, end: date) -> list[date]:
    current = start
    days: list[date] = []
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def school_matches(query: str, school: School) -> bool:
    needle = query.casefold()
    haystack = " ".join(
        [
            school.schulNm,
            school.atptOfcdcScNm,
            school.lctnScNm or "",
            school.schulKndScNm or "",
        ]
    ).casefold()
    return needle in haystack


def search_sample_schools(query: str) -> list[School]:
    exact = [school for school in SAMPLE_SCHOOLS if school_matches(query, school)]
    if exact:
        return exact

    tokens = [token for token in re.split(r"\s+", query.casefold()) if token]
    if not tokens:
        return SAMPLE_SCHOOLS

    token_matches = [
        school
        for school in SAMPLE_SCHOOLS
        if all(
            token in " ".join(
                [school.schulNm, school.atptOfcdcScNm, school.lctnScNm or "", school.schulKndScNm or ""]
            ).casefold()
            for token in tokens
        )
    ]
    return token_matches or SAMPLE_SCHOOLS


async def fetch_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{NEIS_BASE_URL}{path}", params=params)
        response.raise_for_status()
        return response.json()


def extract_rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    envelopes = payload.get(key, [])
    if len(envelopes) < 2:
        return []
    return envelopes[1].get("row", []) or []


def fallback_meals(start: date, end: date) -> list[MealDay]:
    menu_cycle = [
        ["잡곡밥", "김치찌개", "닭갈비", "시금치나물", "배추김치"],
        ["차조밥", "미역국", "돈까스", "양배추샐러드", "깍두기"],
        ["현미밥", "콩나물국", "제육볶음", "계란찜", "열무김치"],
        ["흑미밥", "북엇국", "생선구이", "감자조림", "배추김치"],
        ["보리밥", "된장국", "불고기", "브로콜리무침", "깍두기"],
    ]
    meals: list[MealDay] = []
    for index, day in enumerate(date_range(start, end)):
        menus = menu_cycle[index % len(menu_cycle)]
        meals.append(MealDay(date=day.isoformat(), menus=menus))
    return meals


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(STATIC_INDEX.read_text(encoding="utf-8"))


@app.get("/api/schools", response_model=SchoolSearchResponse)
async def search_schools(query: str) -> SchoolSearchResponse:
    trimmed = query.strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="학교 검색어를 입력하세요.")

    if not NEIS_API_KEY:
        schools = search_sample_schools(trimmed)
        message = None if any(school_matches(trimmed, school) for school in schools) else "샘플 학교 결과를 보여줍니다."
        return SchoolSearchResponse(schools=schools, message=message)

    params = {
        "Key": NEIS_API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": trimmed,
    }

    try:
        payload = await fetch_json("/schoolInfo", params)
        rows = extract_rows(payload, "schoolInfo")
        schools = [
            School(
                atptOfcdcScCode=row.get("ATPT_OFCDC_SC_CODE", ""),
                atptOfcdcScNm=row.get("ATPT_OFCDC_SC_NM", ""),
                sdSchulCode=row.get("SD_SCHUL_CODE", ""),
                schulNm=row.get("SCHUL_NM", ""),
                schulKndScNm=row.get("SCHUL_KND_SC_NM"),
                lctnScNm=row.get("LCTN_SC_NM"),
            )
            for row in rows
        ]
        if schools:
            return SchoolSearchResponse(schools=schools)
    except (httpx.HTTPError, ValueError, KeyError):
        pass

    schools = search_sample_schools(trimmed)
    message = None if any(school_matches(trimmed, school) for school in schools) else "NEIS 결과 대신 샘플 학교 결과를 보여줍니다."
    return SchoolSearchResponse(schools=schools, message=message)


@app.post("/api/meals", response_model=MealSearchResponse)
async def search_meals(payload: MealSearchRequest) -> MealSearchResponse:
    if payload.startDate > payload.endDate:
        raise HTTPException(status_code=400, detail="시작일은 종료일보다 늦을 수 없습니다.")

    if (payload.endDate - payload.startDate).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"최대 {MAX_RANGE_DAYS}일까지 조회할 수 있습니다.")

    if not NEIS_API_KEY:
        meals = fallback_meals(payload.startDate, payload.endDate)
        return MealSearchResponse(
            schoolName=payload.schoolName,
            startDate=payload.startDate.isoformat(),
            endDate=payload.endDate.isoformat(),
            meals=meals,
            hasData=True,
        )

    params = {
        "Key": NEIS_API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": payload.atptOfcdcScCode,
        "SD_SCHUL_CODE": payload.sdSchulCode,
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": payload.startDate.strftime("%Y%m%d"),
        "MLSV_TO_YMD": payload.endDate.strftime("%Y%m%d"),
    }

    try:
        payload_json = await fetch_json("/mealServiceDietInfo", params)
        rows = extract_rows(payload_json, "mealServiceDietInfo")
        grouped: dict[str, list[str]] = {}
        for row in rows:
            meal_date = row.get("MLSV_YMD", "")
            if not meal_date:
                continue
            formatted_date = datetime.strptime(meal_date, "%Y%m%d").date().isoformat()
            grouped.setdefault(formatted_date, [])
            grouped[formatted_date].extend(parse_menu(row.get("DDISH_NM", "")))

        meals = [MealDay(date=day, menus=list(dict.fromkeys(menus))) for day, menus in sorted(grouped.items())]
        if meals:
            return MealSearchResponse(
                schoolName=payload.schoolName,
                startDate=payload.startDate.isoformat(),
                endDate=payload.endDate.isoformat(),
                meals=meals,
                hasData=True,
            )
    except (httpx.HTTPError, ValueError, KeyError):
        pass

    meals = fallback_meals(payload.startDate, payload.endDate)
    return MealSearchResponse(
        schoolName=payload.schoolName,
        startDate=payload.startDate.isoformat(),
        endDate=payload.endDate.isoformat(),
        meals=meals,
        hasData=True,
        message="NEIS 응답을 가져오지 못해 샘플 데이터를 표시했습니다.",
    )
