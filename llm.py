__import__("pysqlite3")
import sys

# Required by streamlit community cloud
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

import os
from uuid import uuid4

import streamlit as st
from groq import Groq
from streamlit_chromadb_connection.chromadb_connection import ChromadbConnection


current_directory = os.path.dirname(os.path.realpath(__file__))


class Database:
    def __init__(self) -> None:
        self.conn = st.connection(
            name="persistent_connection",
            type=ChromadbConnection,
            **{"client": "PersistentClient", "path": "/tmp"}
        )
        self.collection = "reenactify"
        self.embedding_function = "DefaultEmbeddingFunction"
        try:
            self.conn.create_collection(
                collection_name=self.collection,
                embedding_function_name=self.embedding_function,
                embedding_config={},
                metadata={"hnsw:space": "cosine"},
            )
        # Collection already exists
        except:
            pass

    def add(self, document: str):
        chunks = []
        # TODO: Use a better chunking strategy
        for i in range(0, len(document), 2500):
            chunk = document[i : i + 2500]
            chunks.append(chunk)

        self.conn.upload_documents(
            collection_name=self.collection,
            documents=chunks,
            embedding_function_name=self.embedding_function,
            ids=[uuid4().hex for _ in range(len(chunks))],
            metadatas=[{"chunk": i} for i in range(len(chunks))],
        )

    def get(self, topic: str, query: str):
        df = self.conn.query(
            collection_name=self.collection,
            query=[topic, query],
            attributes=["documents"],
            num_results_limit=2,
        )
        return df.documents.to_list()


def get_llm_response(session_type: str, topic: str, prompt: str, db: Database):
    with open(os.path.join(current_directory, "prompt.txt")) as infile:
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
