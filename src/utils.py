import nltk
from textblob import TextBlob
import logging
import re
from config import (
    FEEDBACK_CATEGORIES_WITH_KEYWORDS, DEFAULT_CATEGORY,
    ENHANCED_FEEDBACK_CATEGORIES, AUDIENCE_DETECTION_KEYWORDS, PRIORITY_LEVELS,
    DOMAIN_CATEGORIES, IMPACT_TYPES_CONFIG, WORKLOAD_CATEGORIES
)

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

NLTK_RESOURCES = {
    'corpora/averaged_perceptron_tagger': 'averaged_perceptron_tagger',
    'tokenizers/punkt': 'punkt',
    'corpora/brown': 'brown' # Brown corpus is often used by TextBlob for NP extraction
}

def download_nltk_resources():
    """Downloads necessary NLTK resources if they are not already present."""
    for resource_path, resource_id in NLTK_RESOURCES.items():
        try:
            nltk.data.find(resource_path)
            logger.info(f"NLTK resource '{resource_id}' already downloaded.")
        except LookupError: # Corrected exception type
            logger.warning(f"NLTK resource '{resource_id}' not found. Attempting to download...")
            try:
                nltk.download(resource_id, quiet=True)
                logger.info(f"Successfully downloaded NLTK resource '{resource_id}'.")
            except Exception as e:
                logger.error(f"Failed to download NLTK resource '{resource_id}': {e}")
                logger.error(
                    "Please try downloading it manually by running Python and typing:\n"
                    "import nltk\n"
                    f"nltk.download('{resource_id}')"
                )
        except Exception as e: # Catch any other lookup errors
            logger.error(f"Error checking NLTK resource '{resource_id}': {e}. Attempting download.")
            try:
                nltk.download(resource_id, quiet=True)
                logger.info(f"Successfully downloaded NLTK resource '{resource_id}'.")
            except Exception as download_e:
                logger.error(f"Failed to download NLTK resource '{resource_id}' after error: {download_e}")

# Call download_nltk_resources when the module is loaded
# This ensures that the resources are checked/downloaded once.
# Made lazy-loaded to avoid hanging during import
_nltk_resources_downloaded = False

def ensure_nltk_resources():
    """Ensure NLTK resources are downloaded (lazy loading)"""
    global _nltk_resources_downloaded
    if not _nltk_resources_downloaded:
        download_nltk_resources()
        _nltk_resources_downloaded = True

