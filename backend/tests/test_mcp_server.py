from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

import mcp_server
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def test_search_school_candidates_tool_serializes_schools(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search_schools(query: str, **_: object):
        return mcp_server.SchoolSearchResponse(
            schools=[],
            message="검색 결과가 없습니다.",
        )

    monkeypatch.setattr(mcp_server, "search_schools", fake_search_schools)

    with pytest.raises(ValueError, match="검색 결과가 없습니다."):
        asyncio.run(mcp_server.search_school_candidates_tool("없는학교"))


def test_get_lunch_meals_tool_serializes_meals(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search_meals(payload, **_: object):
        return mcp_server.MealSearchResponse(
            schoolName=payload.schoolName,
            startDate="2026-08-10",
            endDate="2026-08-10",
            meals=[],
            hasData=False,
            message="급식 정보가 없습니다.",
        )

    monkeypatch.setattr(mcp_server, "search_meals", fake_search_meals)

    with pytest.raises(ValueError, match="급식 정보가 없습니다."):
        asyncio.run(
            mcp_server.get_lunch_meals_tool(
                "B10",
                "7010893",
                "서울급식배틀고등학교",
                "2026-08-10",
                "2026-08-10",
            )
        )


def test_get_lunch_meals_tool_rejects_invalid_dates() -> None:
    with pytest.raises(ValueError, match="날짜 형식"):
        asyncio.run(
            mcp_server.get_lunch_meals_tool(
                "B10",
                "7010893",
                "서울급식배틀고등학교",
                "2026-13-01",
                "2026-13-02",
            )
        )


def test_streamable_http_client_can_list_and_call_tools() -> None:
    async def run() -> None:
        env = os.environ.copy()
        env["MCP_HOST"] = "127.0.0.1"
        env["MCP_PORT"] = "8015"
        env["MCP_TRANSPORT"] = "streamable-http"
        proc = subprocess.Popen(
            [sys.executable, "src/mcp/server.py"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
        )

        try:
            url = "http://127.0.0.1:8015/mcp"
            last_error: Exception | None = None
            for _ in range(20):
                try:
                    async with streamablehttp_client(url) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools = await session.list_tools()
                            tool_names = [tool.name for tool in tools.tools]
                            assert "search_school_candidates_tool" in tool_names
                            assert "get_lunch_meals_tool" in tool_names

                            search_result = await session.call_tool(
                                "search_school_candidates_tool",
                                {"query": "서울"},
                            )
                            assert search_result.isError is False
                            assert search_result.structuredContent["count"] == 1

                            meal_result = await session.call_tool(
                                "get_lunch_meals_tool",
                                {
                                    "atptOfcdcScCode": "B10",
                                    "sdSchulCode": "7010893",
                                    "schoolName": "서울급식배틀고등학교",
                                    "startDate": "2026-08-10",
                                    "endDate": "2026-08-10",
                                },
                            )
                            assert meal_result.isError is False
                            assert meal_result.structuredContent["hasData"] is True
                            return
                except Exception as exc:
                    last_error = exc
                    await asyncio.sleep(1)
            raise AssertionError("MCP server did not become ready") from last_error
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    asyncio.run(run())
