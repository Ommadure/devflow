"""The HTTP API tester, run server-side (ADR 0006): no browser CORS limits, and therefore
SSRF protection on every request (services/api_tester/ssrf.py)."""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import (
    AiUsageDep,
    LLMDep,
    ProxyClientDep,
    ResolverDep,
    ai_rate_limit,
    proxy_rate_limit,
)
from app.schemas.api_tester import (
    CurlParsed,
    CurlRequest,
    ExplainErrorRequest,
    HttpErrorExplanation,
    ProxyRequest,
    ProxyResponse,
)
from app.services.ai import assistant
from app.services.api_tester import proxy
from app.services.api_tester.curl import parse_curl

router = APIRouter(prefix="/api-tester", tags=["api tester"])

SEND_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"description": "Invalid URL, or a private/reserved destination (BLOCKED_DESTINATION)"},
    429: {"description": "More than 30 requests a minute"},
    502: {
        "description": "The target was unreachable or too slow (PROXY_UNREACHABLE, PROXY_TIMEOUT)"
    },
}


@router.post("/send", responses=SEND_RESPONSES, dependencies=[Depends(proxy_rate_limit)])
async def send(body: ProxyRequest, client: ProxyClientDep, resolve: ResolverDep) -> ProxyResponse:
    """Send the request from the server and report what came back.

    A 4xx/5xx from the TARGET is a successful proxy call (200 here, the target's status in
    the body); only a failure to get any answer is an error.
    """
    result = await proxy.send(
        client, body.method, body.url, body.headers, body.body, resolve=resolve
    )
    return ProxyResponse(**result.__dict__)


@router.post("/parse-curl")
async def curl(body: CurlRequest) -> CurlParsed:
    """Turn a copied cURL command into method, URL, headers and body. No AI involved."""
    return CurlParsed(**parse_curl(body.command).__dict__)


@router.post(
    "/explain-error",
    dependencies=[Depends(ai_rate_limit)],
    responses={429: {"description": "Rate limited, or the daily AI quota is used up"}},
)
async def explain_error(
    body: ExplainErrorRequest, usage: AiUsageDep, llm: LLMDep
) -> HttpErrorExplanation:
    """Likely causes and fixes for a failed response. Counts against the AI quota."""
    await usage.check_quota("explain_http_error")
    return await assistant.explain_http_error(llm, body, usage)