def clean_feedback_text(text: str) -> str:
    """
    Clean and normalize feedback text from various sources, especially ADO which contains HTML/CSS.
    
    Args:
        text: Raw feedback text that may contain HTML, CSS, or other formatting
    
    Returns:
        Cleaned text suitable for analysis and display
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Remove CSS styles (common in ADO feedback) - more aggressive approach
    # Remove everything that looks like CSS class definitions and rules
    text = re.sub(r'[a-zA-Z0-9\.\#\-_,\s]*\{[^}]*\}', '', text)
    
    # Remove specific CSS patterns that might be missed
    text = re.sub(r'p\.MsoNormal[^}]*}?', '', text)
    text = re.sub(r'li\.MsoNormal[^}]*}?', '', text)
    text = re.sub(r'div\.MsoNormal[^}]*}?', '', text)
    text = re.sub(r'span\.EmailStyle\d+[^}]*}?', '', text)
    text = re.sub(r'\.MsoChpDefault[^}]*}?', '', text)
    text = re.sub(r'div\.WordSection\d+[^}]*}?', '', text)
    
    # Remove the specific problematic pattern from ADO: "a: p.xxmsonormal, li.xxmsonormal, div.xxmsonormal {"
    text = re.sub(r'[a-zA-Z]+:\s*p\.[a-zA-Z]+,?\s*li\.[a-zA-Z]+,?\s*div\.[a-zA-Z]+\s*\{?', '', text, flags=re.IGNORECASE)
    
    # Remove CSS selector lists (handles comma-separated selectors)
    text = re.sub(r'[a-zA-Z]+\.[a-zA-Z]+(?:\s*,\s*[a-zA-Z]+\.[a-zA-Z]+)*\s*\{?', '', text, flags=re.IGNORECASE)
    
    # Remove any remaining CSS-like patterns
    text = re.sub(r'[a-zA-Z\-]+:[^;]{1,50};', '', text)  # CSS properties
    text = re.sub(r'margin:[^;]+;?', '', text)
    text = re.sub(r'font-[^;]+;?', '', text)
    text = re.sub(r'color:[^;]+;?', '', text)
    
    # Remove class name lists that might remain (including x_ prefixed versions)
    text = re.sub(r'p\.x?_?MsoNormal,?\s*li\.x?_?MsoNormal,?\s*div\.x?_?MsoNormal', '', text)
    text = re.sub(r'p\.x_MsoNormal,?\s*li\.x_MsoN[^,\s]*', '', text)  # Handle truncated versions
    
    # Remove any remaining CSS class patterns with x_ prefix
    text = re.sub(r'[a-zA-Z\.x_]+MsoNormal[^,\s]*,?\s*', '', text)
    
    # Remove HTML entities and tags
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', text)  # HTML entities
    text = re.sub(r'<[^>]+>', '', text)  # HTML tags
    
    # Remove font specifications and styling
    text = re.sub(r'font-family:[^;]+;', '', text)
    text = re.sub(r'font-size:[^;]+;', '', text)
    text = re.sub(r'margin:[^;]+;', '', text)
    text = re.sub(r'color:[^;]+;', '', text)
    
    # Remove orphaned CSS fragments and malformed patterns
    text = re.sub(r'[a-zA-Z]+:\s*[^;{}\s]+[;{}\s]*', '', text)  # CSS properties without context
    text = re.sub(r'\{[^}]*\}', '', text)  # Any remaining CSS blocks
    text = re.sub(r'[a-zA-Z]+\.[a-zA-Z]+[,\s]*', '', text)  # Leftover CSS class references
    
    # Remove common CSS properties
    text = re.sub(r'[a-zA-Z-]+:\s*[^;]+;', '', text)
    
    # Clean up whitespace and formatting
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single space
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines to double newline
    text = text.strip()
    
    # Remove empty lines and excessive whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = '\n'.join(lines)
    
    # Remove patterns like "Description:" that appear anywhere in the text
    text = re.sub(r'\bDescription:\s*', '', text, flags=re.IGNORECASE)
    
    # Remove "microsoft.com Description:" pattern specifically
    text = re.sub(r'microsoft\.com\s+Description:\s*', 'microsoft.com ', text, flags=re.IGNORECASE)
    
    # EMAIL REMOVAL - Simple regex approach
    # Remove email headers
    text = re.sub(r'^From:\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^To:\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^Sent:\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^Subject:\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^Cc:\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    # Remove email addresses (replace with placeholder to avoid removing context)
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[email-removed]', text)
    
    # Remove external email markers
    text = re.sub(r'\[EXTERNAL\]\s*', '', text, flags=re.IGNORECASE)
    
    # Remove email signatures
    text = re.sub(r'Best regards,?\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'Thanks,?\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    # Remove email threading
    text = re.sub(r'-----Original Message-----.*', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Clean up whitespace and formatting
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single space
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines to double newline
    text = text.strip()
    
    # Remove empty lines and excessive whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = '\n'.join(lines)
    
    # Remove excessive punctuation
    text = re.sub(r'[.,;:!?]{3,}', '...', text)
    
    return text.strip()

def _detect_feedback_intent(text_lower: str) -> str:
    """
    Detect the primary intent/type of the feedback using pattern matching.
    Returns a short intent label like 'Bug', 'Feature Request', 'Question', etc.
    """
    # Order matters: check more specific patterns first
    intent_patterns = [
        ('Bug', [
            r'\b(bug|crash|exception|error|broken|not working|fails?|failed|failing|defect|regression)\b',
            r'\b(throws?\s+(?:an?\s+)?error|stack\s*trace|unexpected\s+(?:behavior|result))\b',
            r'\b(stopped\s+working|doesn\'t\s+work|does\s+not\s+work|can\'t\s+(?:open|access|use|load|connect))\b',
        ]),
        ('Feature Request', [
            r'\b(feature\s+request|enhancement|suggest(?:ion)?|would\s+(?:be\s+)?(?:great|nice|helpful)\s+(?:if|to))\b',
            r'\b(please\s+add|need\s+(?:a\s+)?(?:way|option|ability)|should\s+(?:have|support|allow|provide))\b',
            r'\b(wish(?:list)?|improve|improvement|missing\s+(?:feature|capability|support))\b',
            r'\b(it\s+would\s+be|can\s+(?:you|we)\s+(?:add|get|have)|requesting)\b',
        ]),
        ('Performance', [
            r'\b(slow|performance|latency|lag|timeout|hang|freeze|speed|optimization|throughput)\b',
            r'\b(takes?\s+(?:too\s+)?long|response\s+time|high\s+(?:cpu|memory|resource))\b',
        ]),
        ('Question', [
            r'\b(how\s+(?:to|do|can|does)|what\s+(?:is|are|does)|is\s+(?:it|there)\s+(?:possible|a\s+way))\b',
            r'\b(can\s+(?:someone|anyone|I)|does\s+(?:anyone|somebody)\s+know|looking\s+for\s+(?:help|guidance))\b',
            r'(?:^|\n)[^\n]*\?(?:\s|$)',
        ]),
        ('Discussion', [
            r'\b(thoughts?\s+on|opinions?\s+on|what\s+do\s+you\s+think|anyone\s+(?:else|using|tried))\b',
            r'\b(best\s+practice|approach|strategy|recommendation|comparison|vs\.?|versus)\b',
            r'\b(share|sharing|experience|journey|story|blog|article|demo)\b',
        ]),
    ]
    
    for intent, patterns in intent_patterns:
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return intent
    
    return 'Feedback'


def _extract_core_ask(text: str) -> str | None:
    """
    Extract the core 'ask' or key statement from feedback text.
    Looks for sentences that express a need, want, request, problem, or question.
    Returns the best candidate sentence, or None.
    """
    # Split into sentences, preserving question marks
    sentences = re.split(r'(?<=[.!?])\s+|\n\n+|\n(?=[A-Z])', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 15]
    
    if not sentences:
        return None
    
    # Patterns that indicate the "core ask" — ranked by specificity
    ask_patterns = [
        # Direct requests / needs (highest value)
        (5, r'\b(?:need|want|require|request(?:ing)?|looking\s+for)\b.*\b(?:way|ability|option|feature|support|tool)\b'),
        (5, r'\b(?:please|can\s+you|could\s+you)\b.*\b(?:add|fix|provide|enable|support|implement|create)\b'),
        (5, r'\b(?:should|must|ought\s+to)\b.*\b(?:support|allow|enable|provide|have|include)\b'),
        # Problem statements
        (4, r'\b(?:(?:it|this)\s+)?(?:crashes?|fails?|throws?|errors?|breaks?|doesn\'t\s+work|does\s+not\s+work|not\s+working)\b'),
        (4, r'\b(?:getting|receiving|seeing|encountering)\s+(?:an?\s+)?(?:error|exception|issue|problem)\b'),
        (4, r'\b(?:unable|impossible|cannot|can\'t)\s+(?:to\s+)?\b'),
        # Strong opinion / value statements
        (3, r'\b(?:would\s+be\s+(?:great|nice|helpful|useful)|it\s+would\s+help|this\s+would)\b'),
        (3, r'\b(?:the\s+(?:main|key|core|primary|biggest)\s+(?:issue|problem|challenge|concern|blocker))\b'),
        # Questions with technical substance
        (2, r'\b(?:how\s+(?:to|do\s+(?:I|we)|can\s+(?:I|we)))\b.*\b(?:fabric|workload|api|sdk|pipeline|lakehouse)\b'),
        (2, r'\b(?:is\s+(?:it|there)\s+(?:possible|a\s+way)\s+to)\b'),
    ]
    
    best_sentence = None
    best_score = 0
    
    for sentence in sentences[:8]:  # Check first 8 sentences
        sentence_lower = sentence.lower()
        score = 0
        
        # Score by ask patterns
        for weight, pattern in ask_patterns:
            if re.search(pattern, sentence_lower):
                score += weight
        
        # Bonus for technical terms
        tech_terms = re.findall(
            r'\b(?:fabric|workload|wdk|sdk|api|pipeline|lakehouse|warehouse|notebook|'
            r'connector|power\s*bi|azure|sql|workspace|tenant|spark|delta|copilot|'
            r'agent|mcp|authentication|oauth|token|deployment|capacity)\b',
            sentence_lower
        )
        score += min(len(tech_terms), 3)  # Cap at 3 bonus points
        
        # Penalize greetings and filler
        if re.match(r'^(?:hey|hi|hello|thanks|thank\s+you|dear|good\s+(?:morning|afternoon|evening))', sentence_lower):
            score -= 5
        # Penalize overly short sentences  
        if len(sentence) < 25:
            score -= 1
        # Penalize enormously long sentences (probably not a good gist)
        if len(sentence) > 200:
            score -= 2
            
        if score > best_score:
            best_score = score
            best_sentence = sentence
    
    if best_sentence and best_score >= 2:
        return best_sentence
    
    return None


def _clean_gist_text(text: str) -> str:
    """Clean and normalize text for use as a gist."""
    # Remove markdown formatting
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # [text](url) -> text
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)  # Remove images
    text = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', text)  # Bold/italic
    text = re.sub(r'`([^`]+)`', r'\1', text)  # Inline code
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)  # Headers
    text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)  # List bullets
    text = re.sub(r'https?://\S+', '', text)  # URLs
    # Remove common prefixes/brackets
    text = re.sub(r'^\s*(?:\{[^}]*\}|\[[^\]]*\])\s*', '', text)  # {Blog}, [Discussion], etc.
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _smart_truncate(text: str, max_length: int) -> str:
    """Truncate text at a word boundary, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    # Find the last space before the limit
    truncated = text[:max_length - 3]
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.5:  # Don't cut too aggressively
        truncated = truncated[:last_space]
    return truncated.rstrip('.,;:!? ') + "..."


