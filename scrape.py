from concurrent.futures import as_completed, Future, ThreadPoolExecutor

import httpx
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


# TODO: Add session type to payload query
def tavily_search_results(topic: str, api_key: str) -> list[TavilySearchResult]:
    payload = {"api_key": api_key, "query": topic}
    response = httpx.post("https://api.tavily.com/search", json=payload)

    if response.status_code != 200:
        raise

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
        response = future.result()
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")
            # Remove unwanted HTML tags
            for data in soup(html_tags):
                data.decompose()
            result.append(" ".join(soup.stripped_strings))

    return result
