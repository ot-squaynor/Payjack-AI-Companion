# from dotenv import load_dotenv

# from answer import answer_question
# from pathlib import Path
# from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# from langchain_chroma import Chroma
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_core.messages import SystemMessage, HumanMessage, convert_to_messages
# from langchain_core.documents import Document
# import numpy as np
# # from ingest import DB_NAME
# from ingest import *
# from ingest import DB_NAME, embeddings


# import os
# import glob
# from pathlib import Path

# from dotenv import load_dotenv
# from langchain_community.document_loaders import DirectoryLoader, TextLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_chroma import Chroma
# # from langchain_huggingface import HuggingFaceEmbeddings  # Optional alternative embeddings backend
# from langchain_openai import OpenAIEmbeddings

# vectorstore = Chroma(
#     persist_directory=DB_NAME,
#     embedding_function=embeddings
# )
# def visualize_vectorstore(vectorstore):
#     collection = vectorstore._collection
#     count = collection.count()

#     sample_embedding = collection.get(limit=1, include=["embeddings"])["embeddings"][0]
#     dimensions = len(sample_embedding)
#     print(f"There are {count:,} vectors with {dimensions:,} dimensions in the vector store")
    
#     # Get all stored vectors
#     result = collection.get(include=['embeddings', 'documents', 'metadatas'])
#     vectors = np.array(result['embeddings'])
#     documents = result['documents']
#     metadatas = result['metadatas']
#     doc_types = [metadata['doc_type'] for metadata in metadatas]
#     colors = [['blue', 'green', 'red', 'orange'][['products', 'employees', 'contracts', 'company'].index(t)] for t in doc_types]

# if __name__ == "__main__":
#     visualize_vectorstore(vectorstore)

# visualize.py
import os
import glob
import tiktoken
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sklearn.manifold import TSNE
import plotly.graph_objects as go
from dotenv import load_dotenv
import numpy as np

from langchain_chroma import Chroma
from ingest import DB_NAME, embeddings  # import ONLY what you need


load_dotenv(override=True)

# Load the existing vector database (created/persisted by ingest.py)
vectorstore = Chroma(
    persist_directory=DB_NAME,
    embedding_function=embeddings,
)


def visualize_vectorstore(vectorstore: Chroma):
    collection = vectorstore._collection
    count = collection.count()

    if count == 0:
        raise RuntimeError(
            f"Chroma collection is empty (0 vectors). Run ingest.py first. DB: {DB_NAME}"
        )

    sample = collection.get(limit=1, include=["embeddings"])
    if sample.get("embeddings") is None or len(sample["embeddings"]) == 0:
        raise RuntimeError("No embeddings returned for sample. Something is wrong with the stored collection.")

    dimensions = len(sample["embeddings"][0])
    print(f"There are {count:,} vectors with {dimensions:,} dimensions in the vector store")

    # Get all stored vectors
    result = collection.get(include=["embeddings", "documents", "metadatas"])

    # --- FIX: avoid `or []` with numpy arrays (ambiguous truth value) ---
    embeddings_list = result.get("embeddings")
    documents = result.get("documents")
    metadatas = result.get("metadatas")

    if embeddings_list is None:
        embeddings_list = []
    if documents is None:
        documents = []
    if metadatas is None:
        metadatas = []

    if len(embeddings_list) == 0:
        raise RuntimeError("No embeddings returned from Chroma. Collection may be empty or corrupted.")

    vectors = np.asarray(embeddings_list)

    # Safe doc_type extraction (won't crash if missing)
    doc_types = [
        (m.get("doc_type", "unknown") if isinstance(m, dict) else "unknown")
        for m in metadatas
    ]

    # Update palette to match YOUR knowledgebase folders
    palette = {
        "accounts": "blue",
        "errors": "red",
        "features": "green",
        "fees": "orange",
        "help_center": "purple",
        "limits": "brown",
        "metadata": "gray",
        "products": "pink",
        "transactions": "black",
    }
    colors = [palette.get(t, "gray") for t in doc_types]

    # t-SNE reduction to 2D
    tsne = TSNE(
        n_components=2,
        random_state=42,
        init="pca",
        learning_rate="auto",
        perplexity=min(30, max(5, (len(vectors) - 1) // 3)),  # safer for small/large sets
    )
    reduced_vectors = tsne.fit_transform(vectors)

    # Create the 2D scatter plot
    hover_text = [
        f"Type: {t}<br>Source: {m.get('source','')}<br>Text: {d[:200]}..."
        for t, d, m in zip(doc_types, documents, metadatas)
    ]

    fig = go.Figure(
        data=[
            go.Scatter(
                x=reduced_vectors[:, 0],
                y=reduced_vectors[:, 1],
                mode="markers",
                marker=dict(size=5, color=colors, opacity=0.8),
                text=hover_text,
                hoverinfo="text",
            )
        ]
    )

    fig.update_layout(
        title="2D Chroma Vector Store Visualization (t-SNE)",
        xaxis_title="x",
        yaxis_title="y",
        width=900,
        height=650,
        margin=dict(r=20, b=10, l=10, t=40),
    )

    fig.show()
    return vectors, documents, metadatas, doc_types, colors


if __name__ == "__main__":
    vectors, documents, metadatas, doc_types, colors = visualize_vectorstore(vectorstore)
    print("vectors shape:", vectors.shape)
    print("sample doc_type counts:", {t: doc_types.count(t) for t in set(doc_types)})
    #pmfeoni