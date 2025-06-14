import os
from dotenv import load_dotenv
import json # Ensure json is imported

load_dotenv()

# API Configuration
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'WorkloadFeedbackCollector/1.0')

# GitHub Configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Fabric Livy API Configuration
FABRIC_LIVY_ENDPOINT = os.getenv('FABRIC_LIVY_ENDPOINT', 'https://msitapi.fabric.microsoft.com/v1/workspaces/e8ba5f1e-6489-4fe4-959b-528f8bf100cb/lakehouses/1a06b857-cd0b-4da3-bd61-ddfcca868607/livyapi/versions/2023-12-01/sessions')
FABRIC_TARGET_TABLE_NAME = os.getenv('FABRIC_TARGET_TABLE_NAME', 'FeedbackCollector')
FABRIC_WRITE_MODE = os.getenv('FABRIC_WRITE_MODE', 'overwrite') # 'overwrite' or 'append'

# Storage Configuration
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FABRIC_STORAGE_URL = "abfss://e8ba5f1e-6489-4fe4-959b-528f8bf100cb@msit-onelake.dfs.fabric.microsoft.com/1a06b857-cd0b-4da3-bd61-ddfcca868607/Tables/dbo/FeedbackCollector"
FABRIC_STORAGE_KEY = os.getenv('FABRIC_STORAGE_KEY')

# Feedback Categories - Display Names
FEEDBACK_CATEGORY_DISPLAY_NAMES = {
    'UI_USABILITY': 'User Interface / Usability',
    'PERFORMANCE': 'Performance / Reliability',
    'SUPPORT_DOCS': 'Support / Documentation',
    'SECURITY': 'Security / Compliance',
    'INTEGRATION': 'Integration / Compatibility',
    'FEATURE_REQUEST': 'Feature Requests',
    'ACCESSIBILITY': 'Accessibility',
    'PRICING': 'Pricing / Value',
    'CUSTOMIZATION': 'Customization / Flexibility',
    'CUSTOMER_SUPPORT': 'Customer Support Experience',
    'OTHER': 'Other / Uncategorized'
}

# Feedback Categories with Keywords for automated categorization
FEEDBACK_CATEGORIES_WITH_KEYWORDS = {
    'FEATURE_REQUEST': {
        'name': FEEDBACK_CATEGORY_DISPLAY_NAMES['FEATURE_REQUEST'],
        'keywords': ['feature request', 'suggest', 'suggestion', 'idea', 'enhancement', 'improve', 'add', 'allow', 'provide', 'would be great if', 'need a way to']
    },
    'PERFORMANCE': {
        'name': FEEDBACK_CATEGORY_DISPLAY_NAMES['PERFORMANCE'],
        'keywords': ['slow', 'performance', 'speed', 'lag', 'delay', 'crash', 'bug', 'error', 'hang', 'freeze', 'timeout', 'reliable', 'stability']
    },
    'UI_USABILITY': {
        'name': FEEDBACK_CATEGORY_DISPLAY_NAMES['UI_USABILITY'],
        'keywords': ['ui', 'ux', 'interface', 'usability', 'design', 'layout', 'navigation', 'confusing', 'hard to use', 'intuitive', 'look and feel', 'user experience']
    },
    'SUPPORT_DOCS': {
        'name': FEEDBACK_CATEGORY_DISPLAY_NAMES['SUPPORT_DOCS'],
        'keywords': ['documentation', 'docs', 'help', 'guide', 'tutorial', 'support article', 'knowledge base', 'faq', 'how to']
    },
    'INTEGRATION': {
        'name': FEEDBACK_CATEGORY_DISPLAY_NAMES['INTEGRATION'],
        'keywords': ['integrate', 'integration', 'connect', 'api', 'compatibility', 'third-party', 'connector']
    },
    'SECURITY': {
        'name': FEEDBACK_CATEGORY_DISPLAY_NAMES['SECURITY'],
        'keywords': ['security', 'vulnerability', 'exploit', 'permission', 'access control', 'auth', 'authentication', 'authorization', 'compliance', 'gdpr']
    },
}
DEFAULT_CATEGORY = FEEDBACK_CATEGORY_DISPLAY_NAMES['OTHER']

# Table Schema
TABLE_COLUMNS = [
    'Feedback_Gist',
    'Feedback',
    'Area',
    'Sources',
    'Impacttype',
    'Scenario',
    'Category',
    'Tag',
    'Customer',
    'Created',
    'Organization',
    'Status',
    'Created_by',
    'Sentiment',
    'Url',
    'Rawfeedback'
]

# Keywords file path
KEYWORDS_FILE = os.path.join(os.path.dirname(__file__), 'keywords.json')

# Default keywords
DEFAULT_KEYWORDS = [
    "workload hub",
    "workloads",
    "Workload Development Kit",
    "WDK",
    "ISV Workloads",
    "Develop Workloads",
    "Marketplace", 
    "ISV"
]

def save_keywords(keywords_to_save):
    try:
        with open(KEYWORDS_FILE, 'w') as f:
            json.dump(keywords_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving keywords to '{KEYWORDS_FILE}': {e}")

def load_keywords():
    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, 'r') as f:
                content = f.read()
                if not content.strip(): # Handles empty file
                    print(f"Warning: '{KEYWORDS_FILE}' is empty. Using default keywords and saving them to the file.")
                    save_keywords(DEFAULT_KEYWORDS)
                    return DEFAULT_KEYWORDS.copy() # Return a copy
                # Attempt to parse non-empty content
                loaded_kws = json.loads(content)
                if isinstance(loaded_kws, list):
                    return loaded_kws # Return the user-defined list (could be empty [])
                else:
                    print(f"Warning: Content of '{KEYWORDS_FILE}' is not a list. Using default keywords and overwriting the file.")
                    save_keywords(DEFAULT_KEYWORDS)
                    return DEFAULT_KEYWORDS.copy()
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from '{KEYWORDS_FILE}': {e}. Overwriting with default keywords.")
            save_keywords(DEFAULT_KEYWORDS) # Overwrite corrupted file
            return DEFAULT_KEYWORDS.copy()
        except Exception as e:
            print(f"Unexpected error loading '{KEYWORDS_FILE}': {e}. Using default keywords for this session and attempting to save defaults to file.")
            try:
                save_keywords(DEFAULT_KEYWORDS)
            except Exception as save_e:
                print(f"Could not save default keywords to '{KEYWORDS_FILE}' after load error: {save_e}")
            return DEFAULT_KEYWORDS.copy()
    else: # File doesn't exist
        print(f"'{KEYWORDS_FILE}' not found. Creating with default keywords.")
        save_keywords(DEFAULT_KEYWORDS)
        return DEFAULT_KEYWORDS.copy()

# Initialize keywords - This is loaded once when the module is imported.
# For dynamic updates during runtime for collectors, app.py will call load_keywords() again.
KEYWORDS = load_keywords()

# Source URLs
MS_FABRIC_COMMUNITY_URL = "https://community.fabric.microsoft.com/t5/Fabric-platform-forums/ct-p/AC-Community"
REDDIT_SUBREDDIT = "MicrosoftFabric"
GITHUB_REPO_OWNER = "microsoft"
GITHUB_REPO_NAME = "Microsoft-Fabric-workload-development-sample"

# Processing Configuration
MAX_ITEMS_PER_RUN = 500
DEFAULT_STATUS = "New"
SYSTEM_USER = "FeedbackCollector"