def generate_feedback_gist(text: str, max_length: int = 150, num_phrases: int = 3) -> str:
    """
    Generates a concise, informative gist from feedback text.
    
    Produces gists in the format: "[Intent] Core summary of the feedback"
    Uses a multi-strategy approach:
      1. Extract and refine the title line (if it's substantive, not just echoed)
      2. Find the "core ask" — the sentence that best captures what the user wants
      3. Build a descriptive summary from intent + key technical terms
      4. Meaningful word extraction fallback
    
    Args:
        text: The feedback text (often title + body combined).
        max_length: The maximum desired length for the gist.
        num_phrases: The number of key phrases to try to combine.
    
    Returns:
        A string representing the feedback gist.
    """
    if not text or not isinstance(text, str):
        return "No content"
    
    text = text.strip()
    if not text:
        return "Empty feedback"
    
    try:
        # --- Preparation ---
        cleaned = _clean_gist_text(text)
        text_lower = cleaned.lower()
        
        # Detect intent
        intent = _detect_feedback_intent(text_lower)
        intent_prefix = f"[{intent}] "
        available_length = max_length - len(intent_prefix)
        
        # Split into title (first line) and body
        parts = text.split('\n', 1)
        raw_title = _clean_gist_text(parts[0].strip()) if parts[0].strip() else ''
        body = _clean_gist_text(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else ''
        
        # --- Strategy 1: Smart title usage ---
        # Use the title if it's substantive and self-explanatory
        if raw_title and 15 < len(raw_title) <= available_length:
            title_lower = raw_title.lower()
            # Skip if title is just a greeting or too generic
            is_greeting = re.match(r'^(?:hey|hi|hello|dear|good\s)', title_lower)
            is_generic = re.match(r'^(?:feedback|comment|question|issue|problem|help|suggestion)$', title_lower)
            
            if not is_greeting and not is_generic:
                # Title is good — but can we enrich it with intent info?
                # Don't prefix if the title already contains the intent
                title_has_intent = any(word in title_lower for word in [
                    'bug', 'error', 'crash', 'feature request', 'question', 'how to',
                    'suggestion', 'performance', 'slow', 'discussion'
                ])
                if title_has_intent:
                    return _smart_truncate(raw_title, max_length)
                
                # If title is good but body adds important context about the actual ask,
                # try to append a brief qualifier from the body
                if body:
                    core_ask = _extract_core_ask(body)
                    if core_ask and len(core_ask) < 100:
                        # Check if the core ask adds genuinely new info vs. the title
                        title_words = set(raw_title.lower().split())
                        ask_words = set(core_ask.lower().split())
                        new_info_ratio = len(ask_words - title_words) / max(len(ask_words), 1)
                        if new_info_ratio > 0.5:  # More than half the words are new
                            combined = f"{raw_title}: {core_ask}"
                            return intent_prefix + _smart_truncate(combined, available_length)
                
                return intent_prefix + _smart_truncate(raw_title, available_length)
        
        # --- Strategy 2: Extract the core ask from the full text ---
        core_ask = _extract_core_ask(cleaned)
        if core_ask:
            return intent_prefix + _smart_truncate(core_ask, available_length)
        
        # --- Strategy 3: Build descriptive summary from key terms ---
        # Extract the most important technical/domain terms from the text
        term_patterns = [
            # Product/platform terms
            (r'\b(fabric|power\s*bi|azure|microsoft|sql|database)\b', 'product'),
            # Component terms
            (r'\b(workload|pipeline|notebook|lakehouse|warehouse|workspace|capacity|'
             r'connector|api|sdk|wdk|copilot|agent|data\s+agent|mcp|gateway|'
             r'semantic\s+model|dataset|dataflow|spark|delta)\b', 'component'),
            # Action/topic terms
            (r'\b(deploy(?:ment)?|install(?:ation)?|authenticat(?:e|ion)|integrat(?:e|ion)|'
             r'monitor(?:ing)?|scaling|permission|security|compliance|'
             r'publish(?:ing)?|ci/?cd|version\s+control|git)\b', 'action'),
            # Architecture terms
            (r'\b(multi-tenant|isv|saas|microservice|architecture|infrastructure|'
             r'real-?time|streaming|batch|etl|elt|medallion)\b', 'architecture'),
        ]
        
        found_terms = {}  # term -> category for dedup
        for pattern, category in term_patterns:
            for match in re.finditer(pattern, text_lower):
                term = match.group(0).strip()
                if term not in found_terms:
                    found_terms[term] = category
        
        if found_terms:
            # Group: pick the most descriptive terms (prefer component + action)
            components = [t for t, c in found_terms.items() if c == 'component']
            actions = [t for t, c in found_terms.items() if c == 'action']
            products = [t for t, c in found_terms.items() if c == 'product']
            arch_terms = [t for t, c in found_terms.items() if c == 'architecture']
            
            summary_parts = []
            # Lead with components (most specific)
            if components:
                summary_parts.extend([t.title() for t in components[:2]])
            # Add action context
            if actions:
                summary_parts.extend([t.title() for t in actions[:2]])
            # Add product context only if we don't have enough yet
            if len(summary_parts) < 2 and products:
                summary_parts.extend([t.title() for t in products[:1]])
            # Add architecture terms
            if arch_terms and len(summary_parts) < 3:
                summary_parts.extend([t.title() for t in arch_terms[:1]])
            
            if summary_parts:
                descriptive = ' - '.join(summary_parts[:3])
                gist = intent_prefix + descriptive
                if len(gist) <= max_length:
                    return gist
        
        # --- Strategy 4: Meaningful first sentence ---
        # Fall back to the best first sentence that isn't a greeting
        sentences = re.split(r'(?<=[.!?])\s+|\n\n+|\n', cleaned)
        for sentence in sentences[:5]:
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue
            s_lower = sentence.lower()
            if re.match(r'^(?:hey|hi|hello|thanks|thank|dear|good\s|edit:|update:)', s_lower):
                continue
            return intent_prefix + _smart_truncate(sentence, available_length)
        
        # --- Strategy 5: Meaningful words fallback ---
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'among', 'within',
            'hey', 'hi', 'hello', 'i', 'we', 'you', 'they', 'it', 'this', 'that',
            'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
            'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may',
            'might', 'must', 'can', 'cannot', 'so', 'just', 'also', 'very', 'really',
            'not', 'all', 'any', 'some', 'my', 'our', 'your', 'its', 'his', 'her',
        }
        
        words = cleaned.split()
        meaningful = [w for w in words if re.sub(r'[^\w]', '', w.lower()) not in stop_words and len(w) > 2]
        
        if meaningful:
            selected = meaningful[:min(10, len(meaningful))]
            gist = ' '.join(selected)
            return intent_prefix + _smart_truncate(gist, available_length)
        
        # --- Final fallback ---
        return intent_prefix + _smart_truncate(cleaned if cleaned else text, available_length)
        
    except Exception as e:
        logger.error(f"Error generating feedback gist: {e}. Using fallback truncation.")
        return _smart_truncate(text, max_length)

