import os
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

def run_document_chatbot(file_path):
    if not os.path.exists(file_path):
        print(f" Error: {file_path} not found. Please create it first.")
        return

    # 1. Read document context once
    print(f"Ingesting document: {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        doc_context = f.read()

    # 2. Initialize local model via Ollama
    llm = ChatOllama(
        model="qwen2.5:3b",
        temperature=0.3, # Slightly higher than 0 for creative follow-up suggestions
        num_predict=512
    )

    # 3. Create System Prompt holding the permanent document context
    system_prompt = (
        "You are an interactive local AI Document Assistant. "
        "You have permanent access to the document text provided below.\n\n"
        "--- DOCUMENT START ---\n"
        f"{doc_context}\n"
        "--- DOCUMENT END ---\n\n"
        "INSTRUCTIONS:\n"
        "- Answer the user's questions using ONLY the document context above.\n"
        "- If the answer is not in the document, say 'I cannot find that in the document.'\n"
        "- CRITICAL: At the very end of your response, you MUST provide exactly 2 relevant, "
        "clickable-style 'Suggested Follow-up Questions' based on what was just discussed or hidden details in the doc. "
        "Format them as bullet points starting with '💡 Suggestion:'."
    )

    # 4. Set up chat prompt template with a placeholder for memory
    prompt_template = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}")
    ])

    # 5. Initialize Ephemeral Memory List (Keeps system RAM completely clean)
    chat_history = []



    print("\n Chatbot Initialized successfully!")
    print("🤖: Ask me anything about the document. Type 'exit' or 'quit' to stop.\n" + "="*60)

    # 6. Interactive Loop
    while True:
        try:
            user_input = input("\n👤 You: ")
            if user_input.lower() in ['exit', 'quit']:
                print(" Exiting agent chatbot. Baseline resources freed.")
                break
                
            if not user_input.strip():
                continue

            print("🧠 Thinking ...")

            # Format prompt with current history and new input
            formatted_prompt = prompt_template.format_messages(
                chat_history=chat_history,
                user_input=user_input
            )

            # Invoke the model
            ai_response = llm.invoke(formatted_prompt)
            
            # Print the response cleanly
            print(f"\n🤖 Agent:\n{ai_response.content}")
            print("="*60)

            # Append interactions to chat history to keep the conversation rolling
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=ai_response.content))

            # Optional: Trim memory window if conversation gets too long (saves your 8GB RAM)
            if len(chat_history) > 6: 
                chat_history = chat_history[-6:]

        except KeyboardInterrupt:
            print("\n👋 Session interrupted cleanly.")
            break

if __name__ == "__main__":
    # Point this to the sample_doc.txt we created earlier
    TARGET_DOC = "sample_doc.txt"
    run_document_chatbot(TARGET_DOC)