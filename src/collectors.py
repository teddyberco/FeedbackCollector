import praw
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta 
import logging
from typing import List, Dict, Any, Tuple 
from textblob import TextBlob
import json
import xml.etree.ElementTree as ET
import re 
import time 
import config 
from utils import generate_feedback_gist, categorize_feedback 

logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)

def analyze_sentiment(text: str) -> str:
    blob = TextBlob(text)
    score = blob.sentiment.polarity
    if score < -0.1: return "Negative"
    if score > 0.1: return "Positive"
    return "Neutral"

class RedditCollector:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=config.REDDIT_CLIENT_ID,
            client_secret=config.REDDIT_CLIENT_SECRET,
            user_agent=config.REDDIT_USER_AGENT
        )
        
    def collect(self) -> List[Dict[str, Any]]:
        feedback_items = []
        try:
            logger.info(f"Collecting feedback from Reddit subreddit: {config.REDDIT_SUBREDDIT}")
            logger.info(f"Using keywords for search: {config.KEYWORDS}") 
            subreddit = self.reddit.subreddit(config.REDDIT_SUBREDDIT)
            
            search_query = " OR ".join([f'"{k}"' for k in config.KEYWORDS])
            logger.info(f"Reddit search query: {search_query}")

            submissions_generator = subreddit.search(search_query, sort="new", limit=config.MAX_ITEMS_PER_RUN)
            
            count = 0
            for submission in submissions_generator:
                if count >= config.MAX_ITEMS_PER_RUN:
                    logger.info(f"Reached MAX_ITEMS_PER_RUN ({config.MAX_ITEMS_PER_RUN}) for Reddit submissions.")
                    break
                
                logger.info(f"Processing submission via search: {submission.title}")
                reddit_url = f"https://www.reddit.com{submission.permalink}"
                full_feedback_text = f"{submission.title}\n\n{submission.selftext}"
                
                tag_value = self._extract_flair(submission)

                feedback_items.append({
                    'Feedback_Gist': generate_feedback_gist(full_feedback_text),
                    'Feedback': full_feedback_text,
                    'Url': reddit_url,
                    'Area': 'Workloads', 
                    'Sources': 'Reddit',
                    'Impacttype': self._determine_impact_type_content(submission.title + " " + submission.selftext),
                    'Scenario': 'Customer',
                    'Customer': str(submission.author) if submission.author else "N/A",
                    'Tag': tag_value, 
                    'Created': datetime.fromtimestamp(submission.created_utc).isoformat(),
                    'Organization': f'Reddit/{config.REDDIT_SUBREDDIT}',
                    'Status': config.DEFAULT_STATUS,
                    'Created_by': config.SYSTEM_USER,
                    'Rawfeedback': f"Source URL: {reddit_url}\nRaw Data: {str(vars(submission))}",
                    'Sentiment': analyze_sentiment(full_feedback_text),
                    'Category': categorize_feedback(full_feedback_text)
                })
                count += 1
            
            logger.info(f"Collected {len(feedback_items)} feedback items from Reddit")
            return feedback_items[:config.MAX_ITEMS_PER_RUN] 
            
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg:
                logger.error("\nReddit authentication failed. Please check your credentials.")
            else:
                logger.error(f"Error collecting Reddit feedback: {error_msg}", exc_info=True)
            return []

    def _determine_impact_type_content(self, content: str) -> str: 
        content_lower = content.lower()
        if any(word in content_lower for word in ['error', 'bug', 'issue', 'problem']): return 'Bug'
        if any(word in content_lower for word in ['suggest', 'feature', 'improve']): return 'Feature Request'
        if any(word in content_lower for word in ['help', 'how to', 'question']): return 'Question'
        return 'Feedback'

    def _extract_flair(self, item) -> str:
        try:
            if hasattr(item, 'link_flair_richtext') and item.link_flair_richtext:
                flair_text = [flair['t'] for flair in item.link_flair_richtext if flair.get('e') == 'text' and flair.get('t')]
                return ', '.join(flair_text)
            if hasattr(item, 'link_flair_text') and item.link_flair_text:
                return item.link_flair_text
            return ''
        except Exception:
            return ''

