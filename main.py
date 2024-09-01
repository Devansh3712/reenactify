import logging

import streamlit as st

from llm import get_llm_response, Database
from scrape import scrape_tavily_results, tavily_search_results

st.set_page_config(page_title="reenactify", page_icon=":material/reply_all:")

st.title("ReEnactify")
st.write("Re-enact any historical event, figure or location")

init = {
    "index": None,
    "session_type": None,
    "session_topic": None,
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
    st.sidebar.text_input(
        f"Enter a {st.session_state.session_type}",
        st.session_state.session_topic,
        key="topic",
        on_change=topic_callback,
    )
    start, reset = st.sidebar.columns([1, 1])
    start.button("Start", use_container_width=True, on_click=start_callback)
    reset.button(
        "Reset",
        type="primary",
        on_click=reset_callback,
        use_container_width=True,
    )

    # Clicked the start button without input topic
    if not st.session_state.session_topic and st.session_state.start:
        st.error(f"A {st.session_state.session_type} is required")

    if st.session_state.topic and st.session_state.start:
        # Do not scrape until session is reset
        if not st.session_state.scraped:
            with st.status("Creating assistant", expanded=True) as status:
                st.write("Searching resources")
                try:
                    tavily_result = tavily_search_results(
                        st.session_state.session_type,
                        st.session_state.session_topic,
                    )
                    st.write("Scraping data")
                    documents = scrape_tavily_results(tavily_result)
                    for document in documents:
                        st.session_state.db.add(document)
                    status.update(label="Assistant created", state="complete")
                    st.session_state.scraped = True
                except Exception as e:
                    logger.error(e)
                    st.error("Unable to fetch resources right now, try again later")
        else:
            st.status("Assistant created", state="complete")

        # Display chat messages from history on app rerun
        # Streamlit reruns script top to bottom on each interaction
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input("Ask something")
        if prompt:
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
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response}
                    )
                except Exception as e:
                    logger.error(e)
                    st.error("Unable to get assistant response, try again later")
