import logging
from concurrent.futures import as_completed, Future, ThreadPoolExecutor

from llm import generate_entity_relationship

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def _create_node(head: str, head_type: str) -> dict:
    return {
        "color": "#97c2fc",
        "font": {"color": "white"},
        "id": head,
        "label": head,
        "shape": "dot",
        "title": head_type,
    }


def _create_edge(head: str, tail: str, text: str) -> dict:
    # Add line breaks to text
    text_list = text.split(" ")
    for i in range(len(text_list)):
        if i > 0 and i % 5 == 0:
            text_list[i] = "<br>" + text_list[i]
    text = " ".join(text_list)
    return {
        "arrows": "to",
        "from": head,
        "to": tail,
        "title": text,
    }


def create_knowledge_graph(documents: list[dict]) -> tuple[list[dict], ...]:
    futures: list[Future] = []
    with ThreadPoolExecutor() as executor:
        for document in documents:
            future = executor.submit(generate_entity_relationship, document)
            futures.append(future)
    # Keep track of added nodes
    seen = set()
    nodes = []
    edges = []
    for future in as_completed(futures):
        try:
            entity_relationship = future.result()
            for item in entity_relationship:
                head = item["head"]
                tail = item["tail"]
                text = item["text"]
                # Add node if it hasn't been included in the graph
                if head not in seen:
                    nodes.append(_create_node(head, item["head_type"]))
                    seen.add(head)
                if tail not in seen:
                    nodes.append(_create_node(tail, item["tail_type"]))
                    seen.add(tail)
                # Add an edge between head and tail node
                edges.append(_create_edge(head, tail, text))
        except Exception as e:
            logger.error(e)

    return nodes, edges
