import os
import requests
from bs4 import BeautifulSoup
from waybackpy import Url
import datetime
import time
from urllib.parse import urljoin, urlparse
import logging
import re

# Setup logging
documents_path = os.path.join(os.path.expanduser("~"), "Documents", "rf")
output_file = os.path.join(documents_path, "dei_changes_detailed.txt")
log_file = os.path.join(documents_path, "debug.log")

# Ensure the rf directory exists
os.makedirs(documents_path, exist_ok=True)

logging.basicConfig(filename=log_file, level=logging.DEBUG, format="%(asctime)s - %(message)s")

def log_message(msg):
    print(msg)  # Show in CMD
    logging.debug(msg)  # Save to log

log_message("Script execution started...")

# List of URLs to scan
rfbc_urls = [
    "https://www.appalachiarfbc.org/",
    "https://deltarfbc.org/",
    "https://www.canr.msu.edu/GLM-RFBC/",
    "https://heartlandfoodbusiness.org/",
    "https://www.indianag.org/intertribalfbc",
    "https://www.islandsandremoteareasrfbc.com/",
    "https://www.northcentralrfbc.org/",
    "https://www.nasda.org/nasda-foundation/northeast-regional-food-business-center/",
    "https://nwrockymountainregionalfoodbusiness.com/",
    "https://rgcolonias.org/",
    "https://southeastrfbc.org/",
    "https://swfoodbiz.org/"
]

# Keywords to search for
dei_keywords = ["equitable", "inclusive", "inclusion", "underinvested", "underserved", "diversity", "minority", "BIPOC", "DEI"]

# Function to get page content
def get_page_content(url):
    try:
        log_message(f"Fetching {url}...")
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        text = soup.get_text().lower()
        paragraphs = [p.get_text().strip() for p in soup.find_all('p')] or [block.strip() for block in text.split('\n\n') if block.strip()]
        return text, paragraphs, soup
    except Exception as e:
        log_message(f"ERROR fetching {url}: {e}")
        return "", [], None

# Crawl site for links
def crawl_site(base_url, max_depth=2, current_depth=0, visited=None):
    if visited is None:
        visited = set()

    if current_depth > max_depth or base_url in visited:
        return visited

    visited.add(base_url)
    log_message(f"Crawling {base_url} (depth {current_depth})")

    _, _, soup = get_page_content(base_url)
    if not soup:
        return visited

    for anchor in soup.find_all('a', href=True):
        link = urljoin(base_url, anchor['href'])
        parsed = urlparse(link)
        if parsed.netloc == urlparse(base_url).netloc and link not in visited:
            visited.add(link)
            visited.update(crawl_site(link, max_depth, current_depth + 1, visited))

    return visited

# Get archived content
def get_archived_content(url, target_date):
    try:
        log_message(f"Fetching archive for {url}...")
        wayback = Url(url, "Mozilla/5.0")
        archived = wayback.near(year=target_date.year, month=target_date.month, day=target_date.day)

        if not archived.archive_url:
            archived = wayback.newest(after=target_date.strftime("%Y%m%d%H%M%S"))
            if not archived.archive_url:
                log_message(f"No archive available for {url}.")
                return "", [], None

        log_message(f"Archive found at {archived.archive_url}")
        response = requests.get(archived.archive_url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        text = soup.get_text().lower()
        paragraphs = [p.get_text().strip() for p in soup.find_all('p')] or [block.strip() for block in text.split('\n\n') if block.strip()]
        return text, paragraphs, archived.archive_url
    except Exception as e:
        log_message(f"ERROR fetching archive: {e}")
        return "", [], None

# Function to find removed keywords and context
def find_removed_keywords_with_context(current_text, archived_text, url, keywords):
    removed_changes = []
    archived_sentences = re.split(r'(?<=[.!?])\s+', archived_text)

    for keyword in keywords:
        if keyword in archived_text and keyword not in current_text:
            # Find keyword in archived text
            for sentence in archived_sentences:
                if keyword in sentence:
                    words = sentence.split()
                    if keyword in words:
                        index = words.index(keyword)
                        
                        # Extract five words before and after
                        start = max(index - 5, 0)
                        end = min(index + 6, len(words))
                        context = " ".join(words[start:end])

                        removed_changes.append({
                            "url": url,
                            "keyword": keyword,
                            "context": context,
                            "archive_url": archive_url
                        })
    
    return removed_changes

# Write results to file
def write_to_file(text):
    try:
        log_message(f"Writing results to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)
        log_message("Results successfully written.")
    except Exception as e:
        log_message(f"ERROR writing file: {e}")

# Main process
target_date = datetime.datetime(2024, 10, 1)
results = []
removed_word_count = 0

log_message("Starting main loop...")
for base_url in rfbc_urls:
    log_message(f"Processing {base_url}...")
    all_pages = crawl_site(base_url, max_depth=2)

    for url in all_pages:
        log_message(f"Checking {url}...")
        current_text, _, _ = get_page_content(url)
        archived_text, _, archive_url = get_archived_content(url, target_date)

        if current_text and archived_text:
            changes = find_removed_keywords_with_context(current_text, archived_text, url, dei_keywords)
            results.extend(changes)
            removed_word_count += len(changes)

        time.sleep(1)

# Format and save results
log_message(f"Processing complete. Found {len(results)} changes.")
output_text = "DEI Language Removals Report\n\n"

if results:
    for result in results:
        output_text += f"URL: {result['url']}\n"
        output_text += f"Keyword Removed: {result['keyword']}\n"
        output_text += f"Wayback URL: {result['archive_url']}\n"
        output_text += f"Context: {result['context']}\n\n"

    output_text += f"Total Number of Removed Keywords: {removed_word_count}\n"
else:
    output_text += "No changes detected.\n"

write_to_file(output_text)

log_message("Script finished. Check dei_changes_detailed.txt in the rf directory under Documents.")