def categorize_feedback(text: str) -> str:
    """
    Legacy categorization function for backward compatibility.
    Use enhanced_categorize_feedback for new functionality.
    """
    if not text or not isinstance(text, str):
        return DEFAULT_CATEGORY

    text_lower = text.lower()
    for category_id, category_info in FEEDBACK_CATEGORIES_WITH_KEYWORDS.items():
        for keyword in category_info.get('keywords', []):
            if keyword.lower() in text_lower:
                return category_info['name']
    return DEFAULT_CATEGORY

def detect_audience(text: str, source: str = "", scenario: str = "", organization: str = "") -> str:
    """
    Detect the audience for feedback based on text analysis and contextual clues.
    Uses project-specific audience labels when a project is active (e.g. Builder/User).
    Falls back to Developer/Customer/ISV for legacy mode.
    """
    import config as _cfg
    
    # Determine the default audience and available audience labels from current config
    audience_labels = list(AUDIENCE_DETECTION_KEYWORDS.keys())
    
    # Get project-specific settings if available
    _active_project = _cfg.get_active_project_id()
    _audience_cfg = None
    if _active_project:
        try:
            import project_manager as _pm
            _project = _pm.load_project(_active_project)
            _audience_cfg = _project.get('audience_config')
        except Exception:
            pass
    
    default_audience = 'Customer'
    source_biases = {}
    if _audience_cfg:
        default_audience = _audience_cfg.get('default_audience', audience_labels[0] if audience_labels else 'Customer')
        source_biases = _audience_cfg.get('source_biases', {})
    
    if not text or not isinstance(text, str):
        return default_audience
    
    text_lower = text.lower()
    audience_scores = {label: 0 for label in audience_labels}
    
    # Score based on keywords from current config (project-specific or global)
    for audience, keywords in AUDIENCE_DETECTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                audience_scores[audience] += 1
    
    # Apply source biases (project-specific or legacy defaults)
    if source_biases:
        # Project-specific source biases from audience_config.json
        for bias_source, bias_info in source_biases.items():
            if source.lower() == bias_source.lower():
                target_audience = bias_info.get('audience', '')
                weight = bias_info.get('weight', 1)
                if target_audience in audience_scores:
                    audience_scores[target_audience] += weight
                break
    else:
        # Legacy source biases (Developer/Customer/ISV mode)
        if 'Developer' in audience_scores:
            if source.lower() in ['github', 'github discussions', 'azure devops', 'ado', 'azure devops child tasks']:
                audience_scores['Developer'] += 3
            elif source.lower() == 'reddit':
                audience_scores.setdefault('Customer', 0)
                audience_scores['Customer'] += 1
            elif source.lower() in ['fabric community', 'fabric community search']:
                audience_scores.setdefault('Customer', 0)
                audience_scores['Customer'] += 0.5
        
        # Legacy DevGateway boost
        devgateway_terms = ['devgateway', 'dev gateway', 'developer gateway', 'dev portal', 'developer portal']
        if any(term in text_lower for term in devgateway_terms):
            audience_scores.get('Developer') is not None and audience_scores.__setitem__('Developer', audience_scores.get('Developer', 0) + 5)
        
        # Legacy scenario-based scoring
        if scenario.lower() == 'partner':
            if any(isv_term in text_lower for isv_term in ['isv', 'independent software vendor', 'multi-tenant', 'tenant', 'saas']):
                if 'ISV' in audience_scores:
                    audience_scores['ISV'] += 3
            elif 'Developer' in audience_scores:
                audience_scores['Developer'] += 2
        elif scenario.lower() == 'customer' and 'Customer' in audience_scores:
            audience_scores['Customer'] += 2
        elif scenario.lower() == 'internal' and 'Developer' in audience_scores:
            audience_scores['Developer'] += 2
        
        # Legacy multi-tenant/SaaS boost
        if 'ISV' in audience_scores:
            if any(term in text_lower for term in ['multi-tenant', 'saas', 'software as a service', 'independent software vendor']):
                audience_scores['ISV'] += 3
    
    # Find the highest scoring audience
    if not audience_scores:
        return default_audience
    
    max_score = max(audience_scores.values())
    if max_score == 0:
        return default_audience
    
    for audience, score in audience_scores.items():
        if score == max_score:
            return audience
    
    return default_audience

def determine_impact_type(text: str) -> str:
    """
    Determine the impact type of feedback based on keyword analysis.
    
    Args:
        text: The feedback text to analyze
    
    Returns:
        Impact type: 'BUG', 'FEATURE_REQUEST', 'PERFORMANCE', 'COMPATIBILITY', 'QUESTION', or 'FEEDBACK'
    """
    if not text or not isinstance(text, str):
        return 'FEEDBACK'
    
    text_lower = text.lower()
    impact_scores = {}
    
    # Score each impact type based on keyword matches
    for impact_id, impact_info in IMPACT_TYPES_CONFIG.items():
        score = 0
        for keyword in impact_info['keywords']:
            if keyword.lower() in text_lower:
                score += 1
        impact_scores[impact_id] = score
    
    # Find the highest scoring impact type
    max_score = max(impact_scores.values()) if impact_scores else 0
    
    if max_score == 0:
        return 'FEEDBACK'  # Default to general feedback
    
    # Return the impact type with the highest score
    for impact_id, score in impact_scores.items():
        if score == max_score:
            return impact_id
    
    return 'FEEDBACK'  # Fallback

