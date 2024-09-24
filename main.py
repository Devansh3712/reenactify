import logging
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components
from jinja2 import Template
from pypdf import PdfReader

from knowledge_graph import create_knowledge_graph
from llm import get_llm_response
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

selectbox_options = ("Event", "Person", "Place", "Time Period", "PDF Chat")

# Use structured logging
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
        help="A knowledge graph is an organized representaton of entities and "
        "their relationships",
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
            st.session_state.nodes, st.session_state.edges = create_knowledge_graph(
                documents
            )

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


# Initialize state variables whose values are not set
for key, value in init.items():
    # On rerun, only set values for keys which have
    # not been used yet
    if key not in st.session_state:
        st.session_state[key] = value

st.sidebar.selectbox(
    "Type of Session",
    selectbox_options,
    index=st.session_state.index,
    key="selectbox",
    on_change=selectbox_callback,
)

if st.session_state.session_type == "PDF Chat":
    st.sidebar.file_uploader("Choose a file", type=["pdf"], key="pdf")
    if st.session_state.pdf:
        reader = PdfReader(st.session_state.pdf)
        num_pages = reader.get_num_pages()
        for i in range(num_pages):
            page = reader.pages[i]
            text = page.extract_text()
else:
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
