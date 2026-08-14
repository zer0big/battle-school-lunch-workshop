from __future__ import annotations

import asyncio
from datetime import date

import pytest

from app.neis import (
    MealSearchRequest,
    NoMealDataError,
    NoSearchResultsError,
    SchoolSearchResponse,
    fallback_meals,
    search_meals,
    search_schools,
)


def test_search_schools_uses_sample_data_without_key() -> None:
    response = asyncio.run(search_schools("서울"))

    assert response.schools
    assert isinstance(response, SchoolSearchResponse)


def test_search_schools_raises_when_neis_has_no_rows() -> None:
    async def fake_fetcher(path: str, params: dict[str, object]) -> dict[str, object]:
        return {"schoolInfo": [{"head": []}, {"row": []}]}

    with pytest.raises(NoSearchResultsError):
        asyncio.run(search_schools("없는학교", api_key="test-key", fetcher=fake_fetcher))


def test_search_meals_validates_date_range() -> None:
    request = MealSearchRequest(
        atptOfcdcScCode="B10",
        sdSchulCode="7010893",
        schoolName="서울급식배틀고등학교",
        startDate=date(2026, 8, 10),
        endDate=date(2026, 8, 9),
    )

    with pytest.raises(ValueError):
        asyncio.run(search_meals(request))


def test_search_meals_raises_when_neis_has_no_rows() -> None:
    async def fake_fetcher(path: str, params: dict[str, object]) -> dict[str, object]:
        return {"mealServiceDietInfo": [{"head": []}, {"row": []}]}

    request = MealSearchRequest(
        atptOfcdcScCode="B10",
        sdSchulCode="7010893",
        schoolName="서울급식배틀고등학교",
        startDate=date(2026, 8, 10),
        endDate=date(2026, 8, 10),
    )

    with pytest.raises(NoMealDataError):
        asyncio.run(search_meals(request, api_key="test-key", fetcher=fake_fetcher))


def test_fallback_meals_matches_date_span() -> None:
    meals = fallback_meals(date(2026, 8, 10), date(2026, 8, 12))

    assert [meal.date for meal in meals] == ["2026-08-10", "2026-08-11", "2026-08-12"]