def enhanced_categorize_feedback(text: str, source: str = "", scenario: str = "", organization: str = "", source_hint: str = "") -> dict:
    """
    Enhanced categorization that provides hierarchical categorization with audience detection.
    
    Args:
        text: The feedback text to analyze
        source: Source of the feedback (Reddit, GitHub, etc.)
        scenario: Scenario field (Customer, Partner, Internal)
        organization: Organization field
    
    Returns:
        Dictionary containing:
        - primary_category: Main category name
        - subcategory: Subcategory name
        - audience: Detected audience
        - priority: Priority level
        - feature_area: Feature area classification
        - confidence: Confidence score (0.0 to 1.0)
        - impact_type: Impact type (BUG, FEATURE_REQUEST, PERFORMANCE, etc.)
        - legacy_category: For backward compatibility
    """
    if not text or not isinstance(text, str):
        return {
            'primary_category': 'Other',
            'subcategory': 'Uncategorized',
            'audience': 'Unknown',
            'priority': 'medium',
            'feature_area': 'General',
            'confidence': 0.0,
            'impact_type': 'FEEDBACK',
            'legacy_category': DEFAULT_CATEGORY
        }
    
    text_lower = text.lower()
    
    # Detect audience first
    audience = detect_audience(text, source, scenario, organization)
    
    # Determine impact type
    impact_type = determine_impact_type(text)
    
    # Initialize result
    result = {
        'primary_category': 'Other',
        'subcategory': 'Uncategorized',
        'audience': audience,
        'priority': 'medium',
        'feature_area': 'General',
        'confidence': 0.0,
        'impact_type': impact_type,
        'legacy_category': categorize_feedback(text)
    }
    
    best_match = None
    best_score = 0
    total_keywords_found = 0
    best_subcategory_keyword_count = 0
    
    # Analyze all categories and subcategories
    for category_id, category_info in ENHANCED_FEEDBACK_CATEGORIES.items():
        for subcategory_id, subcategory_info in category_info['subcategories'].items():
            score = 0
            keywords_found = 0
            
            # Count keyword matches
            for keyword in subcategory_info['keywords']:
                if keyword.lower() in text_lower:
                    score += 1
                    keywords_found += 1
            
            # Bonus for audience alignment
            if category_info['audience'] == audience or category_info['audience'] == 'All':
                score += 2
            
            # Bonus for source alignment
            if audience == 'Developer' and source.lower() == 'github':
                score += 1
            elif audience == 'Customer' and source.lower() in ['reddit', 'fabric community']:
                score += 1
            
            if score > best_score:
                best_score = score
                best_match = {
                    'primary_category': category_info['name'],
                    'subcategory': subcategory_info['name'],
                    'priority': subcategory_info['priority'],
                    'feature_area': subcategory_info['feature_area']
                }
                total_keywords_found = keywords_found
                best_subcategory_keyword_count = len(subcategory_info['keywords'])
    
    # Update result if we found a good match
    if best_match and best_score > 0:
        result.update(best_match)
        
        # Calculate confidence based on keyword matches and context
        # Use specific subcategory count instead of global max
        keyword_confidence = min(total_keywords_found / max(best_subcategory_keyword_count * 0.2, 1), 1.0)
        context_confidence = 0.5 if audience != 'Unknown' else 0.2
        
        result['confidence'] = round((keyword_confidence + context_confidence) / 2, 2)
    
    # Detect domains (cross-cutting concerns)
    detected_domains = detect_domain(text)
    result['domains'] = detected_domains
    result['primary_domain'] = detected_domains[0]['domain'] if detected_domains else None
    
    # Detect workloads (which Fabric workload the feedback addresses)
    # Pass source_hint (e.g. forum name) to boost the matching workload
    detected_workloads = detect_workload(text, source_hint=source_hint)
    result['workloads'] = detected_workloads
    result['primary_workload'] = detected_workloads[0]['workload'] if detected_workloads else None
    
    return result

def get_category_statistics(feedback_items: list) -> dict:
    """
    Generate comprehensive statistics about feedback categorization.
    
    Args:
        feedback_items: List of feedback items to analyze
    
    Returns:
        Dictionary with category statistics
    """
    if not feedback_items:
        return {}
    
    from collections import defaultdict
    
    stats = {
        'total_items': len(feedback_items),
        'by_audience': defaultdict(int),
        'by_enhanced_category': defaultdict(int),
        'by_subcategory': defaultdict(int),
        'by_priority': defaultdict(int),
        'by_domain': defaultdict(int),
        'by_feature_area': defaultdict(int),
        'by_source': defaultdict(int),
        'audience_category_matrix': defaultdict(lambda: defaultdict(int)),
        'domain_audience_matrix': defaultdict(lambda: defaultdict(int)),
        'priority_distribution': {},
        'confidence_stats': {'high': 0, 'medium': 0, 'low': 0}
    }
    
    # Analyze each feedback item
    for item in feedback_items:
        # Basic counts
        audience = item.get('Audience', 'Unknown')
        enhanced_category = item.get('Enhanced_Category', 'Other')
        subcategory = item.get('Subcategory', 'Uncategorized')
        priority = item.get('Priority', 'medium')
        domain = item.get('Primary_Domain', 'General')
        feature_area = item.get('Feature_Area', 'General')
        source = item.get('Sources', 'Unknown')
        
        stats['by_audience'][audience] += 1
        stats['by_enhanced_category'][enhanced_category] += 1
        stats['by_subcategory'][subcategory] += 1
        stats['by_priority'][priority] += 1
        stats['by_domain'][domain] += 1
        stats['by_feature_area'][feature_area] += 1
        stats['by_source'][source] += 1
        
        # Cross-tabulations
        stats['audience_category_matrix'][audience][enhanced_category] += 1
        stats['domain_audience_matrix'][domain][audience] += 1
        
        # Confidence analysis
        confidence = item.get('Categorization_Confidence', 0)
        if confidence >= 0.7:
            stats['confidence_stats']['high'] += 1
        elif confidence >= 0.4:
            stats['confidence_stats']['medium'] += 1
        else:
            stats['confidence_stats']['low'] += 1
    
    # Calculate percentages for priority distribution
    for priority, count in stats['by_priority'].items():
        stats['priority_distribution'][priority] = {
            'count': count,
            'percentage': round((count / stats['total_items']) * 100, 1)
        }
    
    # Convert defaultdicts to regular dicts for JSON serialization
    stats['by_audience'] = dict(stats['by_audience'])
    stats['by_enhanced_category'] = dict(stats['by_enhanced_category'])
    stats['by_subcategory'] = dict(stats['by_subcategory'])
    stats['by_priority'] = dict(stats['by_priority'])
    stats['by_domain'] = dict(stats['by_domain'])
    stats['by_feature_area'] = dict(stats['by_feature_area'])
    stats['by_source'] = dict(stats['by_source'])
    
    # Convert nested defaultdicts
    stats['audience_category_matrix'] = {
        audience: dict(categories)
        for audience, categories in stats['audience_category_matrix'].items()
    }
    stats['domain_audience_matrix'] = {
        domain: dict(audiences)
        for domain, audiences in stats['domain_audience_matrix'].items()
    }
    
    return stats

