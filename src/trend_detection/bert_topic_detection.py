import requests
from bs4 import BeautifulSoup
import pandas as pd
from bertopic import BERTopic
import re
from datetime import datetime
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP
import logging

# Configure logging
logging.basicConfig(
    filename='topic_detection.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants
HACKER_NEWS_URL = 'https://news.ycombinator.com'
OUTPUT_FILE = 'topics.csv'

# Function to scrape Hacker News
def scrape_hacker_news():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(HACKER_NEWS_URL, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        posts = []
        for post in soup.find_all('tr', class_='athing')[:15]:
            title_elem = post.find('span', class_='titleline')
            title = title_elem.find('a').text.strip() if title_elem else ''
            link = title_elem.find('a')['href'] if title_elem else ''
            
            subline = post.find_next_sibling('tr')
            score_elem = subline.find('span', class_='score') if subline else None
            score = int(score_elem.text.replace(' points', '')) if score_elem else 0
            
            comments_elem = subline.find('a', string=re.compile(r'\d+\s*comment')) if subline else None
            comments = int(re.search(r'\d+', comments_elem.text).group()) if comments_elem else 0
            
            if score > 50 or comments > 20:
                posts.append({'title': title, 'link': link, 'score': score, 'comments': comments})
        
        logging.info(f"Scraped {len(posts)} posts: {[p['title'] for p in posts]}")
        print(f"Scraped {len(posts)} posts")
        return posts
    except Exception as e:
        logging.error(f"Error scraping Hacker News: {e}")
        print(f"Error scraping Hacker News: {e}")
        return []

# Function to read existing topics from CSV
def get_existing_topics():
    try:
        if pd.io.common.file_exists(OUTPUT_FILE):
            df = pd.read_csv(OUTPUT_FILE)
            if 'topic' in df.columns:
                return set(df['topic'].str.lower())
        return set()
    except Exception as e:
        logging.error(f"Error reading {OUTPUT_FILE}: {e}")
        print(f"Error reading {OUTPUT_FILE}: {e}")
        return set()

# Function to extract top unique topic
def extract_top_topic(posts):
    if not posts:
        return None
    
    documents = [post['title'] for post in posts]
    existing_topics = get_existing_topics()
    
    # Custom stop words and minimum topic length
    stop_words = set(['mcp', 'show', 'new', 'get', 'use', 'one'])  # Add uninformative words
    min_topic_length = 3  # Minimum characters for a topic
    
    if len(documents) < 5:  # Fallback for small datasets
        try:
            vectorizer = CountVectorizer(
                stop_words=list(stop_words.union({'english'})),
                ngram_range=(1, 2),  # Include unigrams and bigrams
                min_df=1
            )
            word_counts = vectorizer.fit_transform(documents)
            feature_names = vectorizer.get_feature_names_out()
            word_sums = word_counts.sum(axis=0).A1
            word_freq = sorted(
                [(feature_names[i], word_sums[i]) for i in range(len(feature_names))],
                key=lambda x: x[1], reverse=True
            )
            logging.info(f"Fallback word frequencies: {word_freq}")
            
            # Pick first valid topic
            for word, freq in word_freq:
                if (word.lower() not in existing_topics and
                    len(word) >= min_topic_length and
                    word not in stop_words):
                    logging.info(f"Selected fallback topic: {word} (freq: {freq})")
                    return word.replace('_', ' ')  # Replace underscores with spaces
            logging.warning("No unique, valid topics found in fallback")
            print("No unique topics found in fallback")
            return None
        except Exception as e:
            logging.error(f"Fallback error: {e}")
            print(f"Fallback error: {e}")
            return None
    
    try:
        # Custom vectorizer for BERTopic to generate descriptive topics
        vectorizer = CountVectorizer(
            stop_words='english',
            ngram_range=(1, 3),  # Allow unigrams, bigrams, trigrams
            min_df=1
        )
        topic_model = BERTopic(
            language="english",
            min_topic_size=2,
            nr_topics=5,
            embedding_model="all-MiniLM-L6-v2",
            umap_model=UMAP(n_components=2, n_neighbors=max(3, len(documents)-1)),
            vectorizer_model=vectorizer,  # Use custom vectorizer
            verbose=True
        )
        
        topics, _ = topic_model.fit_transform(documents)
        topic_info = topic_model.get_topic_info()
        logging.info(f"BERTopic output: {topic_info.to_dict()}")
        
        # Sort by count, exclude outlier topic (-1)
        sorted_topics = topic_info[topic_info['Topic'] != -1].sort_values('Count', ascending=False)
        
        for _, row in sorted_topics.iterrows():
            topic_name = row['Representation'][0]  # Use top term from Representation
            if (topic_name.lower() not in existing_topics and
                len(topic_name) >= min_topic_length and
                topic_name not in stop_words):
                logging.info(f"Selected BERTopic topic: {topic_name} (count: {row['Count']})")
                return topic_name.replace('_', ' ')
        
        logging.warning("No unique, valid topics found")
        print("No unique topics found")
        return None
    except Exception as e:
        logging.error(f"Error extracting topic: {e}")
        print(f"Error extracting topic: {e}")
        # Fallback
        try:
            vectorizer = CountVectorizer(
                stop_words=list(stop_words.union({'english'})),
                ngram_range=(1, 2),
                min_df=1
            )
            word_counts = vectorizer.fit_transform(documents)
            feature_names = vectorizer.get_feature_names_out()
            word_sums = word_counts.sum(axis=0).A1
            word_freq = sorted(
                [(feature_names[i], word_sums[i]) for i in range(len(feature_names))],
                key=lambda x: x[1], reverse=True
            )
            logging.info(f"Fallback word frequencies: {word_freq}")
            
            for word, freq in word_freq:
                if (word.lower() not in existing_topics and
                    len(word) >= min_topic_length and
                    word not in stop_words):
                    logging.info(f"Selected fallback topic: {word} (freq: {freq})")
                    return word.replace('_', ' ')
            logging.warning("No unique, valid topics found in fallback")
            print("No unique topics found in fallback")
            return None
        except Exception as e:
            logging.error(f"Fallback error: {e}")
            print(f"Fallback error: {e}")
            return None

# Function to save topic to CSV
def save_topic_to_file(topic):
    if not topic:
        print("No topic to save")
        return
    
    data = {'topic': [topic], 'status': [0]}  # Status 0 for INIT
    df = pd.DataFrame(data)
    
    try:
        df.to_csv(OUTPUT_FILE, mode='a', header=not pd.io.common.file_exists(OUTPUT_FILE), index=False)
        logging.info(f"Saved topic to {OUTPUT_FILE}: {topic}, status: 0")
        print(f"Topic saved to {OUTPUT_FILE}")
    except Exception as e:
        logging.error(f"Error saving to file: {e}")
        print(f"Error saving to file: {e}")

# Main function
def main():
    posts = scrape_hacker_news()
    if not posts:
        print("No posts retrieved")
        return
    
    top_topic = extract_top_topic(posts)
    if not top_topic:
        print("No topic extracted")
        return
    
    save_topic_to_file(top_topic)

if __name__ == '__main__':
    main()