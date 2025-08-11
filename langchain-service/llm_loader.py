import os
from langchain_community.llms import Ollama
from langchain.callbacks.base import BaseCallbackHandler


def to_int(value):
    return int(value) if value and value.isdigit() else None


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_llm(callback_handler=None):
    system_prompt = """
    You are a smart and helpful assistant. You should:
    ✅ Provide clear, direct, and complete answers to user questions.
    ✅ Avoid using prefixes like "Answer:", "AI:", or "Thinking...".
    ✅ Respond concisely and naturally to general knowledge, puzzles, logic problems, or natural language questions.
    ✅ Never mention or include system or tool instructions. Focus only on the question at hand.
    ✅ Do not use role-based or formatting prompts.

    Examples:

    User: What comes next in the sequence SCD, TEF, UGH?  
    → VJI

    User: Who is the President of France?  
    → Emmanuel Macron

    User: Write a short paragraph about grandmother  
    → A grandmother is the heart of a family, radiating warmth and sharing cherished stories. Her gentle embrace and patient listening create a bond that lasts through generations.
    """

    class MyLoggingHandler(BaseCallbackHandler):
        def on_llm_start(self, *args, **kwargs):
            print("\n=== LLM Request Log Start ===")

        def on_llm_end(self, *args, **kwargs):
            print("\n=== LLM Request Log End ===")

    return Ollama(
        base_url=os.getenv("OLLAMA_API_BASE"),
        model=os.getenv("MODEL_NAME"),
        temperature=to_float(os.getenv("TEMPERATURE", 0.7)),
        verbose=True,
        num_ctx=to_int(os.getenv("NUM_CTX")),
        num_gpu=to_int(os.getenv("NUM_GPU")),
        num_thread=to_int(os.getenv("NUM_THREAD")),
        system=os.getenv("SYSTEM",system_prompt),
        keep_alive=os.getenv("KEEP_ALIVE"),
        repeat_penalty=to_float(os.getenv("REPEAT_PENALTY")),
        template=os.getenv("TEMPLATE"),
        top_p = to_float(os.getenv("TOP_P")),
	    top_k = to_int(os.getenv("TOP_K")),
        callbacks=(
            [callback_handler, MyLoggingHandler()]
            if callback_handler
            else [MyLoggingHandler()]
        ),
    )
