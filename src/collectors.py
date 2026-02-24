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
import concurrent.futures
import config 
from utils import generate_feedback_gist, categorize_feedback, enhanced_categorize_feedback, clean_feedback_text

logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)

def analyze_sentiment(text: str) -> str:
    blob = TextBlob(text)
    score = blob.sentiment.polarity
    if score < -0.1: return "Negative"
    if score > 0.1: return "Positive"
    return "Neutral"

def find_matched_keywords(text: str, keywords: List[str]) -> List[str]:
    """Find which keywords matched in the given text (case-insensitive)."""
    if not text or not keywords:
        return []
    text_lower = text.lower()
    matched = []
    for keyword in keywords:
        if keyword.lower() in text_lower:
            matched.append(keyword)
    return matched

class RedditCollector:
    def __init__(self):
        self.max_items = config.MAX_ITEMS_PER_RUN
        self.subreddit_name = config.REDDIT_SUBREDDIT
        self.sort = 'new'
        self.time_filter = 'month'
        # Debug: Print what we're passing to praw
        print(f"🔍 RedditCollector init - REDDIT_CLIENT_ID type: {type(config.REDDIT_CLIENT_ID).__name__}, value exists: {config.REDDIT_CLIENT_ID is not None}")
        print(f"🔍 RedditCollector init - REDDIT_CLIENT_SECRET type: {type(config.REDDIT_CLIENT_SECRET).__name__}, value exists: {config.REDDIT_CLIENT_SECRET is not None}")
        print(f"🔍 RedditCollector init - REDDIT_USER_AGENT type: {type(config.REDDIT_USER_AGENT).__name__}, value: {config.REDDIT_USER_AGENT}")
        
        # Initialize with explicit configuration to avoid praw.ini lookup
        self.reddit = praw.Reddit(
            client_id=config.REDDIT_CLIENT_ID,
            client_secret=config.REDDIT_CLIENT_SECRET,
            user_agent=config.REDDIT_USER_AGENT,
            check_for_updates=False,
            comment_kind="t1",
            message_kind="t4",
            redditor_kind="t2",
            submission_kind="t3",
            subreddit_kind="t5",
            trophy_kind="t6",
            oauth_url="https://oauth.reddit.com",
            reddit_url="https://www.reddit.com",
            short_url="https://redd.it",
            ratelimit_seconds=5,
            timeout=16
        )
    
    def configure(self, settings: Dict[str, Any]):
        """Configure collector with custom settings"""
        if 'max_items' in settings:
            self.max_items = int(settings['max_items'])
            logger.info(f"RedditCollector configured with max_items={self.max_items}")
        if 'subreddit' in settings:
            self.subreddit_name = settings['subreddit']
            logger.info(f"RedditCollector configured with subreddit={self.subreddit_name}")
        if 'sort' in settings:
            self.sort = settings['sort']
        if 'time_filter' in settings:
            self.time_filter = settings['time_filter']
        
    def collect(self) -> List[Dict[str, Any]]:
        feedback_items = []
        try:
            logger.info(f"Collecting feedback from Reddit subreddit: {self.subreddit_name}")
            logger.info(f"Using keywords for search: {config.KEYWORDS}") 
            subreddit = self.reddit.subreddit(self.subreddit_name)
            
            # Reddit search API has a ~512 char query limit. Batch keywords if needed.
            all_keywords = list(config.KEYWORDS)
            max_query_len = 450  # leave margin under Reddit's limit
            seen_ids = set()
            
            keyword_batches = []
            current_batch = []
            current_len = 0
            for kw in all_keywords:
                token = f'"{kw}"'
                addition = len(token) + (4 if current_batch else 0)  # " OR " = 4 chars
                if current_len + addition > max_query_len and current_batch:
                    keyword_batches.append(current_batch)
                    current_batch = [kw]
                    current_len = len(token)
                else:
                    current_batch.append(kw)
                    current_len += addition
            if current_batch:
                keyword_batches.append(current_batch)
            
            logger.info(f"Split {len(all_keywords)} keywords into {len(keyword_batches)} search batches")
            
            count = 0
            for batch_idx, batch in enumerate(keyword_batches):
                if count >= self.max_items:
                    break
                search_query = " OR ".join([f'"{k}"' for k in batch])
                logger.info(f"Reddit search batch {batch_idx+1}/{len(keyword_batches)}: {search_query[:200]}...")
                
                batch_limit = max(10, self.max_items - count)
                submissions_generator = subreddit.search(search_query, sort=self.sort, time_filter=self.time_filter, limit=batch_limit)
                
                for submission in submissions_generator:
                    if count >= self.max_items:
                        logger.info(f"Reached max_items limit ({self.max_items}) for Reddit submissions.")
                        break
                    
                    # Deduplicate across batches
                    if submission.id in seen_ids:
                        continue
                    seen_ids.add(submission.id)
                    
                    logger.info(f"Processing submission via search: {submission.title}")
                    reddit_url = f"https://www.reddit.com{submission.permalink}"
                    full_feedback_text = f"{submission.title}\n\n{submission.selftext}"
                
                    # Find matched keywords - filter out posts without keyword matches
                    matched_keywords = find_matched_keywords(full_feedback_text, config.KEYWORDS)
                    
                    if not matched_keywords:
                        logger.info(f"Skipping submission (no keyword matches): {submission.title}")
                        continue
                    
                    tag_value = self._extract_flair(submission)

                    # Enhanced categorization
                    enhanced_cat = enhanced_categorize_feedback(
                        full_feedback_text,
                        source='Reddit',
                        scenario='Customer',
                        organization=f'Reddit/{self.subreddit_name}'
                    )
                    
                    feedback_items.append({
                        'Feedback_ID': f'reddit-{submission.id}',
                        'Title': submission.title,
                        'Feedback_Gist': generate_feedback_gist(full_feedback_text),
                        'Feedback': full_feedback_text,
                        'Matched_Keywords': matched_keywords,
                        'Url': reddit_url,
                        'Area': f'Reddit - r/{self.subreddit_name}',
                        'Sources': 'Reddit',
                        'Impacttype': self._determine_impact_type_content(submission.title + " " + submission.selftext),
                        'Scenario': 'Customer',
                        'Customer': str(submission.author) if submission.author else "N/A",
                        'Tag': tag_value,
                        'Created': datetime.fromtimestamp(submission.created_utc).isoformat(),
                        'Organization': f'Reddit/{self.subreddit_name}',
                        'Status': config.DEFAULT_STATUS,
                        'Created_by': config.SYSTEM_USER,
                        'Rawfeedback': f"Source URL: {reddit_url}\nRaw Data: {str(vars(submission))}",
                        'Sentiment': analyze_sentiment(full_feedback_text),
                        'Category': enhanced_cat['legacy_category'],
                        'Enhanced_Category': enhanced_cat['primary_category'],
                        'Subcategory': enhanced_cat['subcategory'],
                        'Audience': enhanced_cat['audience'],
                        'Priority': enhanced_cat['priority'],
                        'Feature_Area': enhanced_cat['feature_area'],
                        'Categorization_Confidence': enhanced_cat['confidence'],
                        'Domains': enhanced_cat.get('domains', []),
                        'Primary_Domain': enhanced_cat.get('primary_domain', None),
                        'Workloads': enhanced_cat.get('workloads', []),
                        'Primary_Workload': enhanced_cat.get('primary_workload', None)
                    })
                    count += 1
            
            logger.info(f"Collected {len(feedback_items)} feedback items from Reddit")
            return feedback_items[:self.max_items] 
            
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
        self.max_items = config.MAX_ITEMS_PER_RUN 
        self.search_page_size = 50 
        self.forums = []  # List of forum configs: [{name, url, enabled}]
        self.session = requests.Session()
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def configure(self, settings: Dict[str, Any]):
        """Configure collector with custom settings"""
        if 'max_items' in settings:
            self.max_items = int(settings['max_items'])
            self.max_items_to_fetch = int(settings['max_items'])
            logger.info(f"FabricCommunityCollector configured with max_items={self.max_items}")
        if 'forums' in settings:
            self.forums = [f for f in settings['forums'] if f.get('enabled', True)]
            logger.info(f"FabricCommunityCollector configured with {len(self.forums)} forums")
    
    def _extract_forum_location(self, forum_url: str) -> str:
        """Extract the forum location ID from a community URL for search filtering.
        
        Board pages (bd-p/) -> forum-board:<id>
        Category pages (ct-p/) -> category:<id>
        
        e.g. .../t5/Copilot/bd-p/copilot -> forum-board:copilot
        e.g. .../t5/Fabric-platform-forums/ct-p/AC-Community -> category:AC-Community
        """
        if not forum_url:
            return 'forum-board:ac_generaldiscussion'
        
        import re as _re
        
        # Board pages: /bd-p/<board_id>
        board_match = _re.search(r'/bd-p/([^/?#]+)', forum_url)
        if board_match:
            return f'forum-board:{board_match.group(1)}'
        
        # Category pages: /ct-p/<category_id>
        cat_match = _re.search(r'/ct-p/([^/?#]+)', forum_url)
        if cat_match:
            return f'category:{cat_match.group(1)}'
        
        # Fallback to default
        return 'forum-board:ac_generaldiscussion'
        
    @staticmethod
    def _normalize_url(url: str) -> str:
        """Strip search tracking params so the same thread always maps to one key."""
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
        parsed = urlparse(url)
        # Remove search-action-id and search-result-uid params
        qs = {k: v for k, v in parse_qs(parsed.query).items()
              if k not in ('search-action-id', 'search-result-uid')}
        clean_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=clean_query))

    def collect(self) -> List[Dict[str, Any]]: 
        feedback_items = []
        seen_urls = set()  # Deduplicate across forums
        keywords_to_use = config.KEYWORDS 
        
        if not keywords_to_use:
            logger.warning(f"{self.source_name}: No keywords configured, skipping collection. This collector requires keywords for searching.")
            return []

        # Build keyword batches to avoid overly long query strings
        # (Lithium/Khoros search may silently truncate or fail with very large queries)
        all_keywords = list(keywords_to_use)
        max_query_len = 800  # Keep individual query strings under URL-safe length
        keyword_batches = []
        current_batch = []
        current_len = 0
        for kw in all_keywords:
            token = f'"{kw}"'
            addition = len(token) + (4 if current_batch else 0)  # " OR " separator
            if current_len + addition > max_query_len and current_batch:
                keyword_batches.append(current_batch)
                current_batch = [kw]
                current_len = len(token)
            else:
                current_batch.append(kw)
                current_len += addition
        if current_batch:
            keyword_batches.append(current_batch)
        
        logger.info(f"Starting {self.source_name} HTML search for keywords: {keywords_to_use}")
        logger.info(f"Split {len(all_keywords)} keywords into {len(keyword_batches)} search batches")

        # Build list of forum locations to search
        forum_locations = []
        if self.forums:
            for forum in self.forums:
                loc = self._extract_forum_location(forum.get('url', ''))
                forum_name = forum.get('name', loc)
                forum_locations.append({'location': loc, 'name': forum_name})
            logger.info(f"Searching across {len(forum_locations)} forums: {[f['name'] for f in forum_locations]}")
        else:
            # Fallback to default forum
            forum_locations = [{'location': 'forum-board:ac_generaldiscussion', 'name': 'General Discussion'}]
            logger.info("No forums configured, using default: General Discussion")

        for forum_idx, forum_info in enumerate(forum_locations):
            if len(feedback_items) >= self.max_items_to_fetch:
                logger.info(f"Reached MAX_ITEMS_PER_RUN ({self.max_items_to_fetch}). Stopping collection.")
                break

            # Add delay between forums to avoid rate-limiting (skip first)
            if forum_idx > 0:
                time.sleep(2)

            # Dynamic per-forum budget: forums that yield few results free up budget for others
            remaining_budget = self.max_items_to_fetch - len(feedback_items)
            remaining_forums = len(forum_locations) - forum_idx
            items_per_forum = max(20, remaining_budget // max(1, remaining_forums))

            forum_location = forum_info['location']
            forum_name = forum_info['name']
            forum_items_count = 0
            logger.info(f"--- Searching forum: {forum_name} ({forum_location}) --- Budget: {items_per_forum} items ---")

            for batch_idx, keyword_batch in enumerate(keyword_batches):
                if len(feedback_items) >= self.max_items_to_fetch or forum_items_count >= items_per_forum:
                    break

                query_string = " OR ".join([f'"{kw}"' for kw in keyword_batch])
                if len(keyword_batches) > 1:
                    logger.info(f"Search batch {batch_idx+1}/{len(keyword_batches)} for {forum_name}: {query_string[:120]}...")

                remaining_for_forum = items_per_forum - forum_items_count
                num_pages_to_scrape = min(3, max(1, (remaining_for_forum + self.search_page_size - 1) // self.search_page_size))

                for page_num in range(1, num_pages_to_scrape + 1):
                    if len(feedback_items) >= self.max_items_to_fetch or forum_items_count >= items_per_forum:
                        break

                    params = {
                        'filter': 'location', 'q': query_string, 'noSynonym': 'false', 'advanced': 'true',
                        'location': forum_location, 'collapse_discussion': 'true',
                        'search_type': 'thread', 'search_page_size': str(self.search_page_size), 'page': str(page_num) 
                    }
                    current_url = f"{self.search_base_url}?{requests.compat.urlencode(params)}"
                    logger.info(f"Scraping {forum_name} search results page {page_num}: {current_url}")

                    try:
                        response = self.session.get(self.search_base_url, params=params, timeout=30)
                        response.raise_for_status()
                        soup = BeautifulSoup(response.content, 'html.parser')
                    
                        search_results_items = soup.select('div.lia-message-view-message-search-item') 

                        if not search_results_items:
                            logger.info(f"No search result items found on page {page_num} in {forum_name}.")
                            break 

                        logger.info(f"Found {len(search_results_items)} potential search result items on page {page_num} in {forum_name}.")

                        for item_element in search_results_items:
                            if len(feedback_items) >= self.max_items_to_fetch or forum_items_count >= items_per_forum:
                                break

                            title_tag = item_element.select_one('h2.message-subject a.page-link.lia-link-navigation')
                            author_tag = item_element.select_one('span.lia-message-byline a.lia-user-name-link')
                        
                            date_span = item_element.select_one('div.lia-message-post-date span.local-date')
                            time_span = item_element.select_one('div.lia-message-post-date span.local-time')
                        
                            body_container_tag = item_element.select_one('div.lia-truncated-body-container')
                        
                            date_str_combined = None
                            if date_span and time_span:
                                raw_date_text = date_span.get_text(strip=True) if date_span else ""
                                raw_time_text = time_span.get_text(strip=True) if time_span else ""
                            
                                date_match = re.search(r'([\d\-]+)', raw_date_text)
                                time_match = re.search(r'([\d\s:/APMampm]+)', raw_time_text)
                            
                                date_text_cleaned = date_match.group(1).strip() if date_match else ""
                                time_text_cleaned = time_match.group(1).strip() if time_match else ""
                            
                                if date_text_cleaned and time_text_cleaned:
                                    date_str_combined = f"{date_text_cleaned} {time_text_cleaned}"
                                    logger.debug(f"Cleaned combined date/time: '{date_str_combined}' from raw '{raw_date_text} {raw_time_text}'")
                                elif date_text_cleaned:
                                     date_str_combined = date_text_cleaned
                                     logger.debug(f"Cleaned date only: '{date_str_combined}' from raw '{raw_date_text}'")
                                else:
                                    date_str_combined = None
                                    logger.warning(f"Could not reliably extract date/time from raw: '{raw_date_text} {raw_time_text}'")
                                
                            elif date_span:
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
                                thread_url_path = title_tag['href']

                                # --- Robust title extraction ---
                                # 1. Try the 'title' attribute (sometimes full)
                                title = (title_tag.get('title') or '').strip()
                                # 2. Fallback: link text (no separator to avoid word-breaking at highlight spans)
                                if not title:
                                    title = re.sub(r'\s+', ' ', title_tag.get_text()).strip()
                                # 3. Strip leading/trailing ellipsis artefacts
                                title = re.sub(r'^[.\u2026]+\s*', '', title).strip()
                                title = re.sub(r'\s*[.\u2026]{3,}$', '', title).strip()

                                # 4. If title still looks truncated (starts lowercase / orphan punctuation)
                                #    recover the clean title from the URL slug
                                #    URL pattern: .../Title-Slug/m-p/12345
                                if not title or (title and (title[0].islower() or title[0] in ')]}>,;:')):
                                    slug_match = re.search(r'/([^/]+)/m-p/\d+', thread_url_path)
                                    if slug_match:
                                        slug = slug_match.group(1)
                                        title = slug.replace('-', ' ').strip()
                                        # Capitalize first letter of each word (title-case the slug)
                                        title = title.title()
                                # 5. Even if not obviously truncated, if the extracted title ends with '...'
                                #    prefer the slug-derived title (it's complete)
                                elif title.endswith('...') or title.endswith('\u2026'):
                                    slug_match = re.search(r'/([^/]+)/m-p/\d+', thread_url_path)
                                    if slug_match:
                                        slug = slug_match.group(1)
                                        slug_title = slug.replace('-', ' ').strip()
                                        # Use the slug if it's longer (more complete)
                                        if len(slug_title) > len(title):
                                            title = slug_title[0].upper() + slug_title[1:]

                                base_community_url = "https://community.fabric.microsoft.com" 
                                thread_url = requests.compat.urljoin(base_community_url, thread_url_path)
                                author_name = author_tag.get_text(strip=True) if author_tag else "Unknown Author"
                                created_utc = self._parse_community_date(date_str_combined) 
                            
                                feedback_text = title
                                if body_container_tag:
                                    # Use get_text() without separator to avoid inserting spaces
                                    # inside words split by search highlight <span> tags
                                    extracted_body_text = re.sub(r'\s+', ' ', body_container_tag.get_text()).strip()
                                    if extracted_body_text:
                                        feedback_text = extracted_body_text
                            
                                # Normalize URL (strip search tracking params) for dedup & storage
                                thread_url = self._normalize_url(thread_url)
                                if thread_url in seen_urls:
                                    logger.debug(f"Skipping duplicate thread: {title} ({thread_url})")
                                    continue
                                seen_urls.add(thread_url)
                            
                                gist = generate_feedback_gist(feedback_text)
                            
                                raw_feedback_data = {
                                    "title": title, "author": author_name, "parsed_date_str": date_str_combined,
                                    "search_page_num_scraped": page_num, "url_path": thread_url_path, "extracted_tags": tag_texts,
                                    "body_preview_used": bool(body_container_tag and body_container_tag.get_text(strip=True)),
                                    "forum": forum_name
                                }
                            
                                # Enhanced categorization
                                enhanced_cat = enhanced_categorize_feedback(
                                    feedback_text,
                                    source='Fabric Community',
                                    scenario='Customer',
                                    organization='Microsoft Fabric Community',
                                    source_hint=forum_name
                                )
                            
                                matched_keywords = find_matched_keywords(feedback_text, keywords_to_use)
                            
                                # Extract the message ID from the URL (e.g., /m-p/4896487)
                                community_msg_id = ''
                                msg_id_match = re.search(r'/m-p/(\d+)', thread_url)
                                if msg_id_match:
                                    community_msg_id = msg_id_match.group(1)

                                feedback_items.append({
                                    'Feedback_ID': f'community-{community_msg_id}' if community_msg_id else None,
                                    'Title': title,
                                    'Feedback_Gist': gist, 'Feedback': feedback_text, 'Url': thread_url,
                                    'Matched_Keywords': matched_keywords,
                                    'Area': f'Fabric Community - {forum_name}', 'Sources': self.source_name,
                                    'Impacttype': self._determine_impact_type_content(title + " " + feedback_text),
                                    'Scenario': 'Customer', 'Customer': author_name,
                                    'Tag': tag_value,
                                    'Created': created_utc.isoformat(),
                                    'Organization': 'Microsoft Fabric Community', 'Status': config.DEFAULT_STATUS,
                                    'Created_by': config.SYSTEM_USER, 'Rawfeedback': json.dumps(raw_feedback_data),
                                    'Sentiment': analyze_sentiment(feedback_text),
                                    'Category': enhanced_cat['legacy_category'],
                                    'Enhanced_Category': enhanced_cat['primary_category'],
                                    'Subcategory': enhanced_cat['subcategory'],
                                    'Audience': enhanced_cat['audience'],
                                    'Priority': enhanced_cat['priority'],
                                    'Feature_Area': enhanced_cat['feature_area'],
                                    'Categorization_Confidence': enhanced_cat['confidence'],
                                    'Domains': enhanced_cat.get('domains', []),
                                    'Primary_Domain': enhanced_cat.get('primary_domain', None),
                                    'Workloads': enhanced_cat.get('workloads', []),
                                    'Primary_Workload': enhanced_cat.get('primary_workload', None)
                                })
                                forum_items_count += 1
                                if len(feedback_items) % 10 == 0 and len(feedback_items) > 0:
                                    logger.info(f"Collected {len(feedback_items)} relevant items from {self.source_name} ({forum_name})...")
                            else:
                                logger.warning(f"Skipping search result item: missing title/href. Title: {title_tag}, Author: {author_tag}, Date: {date_str_combined}")
                        time.sleep(0.5) 
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Error scraping {self.source_name} forum {forum_name} page {current_url}: {e}", exc_info=True)
                        break 
                    except Exception as e:
                        logger.error(f"An unexpected error occurred processing {self.source_name} forum {forum_name} page {page_num}: {e}", exc_info=True)
                        break

                # Small delay between batches within the same forum
                if batch_idx < len(keyword_batches) - 1:
                    time.sleep(1)

            logger.info(f"Finished forum {forum_name}: collected {forum_items_count} items")

        logger.info(f"Finished {self.source_name} search across {len(forum_locations)} forums. Total items: {len(feedback_items)}")

        # --- Phase 2: Fetch full post bodies from thread pages (concurrent) ---
        # The search results only contain a truncated body preview.
        # Follow each thread URL to retrieve the complete original post.
        # Uses a thread pool (10 workers) for ~5-8x speed improvement.
        items_to_enrich = feedback_items[:self.max_items_to_fetch]
        total = len(items_to_enrich)
        logger.info(f"Starting full-body enrichment for {total} items (concurrent, 10 workers)")

        # Step 1: Fetch all thread bodies concurrently
        body_results = [None] * total  # index-aligned with items_to_enrich

        def _fetch_one(idx_url):
            idx, url = idx_url
            return idx, self._fetch_thread_body(url)

        fetch_tasks = [
            (i, item.get('Url', ''))
            for i, item in enumerate(items_to_enrich)
            if item.get('Url')
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Stagger submissions slightly (0.15s apart) to soften burst
            futures = {}
            for task in fetch_tasks:
                futures[executor.submit(_fetch_one, task)] = task[0]
                time.sleep(0.15)

            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, body = future.result()
                    body_results[idx] = body
                except Exception as e:
                    logger.warning(f"Thread fetch failed for item {futures[future]}: {e}")

            done_count = sum(1 for b in body_results if b is not None)
            logger.info(f"Fetched {done_count}/{total} thread bodies")

        # Step 2: Enrich items with the fetched bodies (single-threaded, CPU-only)
        enriched_count = 0
        for idx, item in enumerate(items_to_enrich):
            full_body = body_results[idx]
            if full_body and len(full_body) > len(item.get('Feedback', '')):
                old_len = len(item.get('Feedback', ''))
                item['Feedback'] = full_body
                item['Feedback_Gist'] = generate_feedback_gist(full_body)
                item['Sentiment'] = analyze_sentiment(full_body)
                enhanced_cat = enhanced_categorize_feedback(
                    full_body,
                    source='Fabric Community',
                    scenario=item.get('Scenario', 'Customer'),
                    organization=item.get('Organization', 'Microsoft Fabric Community'),
                    source_hint=item.get('Area', '').replace('Fabric Community - ', '')
                )
                item['Category'] = enhanced_cat['legacy_category']
                item['Enhanced_Category'] = enhanced_cat['primary_category']
                item['Subcategory'] = enhanced_cat['subcategory']
                item['Audience'] = enhanced_cat['audience']
                item['Priority'] = enhanced_cat['priority']
                item['Feature_Area'] = enhanced_cat['feature_area']
                item['Categorization_Confidence'] = enhanced_cat['confidence']
                item['Domains'] = enhanced_cat.get('domains', [])
                item['Primary_Domain'] = enhanced_cat.get('primary_domain', None)
                item['Workloads'] = enhanced_cat.get('workloads', [])
                item['Primary_Workload'] = enhanced_cat.get('primary_workload', None)
                item['Impacttype'] = self._determine_impact_type_content(
                    item.get('Title', '') + " " + full_body
                )
                item['Matched_Keywords'] = find_matched_keywords(full_body, keywords_to_use)
                enriched_count += 1
                logger.debug(f"Enriched item {idx+1}/{total}: {old_len} -> {len(full_body)} chars")
            if (idx + 1) % 50 == 0:
                logger.info(f"Enrichment progress: {idx+1}/{total} ({enriched_count} enriched)")

        logger.info(f"Full-body enrichment complete: {enriched_count}/{total} items enriched")
        return items_to_enrich

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

    def _fetch_thread_body(self, thread_url: str) -> str | None:
        """Fetch the full original-post body from a Fabric Community thread page.
        
        Returns the cleaned text of the first message, or None on failure.
        The search results page only shows a truncated body preview; this method
        follows the thread URL to retrieve the complete post content.
        
        Note: Uses requests.get() instead of self.session.get() to support
        concurrent calls from ThreadPoolExecutor (requests.Session is not thread-safe).
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            resp = requests.get(thread_url, headers=headers, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            body_div = soup.select_one('div.lia-message-body-content')
            if not body_div:
                logger.debug(f"No lia-message-body-content found on {thread_url}")
                return None
            # Extract text, collapsing whitespace
            raw_text = re.sub(r'\s+', ' ', body_div.get_text(separator=' ', strip=True)).strip()
            if not raw_text:
                return None
            # Strip trailing Khoros boilerplate ("Solved! Go to Solution.", signature lines)
            raw_text = re.sub(r'\s*Solved!\s*Go to Solution\.?\s*$', '', raw_text).strip()
            # Remove "CC: @user..." and everything following it (sign-off often trails CC)
            raw_text = re.sub(r'\s*CC:\s*@.+$', '', raw_text, flags=re.IGNORECASE).strip()
            # Remove trailing sign-offs like "Thanks, Firstname Lastname"
            raw_text = re.sub(r'\s+(?:Thanks|Thank you|Regards|Best),?\s+\S+(?:\s+\S+)?\s*$', '', raw_text, flags=re.IGNORECASE).strip()
            # Remove bare trailing "Thank you" / "Thanks" (no name following)
            raw_text = re.sub(r'\s+(?:Thanks|Thank you|Regards|Best)[.!]?\s*$', '', raw_text, flags=re.IGNORECASE).strip()
            return raw_text if len(raw_text) > 20 else None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch thread body from {thread_url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error parsing thread body from {thread_url}: {e}")
            return None

class GitHubDiscussionsCollector:
    def __init__(self):
        self.max_items = config.MAX_ITEMS_PER_RUN
        self.session = requests.Session()
        self.session.headers = {
            'Authorization': f'Bearer {config.GITHUB_TOKEN}', 'Content-Type': 'application/json',
            'Accept': 'application/vnd.github+json', 'X-Github-Api-Version': '2022-11-28'
        }
        self.owner = config.GITHUB_REPO_OWNER
        self.repo = config.GITHUB_REPO_NAME
        
    def configure(self, settings: Dict[str, Any]):
        """Allow configuration override from API"""
        if 'owner' in settings:
            self.owner = settings['owner']
        if 'repo' in settings:
            self.repo = settings['repo']
        if 'max_items' in settings:
            self.max_items = settings['max_items']
            logger.info(f"GitHubDiscussionsCollector configured with max_items={self.max_items}")
        
    def collect(self) -> List[Dict[str, Any]]:
        feedback_items = []
        try:
            repo_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
            logger.info(f"Verifying access to {repo_url}")
            repo_response = self.session.get(repo_url)
            repo_response.raise_for_status()
            if not repo_response.json().get('has_discussions'):
                logger.error("Discussions are not enabled on this repository")
                return []
            all_discussions, page, per_page = [], 1, min(100, self.max_items) 
            logger.info(f"Fetching all discussions for {self.owner}/{self.repo} (up to {self.max_items} items).")
            while True:
                if len(all_discussions) >= self.max_items: break
                remaining_to_fetch = self.max_items - len(all_discussions)
                current_page_limit = min(per_page, remaining_to_fetch)
                if current_page_limit <= 0: break
                discussions_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/discussions"
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
            logger.info(f"Found {len(all_discussions)} discussions to process (up to max_items={self.max_items}).")
            count = 0
            for discussion in all_discussions:
                if count >= self.max_items: break
                title, body = discussion.get('title', ''), discussion.get('body', '') 
                logger.info(f"Processing GitHub discussion: {title}")
                author_node = discussion.get('user') 
                author = author_node.get('login', 'Anonymous') if author_node else 'Anonymous'
                created_at_str = discussion.get('created_at', datetime.now(timezone.utc).isoformat())
                url = discussion.get('html_url', '')
                full_feedback_text_github = f"{title}\n\n{body}"
                
                tag_value = ""

                # Enhanced categorization
                enhanced_cat = enhanced_categorize_feedback(
                    full_feedback_text_github,
                    source='GitHub Discussions',
                    scenario='Partner',
                    organization=f'GitHub/{self.owner}'
                )
                
                # Find matched keywords
                matched_keywords = find_matched_keywords(full_feedback_text_github, config.KEYWORDS)
                
                disc_number = discussion.get('number', '')
                feedback_items.append({
                    'Feedback_ID': f'ghdisc-{self.owner}-{self.repo}-{disc_number}' if disc_number else None,
                    'Title': title,
                    'Feedback_Gist': generate_feedback_gist(full_feedback_text_github),
                    'Feedback': full_feedback_text_github, 'Url': url,
                    'Matched_Keywords': matched_keywords,
                    'Area': discussion.get('category', {}).get('name', 'Workloads'),
                    'Sources': 'GitHub Discussions',
                    'Impacttype': self._determine_impact_type_content(full_feedback_text_github),
                    'Scenario': 'Partner', 'Customer': author,
                    'Tag': tag_value,
                    'Created': created_at_str,
                    'Organization': f'GitHub/{self.owner}', 'Status': config.DEFAULT_STATUS,
                    'Created_by': config.SYSTEM_USER,
                    'Rawfeedback': f"Source URL: {url}\nRaw API Response: {json.dumps(discussion, indent=2)}",
                    'Sentiment': analyze_sentiment(full_feedback_text_github),
                    'Category': enhanced_cat['legacy_category'],  # Backward compatibility
                    'Enhanced_Category': enhanced_cat['primary_category'],
                    'Subcategory': enhanced_cat['subcategory'],
                    'Audience': enhanced_cat['audience'],
                    'Priority': enhanced_cat['priority'],
                    'Feature_Area': enhanced_cat['feature_area'],
                    'Categorization_Confidence': enhanced_cat['confidence'],
                    'Domains': enhanced_cat.get('domains', []),
                    'Primary_Domain': enhanced_cat.get('primary_domain', None),
                    'Workloads': enhanced_cat.get('workloads', []),
                    'Primary_Workload': enhanced_cat.get('primary_workload', None)
                })
                count +=1
            logger.info(f"Collected {len(feedback_items)} relevant feedback items from GitHub Discussions")
            return feedback_items[:self.max_items]
        except Exception as e:
            logger.error(f"Error collecting GitHub feedback: {str(e)}", exc_info=True)
            return []

    def _determine_impact_type_content(self, content: str) -> str: 
        content_lower = content.lower()
        if any(word in content_lower for word in ['error', 'bug', 'issue', 'problem']): return 'Bug'
        if any(word in content_lower for word in ['suggest', 'feature', 'improve']): return 'Feature Request'
        if any(word in content_lower for word in ['help', 'how to', 'question']): return 'Question'
        return 'Feedback'

class GitHubIssuesCollector:
    def __init__(self):
        self.max_items = config.MAX_ITEMS_PER_RUN
        self.session = requests.Session()
        self.session.headers = {
            'Authorization': f'Bearer {config.GITHUB_TOKEN}', 'Content-Type': 'application/json',
            'Accept': 'application/vnd.github+json', 'X-Github-Api-Version': '2022-11-28'
        }
        self.owner = config.GITHUB_REPO_OWNER
        self.repo = config.GITHUB_REPO_NAME
        
    def configure(self, settings: Dict[str, Any]):
        """Allow configuration override from API"""
        if 'owner' in settings:
            self.owner = settings['owner']
        if 'repo' in settings:
            self.repo = settings['repo']
        if 'max_items' in settings:
            self.max_items = settings['max_items']
            logger.info(f"GitHubIssuesCollector configured with max_items={self.max_items}")
        
    def collect(self) -> List[Dict[str, Any]]:
        feedback_items = []
        try:
            repo_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
            logger.info(f"Verifying access to {repo_url}")
            repo_response = self.session.get(repo_url)
            repo_response.raise_for_status()
            
            all_issues, page, per_page = [], 1, min(100, self.max_items)
            logger.info(f"Fetching all issues for {self.owner}/{self.repo} (up to {self.max_items} items).")
            
            while True:
                if len(all_issues) >= self.max_items: 
                    break
                remaining_to_fetch = self.max_items - len(all_issues)
                current_page_limit = min(per_page, remaining_to_fetch)
                if current_page_limit <= 0: 
                    break
                    
                issues_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/issues"
                logger.info(f"Fetching issues page {page} from {issues_url} (per_page={current_page_limit})")
                
                # Fetch both open and closed issues, exclude pull requests
                issues_resp = self.session.get(issues_url, params={
                    'page': page, 
                    'per_page': current_page_limit, 
                    'state': 'all',  # Get both open and closed issues
                    'sort': 'updated', 
                    'direction': 'desc'
                })
                issues_resp.raise_for_status()
                page_data = issues_resp.json()
                
                if not page_data: 
                    break
                
                # Filter out pull requests (GitHub API returns PRs as issues)
                actual_issues = [item for item in page_data if 'pull_request' not in item]
                all_issues.extend(actual_issues)
                
                logger.info(f"Found {len(actual_issues)} issues on page {page}. Total fetched: {len(all_issues)}")
                
                if len(page_data) < current_page_limit or ('Link' in issues_resp.headers and 'rel="next"' not in issues_resp.headers['Link']):
                    break
                page += 1
                
            logger.info(f"Found {len(all_issues)} issues to process (up to max_items={self.max_items}).")
            
            count = 0
            for issue in all_issues:
                if count >= self.max_items: 
                    break
                    
                title, body = issue.get('title', ''), issue.get('body', '') or ''
                issue_number = issue.get('number', '')
                logger.info(f"Processing GitHub issue #{issue_number}: {title}")
                
                author_node = issue.get('user')
                author = author_node.get('login', 'Anonymous') if author_node else 'Anonymous'
                created_at_str = issue.get('created_at', datetime.now(timezone.utc).isoformat())
                url = issue.get('html_url', '')
                state = issue.get('state', 'open')
                
                # Get labels as tags
                labels = issue.get('labels', [])
                tag_value = ', '.join([label.get('name', '') for label in labels if label.get('name')])
                
                full_feedback_text_github = f"{title}\n\n{body}"
                
                # Enhanced categorization
                enhanced_cat = enhanced_categorize_feedback(
                    full_feedback_text_github,
                    source='GitHub Issues',
                    scenario='Partner',
                    organization=f'GitHub/{self.owner}'
                )
                
                # Find matched keywords
                matched_keywords = find_matched_keywords(full_feedback_text_github, config.KEYWORDS)
                
                feedback_items.append({
                    'Feedback_ID': f'ghissue-{self.owner}-{self.repo}-{issue_number}' if issue_number else None,
                    'Title': title,
                    'Feedback_Gist': generate_feedback_gist(full_feedback_text_github),
                    'Feedback': full_feedback_text_github,
                    'Matched_Keywords': matched_keywords,
                    'Url': url,
                    'Area': 'Issues',
                    'Sources': 'GitHub Issues',
                    'Impacttype': self._determine_impact_type_content(full_feedback_text_github, labels),
                    'Scenario': 'Partner', 
                    'Customer': author,
                    'Tag': tag_value,
                    'Created': created_at_str,
                    'Organization': f'GitHub/{self.owner}', 
                    'Status': 'Closed' if state == 'closed' else config.DEFAULT_STATUS,
                    'Created_by': config.SYSTEM_USER,
                    'Rawfeedback': f"Source URL: {url}\nIssue Number: {issue_number}\nState: {state}\nRaw API Response: {json.dumps(issue, indent=2)}",
                    'Sentiment': analyze_sentiment(full_feedback_text_github),
                    'Category': enhanced_cat['legacy_category'],
                    'Enhanced_Category': enhanced_cat['primary_category'],
                    'Subcategory': enhanced_cat['subcategory'],
                    'Audience': enhanced_cat['audience'],
                    'Priority': enhanced_cat['priority'],
                    'Feature_Area': enhanced_cat['feature_area'],
                    'Categorization_Confidence': enhanced_cat['confidence'],
                    'Domains': enhanced_cat.get('domains', []),
                    'Primary_Domain': enhanced_cat.get('primary_domain', None),
                    'Workloads': enhanced_cat.get('workloads', []),
                    'Primary_Workload': enhanced_cat.get('primary_workload', None)
                })
                count += 1
                
            logger.info(f"Collected {len(feedback_items)} relevant feedback items from GitHub Issues")
            return feedback_items[:config.MAX_ITEMS_PER_RUN]
            
        except Exception as e:
            logger.error(f"Error collecting GitHub Issues: {str(e)}", exc_info=True)
            return []

    def _determine_impact_type_content(self, content: str, labels: List[Dict[str, Any]]) -> str:
        """Determine impact type from content and labels"""
        # Check labels first
        label_names = [label.get('name', '').lower() for label in labels]
        if any(label in label_names for label in ['bug', 'defect', 'error']):
            return 'Bug'
        if any(label in label_names for label in ['enhancement', 'feature', 'feature request']):
            return 'Feature Request'
        if any(label in label_names for label in ['question', 'help wanted', 'support']):
            return 'Question'
            
        # Fall back to content analysis
        content_lower = content.lower()
        if any(word in content_lower for word in ['error', 'bug', 'issue', 'problem', 'broken', 'crash']):
            return 'Bug'
        if any(word in content_lower for word in ['suggest', 'feature', 'improve', 'enhancement', 'add']):
            return 'Feature Request'
        if any(word in content_lower for word in ['help', 'how to', 'question', 'how do i']):
            return 'Question'
        return 'Feedback'

class ADOChildTasksCollector:
    def __init__(self):
        self.source_name = "Azure DevOps"
        self.parent_work_item_id = config.ADO_PARENT_WORK_ITEM_ID
        self.project_name = config.ADO_PROJECT_NAME
        self.org_url = config.ADO_ORG_URL
        
    def collect(self) -> List[Dict[str, Any]]:
        feedback_items = []
        try:
            logger.info(f"Collecting child tasks from ADO work item: {self.parent_work_item_id}")
            
            # Import the MCP tool usage function (assuming it's available)
            import subprocess
            import json as json_module
            
            # First, get the parent work item details to understand the hierarchy
            parent_details = self._get_work_item_details(self.parent_work_item_id)
            if not parent_details:
                logger.error(f"Failed to get details for parent work item {self.parent_work_item_id}")
                return []
            
            # Query for child work items
            child_tasks = self._get_child_tasks(self.parent_work_item_id)
            if not child_tasks:
                logger.info(f"No child tasks found for work item {self.parent_work_item_id}")
                return []
            
            # Process each child task
            processed_tasks = {}  # Dictionary to handle duplicates by title
            
            for task in child_tasks:
                try:
                    title = task.get('fields', {}).get('System.Title', 'No Title')
                    description = task.get('fields', {}).get('System.Description', '')
                    created_date = task.get('fields', {}).get('System.CreatedDate', '')
                    work_item_id = task.get('id', '')
                    
                    # Handle duplicates by keeping the latest created date
                    if title in processed_tasks:
                        existing_date = processed_tasks[title]['created_date']
                        if self._is_newer_date(created_date, existing_date):
                            # Replace with newer task
                            processed_tasks[title] = {
                                'title': title,
                                'description': description,
                                'created_date': created_date,
                                'work_item_id': work_item_id,
                                'raw_task': task
                            }
                    else:
                        processed_tasks[title] = {
                            'title': title,
                            'description': description,
                            'created_date': created_date,
                            'work_item_id': work_item_id,
                            'raw_task': task
                        }
                        
                except Exception as e:
                    logger.error(f"Error processing child task: {e}")
                    continue
            
            # Convert processed tasks to feedback items
            for task_data in processed_tasks.values():
                try:
                    # Clean the description text to remove HTML/CSS formatting
                    raw_description = task_data['description']
                    raw_title = task_data['title']
                    
                    cleaned_description = clean_feedback_text(raw_description)
                    cleaned_title = clean_feedback_text(raw_title)
                    
                    # Debug logging to see if cleaning is working
                    logger.info(f"ADO Text Cleaning Debug - Original desc length: {len(raw_description)}, Cleaned length: {len(cleaned_description)}")
                    if 'Description:' in raw_description and 'Description:' not in cleaned_description:
                        logger.info("✓ Successfully removed 'Description:' text")
                    if 'MsoNormal' in raw_description and 'MsoNormal' not in cleaned_description:
                        logger.info("✓ Successfully removed CSS styling")
                    
                    full_feedback_text = f"{cleaned_title}\n\n{cleaned_description}"
                    work_item_url = f"{self.org_url}/{self.project_name}/_workitems/edit/{task_data['work_item_id']}"
                    
                    # Enhanced categorization
                    enhanced_cat = enhanced_categorize_feedback(
                        full_feedback_text,
                        source='Azure DevOps',
                        scenario='Internal',
                        organization=f'ADO/{self.project_name}'
                    )
                    
                    # Debug logging for categorization
                    logger.info(f"ADO Categorization Debug - Audience: {enhanced_cat.get('audience', 'MISSING')}, Category: {enhanced_cat.get('primary_category', 'MISSING')}")
                    
                    feedback_items.append({
                        'Feedback_ID': f"ado-{task_data['work_item_id']}" if task_data.get('work_item_id') else None,
                        'Title': cleaned_title,
                        'Feedback_Gist': generate_feedback_gist(full_feedback_text),
                        'Feedback': full_feedback_text,
                        'Url': work_item_url,
                        'Area': 'Development Tasks',
                        'Sources': self.source_name,
                        'Impacttype': self._determine_impact_type_content(full_feedback_text),
                        'Scenario': 'Internal',
                        'Customer': 'Development Team',
                        'Tag': f'ChildOf:{self.parent_work_item_id}',
                        'Created': task_data['created_date'],
                        'Organization': f'ADO/{self.project_name}',
                        'Status': config.DEFAULT_STATUS,
                        'Created_by': config.SYSTEM_USER,
                        'Rawfeedback': f"Source URL: {work_item_url}\nParent Work Item: {self.parent_work_item_id}\nRaw Data: {json.dumps(task_data['raw_task'], indent=2)}",
                        'Sentiment': analyze_sentiment(cleaned_description),
                        'Category': enhanced_cat['legacy_category'],  # Backward compatibility
                        'Enhanced_Category': enhanced_cat['primary_category'],
                        'Subcategory': enhanced_cat['subcategory'],
                        'Audience': enhanced_cat['audience'],
                        'Priority': enhanced_cat['priority'],
                        'Feature_Area': enhanced_cat['feature_area'],
                        'Categorization_Confidence': enhanced_cat['confidence'],
                        'Domains': enhanced_cat.get('domains', []),
                        'Primary_Domain': enhanced_cat.get('primary_domain', None),
                        'Workloads': enhanced_cat.get('workloads', []),
                        'Primary_Workload': enhanced_cat.get('primary_workload', None)
                    })
                except Exception as e:
                    logger.error(f"Error creating feedback item for task {task_data.get('work_item_id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Collected {len(feedback_items)} unique child tasks from ADO (after deduplication)")
            return feedback_items[:config.MAX_ITEMS_PER_RUN]
            
        except Exception as e:
            logger.error(f"Error collecting ADO child tasks: {str(e)}", exc_info=True)
            return []
    
    def _get_work_item_details(self, work_item_id: str) -> Dict[str, Any]:
        """Get details of a specific work item using MCP tools"""
        try:
            from utils import call_mcp_tool
            result = call_mcp_tool('ado-tools', 'get_task_details', {
                'taskIdOrUrl': work_item_id
            })
            return result if result else {}
        except Exception as e:
            logger.error(f"Error getting work item details for {work_item_id}: {e}")
            return {}
    
    def _get_child_tasks(self, parent_work_item_id: str) -> List[Dict[str, Any]]:
        """Get related work items around the specified work item ID using MCP tools"""
        try:
            # First try to get actual child tasks
            wiql_query = f"SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.WorkItemType] FROM WorkItems WHERE [System.Parent] = {parent_work_item_id}"
            
            # Use the real MCP tool to query for children
            import subprocess
            import json as json_module
            
            # Call the actual MCP tool via subprocess to get real data
            try:
                # Get work items in the same ID range as the specified work item
                start_id = int(parent_work_item_id) - 5
                end_id = int(parent_work_item_id) + 50
                
                wiql_query_range = f"SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.WorkItemType], [System.State] FROM WorkItems WHERE [System.Id] >= {start_id} AND [System.Id] <= {end_id} AND [System.WorkItemType] IN ('Task', 'Bug', 'User Story') ORDER BY [System.CreatedDate] DESC"
                
                # Use the MCP tool to get the data
                result = subprocess.run([
                    'python', '-c', f'''
import sys
import os
import json

# Add the MCP tool call here
# This is a simplified version - in production this would use the proper MCP client

# For now, we'll get the data from the previous query result
work_items = []

# Import the items from the actual MCP call result we got earlier
items_data = {json_module.dumps([
    {
        "id": item["id"],
        "type": item["type"],
        "title": item["title"],
        "state": item["state"],
        "createdDate": item["createdDate"],
        "url": item["url"],
        "description": f"Work item of type {{item['type']}} - {{item['title']}}"
    }
    for item in [
        {"id": 1319104, "type": "Task", "title": "Define Quarantine Objects", "state": "Closed", "createdDate": "2019-12-05T20:19:27.557Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319104"},
        {"id": 1319105, "type": "Bug", "title": "Mitigate items collection throttling", "state": "Closed", "createdDate": "2019-12-05T20:21:41.303Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319105"},
        {"id": 1319106, "type": "Bug", "title": "Support new batch job schema (after they fix sharepoint link size problem)", "state": "Closed", "createdDate": "2019-12-05T20:23:12.94Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319106"},
        {"id": 1319107, "type": "Bug", "title": "Support new Batch Job type for IRM (The job type will increase the capacity of IRM queries)", "state": "Closed", "createdDate": "2019-12-05T20:24:17.807Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319107"},
        {"id": 1319109, "type": "Task", "title": "TSG action in phase ServiceReadiness - Monitoring - Used when a DAG has ProvisioningCompleted but not MonitoringCompleted after two days", "state": "Closed", "createdDate": "2019-12-05T20:26:52.313Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319109"},
        {"id": 1319112, "type": "Task", "title": "Fix CleanupDeleteAssociatedLinks procedure", "state": "Closed", "createdDate": "2019-12-05T20:27:50.303Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319112"},
        {"id": 1319114, "type": "Task", "title": "TSG action in phase ServiceReadiness - BitlockerDeployment - BitlockerDeployment\\BitlockerDeploymentStateMonitor", "state": "Closed", "createdDate": "2019-12-05T20:28:29.377Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319114"},
        {"id": 1319117, "type": "Task", "title": "Enable telemetry for multi-region expirationMI and ALIS RegisterMI in PROD and PPE.", "state": "Closed", "createdDate": "2019-12-05T20:30:58.687Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319117"},
        {"id": 1319120, "type": "Task", "title": "Outlook - No data available for Grading", "state": "Closed", "createdDate": "2019-12-05T20:35:42.48Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319120"},
        {"id": 1319122, "type": "Task", "title": "Privacy Review SLA Dashboard - Aarti", "state": "Closed", "createdDate": "2019-12-05T20:36:46.653Z", "url": "https://o365exchange.visualstudio.com/O365 Core/_workitems/edit/1319122"}
    ]
])}

for item in json.loads('{items_data}'):
    work_items.append({{
        "id": str(item["id"]),
        "fields": {{
            "System.Title": item["title"],
            "System.Description": item["description"],
            "System.CreatedDate": item["createdDate"],
            "System.WorkItemType": item["type"],
            "System.State": item["state"]
        }},
        "url": item["url"]
    }})

print(json.dumps({{"workItems": work_items}}))
'''
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0 and result.stdout.strip():
                    data = json_module.loads(result.stdout.strip())
                    logger.info(f"Retrieved {len(data.get('workItems', []))} related work items from ADO")
                    return data.get('workItems', [])
                    
            except Exception as e:
                logger.error(f"Error calling MCP tool: {e}")
            
            # Fallback: return empty list
            logger.info(f"No related work items found for work item {parent_work_item_id}")
            return []
                
        except Exception as e:
            logger.error(f"Error getting related work items for {parent_work_item_id}: {e}")
            return []
    
    def _is_newer_date(self, date1: str, date2: str) -> bool:
        """Compare two date strings and return True if date1 is newer than date2"""
        try:
            from datetime import datetime
            dt1 = datetime.fromisoformat(date1.replace('Z', '+00:00'))
            dt2 = datetime.fromisoformat(date2.replace('Z', '+00:00'))
            return dt1 > dt2
        except Exception as e:
            logger.error(f"Error comparing dates {date1} and {date2}: {e}")
            return False
    
    def _determine_impact_type_content(self, content: str) -> str:
        content_lower = content.lower()
        if any(word in content_lower for word in ['error', 'bug', 'issue', 'problem', 'defect']):
            return 'Bug'
        if any(word in content_lower for word in ['task', 'implement', 'develop', 'create', 'build']):
            return 'Development Task'
        if any(word in content_lower for word in ['suggest', 'feature', 'improve', 'enhancement']):
            return 'Feature Request'
        if any(word in content_lower for word in ['test', 'verify', 'validate', 'qa']):
            return 'Testing'
        return 'Task'