def get_priority_weight(priority: str) -> int:
    """
    Get the numeric weight for a priority level.
    
    Args:
        priority: Priority level string
    
    Returns:
        Numeric weight for sorting/analysis
    """
    return PRIORITY_LEVELS.get(priority.lower(), PRIORITY_LEVELS['medium'])['weight']

def analyze_feedback_trends(feedback_items: list) -> dict:
    """
    Analyze trends in categorized feedback items.
    
    Args:
        feedback_items: List of feedback items with enhanced categorization
    
    Returns:
        Dictionary with trend analysis
    """
    if not feedback_items:
        return {}
    
    trends = {
        'total_items': len(feedback_items),
        'by_audience': {},
        'by_primary_category': {},
        'by_subcategory': {},
        'by_priority': {},
        'by_feature_area': {},
        'top_developer_requests': [],
        'top_customer_requests': [],
        'critical_issues': []
    }
    
    # Analyze each feedback item
    for item in feedback_items:
        # Get enhanced categorization if not already present
        if 'enhanced_category' not in item:
            enhanced = enhanced_categorize_feedback(
                item.get('Feedback', ''),
                item.get('Sources', ''),
                item.get('Scenario', ''),
                item.get('Organization', '')
            )
            item['enhanced_category'] = enhanced
        else:
            enhanced = item['enhanced_category']
        
        # Count by audience
        audience = enhanced['audience']
        trends['by_audience'][audience] = trends['by_audience'].get(audience, 0) + 1
        
        # Count by primary category
        primary = enhanced['primary_category']
        trends['by_primary_category'][primary] = trends['by_primary_category'].get(primary, 0) + 1
        
        # Count by subcategory
        subcategory = enhanced['subcategory']
        trends['by_subcategory'][subcategory] = trends['by_subcategory'].get(subcategory, 0) + 1
        
        # Count by priority
        priority = enhanced['priority']
        trends['by_priority'][priority] = trends['by_priority'].get(priority, 0) + 1
        
        # Count by feature area
        feature_area = enhanced['feature_area']
        trends['by_feature_area'][feature_area] = trends['by_feature_area'].get(feature_area, 0) + 1
        
        # Collect specific request types
        if audience == 'Developer' and enhanced['priority'] in ['high', 'critical']:
            trends['top_developer_requests'].append({
                'feedback': item.get('Feedback_Gist', ''),
                'subcategory': subcategory,
                'priority': priority
            })
        
        if audience == 'Customer' and enhanced['priority'] in ['high', 'critical']:
            trends['top_customer_requests'].append({
                'feedback': item.get('Feedback_Gist', ''),
                'subcategory': subcategory,
                'priority': priority
            })
        
        if enhanced['priority'] == 'critical':
            trends['critical_issues'].append({
                'feedback': item.get('Feedback_Gist', ''),
                'audience': audience,
                'subcategory': subcategory
            })
    
    # Limit lists to top items
    trends['top_developer_requests'] = trends['top_developer_requests'][:10]
    trends['top_customer_requests'] = trends['top_customer_requests'][:10]
    trends['critical_issues'] = trends['critical_issues'][:10]
    
    return trends

def analyze_sentiment(text: str) -> dict:
    """
    Analyzes sentiment of the given text using TextBlob.
    
    Args:
        text: The text to analyze for sentiment
    
    Returns:
        Dictionary containing sentiment score, polarity, and label
    """
    if not text or not isinstance(text, str):
        return {
            'polarity': 0.0,
            'subjectivity': 0.0,
            'label': 'Neutral',
            'confidence': 'Low'
        }
    
    try:
        # Ensure NLTK resources are downloaded before using TextBlob
        ensure_nltk_resources()
        
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity  # Range: -1 (negative) to 1 (positive)
        subjectivity = blob.sentiment.subjectivity  # Range: 0 (objective) to 1 (subjective)
        
        # Determine sentiment label based on polarity
        if polarity > 0.1:
            label = 'Positive'
        elif polarity < -0.1:
            label = 'Negative'
        else:
            label = 'Neutral'
        
        # Determine confidence based on absolute polarity value
        abs_polarity = abs(polarity)
        if abs_polarity >= 0.5:
            confidence = 'High'
        elif abs_polarity >= 0.2:
            confidence = 'Medium'
        else:
            confidence = 'Low'
        
        return {
            'polarity': round(polarity, 3),
            'subjectivity': round(subjectivity, 3),
            'label': label,
            'confidence': confidence
        }
        
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        return {
            'polarity': 0.0,
            'subjectivity': 0.0,
            'label': 'Neutral',
            'confidence': 'Low'
        }

