__import__("pysqlite3")
import sys

sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

from uuid import uuid4

import streamlit as st
from streamlit_chromadb_connection.chromadb_connection import ChromadbConnection


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
