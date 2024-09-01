from pydantic import BaseModel


class TavilySearchResult(BaseModel):
    title: str
    url: str


class _TavilySearchResults(BaseModel):
    results: list[TavilySearchResult]
