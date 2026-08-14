from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable

import httpx
from pydantic import BaseModel, Field

NEIS_BASE_URL = "https://open.neis.go.kr/hub"
NEIS_API_KEY = os.getenv("NEIS_API_KEY", "").strip()
MAX_RANGE_DAYS = int(os.getenv("MAX_RANGE_DAYS", "31"))


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


class NeisLookupError(RuntimeError):
    pass


class NoSearchResultsError(NeisLookupError):
    pass


class NoMealDataError(NeisLookupError):
    pass


class NeisServiceError(NeisLookupError):
    pass


Fetcher = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


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

_SAMPLE_MENU_CYCLE: list[list[str]] = [
    ["잡곡밥", "김치찌개", "닭갈비", "시금치나물", "배추김치"],
    ["차조밥", "미역국", "돈까스", "양배추샐러드", "깍두기"],
    ["현미밥", "콩나물국", "제육볶음", "계란찜", "열무김치"],
    ["흑미밥", "북엇국", "생선구이", "감자조림", "배추김치"],
    ["보리밥", "된장국", "불고기", "브로콜리무침", "깍두기"],
]


def parse_menu(raw: str) -> list[str]:
    cleaned = re.sub(r"\([^)]*\)", "", raw)
    cleaned = cleaned.replace("<br/>", "\n").replace("<br>", "\n")
    return [part.strip() for part in cleaned.split("\n") if part.strip()]


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
        [school.schulNm, school.atptOfcdcScNm, school.lctnScNm or "", school.schulKndScNm or ""]
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
    return token_matches


def fallback_meals(start: date, end: date) -> list[MealDay]:
    meals: list[MealDay] = []
    for index, day in enumerate(date_range(start, end)):
        menus = _SAMPLE_MENU_CYCLE[index % len(_SAMPLE_MENU_CYCLE)]
        meals.append(MealDay(date=day.isoformat(), menus=menus))
    return meals


async def fetch_json(
    path: str,
    params: dict[str, Any],
    *,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(f"{NEIS_BASE_URL}{path}", params=params)
        response.raise_for_status()
        return response.json()


def extract_rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    envelopes = payload.get(key, [])
    if len(envelopes) < 2:
        return []
    return envelopes[1].get("row", []) or []


def normalize_school_rows(rows: list[dict[str, Any]]) -> list[School]:
    return [
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


def normalize_meal_rows(rows: list[dict[str, Any]]) -> list[MealDay]:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        meal_date = row.get("MLSV_YMD", "")
        if not meal_date:
            continue
        formatted_date = datetime.strptime(meal_date, "%Y%m%d").date().isoformat()
        grouped.setdefault(formatted_date, [])
        grouped[formatted_date].extend(parse_menu(row.get("DDISH_NM", "")))

    return [MealDay(date=day, menus=list(dict.fromkeys(menus))) for day, menus in sorted(grouped.items())]


def _validate_date_range(start: date, end: date, max_range_days: int) -> None:
    if start > end:
        raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")

    if (end - start).days > max_range_days:
        raise ValueError(f"최대 {max_range_days}일까지 조회할 수 있습니다.")


async def search_schools(
    query: str,
    *,
    api_key: str | None = None,
    fetcher: Fetcher = fetch_json,
) -> SchoolSearchResponse:
    trimmed = query.strip()
    if not trimmed:
        raise ValueError("학교 검색어를 입력하세요.")

    resolved_api_key = (api_key if api_key is not None else NEIS_API_KEY).strip()
    if not resolved_api_key:
        schools = search_sample_schools(trimmed)
        if not schools:
            raise NoSearchResultsError("검색 결과가 없습니다.")
        return SchoolSearchResponse(schools=schools, message="NEIS 키가 없어 샘플 결과를 표시했습니다.")

    params = {
        "Key": resolved_api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": trimmed,
    }

    try:
        payload = await fetcher("/schoolInfo", params)
        rows = extract_rows(payload, "schoolInfo")
        schools = normalize_school_rows(rows)
    except httpx.TimeoutException as exc:
        raise NeisServiceError("NEIS API 응답이 지연되었습니다.") from exc
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise NeisServiceError("NEIS API와 통신하지 못했습니다.") from exc

    if not schools:
        raise NoSearchResultsError("검색 결과가 없습니다.")

    return SchoolSearchResponse(schools=schools)


async def search_meals(
    payload: MealSearchRequest,
    *,
    api_key: str | None = None,
    max_range_days: int | None = None,
    fetcher: Fetcher = fetch_json,
) -> MealSearchResponse:
    range_limit = MAX_RANGE_DAYS if max_range_days is None else max_range_days
    _validate_date_range(payload.startDate, payload.endDate, range_limit)

    resolved_api_key = (api_key if api_key is not None else NEIS_API_KEY).strip()
    if not resolved_api_key:
        meals = fallback_meals(payload.startDate, payload.endDate)
        return MealSearchResponse(
            schoolName=payload.schoolName,
            startDate=payload.startDate.isoformat(),
            endDate=payload.endDate.isoformat(),
            meals=meals,
            hasData=bool(meals),
            message="NEIS 키가 없어 샘플 데이터를 표시했습니다.",
        )

    params = {
        "Key": resolved_api_key,
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
        payload_json = await fetcher("/mealServiceDietInfo", params)
        rows = extract_rows(payload_json, "mealServiceDietInfo")
        meals = normalize_meal_rows(rows)
    except httpx.TimeoutException as exc:
        raise NeisServiceError("NEIS API 응답이 지연되었습니다.") from exc
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise NeisServiceError("NEIS API와 통신하지 못했습니다.") from exc

    if not meals:
        raise NoMealDataError("급식 정보가 없습니다.")

    return MealSearchResponse(
        schoolName=payload.schoolName,
        startDate=payload.startDate.isoformat(),
        endDate=payload.endDate.isoformat(),
        meals=meals,
        hasData=True,
    )
