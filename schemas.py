from typing_extensions import TypedDict

from pydantic import BaseModel


class TavilySearchResult(BaseModel):
    title: str
    url: str


class _TavilySearchResults(BaseModel):
    results: list[TavilySearchResult]


class GraphNode(TypedDict):
    text: str
    head: str
    head_type: str
    relation: str
    tail: str
    tail_type: str
