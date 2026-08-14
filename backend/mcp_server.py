import os
from typing import Any

import anyio
import uvicorn
from pydantic import ValidationError
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.neis import (
    MealSearchRequest,
    MealSearchResponse,
    SchoolSearchResponse,
    NoMealDataError,
    NoSearchResultsError,
    NeisServiceError,
    search_meals,
    search_schools,
)

MCP_NAME = "battle-school-lunch-mcp"
MCP_BROWSER_TEXT = """MCP server is running.

Browser check: OK
Protocol endpoint: /mcp
Inspector URL: http://127.0.0.1:8001/mcp

Note: MCP clients use Streamable HTTP headers. A normal browser page is only a status view.
"""


class BrowserFriendlyMcpMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "GET" and scope["path"] == "/mcp":
            headers = dict(scope.get("headers") or [])
            accept = headers.get(b"accept", b"").decode("latin-1")
            if "text/event-stream" not in accept:
                await PlainTextResponse(MCP_BROWSER_TEXT)(scope, receive, send)
                return

        await self.app(scope, receive, send)


def _school_to_dict(school: Any) -> dict[str, Any]:
    return school.model_dump()


def _meal_to_dict(meal: Any) -> dict[str, Any]:
    return meal.model_dump()


async def search_school_candidates_tool(query: str) -> dict[str, Any]:
    """학교 이름 일부로 학교 후보를 검색한다."""

    response: SchoolSearchResponse
    try:
        response = await search_schools(query)
    except (ValueError, NoSearchResultsError, NeisServiceError) as exc:
        raise ValueError(str(exc)) from exc

    if not response.schools:
        raise ValueError(response.message or "검색 결과가 없습니다.")

    return {
        "query": query,
        "count": len(response.schools),
        "message": response.message,
        "schools": [_school_to_dict(school) for school in response.schools],
    }


async def get_lunch_meals_tool(
    atptOfcdcScCode: str,
    sdSchulCode: str,
    schoolName: str,
    startDate: str,
    endDate: str,
) -> dict[str, Any]:
    """선택한 학교와 날짜 범위의 중식 급식을 조회한다."""

    try:
        request = MealSearchRequest(
            atptOfcdcScCode=atptOfcdcScCode,
            sdSchulCode=sdSchulCode,
            schoolName=schoolName,
            startDate=startDate,
            endDate=endDate,
        )
    except ValidationError as exc:
        raise ValueError("입력한 날짜 형식이 올바르지 않습니다.") from exc

    response: MealSearchResponse
    try:
        response = await search_meals(request)
    except (ValueError, NoMealDataError, NeisServiceError) as exc:
        raise ValueError(str(exc)) from exc

    if not response.hasData or not response.meals:
        raise ValueError(response.message or "급식 정보가 없습니다.")

    return {
        "schoolName": response.schoolName,
        "startDate": response.startDate,
        "endDate": response.endDate,
        "hasData": response.hasData,
        "message": response.message,
        "meals": [_meal_to_dict(meal) for meal in response.meals],
    }


def build_server(*, host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    mcp = FastMCP(MCP_NAME, host=host, port=port)
    mcp.tool()(search_school_candidates_tool)
    mcp.tool()(get_lunch_meals_tool)

    @mcp.custom_route("/", methods=["GET"], include_in_schema=False)
    async def root(_: Request) -> PlainTextResponse:
        return PlainTextResponse("MCP server is running. Connect to /mcp.")

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return mcp


def main() -> None:
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8001"))
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    server = build_server(host=host, port=port)

    if transport == "streamable-http":
        app = BrowserFriendlyMcpMiddleware(server.streamable_http_app())
        config = uvicorn.Config(app, host=host, port=port, log_level=server.settings.log_level.lower())
        anyio.run(uvicorn.Server(config).serve)
        return

    server.run(transport=transport)


if __name__ == "__main__":
    main()