class FabricCommunityCollector:
    def __init__(self):
        self.source_name = "Fabric Community"
        self.search_base_url = "https://community.fabric.microsoft.com/t5/forums/searchpage/tab/message"
        self.max_items_to_fetch = config.MAX_ITEMS_PER_RUN 
        self.search_page_size = 50 
        self.session = requests.Session()
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
    def collect(self) -> List[Dict[str, Any]]: 
        feedback_items = []
        keywords_to_use = config.KEYWORDS 
        
        if not keywords_to_use:
            logger.warning(f"{self.source_name}: No keywords configured, skipping collection. This collector requires keywords for searching.")
            return []

        query_string = " OR ".join([f'"{keyword}"' for keyword in keywords_to_use])
        
        logger.info(f"Starting {self.source_name} HTML search for keywords: {keywords_to_use}")
        logger.info(f"Query string for search: {query_string}")

        num_pages_to_scrape = (self.max_items_to_fetch + self.search_page_size - 1) // self.search_page_size
        num_pages_to_scrape = min(num_pages_to_scrape, 5) 
        logger.info(f"Pages to scrape (max 5): {num_pages_to_scrape}")

        for page_num in range(1, num_pages_to_scrape + 1):
            if len(feedback_items) >= self.max_items_to_fetch:
                logger.info(f"Reached MAX_ITEMS_PER_RUN ({self.max_items_to_fetch}). Stopping collection.")
                break
            
            params = {
                'filter': 'location', 'q': query_string, 'noSynonym': 'false', 'advanced': 'true',
                'location': 'forum-board:ac_generaldiscussion', 'collapse_discussion': 'true',
                'search_type': 'thread', 'search_page_size': str(self.search_page_size), 'page': str(page_num) 
            }
            current_url = f"{self.search_base_url}?{requests.compat.urlencode(params)}"
            logger.info(f"Scraping search results page {page_num}: {current_url}")

            try:
                response = self.session.get(self.search_base_url, params=params, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                search_results_items = soup.select('div.lia-message-view-message-search-item') 

                if not search_results_items:
                    logger.info(f"No search result items found on page {page_num} using selector 'div.lia-message-view-message-search-item'.")
                    break 

                logger.info(f"Found {len(search_results_items)} potential search result items on page {page_num}.")

                for item_element in search_results_items:
                    if len(feedback_items) >= self.max_items_to_fetch: break

                    title_tag = item_element.select_one('h2.message-subject a.page-link.lia-link-navigation')
                    author_tag = item_element.select_one('span.lia-message-byline a.lia-user-name-link')
                    
                    date_span = item_element.select_one('div.lia-message-post-date span.local-date')
                    time_span = item_element.select_one('div.lia-message-post-date span.local-time')
                    
                    body_container_tag = item_element.select_one('div.lia-truncated-body-container') # New selector for body
                    
                    date_str_combined = None
                    if date_span and time_span:
                        raw_date_text = date_span.get_text(strip=True) if date_span else ""
                        raw_time_text = time_span.get_text(strip=True) if time_span else ""
                        
                        # Aggressively clean date and time parts individually using regex
                        date_match = re.search(r'([\d\-]+)', raw_date_text)
                        time_match = re.search(r'([\d\s:/APMampm]+)', raw_time_text) # Allow space in time
                        
                        date_text_cleaned = date_match.group(1).strip() if date_match else ""
                        time_text_cleaned = time_match.group(1).strip() if time_match else ""
                        
                        if date_text_cleaned and time_text_cleaned:
                            date_str_combined = f"{date_text_cleaned} {time_text_cleaned}"
                            logger.debug(f"Cleaned combined date/time: '{date_str_combined}' from raw '{raw_date_text} {raw_time_text}'")
                        elif date_text_cleaned: # Case where only date_span might exist
                             date_str_combined = date_text_cleaned
                             logger.debug(f"Cleaned date only: '{date_str_combined}' from raw '{raw_date_text}'")
                        else:
                            date_str_combined = None # Will trigger fallback in _parse_community_date
                            logger.warning(f"Could not reliably extract date/time from raw: '{raw_date_text} {raw_time_text}'")
                            
                    elif date_span: # This case might be redundant now but kept for safety if only date_span exists without time_span initially
                        raw_date_text_only = date_span.get_text(strip=True)
                        date_match_only = re.search(r'([\d\-]+)', raw_date_text_only)
                        date_str_combined = date_match_only.group(1).strip() if date_match_only else None
                        logger.debug(f"Cleaned date only (elif branch): '{date_str_combined}' from raw '{raw_date_text_only}'")


                    labels_list_container = item_element.select_one('div.LabelsList')
                    tag_texts = []
                    if labels_list_container:
                        label_links = labels_list_container.select('li.label a.label-link')
                        for link in label_links:
                            tag_texts.append(link.get_text(strip=True).replace('', '')) 
                    tag_value = ", ".join(tag_texts)

                    if title_tag and title_tag.has_attr('href'):
                        title = title_tag.get_text(strip=True)
                        thread_url_path = title_tag['href']
                        base_community_url = "https://community.fabric.microsoft.com" 
                        thread_url = requests.compat.urljoin(base_community_url, thread_url_path)
                        author_name = author_tag.get_text(strip=True) if author_tag else "Unknown Author"
                        created_utc = self._parse_community_date(date_str_combined) 
                        
                        feedback_text = title # Default feedback text
                        if body_container_tag:
                            extracted_body_text = body_container_tag.get_text(strip=True)
                            if extracted_body_text: # Use body if found and not empty
                                feedback_text = extracted_body_text
                        
                        gist = generate_feedback_gist(feedback_text) # Generate gist from new feedback_text
                        
                        raw_feedback_data = {
                            "title": title, "author": author_name, "parsed_date_str": date_str_combined,
                            "search_page_num_scraped": page_num, "url_path": thread_url_path, "extracted_tags": tag_texts,
                            "body_preview_used": bool(body_container_tag and body_container_tag.get_text(strip=True))
                        }
                        
                        feedback_items.append({
                            'Feedback_Gist': gist, 'Feedback': feedback_text, 'Url': thread_url,
                            'Area': 'Fabric Platform Search', 'Sources': self.source_name,
                            'Impacttype': self._determine_impact_type_content(title + " " + feedback_text), # Use title + feedback for impact
                            'Scenario': 'Customer', 'Customer': author_name,
                            'Tag': tag_value, 
                            'Created': created_utc.isoformat(),
                            'Organization': 'Microsoft Fabric Community', 'Status': config.DEFAULT_STATUS,
                            'Created_by': config.SYSTEM_USER, 'Rawfeedback': json.dumps(raw_feedback_data),
                            'Sentiment': analyze_sentiment(feedback_text), # Analyze new feedback_text
                            'Category': categorize_feedback(feedback_text) # Categorize new feedback_text
                        })
                        if len(feedback_items) % 10 == 0 and len(feedback_items) > 0:
                            logger.info(f"Collected {len(feedback_items)} relevant items from {self.source_name} search...")
                    else:
                        logger.warning(f"Skipping search result item: missing title/href. Title: {title_tag}, Author: {author_tag}, Date: {date_str_combined}")
                time.sleep(1.5) 
            except requests.exceptions.RequestException as e:
                logger.error(f"Error scraping {self.source_name} search page {current_url}: {e}", exc_info=True)
                break 
            except Exception as e:
                logger.error(f"An unexpected error occurred processing {self.source_name} page {page_num}: {e}", exc_info=True)
                break
        logger.info(f"Finished {self.source_name} search. Total items: {len(feedback_items)}")
        return feedback_items[:self.max_items_to_fetch]

    def _parse_community_date(self, date_str: str) -> datetime: 
        # The date_str should be pre-cleaned by the caller now
        cleaned_date_str = date_str # Assume it's clean
        if not cleaned_date_str: # Add a check here in case pre-cleaning resulted in empty string
             logger.warning(f"Date string became empty after pre-cleaning for {self.source_name}. Using current time.")
             return datetime.now(timezone.utc)
        logger.debug(f"Date string received by _parse_community_date: '{cleaned_date_str}'")
        
        now = datetime.now(timezone.utc)
        formats_to_try = ["%m-%d-%Y %I:%M %p", "%m-%d-%Y", "%b %d, %Y %I:%M %p", "%d-%m-%Y %I:%M %p"]
        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(cleaned_date_str, fmt)
                return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            except ValueError: continue
        date_str_lower = cleaned_date_str.lower()
        if "yesterday at" in date_str_lower or "today at" in date_str_lower:
            day_offset = 1 if "yesterday at" in date_str_lower else 0
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM))', cleaned_date_str, re.IGNORECASE)
            target_date = (now - timedelta(days=day_offset)).date()
            if time_match:
                try:
                    time_obj = datetime.strptime(time_match.group(1), "%I:%M %p").time()
                    return datetime.combine(target_date, time_obj, tzinfo=timezone.utc)
                except ValueError: pass
            return datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        if "ago" in date_str_lower:
            try:
                num_match = re.search(r'(\d+)', date_str_lower)
                if num_match:
                    num = int(num_match.group(1))
                    if "minute" in date_str_lower: return now - timedelta(minutes=num)
                    if "hour" in date_str_lower: return now - timedelta(hours=num)
                    if "day" in date_str_lower: return now - timedelta(days=num)
            except (ValueError, AttributeError): pass
        logger.warning(f"Could not parse date: '{date_str}' (cleaned: '{cleaned_date_str}') for {self.source_name}. Using current time.")
        return now
        
    def _determine_impact_type_content(self, content: str) -> str: 
        content_lower = content.lower()
        if any(word in content_lower for word in ['error', 'bug', 'issue', 'problem']): return 'Bug'
        if any(word in content_lower for word in ['suggest', 'feature', 'improve']): return 'Feature Request'
        if any(word in content_lower for word in ['help', 'how to', 'question']): return 'Question'
        return 'Feedback'

class GitHubDiscussionsCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            'Authorization': f'Bearer {config.GITHUB_TOKEN}', 'Content-Type': 'application/json',
            'Accept': 'application/vnd.github+json', 'X-Github-Api-Version': '2022-11-28'
        }
        
    def collect(self) -> List[Dict[str, Any]]:
        feedback_items = []
        try:
            repo_url = f"https://api.github.com/repos/{config.GITHUB_REPO_OWNER}/{config.GITHUB_REPO_NAME}"
            logger.info(f"Verifying access to {repo_url}")
            repo_response = self.session.get(repo_url)
            repo_response.raise_for_status()
            if not repo_response.json().get('has_discussions'):
                logger.error("Discussions are not enabled on this repository")
                return []
            all_discussions, page, per_page = [], 1, min(100, config.MAX_ITEMS_PER_RUN) 
            logger.info(f"Fetching all discussions for {config.GITHUB_REPO_OWNER}/{config.GITHUB_REPO_NAME} (up to {config.MAX_ITEMS_PER_RUN} items).")
            while True:
                if len(all_discussions) >= config.MAX_ITEMS_PER_RUN: break
                remaining_to_fetch = config.MAX_ITEMS_PER_RUN - len(all_discussions)
                current_page_limit = min(per_page, remaining_to_fetch)
                if current_page_limit <= 0: break
                discussions_url = f"https://api.github.com/repos/{config.GITHUB_REPO_OWNER}/{config.GITHUB_REPO_NAME}/discussions"
                logger.info(f"Fetching discussions page {page} from {discussions_url} (per_page={current_page_limit})")
                discussions_resp = self.session.get(discussions_url, params={'page': page, 'per_page': current_page_limit, 'sort': 'updated', 'direction': 'desc'})
                discussions_resp.raise_for_status()
                page_data = discussions_resp.json()
                if not page_data: break
                all_discussions.extend(page_data)
                logger.info(f"Found {len(page_data)} discussions on page {page}. Total fetched: {len(all_discussions)}")
                if len(page_data) < current_page_limit or ('Link' in discussions_resp.headers and 'rel="next"' not in discussions_resp.headers['Link']):
                    break
                page += 1
            logger.info(f"Found {len(all_discussions)} discussions to process (up to MAX_ITEMS_PER_RUN).")
            count = 0
            for discussion in all_discussions:
                if count >= config.MAX_ITEMS_PER_RUN: break
                title, body = discussion.get('title', ''), discussion.get('body', '') 
                logger.info(f"Processing GitHub discussion: {title}")
                author_node = discussion.get('user') 
                author = author_node.get('login', 'Anonymous') if author_node else 'Anonymous'
                created_at_str = discussion.get('created_at', datetime.now(timezone.utc).isoformat())
                url = discussion.get('html_url', '')
                full_feedback_text_github = f"{title}\n\n{body}"
                
                tag_value = ""

                feedback_items.append({
                    'Feedback_Gist': generate_feedback_gist(full_feedback_text_github),
                    'Feedback': full_feedback_text_github, 'Url': url,
                    'Area': discussion.get('category', {}).get('name', 'Workloads'), 
                    'Sources': 'GitHub Discussions',
                    'Impacttype': self._determine_impact_type_content(full_feedback_text_github),
                    'Scenario': 'Partner', 'Customer': author,
                    'Tag': tag_value, 
                    'Created': created_at_str, 
                    'Organization': f'GitHub/{config.GITHUB_REPO_OWNER}', 'Status': config.DEFAULT_STATUS,
                    'Created_by': config.SYSTEM_USER,
                    'Rawfeedback': f"Source URL: {url}\nRaw API Response: {json.dumps(discussion, indent=2)}",
                    'Sentiment': analyze_sentiment(full_feedback_text_github),
                    'Category': categorize_feedback(full_feedback_text_github)
                })
                count +=1
            logger.info(f"Collected {len(feedback_items)} relevant feedback items from GitHub Discussions")
            return feedback_items[:config.MAX_ITEMS_PER_RUN]
        except Exception as e:
            logger.error(f"Error collecting GitHub feedback: {str(e)}", exc_info=True)
            return []

    def _determine_impact_type_content(self, content: str) -> str: 
        content_lower = content.lower()
        if any(word in content_lower for word in ['error', 'bug', 'issue', 'problem']): return 'Bug'
        if any(word in content_lower for word in ['suggest', 'feature', 'improve']): return 'Feature Request'
        if any(word in content_lower for word in ['help', 'how to', 'question']): return 'Question'
        return 'Feedback'
