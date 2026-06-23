from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.models.google import Gemini
from agno.tools.duckduckgo import DuckDuckGoTools


def get_rag_agent(model_version: str):
    """Build the reasoning agent for local RAG responses."""
    return Agent(
        name="DeepSeek RAG Agent",
        model=Ollama(id=model_version),
        instructions="Answer using the most relevant available information.",
        markdown=True,
    )


def get_web_search_agent():
    """Build the fallback web search agent."""
    return Agent(
        name="Web Search Agent",
        model=Gemini(id="gemini-2.0-flash-exp"),
        tools=[DuckDuckGoTools()],
        instructions="Search the web using DuckDuckGo and summarize key points.",
        markdown=True,
    )
