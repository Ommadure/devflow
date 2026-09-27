from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.services.api_tester.proxy import Method

HeaderMap = Annotated[
    dict[str, Annotated[str, StringConstraints(max_length=8_192)]], Field(max_length=50)
]


class ProxyRequest(BaseModel):
    method: Method = "GET"
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_048)]
    headers: HeaderMap = {}
    body: Annotated[str, StringConstraints(max_length=1_000_000)] | None = None


class ProxyResponse(BaseModel):
    status: int
    status_text: str
    headers: list[tuple[str, str]]
    body: str
    body_truncated: bool
    elapsed_ms: int
    size_bytes: int
    final_url: str
    redirects: list[str]


class CurlRequest(BaseModel):
    command: Annotated[str, StringConstraints(min_length=1, max_length=20_000)]


class CurlParsed(BaseModel):
    method: str
    url: str
    headers: dict[str, str]
    body: str | None
    warnings: list[str]


class ExplainErrorRequest(BaseModel):
    """The failed exchange, as the tester shows it."""

    method: Method
    url: Annotated[str, StringConstraints(max_length=2_048)]
    status: int = Field(ge=100, le=599)
    status_text: Annotated[str, StringConstraints(max_length=200)] = ""
    response_headers: Annotated[list[tuple[str, str]], Field(max_length=100)] = []
    # Only the start of the body is sent to the model: enough to see the error message.
    response_body: Annotated[str, StringConstraints(max_length=1_000_000)] = ""


class HttpErrorExplanation(BaseModel):
    likely_causes: Annotated[
        list[Annotated[str, StringConstraints(max_length=300)]], Field(min_length=1, max_length=5)
    ]
    suggested_fixes: Annotated[
        list[Annotated[str, StringConstraints(max_length=300)]], Field(min_length=1, max_length=5)
    ]
    confidence: Literal["low", "medium", "high"]
