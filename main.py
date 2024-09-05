import logging
from concurrent.futures import as_completed, Future, ThreadPoolExecutor
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components
from jinja2 import Template

from llm import get_llm_response, generate_entity_relationship
from rag import Database
from scrape import scrape_tavily_results, tavily_search_results

st.set_page_config(page_title="reenactify", page_icon=":material/reply_all:")

st.title("ReEnactify")
st.write("Re-enact any historical event, figure or location")

init = {
    "session_id": uuid4().hex,
    "index": None,
    "session_type": None,
    "session_topic": None,
    "nodes": [],
    "edges": [],
    "knowledge_graph": False,
    "start": False,
    "db": Database(),
    "scraped": False,
    "messages": [],
}

selectbox_options = ("Event", "Person", "Place", "Time Period")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def selectbox_callback():
    st.session_state.session_type = st.session_state.selectbox
    st.session_state.index = selectbox_options.index(st.session_state.selectbox)


def topic_callback():
    st.session_state.session_topic = st.session_state.topic


def start_callback():
    st.session_state.start = True


def reset_callback():
    # Reset state variables to their default values
    for key, value in init.items():
        st.session_state[key] = value


def create_node(head: str, head_type: str):
    return {
        "color": "#97c2fc",
        "font": {"color": "white"},
        "id": head,
        "label": head,
        "shape": "dot",
        "title": head_type,
    }


def create_edge(head: str, tail: str, text: str):
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


# Create graph using Jinja2 and vis.js template
def create_knowledge_graph(documents: list[dict]):
    futures: list[Future] = []
    with ThreadPoolExecutor() as executor:
        for document in documents:
            future = executor.submit(generate_entity_relationship, document)
            futures.append(future)
    # Keep track of added nodes
    nodes = set()
    node_list = []
    edge_list = []
    for future in as_completed(futures):
        try:
            entity_relationship = future.result()
            for item in entity_relationship:
                head = item["head"]
                tail = item["tail"]
                text = item["text"]
                # Add node if it hasn't been included in the graph
                if head not in nodes:
                    node_list.append(create_node(head, item["head_type"]))
                    nodes.add(head)
                if tail not in nodes:
                    node_list.append(create_node(tail, item["tail_type"]))
                    nodes.add(tail)
                # Add an edge between head and tail node
                edge_list.append(create_edge(head, tail, text))
        except Exception as e:
            logger.error(e)

    st.session_state.nodes = node_list
    st.session_state.edges = edge_list


def initialize_sidebar():
    st.sidebar.text_input(
        f"Enter a {st.session_state.session_type}",
        st.session_state.session_topic,
        key="topic",
        on_change=topic_callback,
    )
    st.sidebar.checkbox(
        "Generate Knowledge Graph",
        key="knowledge_graph",
        value=st.session_state.knowledge_graph,
    )
    start, reset = st.sidebar.columns([1, 1])
    start.button("Start", use_container_width=True, on_click=start_callback)
    reset.button(
        "Reset",
        type="primary",
        on_click=reset_callback,
        use_container_width=True,
    )


def initialize_rag():
    with st.status("Creating assistant", expanded=True) as status:
        st.write("Searching resources")
        tavily_result = tavily_search_results(
            st.session_state.session_type,
            st.session_state.session_topic,
        )
        # Scrape websites and add to vector database
        st.write("Scraping data")
        documents = scrape_tavily_results(tavily_result)
        for document in documents:
            st.session_state.db.add(document)
        # Generate a knowledge graph
        if st.session_state.knowledge_graph:
            st.toast("Creating a knowledge graph might take some time")
            st.write("Creating knowledge graph")
            create_knowledge_graph(documents)

        status.update(label="Assistant created", state="complete")
        st.session_state.scraped = True


def render_knowledge_graph():
    if st.session_state.knowledge_graph:
        with open("template.html") as html:
            template = Template(html.read())
        rendered_html = template.render(
            nodes=st.session_state.nodes, edges=st.session_state.edges
        )
        components.html(rendered_html, height=500)


def chat(prompt: str):
    with st.chat_message("user"):
        st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        try:
            stream = get_llm_response(
                st.session_state.session_type,
                st.session_state.topic,
                st.session_state.messages[-1]["content"],
                st.session_state.db,
            )
            response = st.write_stream(stream)
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            logger.error(e)
            st.error("Unable to get assistant response, try again later")


# Initialize state variables
for key, value in init.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.sidebar.selectbox(
    "Type of Session",
    selectbox_options,
    index=st.session_state.index,
    key="selectbox",
    on_change=selectbox_callback,
)

if st.session_state.session_type:
    initialize_sidebar()
    # Clicked the start button without input topic
    if not st.session_state.session_topic and st.session_state.start:
        st.error(f"A {st.session_state.session_type} is required")

    if st.session_state.topic and st.session_state.start:
        # Do not scrape until session is reset
        if not st.session_state.scraped:
            initialize_rag()
        else:
            st.status("Assistant created", state="complete")

        if st.session_state.nodes and st.session_state.edges:
            render_knowledge_graph()
        # Display chat messages from history on app rerun
        # Streamlit reruns script top to bottom on each interaction
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input("Ask something")
        if prompt:
            chat(prompt)
