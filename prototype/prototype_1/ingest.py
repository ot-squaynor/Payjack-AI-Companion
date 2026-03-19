# # This script ingests markdown documents from the knowledge base, creates chunks, generates embeddings, and stores them in a Chroma vector database.
# import os
# import glob
# import json
# from pathlib import Path
# from langchain_community.document_loaders import DirectoryLoader, TextLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_chroma import Chroma
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_openai import OpenAIEmbeddings


# from dotenv import load_dotenv

# # Load environment variables from .env file, with override to ensure latest values are used
# MODEL = "gpt-4.1-nano"

# DB_NAME = str(Path(__file__).parent.parent / "test_vector_db")
# KNOWLEDGE_BASE = str(Path(__file__).parent.parent / "knowledgebase")

# # embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# load_dotenv(override=True)

# embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

# # Number of top relevant documents to retrieve for each question
# def fetch_documents():
#     folders = glob.glob(str(Path(KNOWLEDGE_BASE) / "*"))
#     documents = []
#     for folder in folders:
#         doc_type = os.path.basename(folder)
#         # loader = DirectoryLoader(
#         #     folder, glob="**/*.json", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"}
#         # )

#         # patterns = ["**/*.md", "**/*.markdown", "**/*.csv", "**/*.json", "**/*.txt"]
#         # for pattern in patterns:
#         #     loader = DirectoryLoader(folder, glob=pattern, loader_cls=TextLoader, loader_kwargs={"encoding":"utf-8"})
#         #     folder_docs = loader.load()

#         # We can easily add support for more file types by updating the glob pattern and loader configuration.
#         loader = DirectoryLoader(
#             folder,
#             glob="**/*.{md,markdown,csv,json,txt}",
#             loader_cls=TextLoader,
#             loader_kwargs={"encoding": "utf-8"},
#         )

#         folder_docs = loader.load()
#         for doc in folder_docs:
#             doc.metadata["doc_type"] = doc_type
#             documents.append(doc)
#         if not documents:
#             raise RuntimeError(f"No documents found under {KNOWLEDGE_BASE}. Check your glob patterns and folder structure.")

#         if not chunks:
#             raise RuntimeError("No chunks created. Documents may be empty or loaders didn't load content.")
#     return documents

# # Create chunks of text from the documents, with overlap to preserve context
# def create_chunks(documents):
#     text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
#     chunks = text_splitter.split_documents(documents)
#     return chunks

# # Create embeddings for the chunks and store them in a Chroma vector database
# def create_embeddings(chunks):
#     if os.path.exists(DB_NAME):
#         Chroma(persist_directory=DB_NAME, embedding_function=embeddings).delete_collection()

#     vectorstore = Chroma.from_documents(
#         documents=chunks, embedding=embeddings, persist_directory=DB_NAME
#     )

#     collection = vectorstore._collection
#     count = collection.count()

#     sample_embedding = collection.get(limit=1, include=["embeddings"])["embeddings"][0]
#     dimensions = len(sample_embedding)
#     print(f"There are {count:,} vectors with {dimensions:,} dimensions in the vector store")
#     return vectorstore

# # Main function to run the ingestion process
# if __name__ == "__main__":
#     documents = fetch_documents()
#     chunks = create_chunks(documents)
#     create_embeddings(chunks)
#     print("Ingestion complete")

# This script ingests documents from the knowledge base, chunks them, generates embeddings,
# and stores them in a Chroma vector database.

import os
import glob
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
# from langchain_huggingface import HuggingFaceEmbeddings  # Optional alternative embeddings backend
from langchain_openai import OpenAIEmbeddings

# --- Config ---
# MODEL = "gpt-4.1-nano"  # Not used in ingestion; used later for chat/QA if you have a separate script.

DB_NAME = str(Path(__file__).parent.parent / "test_vector_db")
KNOWLEDGE_BASE = str(Path(__file__).parent.parent / "prototype_1/knowledgebase")
print(KNOWLEDGE_BASE)

load_dotenv(override=True)

# embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")  # Optional alternative
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")


def fetch_documents():
    """
    Loads supported file types from each top-level folder under KNOWLEDGE_BASE.
    Uses multiple glob patterns (more reliable on Windows than brace expansion).
    """
    folders = glob.glob(str(Path(KNOWLEDGE_BASE) / "*"))
    if not folders:
        raise RuntimeError(f"No folders found under {KNOWLEDGE_BASE}. Check the path.")

    patterns = ["**/*.md", "**/*.markdown", "**/*.csv", "**/*.json", "**/*.txt"]
    documents = []

    for folder in folders:
        doc_type = os.path.basename(folder)

        for pattern in patterns:
            loader = DirectoryLoader(
                folder,
                glob=pattern,
                loader_cls=TextLoader,
                loader_kwargs={"encoding": "utf-8"},
            )
            folder_docs = loader.load()
            documents = [d for d in documents if "placeholder" not in (d.metadata.get("source","").lower())]

            for doc in folder_docs:
                doc.metadata["doc_type"] = doc_type
                documents.append(doc)

    # Quick visibility for debugging
    print(f"Loaded {len(documents)} documents from: {KNOWLEDGE_BASE}")
    if documents:
        print("Example sources:", [d.metadata.get("source") for d in documents[:5]])

    if not documents:
        raise RuntimeError(
            f"No documents matched patterns {patterns} under {KNOWLEDGE_BASE}. "
            "Check folder structure, file extensions, and encoding."
        )

    return documents


def create_chunks(documents):
    """Splits documents into overlapping chunks for better retrieval."""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)

    print(f"Created {len(chunks)} chunks")
    if not chunks:
        raise RuntimeError(
            "No chunks created. Documents may be empty, unreadable, or loaders didn't load content."
        )

    return chunks


def create_embeddings(chunks):
    """Embeds chunks and stores them in a persistent Chroma vector DB."""
    if not chunks:
        raise RuntimeError("Chunks list is empty; refusing to create an empty vector store.")

    # Clear previous DB (simple approach for prototypes)
    if os.path.exists(DB_NAME):
        try:
            Chroma(persist_directory=DB_NAME, embedding_function=embeddings).delete_collection()
        except Exception:
            # If delete_collection fails (e.g., missing collection), just continue
            pass

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_NAME,
    )

    # Sanity checks / stats
    collection = vectorstore._collection
    count = collection.count()
    if count == 0:
        raise RuntimeError("Chroma collection count is 0 after upsert; nothing was stored.")

    sample = collection.get(limit=1, include=["embeddings"])
    sample_embedding = sample["embeddings"][0]
    dimensions = len(sample_embedding)

    print(f"There are {count:,} vectors with {dimensions:,} dimensions in the vector store")
    return vectorstore


if __name__ == "__main__":
    documents = fetch_documents()
    chunks = create_chunks(documents)
    create_embeddings(chunks)
    print("Ingestion complete")