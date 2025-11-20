import nltk
from textblob import TextBlob
import logging
import re
from config import (
    FEEDBACK_CATEGORIES_WITH_KEYWORDS, DEFAULT_CATEGORY,
    ENHANCED_FEEDBACK_CATEGORIES, AUDIENCE_DETECTION_KEYWORDS, PRIORITY_LEVELS,
    DOMAIN_CATEGORIES, IMPACT_TYPES_CONFIG
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

def generate_feedback_gist(text: str, max_length: int = 150, num_phrases: int = 3) -> str:
    """
    Generates a concise, informative gist from feedback text using multiple strategies.
    
    Args:
        text: The feedback text.
        max_length: The maximum desired length for the gist.
        num_phrases: The number of key phrases to try to combine.
    
    Returns:
        A string representing the feedback gist.
    """
    if not text or not isinstance(text, str):
        return "No content"
    
    # Clean the text
    text = text.strip()
    if not text:
        return "Empty feedback"
    
    try:
        # Strategy 1: Extract title from structured content (if available)
        title_match = re.search(r'^([^.\n!?]+)[.\n!?]', text)
        if title_match:
            potential_title = title_match.group(1).strip()
            if len(potential_title) > 10 and len(potential_title) < max_length:
                # Check if it looks like a meaningful title
                if not potential_title.lower().startswith(('hey', 'hi', 'hello', 'i ', 'we ', 'the ', 'a ', 'an ')):
                    return potential_title
        
        # Strategy 2: Domain-specific keyword extraction
        fabric_keywords = {
            'workloads': ['workload', 'workloads', 'marketplace', 'hub'],
            'development': ['wdk', 'sdk', 'develop', 'developing', 'development', 'api', 'build'],
            'data': ['pipeline', 'notebooks', 'lakehouse', 'warehouse', 'delta', 'spark'],
            'integration': ['connector', 'integration', 'authenticate', 'oauth', 'token'],
            'performance': ['slow', 'performance', 'speed', 'optimization', 'latency'],
            'security': ['security', 'permission', 'access', 'authentication', 'authorization'],
            'ui': ['interface', 'ui', 'ux', 'usability', 'design', 'navigation'],
            'multi-tenant': ['tenant', 'tenancy', 'isv', 'multi-tenant', 'customer'],
            'architecture': ['architecture', 'structure', 'pattern', 'design'],
            'issues': ['error', 'bug', 'issue', 'problem', 'crash', 'fail', 'not working']
        }
        
        # Find relevant domain keywords
        text_lower = text.lower()
        found_categories = []
        for category, keywords in fabric_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                found_categories.append(category)
        
        # Strategy 3: Enhanced extractive summarization
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        if sentences:
            # Find the most informative sentence (contains keywords, not too long, not a question)
            best_sentence = None
            best_score = 0
            
            for sentence in sentences[:3]:  # Only check first 3 sentences
                if len(sentence) > max_length:
                    continue
                
                score = 0
                sentence_lower = sentence.lower()
                
                # Boost score for domain keywords
                for category in found_categories:
                    if category in fabric_keywords:
                        for keyword in fabric_keywords[category]:
                            if keyword in sentence_lower:
                                score += 2
                
                # Boost score for technical terms
                technical_terms = ['fabric', 'microsoft', 'azure', 'sql', 'database', 'workspace']
                for term in technical_terms:
                    if term in sentence_lower:
                        score += 1
                
                # Penalize questions and conversational starts
                if sentence.strip().endswith('?'):
                    score -= 1
                if sentence_lower.startswith(('hey', 'hi', 'hello', 'i am', 'we are')):
                    score -= 2
                
                if score > best_score:
                    best_score = score
                    best_sentence = sentence
            
            if best_sentence and best_score > 0:
                return best_sentence.strip()
        
        # Strategy 4: Generate descriptive title from categories and key terms
        if found_categories:
            # Extract key business terms
            business_terms = []
            patterns = [
                r'\b(multi-tenant|isv|customer|workspace|pipeline|notebook|lakehouse|warehouse)\b',
                r'\b(workload|development|integration|performance|security|authentication)\b',
                r'\b(fabric|power bi|azure|sql|database|api|connector)\b'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                business_terms.extend(matches)
            
            # Remove duplicates while preserving order
            unique_terms = []
            for term in business_terms:
                if term not in unique_terms:
                    unique_terms.append(term)
            
            # Create descriptive title
            if unique_terms:
                if len(found_categories) == 1:
                    category = found_categories[0].replace('-', ' ').title()
                    key_terms = ' '.join(unique_terms[:3]).title()
                    gist = f"{category} - {key_terms}"
                else:
                    key_terms = ' '.join(unique_terms[:4]).title()
                    gist = f"{key_terms} - {' & '.join(found_categories[:2]).title()}"
                
                if len(gist) <= max_length:
                    return gist
        
        # Strategy 5: Improved fallback - use most meaningful words
        words = text.split()
        
        # Filter out common stop words and conversational starts
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'among', 'within', 'without', 'against', 'hey', 'hi', 'hello', 'i', 'we', 'you', 'they', 'it', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'cannot'}
        
        meaningful_words = []
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word and clean_word not in stop_words and len(clean_word) > 2:
                meaningful_words.append(word)
        
        if meaningful_words:
            # Take first 8-12 meaningful words
            selected_words = meaningful_words[:min(12, len(meaningful_words))]
            gist = ' '.join(selected_words)
            
            if len(gist) > max_length:
                gist = gist[:max_length-3] + "..."
            
            return gist
        
        # Final fallback - simple truncation
        return text[:max_length-3] + "..." if len(text) > max_length else text
        
    except Exception as e:
        logger.error(f"Error generating feedback gist: {e}. Using fallback truncation.")
        return text[:max_length-3] + "..." if len(text) > max_length else text

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
    
    Args:
        text: The feedback text to analyze
        source: Source of the feedback (Reddit, GitHub, etc.)
        scenario: Scenario field (Customer, Partner, Internal)
        organization: Organization field
    
    Returns:
        Detected audience: 'Developer', 'Customer', or 'ISV'
    """
    if not text or not isinstance(text, str):
        return 'Customer'  # Default to Customer instead of Unknown
    
    text_lower = text.lower()
    audience_scores = {'Developer': 0, 'Customer': 0, 'ISV': 0}
    
    # Score based on keywords - now including ISV as separate category
    for audience, keywords in AUDIENCE_DETECTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                audience_scores[audience] += 1
    
    # DevGateway and related terms get very strong Developer scoring
    devgateway_terms = ['devgateway', 'dev gateway', 'developer gateway', 'dev portal', 'developer portal']
    if any(term in text_lower for term in devgateway_terms):
        audience_scores['Developer'] += 5  # Very strong Developer indication
    
    # Strong contextual scoring based on source and scenario
    # GitHub and ADO are primarily developer-oriented
    if source.lower() in ['github', 'github discussions', 'azure devops', 'ado', 'azure devops child tasks']:
        audience_scores['Developer'] += 3  # Strong bias for developer sources
    elif source.lower() == 'reddit':
        audience_scores['Customer'] += 1
    elif source.lower() in ['fabric community', 'fabric community search']:
        # Fabric community could be either, slight customer bias
        audience_scores['Customer'] += 0.5
    
    # Scenario-based scoring
    if scenario.lower() == 'partner':
        # Partner could be ISV or Developer, check context
        if any(isv_term in text_lower for isv_term in ['isv', 'independent software vendor', 'multi-tenant', 'tenant', 'saas']):
            audience_scores['ISV'] += 3
        else:
            audience_scores['Developer'] += 2
    elif scenario.lower() == 'customer':
        audience_scores['Customer'] += 2
    elif scenario.lower() == 'internal':
        audience_scores['Developer'] += 2
    
    # Organization-based scoring
    if organization:
        org_lower = organization.lower()
        if 'isv' in org_lower or any(isv_term in org_lower for isv_term in ['vendor', 'partner', 'saas']):
            audience_scores['ISV'] += 2
        elif any(dev_org in org_lower for dev_org in ['github', 'ado', 'azure devops', 'devgateway']):
            audience_scores['Developer'] += 2
    
    # Multi-tenant and SaaS patterns strongly indicate ISV
    if any(term in text_lower for term in ['multi-tenant', 'saas', 'software as a service', 'independent software vendor']):
        audience_scores['ISV'] += 3
    
    # Find the highest scoring audience
    max_score = max(audience_scores.values())
    if max_score == 0:
        return 'Customer'  # Default to Customer
    
    # Return the audience with the highest score
    for audience, score in audience_scores.items():
        if score == max_score:
            return audience
    
    return 'Customer'  # Fallback

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

def enhanced_categorize_feedback(text: str, source: str = "", scenario: str = "", organization: str = "") -> dict:
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
    
    # Update result if we found a good match
    if best_match and best_score > 0:
        result.update(best_match)
        
        # Calculate confidence based on keyword matches and context
        max_possible_keywords = max([
            len(subcategory['keywords'])
            for category in ENHANCED_FEEDBACK_CATEGORIES.values()
            for subcategory in category['subcategories'].values()
        ])
        
        keyword_confidence = min(total_keywords_found / max(max_possible_keywords * 0.1, 1), 1.0)
        context_confidence = 0.5 if audience != 'Unknown' else 0.2
        
        result['confidence'] = round((keyword_confidence + context_confidence) / 2, 2)
    
    # Detect domains (cross-cutting concerns)
    detected_domains = detect_domain(text)
    result['domains'] = detected_domains
    result['primary_domain'] = detected_domains[0]['domain'] if detected_domains else None
    
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
    sample1 = "The user interface is very intuitive and the performance is excellent. I love the new dashboard feature!"
    print(f"Text: {sample1}\nGist: {generate_feedback_gist(sample1)}")

    sample2 = "It crashes frequently on my Android device, especially when I try to upload a file."
    print(f"Text: {sample2}\nGist: {generate_feedback_gist(sample2)}")

    sample3 = "Good."
    print(f"Text: {sample3}\nGist: {generate_feedback_gist(sample3)}")
    
    sample4 = "This is a very long piece of feedback that talks about many different things including the speed, the reliability, the customer service which was not great, and also the pricing model which I think could be improved significantly for small businesses like mine."
    print(f"Text: {sample4}\nGist: {generate_feedback_gist(sample4, num_phrases=3)}")

    sample5 = ""
    print(f"Text: '{sample5}'\nGist: {generate_feedback_gist(sample5)}")

    sample6 = "Login button not working."
    print(f"Text: '{sample6}'\nGist: {generate_feedback_gist(sample6)}")

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
