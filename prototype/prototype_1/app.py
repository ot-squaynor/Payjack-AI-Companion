# This script sets up a Gradio web interface for the Payjack AI Expert Assistant. It allows users to ask questions about Payjack and retrieves relevant context from a vector database to provide informed answers using a language model.
import gradio as gr
from pathlib import Path
from dotenv import load_dotenv
from ingest import fetch_documents, create_chunks, create_embeddings
#from visualize import visualize_vectorstore, vectorstore, metadatas, doc_types, colors
from answer import answer_question

load_dotenv(override=True)
directory_path ="prototype/test_vector_db"
# Color coding thresholds - Retrieval
def format_context(context):
    result = "<h2 style='color: #ff7800;'>Relevant Context</h2>\n\n"
    for doc in context:
        result += f"<span style='color: #ff7800;'>Source: {doc.metadata['source']}</span>\n\n"
        result += doc.page_content + "\n\n"
    return result

# Main function to handle the chat interaction
def chat(history):
    last_message = history[-1]["content"]
    prior = history[:-1]
    answer, context = answer_question(last_message, prior)
    history.append({"role": "assistant", "content": answer})
    return history, format_context(context)

# Main function to launch the Gradio interface
def main():
    path = Path(directory_path)

    if not path.exists():
        print("Directory does not exist")
        return
    else:
        print("Directory exists → checking if empty")
    

    # Check if directory is empty
    if any(path.iterdir()):
        print("Directory is NOT empty → running function")
    
    else:
        print("Directory is empty → running alternative")
        #ingestion steps - only run once to populate the vector database, then comment out for subsequent runs
        documents = fetch_documents()
        chunks = create_chunks(documents)
        create_embeddings(chunks)
        print("Ingestion complete")

    # # Visualization of the vector database
    # vectors, documents, metadatas, doc_types, colors = visualize_vectorstore(vectorstore)
    # print("vectors shape:", vectors.shape)
    # print("sample doc_type counts:", {t: doc_types.count(t) for t in set(doc_types)})

    def put_message_in_chatbot(message, history):
        return "", history + [{"role": "user", "content": message}]

    theme = gr.themes.Soft(font=["Inter", "system-ui", "sans-serif"])

    with gr.Blocks(title="Payjack AI Expert Assistant", theme=theme) as ui:
        gr.Markdown("# 🏢 Payjack AI Expert Assistant\nAsk me anything about Payjack!")

        with gr.Row():
            with gr.Column(scale=1):
                chatbot = gr.Chatbot(
                    label="💬 Conversation", height=600, type="messages", show_copy_button=True
                )
                message = gr.Textbox(
                    label="Your Question",
                    placeholder="Ask anything about Payjack...",
                    show_label=False,
                )

            with gr.Column(scale=1):
                context_markdown = gr.Markdown(
                    label="📚 Retrieved Context",
                    value="*Retrieved context will appear here*",
                    container=True,
                    height=600,
                )

        message.submit(
            put_message_in_chatbot, inputs=[message, chatbot], outputs=[message, chatbot]
        ).then(chat, inputs=chatbot, outputs=[chatbot, context_markdown])

    ui.launch(server_name="0.0.0.0", server_port=7860,
    share=True,
    inbrowser=False,
    show_error=True,)


if __name__ == "__main__":
    main()