if __name__ == '__main__':
    # Test cases 
    print(f"NLTK Resource Check Complete (see logs above).")
    print("=" * 80)
    print("FEEDBACK GIST GENERATION TESTS")
    print("=" * 80)

    test_cases = [
        # (label, input_text)
        ("UI praise", "The user interface is very intuitive and the performance is excellent. I love the new dashboard feature!"),
        
        ("Bug report", "It crashes frequently on my Android device, especially when I try to upload a file."),
        
        ("Minimal", "Good."),
        
        ("Long mixed", "This is a very long piece of feedback that talks about many different things including the speed, the reliability, the customer service which was not great, and also the pricing model which I think could be improved significantly for small businesses like mine."),
        
        ("Empty", ""),
        
        ("Short bug", "Login button not working."),
        
        ("Reddit-style title+body",
         "Semantic model permissions - WHat am I missing?\n\n"
         "So I have a process to gather information about the RLS on 40k reports and 5k semantic models which I store in a lakehouse. "
         "The notebook summary I created works fine but I need a way to handle permission errors across models."),
        
        ("Feature request body",
         "Data Agent improvements\n\n"
         "I know Data Agent is still in preview mode and the Fabric team is actively working to improve it, "
         "but would be great if it could support business terminology variations. "
         "For example, when users ask about 'revenue', it should also search for 'sales amount'."),
        
        ("Blog/sharing post",
         "{Blog} dbt with Fabric Spark in Production\n\n"
         "Link: [dbt with Fabric Spark in Production](https://www.rakirahman.me/dbt-fabric-spark/)\n"
         "Demo: [YouTube](https://www.youtube.com/watch?v=example)"),
        
        ("Greeting + bug",
         "Hi everyone!\n\n"
         "I am trying to create data agent under lakehouse but it throws error as power bi features disabled "
         "but under tenant settings this option was enabled already. Is it because I have Power BI Pro license? "
         "Is it mandatory to have premium?"),
        
        ("DevOps/CI question",
         "Avoiding pip install in Azure DevOps yaml pipelines\n\n"
         "Hi, I'm using Azure DevOps (ADO) to run a yaml script for automated deployment. "
         "In the yaml I have a pip install fabric cicd, so it installs or upgrades every time. "
         "Is there a way to cache or skip the install step?"),
        
        ("Multi-tenant architecture",
         "Multi-tenant workload architecture\n\n"
         "We are building a multi-tenant ISV solution on Fabric. We need a way to isolate tenant data "
         "in workspaces while sharing the same Spark compute. Should we use separate lakehouses per tenant "
         "or a shared lakehouse with row-level security?"),
        
        ("Performance complaint",
         "Notebook execution is extremely slow\n\n"
         "Our Spark notebooks are taking 15-20 minutes just to start the session. "
         "The actual computation is only 2 minutes. This latency makes iterative development impossible."),
    ]
    
    for label, text in test_cases:
        gist = generate_feedback_gist(text)
        print(f"\n[{label}]")
        print(f"  Input:  {text[:100]}{'...' if len(text) > 100 else ''}")
        print(f"  Gist:   {gist}")
    
    print("\n" + "=" * 80)

def call_mcp_tool(server_name: str, tool_name: str, arguments: dict):
    """
    Call an MCP tool - placeholder for integration with actual MCP tools
    
    Args:
        server_name: Name of the MCP server
        tool_name: Name of the tool to call
        arguments: Dictionary of arguments to pass to the tool
    
    Returns:
        The result from the MCP tool call
    """
    logger.info(f"🔄 MCP tool call requested: {server_name}.{tool_name}")
    logger.info(f"📞 This should be replaced with actual MCP client integration")
    
    # Return a placeholder indicating real MCP integration is needed
    return {
        'items': [],
        'totalCount': 0,
        'hasMore': False,
        'message': f'Real MCP integration needed for {server_name}.{tool_name}'
    }

# Removed _call_ado_tool_direct function - replaced with direct MCP integration recommendation

def detect_domain(text: str) -> list:
    """
    Detect domain categories (Governance, UX, Authentication, Performance, etc.) from feedback text.
    
    Args:
        text: The feedback text to analyze
    
    Returns:
        List of detected domain categories with confidence scores
    """
    if not text or not isinstance(text, str):
        return []
    
    text_lower = text.lower()
    detected_domains = []
    
    for domain_id, domain_info in DOMAIN_CATEGORIES.items():
        score = 0
        matched_keywords = []
        
        for keyword in domain_info['keywords']:
            if keyword.lower() in text_lower:
                score += 1
                matched_keywords.append(keyword)
        
        if score > 0:
            confidence = min(score / len(domain_info['keywords']), 1.0)
            detected_domains.append({
                'domain': domain_info['name'],
                'domain_id': domain_id,
                'confidence': round(confidence, 2),
                'score': score,
                'matched_keywords': matched_keywords,
                'color': domain_info['color']
            })
    
    # Sort by confidence score descending
    detected_domains.sort(key=lambda x: x['confidence'], reverse=True)
    return detected_domains

# Mapping from forum names (as configured in project.json) to workload names
FORUM_TO_WORKLOAD = {
    'Power BI': 'Power BI',
    'Data Engineering': 'Data Engineering',
    'Data Warehouse': 'Data Warehouse',
    'Data Science': 'Data Science',
    'Data Factory': 'Data Factory',
    'IQ': 'IQ',
    'Copilot & AI': 'Copilot & AI',
    'Real-Time Intelligence': 'Real-Time Intelligence',
    'Databases': 'Databases',
    'Fabric Platform': 'Fabric Platform',
}

def detect_workload(text: str, source_hint: str = "") -> list:
    """
    Detect which Microsoft Fabric workload(s) the feedback addresses.
    
    When source_hint is provided (e.g. the forum name the feedback was scraped from),
    the matching workload receives a significant score boost so it is more likely
    to be selected as the primary workload.
    
    Args:
        text: The feedback text to analyze
        source_hint: Optional hint from the source (e.g. forum name) to boost
                     the most likely workload
    
    Returns:
        List of detected workloads with confidence scores, sorted by confidence descending
    """
    if not text or not isinstance(text, str):
        return []
    
    text_lower = text.lower()
    detected_workloads = []
    
    # Resolve the source hint to a workload name
    hint_workload = FORUM_TO_WORKLOAD.get(source_hint, "") if source_hint else ""
    
    for workload_id, workload_info in WORKLOAD_CATEGORIES.items():
        score = 0
        matched_keywords = []
        
        for keyword in workload_info['keywords']:
            if keyword.lower() in text_lower:
                score += 1
                matched_keywords.append(keyword)
        
        # Apply forum-based boost: if the feedback came from a forum that
        # directly maps to this workload, add a flat confidence bonus.
        # This ensures the forum workload wins when keyword evidence is 
        # ambiguous or absent, but can be overridden when the text 
        # strongly matches a different workload.
        forum_boosted = False
        if hint_workload and workload_info['name'] == hint_workload:
            forum_boosted = True
            if not matched_keywords:
                matched_keywords.append(f'[forum:{source_hint}]')
        
        if score > 0 or forum_boosted:
            confidence = min(score / len(workload_info['keywords']), 1.0) if workload_info['keywords'] else 0.0
            if forum_boosted:
                confidence = min(confidence + 0.15, 1.0)
            detected_workloads.append({
                'workload': workload_info['name'],
                'workload_id': workload_id,
                'confidence': round(confidence, 2),
                'score': score,
                'matched_keywords': matched_keywords,
                'color': workload_info['color'],
                'forum_boosted': forum_boosted
            })
    
    # Sort by confidence score descending
    detected_workloads.sort(key=lambda x: x['confidence'], reverse=True)
    return detected_workloads

