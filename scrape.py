from concurrent.futures import as_completed, Future, ThreadPoolExecutor

import httpx
import streamlit as st
from bs4 import BeautifulSoup
from httpx import Response

from schemas import _TavilySearchResults, TavilySearchResult

html_tags = [
    "style",
    "script",
    "a",
    "nav",
    "footer",
    "header",
    "form",
    "iframe",
    "noscript",
]

sections = [
    "references",
    "see also",
    "related articles",
    "notes",
    "external links",
    "further reading",
    "citations",
]


def tavily_search_results(session_type: str, topic: str) -> list[TavilySearchResult]:
    payload = {
        "api_key": st.secrets.TAVILY_SEARCH_API_KEY,
        "query": f"Historical {session_type} {topic}",
        "exclude_domains": ["youtube.com"],
    }
    response = httpx.post("https://api.tavily.com/search", json=payload)

    if response.status_code != 200:
        return []

    data = response.json()
    return _TavilySearchResults(**data).results


def scrape_tavily_results(tavily_result: list[TavilySearchResult]):
    futures: list[Future[Response]] = []

    with ThreadPoolExecutor() as executor:
        for result in tavily_result:
            future = executor.submit(httpx.get, result.url)
            futures.append(future)

    result: list[str] = []
    for future in as_completed(futures):
        try:
            response = future.result()
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "lxml")
                # Remove unwanted HTML tags
                for data in soup(html_tags):
                    data.decompose()
                result.append(" ".join(soup.stripped_strings))
        except:
            continue

    return result
