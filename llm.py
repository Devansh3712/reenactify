import json
import os

import streamlit as st
import google.generativeai as genai
from groq import Groq

from rag import Database
from schemas import GraphNode

genai.configure(api_key=st.secrets.GEMINI_API_KEY)
current_directory = os.path.dirname(os.path.realpath(__file__))
prompts_directory = os.path.join(current_directory, "prompts")


def get_llm_response(session_type: str, topic: str, prompt: str, db: Database):
    with open(os.path.join(prompts_directory, "historian.txt")) as infile:
        system = infile.read()
    system = system.format(
        session_type=session_type, topic=topic, rag=db.get(topic, prompt)
    )

    client = Groq(api_key=st.secrets.GROQ_API_KEY)
    stream = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        model="llama3-70b-8192",
        stream=True,
    )
    for chunk in stream:
        data = chunk.choices[0].delta.content
        if data:
            yield data


def generate_entity_relationship(document: str):
    with open(os.path.join(prompts_directory, "entity_relationship.txt")) as infile:
        prompt = infile.read()
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": list[GraphNode],
        },
    )
    chat = model.start_chat(
        history=[
            {"role": "model", "parts": prompt},
        ]
    )
    response = chat.send_message(document)
    data = json.loads(response.text)
    return data
