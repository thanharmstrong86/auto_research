import os
import re
import csv
from dotenv import load_dotenv
from langchain_community.tools.google_trends.tool import GoogleTrendsQueryRun
from langchain_community.utilities.google_trends import GoogleTrendsAPIWrapper
from langgraph.prebuilt import ToolNode

load_dotenv()

# === CONFIGURATION ===
SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY', '') 
keyword = "AI Agent"
filename = "trend.csv"

# === SETUP WRAPPER AND TOOL ===
wrapper = GoogleTrendsAPIWrapper(serp_api_key=SERPAPI_API_KEY)
google_trends_tool = GoogleTrendsQueryRun(api_wrapper=wrapper)

# === DEFINE TOOL NODE ===
tools = [google_trends_tool]
run_google_trends = ToolNode(tools)

# === RUN GOOGLE TRENDS QUERY ===
print(f"Searching Google Trends for: {keyword}")
result = google_trends_tool.run(keyword)
print("=== Raw Result ===")
print(result)

# === EXTRACT AND CLEAN RISING RELATED QUERIES ===
def extract_rising_queries(text):
    rising_start = text.find("Rising Related Queries:")
    top_start = text.find("Top Related Queries:")
    if rising_start == -1 or top_start == -1:
        return []
    rising_text = text[rising_start + len("Rising Related Queries:"):top_start].strip()
    topics = [t.strip() for t in rising_text.split(",") if t.strip()]
    return topics

def remove_subtopics(topics):
    """Keep only most specific topics in their original order, removing ones that are substrings of already kept topics."""
    final = []
    for topic in topics:  # Iterate in original order
        if all(existing.lower() not in topic.lower() and topic.lower() not in existing.lower() for existing in final):
            final.append(topic)
    return final

rising_topics_raw = extract_rising_queries(result)
rising_topics = remove_subtopics(rising_topics_raw)
print("\n🎯 Filtered Unique Topics (no sub-phrases):")
print(rising_topics[:10])

if not rising_topics:
    print("❌ No unique rising topics found.")
    exit()

# === CHECK EXISTING CSV FILE ===
def topic_exists(topic, file_path):
    if not os.path.exists(file_path):
        return False
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['topic'].strip().lower() == topic.lower():
                return True
    return False

# === SAVE MULTIPLE NON-DUPLICATE TOPICS ===
def save_topic(topic, file_path):
    file_exists = os.path.exists(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["topic", "status"])
        writer.writerow([topic, "0"])

filename = "trend.csv"
saved_count = 0
for topic in rising_topics:
    if not topic_exists(topic, filename):
        save_topic(topic, filename)
        print(f"✅ Saved new trending topic: {topic}")
        saved_count += 1
    if saved_count == 3:
        break

if saved_count == 0:
    print("⚠️ All top filtered topics already saved. No new topics added.")
else:
    print(f"🎉 Saved {saved_count} new topic(s).")