def find_similar_feedback(feedback_text: str, all_feedback: list, similarity_threshold: float = 0.7, exclude_self: bool = True) -> list:
    """
    Find similar/repeating feedback items based on text similarity.
    
    Args:
        feedback_text: The feedback text to find similar items for
        all_feedback: List of all feedback items to search through
        similarity_threshold: Minimum similarity score (0.0 to 1.0)
        exclude_self: Whether to exclude the exact same feedback item
    
    Returns:
        List of similar feedback items with similarity scores
    """
    if not feedback_text or not all_feedback:
        return []
    
    from difflib import SequenceMatcher
    import re
    
    def clean_text(text):
        """Clean and normalize text for comparison"""
        if not text:
            return ""
        # Convert to lowercase, remove extra whitespace, remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def calculate_similarity(text1, text2):
        """Calculate similarity between two texts"""
        clean1 = clean_text(text1)
        clean2 = clean_text(text2)
        
        if not clean1 or not clean2:
            return 0.0
        
        # Use SequenceMatcher for similarity
        similarity = SequenceMatcher(None, clean1, clean2).ratio()
        
        # Boost similarity for exact keyword matches
        words1 = set(clean1.split())
        words2 = set(clean2.split())
        common_words = words1.intersection(words2)
        word_boost = len(common_words) / max(len(words1), len(words2), 1) * 0.2
        
        return min(similarity + word_boost, 1.0)
    
    clean_input = clean_text(feedback_text)
    similar_items = []
    
    for item in all_feedback:
        item_text = item.get('Feedback', '') or item.get('Feedback_Gist', '')
        if not item_text:
            continue
        
        # Skip exact matches only if exclude_self is True
        if exclude_self and item_text == feedback_text:
            continue
        
        similarity = calculate_similarity(feedback_text, item_text)
        
        if similarity >= similarity_threshold:
            similar_items.append({
                'feedback_item': item,
                'similarity': round(similarity, 3),
                'matched_text': item_text[:100] + "..." if len(item_text) > 100 else item_text
            })
    
    # Sort by similarity descending
    similar_items.sort(key=lambda x: x['similarity'], reverse=True)
    return similar_items

def analyze_repeating_requests(feedback_items: list) -> dict:
    """
    Analyze feedback items to find repeating requests and common themes.
    
    Args:
        feedback_items: List of feedback items to analyze
    
    Returns:
        Dictionary with repeating request analysis
    """
    if not feedback_items:
        return {
            'total_items': 0,
            'unique_requests': 0,
            'repeating_clusters': [],
            'cluster_count': 0,
            'repetition_rate': 0.0,
            'top_keywords': [],
            'top_repeating_requests': []
        }
    
    from collections import defaultdict
    import re
    
    def extract_keywords(text, min_length=3):
        """Extract meaningful keywords from text"""
        if not text:
            return []
        
        # Clean text and extract words
        clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = [w for w in clean_text.split() if len(w) >= min_length]
        
        # Filter out common stop words
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her',
            'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its',
            'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'don', 'way',
            'with', 'have', 'this', 'will', 'your', 'from', 'they', 'know', 'want',
            'been', 'good', 'much', 'some', 'time', 'very', 'when', 'come', 'here',
            'just', 'like', 'long', 'make', 'many', 'over', 'such', 'take', 'than',
            'them', 'well', 'were', 'what', 'need', 'would', 'there', 'should'
        }
        
        return [w for w in words if w not in stop_words]
    
    # Group similar feedback by clustering
    clusters = []
    processed = set()
    total_clustered_items = 0  # Track total items that are part of any cluster
    
    logger.info(f"Starting repeating request analysis with {len(feedback_items)} items")
    
    for i, item in enumerate(feedback_items):
        if i in processed:
            continue
        
        item_text = item.get('Feedback', '') or item.get('Feedback_Gist', '')
        if not item_text:
            continue
        
        # Find similar items with a balanced threshold for clustering
        similar_items = find_similar_feedback(item_text, feedback_items, similarity_threshold=0.4, exclude_self=False)
        
        # Filter out the current item from similar items to avoid self-inclusion
        similar_items = [si for si in similar_items if si['feedback_item'] != item]
        
        # Only create a cluster if there are actually similar items (i.e., repetitions)
        if similar_items:
            cluster_items = [item] + [si['feedback_item'] for si in similar_items]
            cluster = {
                'primary_item': item,
                'similar_items': similar_items,
                'count': len(cluster_items),  # Total items in this cluster
                'keywords': extract_keywords(item_text),
                'sources': list(set([ci.get('Sources', 'Unknown') for ci in cluster_items])),
                'audiences': list(set([ci.get('Audience', 'Unknown') for ci in cluster_items])),
                'priorities': list(set([ci.get('Priority', 'medium') for ci in cluster_items]))
            }
            clusters.append(cluster)
            
            # Mark all items in this cluster as processed
            processed.add(i)
            total_clustered_items += 1  # Count the primary item
            
            for similar in similar_items:
                for j, check_item in enumerate(feedback_items):
                    if check_item == similar['feedback_item'] and j not in processed:
                        processed.add(j)
                        total_clustered_items += 1  # Count each similar item
                        break
    
    # Sort clusters by count (most frequent first)
    clusters.sort(key=lambda x: x['count'], reverse=True)
    
    # Analyze keyword frequency across all feedback
    keyword_freq = defaultdict(int)
    for item in feedback_items:
        text = item.get('Feedback', '') or item.get('Feedback_Gist', '')
        keywords = extract_keywords(text)
        for keyword in keywords:
            keyword_freq[keyword] += 1
    
    # Get top keywords
    top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:20]
    
    # Calculate metrics correctly
    total_items = len(feedback_items)
    unique_requests = total_items - total_clustered_items  # Items not part of any cluster are unique
    
    # Repetition rate = percentage of items that are part of clusters (i.e., have duplicates)
    repetition_rate = round(total_clustered_items / total_items * 100, 1) if total_items > 0 else 0.0
    
    # Only count clusters with more than 1 item (actual repetitions)
    actual_repeating_clusters = [c for c in clusters if c['count'] > 1]
    
    analysis = {
        'total_items': total_items,
        'unique_requests': unique_requests,
        'repeating_clusters': actual_repeating_clusters[:10],  # Top 10 most frequent clusters
        'cluster_count': len(actual_repeating_clusters),
        'repetition_rate': repetition_rate,
        'top_keywords': top_keywords,
        'top_repeating_requests': [
            {
                'summary': cluster['primary_item'].get('Feedback_Gist', '')[:100] + "..." if len(cluster['primary_item'].get('Feedback_Gist', '')) > 100 else cluster['primary_item'].get('Feedback_Gist', ''),
                'count': cluster['count'],
                'sources': cluster['sources'],
                'audiences': cluster['audiences'],
                'keywords': cluster['keywords'][:5]
            }
            for cluster in actual_repeating_clusters[:5]
        ]
    }
    
    logger.info(f"Repeating request analysis complete: {len(actual_repeating_clusters)} clusters found, {repetition_rate}% repetition rate, {unique_requests} unique requests")
    
    return analysis
