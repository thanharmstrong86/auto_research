import os
from dotenv import load_dotenv
from langchain_community.tools.google_trends import GoogleTrendsQueryRun
from langchain_community.utilities.google_trends import GoogleTrendsAPIWrapper
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from typing import TypedDict, List, Union
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

load_dotenv()

# === CONFIGURATION ===
SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY', '') 
keyword = "AI Agent"

# === SETUP WRAPPER AND TOOL ===
wrapper = GoogleTrendsAPIWrapper(serp_api_key=SERPAPI_API_KEY)
google_trends_tool = GoogleTrendsQueryRun(api_wrapper=wrapper)

# === STATE DEFINITION ===
class TrendState(TypedDict):
    messages: List[Union[HumanMessage, AIMessage, BaseMessage]]
    topics: List[str] 

# === TOOL NODE WITH OUTPUT WRAPPING ===
def tool_node_with_output(state: TrendState) -> TrendState:
    # Convert the raw dict into a LangChain HumanMessage (if not already)
    last_message = state["messages"][-1]
    if isinstance(last_message, dict):
        last_message = HumanMessage(**last_message)

    # Run the tool with the message content
    result = google_trends_tool.run(last_message.content)

    # Append an AIMessage with the result
    state["messages"].append(AIMessage(content=result))
    return state

# === GENERATING A STRUCTURED MESSAGE RESPONSE ===
def extract_topics_node(state: TrendState) -> TrendState:
    last_ai_message = state["messages"][-1]
    if isinstance(last_ai_message, dict):  # just in case
        last_ai_message = AIMessage(**last_ai_message)

    raw_text = last_ai_message.content
    rising_raw = extract_rising_queries(raw_text)
    cleaned_topics = remove_subtopics(rising_raw)
    
    # Add to state
    state["topics"] = cleaned_topics
    return state

def extract_rising_queries(text):
    rising_start = text.find("Rising Related Queries:")
    top_start = text.find("Top Related Queries:")
    if rising_start == -1 or top_start == -1:
        return []
    rising_text = text[rising_start + len("Rising Related Queries:"):top_start].strip()
    topics = [t.strip() for t in rising_text.split(",") if t.strip()]
    return topics

def remove_subtopics(topics):
    final = []
    for topic in topics:
        if all(existing.lower() not in topic.lower() and topic.lower() not in existing.lower() for existing in final):
            final.append(topic)
    return final

# === GRAPH FACTORY ===
def run_google_trends():
    graph = StateGraph(TrendState)
    graph.add_node("google_trends", tool_node_with_output)
    graph.add_node("extract_topics", extract_topics_node)  # 👈 new node
    
    graph.add_edge("google_trends", "extract_topics")
    graph.add_edge("extract_topics", END)
    graph.set_entry_point("google_trends")
    return graph.compile()

if __name__ == "__main__":
    # For local testing
    print(f"Searching Google Trends for: {keyword}")
    result = google_trends_tool.run(keyword)
    print("=== Raw Result ===")
    print(result)