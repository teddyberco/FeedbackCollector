import os
import sys
from dotenv import load_dotenv
import json # Ensure json is imported

# Determine the correct path for .env file when frozen
if getattr(sys, 'frozen', False):
    # Running as compiled executable - PyInstaller extracts to _internal
    # Try multiple locations
    application_path = os.path.dirname(sys.executable)
    env_paths = [
        os.path.join(sys._MEIPASS, '.env'),  # Inside _internal (PyInstaller temp dir)
        os.path.join(application_path, '_internal', '.env'),  # Relative to exe
        os.path.join(application_path, '.env'),  # Same dir as exe
    ]
    env_path = None
    for path in env_paths:
        if os.path.exists(path):
            env_path = path
            print(f"✅ Found .env file at: {path}")
            break
    if not env_path:
        env_path = env_paths[0]  # Default to first option
        print(f"⚠️ .env file not found. Tried: {env_paths}")
else:
    # Running in normal Python environment
    env_path = os.path.join(os.path.dirname(__file__), '.env')

# Load .env file with override=True to ensure values are loaded
result = load_dotenv(env_path, override=True)
print(f"🔧 load_dotenv result: {result}, path: {env_path}")

# Verify credentials are loaded
if getattr(sys, 'frozen', False):
    reddit_id = os.getenv('REDDIT_CLIENT_ID')
    print(f"🔍 REDDIT_CLIENT_ID loaded: {reddit_id is not None and reddit_id != ''} (type: {type(reddit_id).__name__})")

# API Configuration
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'WorkloadFeedbackCollector/1.0')

# GitHub Configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Azure DevOps Configuration
ADO_PAT = os.getenv('ADO_PAT')
ADO_PARENT_WORK_ITEM_ID = os.getenv('ADO_PARENT_WORK_ITEM_ID')
ADO_PROJECT_NAME = os.getenv('ADO_PROJECT_NAME')
ADO_ORG_URL = os.getenv('ADO_ORG_URL')

# Fabric Livy API Configuration
FABRIC_LIVY_ENDPOINT = os.getenv('FABRIC_LIVY_ENDPOINT')
FABRIC_TARGET_TABLE_NAME = os.getenv('FABRIC_TARGET_TABLE_NAME')
FABRIC_WRITE_MODE = os.getenv('FABRIC_WRITE_MODE')

# Power BI Report Configuration
POWERBI_REPORT_ID = os.getenv('POWERBI_REPORT_ID')
POWERBI_TENANT_ID = os.getenv('POWERBI_TENANT_ID')
POWERBI_EMBED_BASE_URL = os.getenv('POWERBI_EMBED_BASE_URL')

# Storage Configuration
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FABRIC_STORAGE_URL = os.getenv('FABRIC_STORAGE_URL')
FABRIC_STORAGE_KEY = os.getenv('FABRIC_STORAGE_KEY')

# Fabric SQL Database Configuration
FABRIC_SQL_SERVER = os.getenv('FABRIC_SQL_SERVER')
FABRIC_SQL_DATABASE = os.getenv('FABRIC_SQL_DATABASE')
FABRIC_SQL_AUTHENTICATION = os.getenv('FABRIC_SQL_AUTHENTICATION', 'AzureActiveDirectoryInteractive')

# Enhanced Hierarchical Feedback Categories (Default Configuration)
DEFAULT_ENHANCED_FEEDBACK_CATEGORIES = {
    'DEVELOPER_REQUESTS': {
        'name': 'Developer Experience Requests',
        'audience': 'Developer',
        'description': 'Feedback related to workload development using WDK/SDK',
        'subcategories': {
            'WDK_FEATURES': {
                'name': 'WDK Enhancement',
                'keywords': [
                    'wdk', 'workload development kit', 'development kit', 'build', 'compile', 'debug',
                    'testing framework', 'unit test', 'deployment', 'packaging', 'manifest', 'workload project',
                    'fet', 'fabric extensibility toolkit'
                ],
                'priority': 'high',
                'feature_area': 'Workload Development'
            },
            'SDK_FEATURES': {
                'name': 'SDK Enhancement',
                'keywords': [
                    'sdk', 'software development kit', 'api', 'connector', 'authentication', 'data source',
                    'data connection', 'rest api', 'graphql', 'oauth', 'service principal', 'token',
                    'fet', 'fabric extensibility toolkit'
                ],
                'priority': 'high',
                'feature_area': 'Workload Development'
            },
            'DEV_TOOLS': {
                'name': 'Development Tools',
                'keywords': [
                    'ide', 'visual studio', 'vs code', 'intellisense', 'git', 'version control',
                    'source control', 'debugging', 'breakpoint', 'profiling', 'local development'
                ],
                'priority': 'medium',
                'feature_area': 'Development Experience'
            },
            'DEV_DOCUMENTATION': {
                'name': 'Developer Documentation',
                'keywords': [
                    'developer docs', 'api documentation', 'sample code', 'code samples', 'tutorial',
                    'developer guide', 'how to develop', 'best practices', 'reference', 'sdk docs'
                ],
                'priority': 'medium',
                'feature_area': 'Documentation'
            },
            'DEV_EXPERIENCE': {
                'name': 'Development Experience',
                'keywords': [
                    'developer experience', 'dx', 'workflow', 'productivity', 'automation',
                    'ci/cd', 'continuous integration', 'testing automation', 'build pipeline'
                ],
                'priority': 'medium',
                'feature_area': 'Development Experience'
            }
        }
    },
    'CUSTOMER_REQUESTS': {
        'name': 'Customer Experience Requests',
        'audience': 'Customer',
        'description': 'Feedback related to using workloads from Workload Hub/Marketplace',
        'subcategories': {
            'WORKLOAD_HUB': {
                'name': 'Workload Hub Experience',
                'keywords': [
                    'workload hub', 'hub', 'browse workloads', 'discover workloads', 'find workloads',
                    'workload gallery', 'workload store', 'search workloads', 'filter workloads'
                ],
                'priority': 'high',
                'feature_area': 'Workload Discovery'
            },
            'MARKETPLACE': {
                'name': 'Marketplace Features',
                'keywords': [
                    'marketplace', 'publish workload', 'workload publishing', 'certification',
                    'workload approval', 'listing', 'pricing', 'billing', 'monetization'
                ],
                'priority': 'high',
                'feature_area': 'Workload Publishing'
            },
            'INSTALLATION': {
                'name': 'Installation & Setup',
                'keywords': [
                    'install workload', 'installation', 'setup', 'configure', 'deployment',
                    'getting started', 'onboarding', 'first time setup', 'workload configuration'
                ],
                'priority': 'high',
                'feature_area': 'Workload Usage'
            },
            'WORKLOAD_USAGE': {
                'name': 'Workload Usage Experience',
                'keywords': [
                    'using workload', 'workload performance', 'workload ui', 'workload interface',
                    'workload features', 'workload functionality', 'user experience', 'usability'
                ],
                'priority': 'high',
                'feature_area': 'Workload Usage'
            },
            'CUSTOMER_SUPPORT': {
                'name': 'Customer Support & Help',
                'keywords': [
                    'help', 'support', 'customer support', 'documentation', 'user guide',
                    'how to use', 'tutorial', 'faq', 'troubleshooting', 'knowledge base'
                ],
                'priority': 'medium',
                'feature_area': 'Support'
            }
        }
    },
    'PLATFORM_REQUESTS': {
        'name': 'Platform & Infrastructure Requests',
        'audience': 'Platform',
        'description': 'Feedback related to platform-level features and infrastructure',
        'subcategories': {
            'INFRASTRUCTURE': {
                'name': 'Infrastructure & Scaling',
                'keywords': [
                    'infrastructure', 'scaling', 'scale', 'capacity', 'resources', 'multi-tenant',
                    'regional', 'availability', 'reliability', 'uptime', 'disaster recovery'
                ],
                'priority': 'high',
                'feature_area': 'Platform Infrastructure'
            },
            'SECURITY': {
                'name': 'Security & Compliance',
                'keywords': [
                    'security', 'vulnerability', 'exploit', 'permission', 'access control', 'rbac',
                    'authentication', 'authorization', 'compliance', 'gdpr', 'privacy', 'audit'
                ],
                'priority': 'critical',
                'feature_area': 'Security'
            },
            'MONITORING': {
                'name': 'Monitoring & Analytics',
                'keywords': [
                    'monitoring', 'analytics', 'metrics', 'telemetry', 'logging', 'diagnostics',
                    'performance monitoring', 'usage analytics', 'business intelligence', 'reporting'
                ],
                'priority': 'medium',
                'feature_area': 'Platform Services'
            },
            'INTEGRATION': {
                'name': 'Platform Integration',
                'keywords': [
                    'integration', 'fabric integration', 'power bi', 'teams', 'office', 'azure',
                    'third-party', 'connector', 'api integration', 'service integration'
                ],
                'priority': 'medium',
                'feature_area': 'Platform Integration'
            }
        }
    }
}

# Impact Types Configuration
IMPACT_TYPES = {
    'BUG': {
        'name': 'Bug',
        'description': 'Defects, errors, crashes, or incorrect behavior',
        'keywords': [
            'bug', 'error', 'issue', 'problem', 'broken', 'not working', 'crash',
            'exception', 'failure', 'malfunction', 'incorrect behavior', 'defect'
        ],
        'priority': 'critical',
        'color': '#dc3545'  # Red
    },
    'FEATURE_REQUEST': {
        'name': 'Feature Request',
        'description': 'Requests for new features or enhancements',
        'keywords': [
            'feature request', 'suggest', 'suggestion', 'enhancement', 'improve',
            'add', 'allow', 'provide', 'would be great if', 'need a way to',
            'missing', 'lack', 'should have'
        ],
        'priority': 'medium',
        'color': '#28a745'  # Green
    },
    'PERFORMANCE': {
        'name': 'Performance',
        'description': 'Speed, latency, throughput, or resource usage issues',
        'keywords': [
            'slow', 'performance', 'speed', 'lag', 'delay', 'timeout', 'hang', 'freeze',
            'response time', 'latency', 'throughput', 'optimization', 'memory',
            'cpu', 'resource usage'
        ],
        'priority': 'high',
        'color': '#fd7e14'  # Orange
    },
    'COMPATIBILITY': {
        'name': 'Compatibility',
        'description': 'Version, platform, or integration compatibility issues',
        'keywords': [
            'compatibility', 'incompatible', 'version', 'browser', 'environment',
            'platform support', 'cross-platform', 'backwards compatibility',
            'breaking change'
        ],
        'priority': 'medium',
        'color': '#ffc107'  # Yellow
    },
    'QUESTION': {
        'name': 'Question',
        'description': 'Questions, clarifications, or help requests',
        'keywords': [
            'question', 'how to', 'how do i', 'help', 'clarification', 'unclear',
            'understand', 'explain', 'what is', 'why', 'when', 'where'
        ],
        'priority': 'low',
        'color': '#17a2b8'  # Cyan
    },
    'FEEDBACK': {
        'name': 'General Feedback',
        'description': 'General observations, opinions, or comments',
        'keywords': [
            'feedback', 'comment', 'observation', 'opinion', 'thought',
            'experience', 'note', 'remark'
        ],
        'priority': 'low',
        'color': '#6c757d'  # Gray
    }
}

# Legacy category mapping for backward compatibility
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

# Legacy categories with keywords (kept for backward compatibility)
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

# Audience detection keywords
AUDIENCE_DETECTION_KEYWORDS = {
    'Developer': [
        'wdk', 'sdk', 'development kit', 'api', 'develop', 'developing', 'developer',
        'code', 'programming', 'build', 'compile', 'debug', 'visual studio', 'ide',
        'git', 'version control', 'deployment', 'testing', 'unit test',
        'devgateway', 'dev gateway', 'developer gateway', 'dev portal', 'developer portal',
        'dev tools', 'developer tools', 'development tools', 'cicd', 'ci/cd', 'continuous integration',
        'continuous deployment', 'azure devops', 'ado', 'github', 'source control',
        'npm', 'nuget', 'package manager', 'maven', 'gradle', 'pip', 'conda',
        'frontend', 'backend', 'workload development sample', 'fabric wdk', 'quickstart'
    ],
    'Customer': [
        'workload hub', 'marketplace', 'install', 'using', 'user', 'customer',
        'browse', 'discover', 'find workloads', 'workload gallery', 'end user',
        'business user', 'analyst', 'report', 'dashboard'
    ],
    'ISV': [
        'isv', 'independent software vendor', 'partner', 'publish', 'publishing',
        'certification', 'monetize', 'sell', 'distribute', 'listing', 'multi-tenant',
        'tenant', 'saas', 'software as a service', 'reseller', 'vendor'
    ]
}

# Priority levels
PRIORITY_LEVELS = {
    'critical': {'weight': 4, 'sla_days': 1},
    'high': {'weight': 3, 'sla_days': 7},
    'medium': {'weight': 2, 'sla_days': 14},
    'low': {'weight': 1, 'sla_days': 30}
}

# Domain Categories for cross-cutting concerns
DOMAIN_CATEGORIES = {
    'GETTING_STARTED': {
        'name': 'Getting Started',
        'description': 'Onboarding, tutorials, quickstart guides, initial setup',
        'keywords': [
            'getting started', 'quickstart', 'quick start', 'tutorial', 'onboarding',
            'setup', 'initial setup', 'first time', 'beginner', 'introduction',
            'walkthrough', 'guide', 'how to start', 'starting guide', 'initial configuration',
            'setup guide', 'installation guide', 'first steps', 'basic setup'
        ],
        'color': '#20c997'  # Teal
    },
    'GOVERNANCE': {
        'name': 'Governance',
        'description': 'Compliance, policies, data governance, regulatory requirements',
        'keywords': [
            'governance', 'compliance', 'policy', 'policies', 'regulation', 'regulatory',
            'audit', 'auditing', 'data governance', 'data lineage', 'gdpr', 'privacy',
            'retention', 'classification', 'data classification', 'metadata', 'catalog'
        ],
        'color': '#6f42c1'  # Purple
    },
    'USER_EXPERIENCE': {
        'name': 'User Experience',
        'description': 'UI/UX design, usability, accessibility, user workflows',
        'keywords': [
            'user experience', 'ux', 'ui', 'interface', 'usability', 'accessibility',
            'design', 'layout', 'navigation', 'workflow', 'user journey', 'intuitive',
            'confusing', 'hard to use', 'easy to use', 'user-friendly', 'responsive'
        ],
        'color': '#28a745'  # Green
    },
    'AUTHENTICATION': {
        'name': 'Authentication & Security',
        'description': 'Identity, access control, security, permissions, SSO',
        'keywords': [
            'authentication', 'auth', 'login', 'sso', 'single sign-on', 'identity',
            'access control', 'permissions', 'rbac', 'security', 'authorization',
            'token', 'oauth', 'saml', 'azure ad', 'active directory', 'mfa'
        ],
        'color': '#dc3545'  # Red
    },
    'PERFORMANCE': {
        'name': 'Performance & Scalability',
        'description': 'Speed, scalability, optimization, resource usage, latency',
        'keywords': [
            'performance', 'speed', 'slow', 'fast', 'scalability', 'scale', 'optimization',
            'latency', 'response time', 'throughput', 'memory', 'cpu', 'resource',
            'timeout', 'lag', 'delay', 'bottleneck', 'capacity', 'load'
        ],
        'color': '#fd7e14'  # Orange
    },
    'INTEGRATION': {
        'name': 'Integration & APIs',
        'description': 'APIs, connectors, third-party integrations, data flow',
        'keywords': [
            'api', 'integration', 'connector', 'connect', 'third-party', 'external',
            'webhook', 'rest', 'graphql', 'endpoint', 'data flow', 'etl', 'pipeline',
            'sync', 'synchronization', 'import', 'export', 'federation'
        ],
        'color': '#17a2b8'  # Cyan
    },
    'ANALYTICS': {
        'name': 'Analytics & Reporting',
        'description': 'Business intelligence, reporting, dashboards, metrics, insights',
        'keywords': [
            'analytics', 'reporting', 'report', 'dashboard', 'visualization', 'chart',
            'metric', 'kpi', 'insight', 'business intelligence', 'bi', 'data analysis',
            'trending', 'statistics', 'aggregation', 'summary', 'drill-down'
        ],
        'color': '#ffc107'  # Yellow
    }
}

# Table Schema
TABLE_COLUMNS = [
    'Feedback_ID',  # NEW: Unique identifier for each feedback item
    'Feedback_Gist',
    'Feedback',
    'Area',
    'Sources',
    'Impacttype',
    'Scenario',
    'Category',  # Legacy category field for backward compatibility
    'Enhanced_Category',  # New primary category
    'Subcategory',  # New subcategory field
    'Audience',  # Developer/Customer/ISV classification
    'Priority',  # Priority level (critical/high/medium/low)
    'Feature_Area',  # Feature area classification
    'Categorization_Confidence',  # Confidence score for categorization
    'Domains',  # Cross-cutting domain concerns (JSON array)
    'Primary_Domain',  # Primary domain classification
    'State',  # NEW: Current state of feedback (New, Triaged, Closed, Irrelevant)
    'Feedback_Notes',  # NEW: Notes about the feedback
    'Last_Updated',  # NEW: When the state was last changed
    'Updated_By',  # NEW: Who made the last change (extracted from bearer token)
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
    "ISV",
    "FET",
    "Fabric Extensibility Toolkit"
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

# Categories and Impact Types file paths
CATEGORIES_FILE = os.path.join(os.path.dirname(__file__), 'categories.json')
IMPACT_TYPES_FILE = os.path.join(os.path.dirname(__file__), 'impact_types.json')

def save_categories(categories_to_save):
    """Save custom categories configuration to JSON file."""
    try:
        with open(CATEGORIES_FILE, 'w') as f:
            json.dump(categories_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving categories to '{CATEGORIES_FILE}': {e}")

def load_categories():
    """Load categories configuration from JSON file, or use defaults."""
    if os.path.exists(CATEGORIES_FILE):
        try:
            with open(CATEGORIES_FILE, 'r') as f:
                content = f.read()
                if not content.strip():
                    print(f"Warning: '{CATEGORIES_FILE}' is empty. Using default categories and saving them to the file.")
                    save_categories(DEFAULT_ENHANCED_FEEDBACK_CATEGORIES)
                    return DEFAULT_ENHANCED_FEEDBACK_CATEGORIES.copy()
                loaded_cats = json.loads(content)
                if isinstance(loaded_cats, dict):
                    return loaded_cats
                else:
                    print(f"Warning: Content of '{CATEGORIES_FILE}' is not a dict. Using default categories and overwriting the file.")
                    save_categories(DEFAULT_ENHANCED_FEEDBACK_CATEGORIES)
                    return DEFAULT_ENHANCED_FEEDBACK_CATEGORIES.copy()
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from '{CATEGORIES_FILE}': {e}. Overwriting with default categories.")
            save_categories(DEFAULT_ENHANCED_FEEDBACK_CATEGORIES)
            return DEFAULT_ENHANCED_FEEDBACK_CATEGORIES.copy()
        except Exception as e:
            print(f"Unexpected error loading '{CATEGORIES_FILE}': {e}. Using default categories for this session.")
            try:
                save_categories(DEFAULT_ENHANCED_FEEDBACK_CATEGORIES)
            except Exception as save_e:
                print(f"Could not save default categories to '{CATEGORIES_FILE}' after load error: {save_e}")
            return DEFAULT_ENHANCED_FEEDBACK_CATEGORIES.copy()
    else:
        print(f"'{CATEGORIES_FILE}' not found. Creating with default categories.")
        save_categories(DEFAULT_ENHANCED_FEEDBACK_CATEGORIES)
        return DEFAULT_ENHANCED_FEEDBACK_CATEGORIES.copy()

def save_impact_types(impact_types_to_save):
    """Save custom impact types configuration to JSON file."""
    try:
        with open(IMPACT_TYPES_FILE, 'w') as f:
            json.dump(impact_types_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving impact types to '{IMPACT_TYPES_FILE}': {e}")

def load_impact_types():
    """Load impact types configuration from JSON file, or use defaults."""
    if os.path.exists(IMPACT_TYPES_FILE):
        try:
            with open(IMPACT_TYPES_FILE, 'r') as f:
                content = f.read()
                if not content.strip():
                    print(f"Warning: '{IMPACT_TYPES_FILE}' is empty. Using default impact types and saving them to the file.")
                    save_impact_types(IMPACT_TYPES)
                    return IMPACT_TYPES.copy()
                loaded_types = json.loads(content)
                if isinstance(loaded_types, dict):
                    return loaded_types
                else:
                    print(f"Warning: Content of '{IMPACT_TYPES_FILE}' is not a dict. Using default impact types and overwriting the file.")
                    save_impact_types(IMPACT_TYPES)
                    return IMPACT_TYPES.copy()
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from '{IMPACT_TYPES_FILE}': {e}. Overwriting with default impact types.")
            save_impact_types(IMPACT_TYPES)
            return IMPACT_TYPES.copy()
        except Exception as e:
            print(f"Unexpected error loading '{IMPACT_TYPES_FILE}': {e}. Using default impact types for this session.")
            try:
                save_impact_types(IMPACT_TYPES)
            except Exception as save_e:
                print(f"Could not save default impact types to '{IMPACT_TYPES_FILE}' after load error: {save_e}")
            return IMPACT_TYPES.copy()
    else:
        print(f"'{IMPACT_TYPES_FILE}' not found. Creating with default impact types.")
        save_impact_types(IMPACT_TYPES)
        return IMPACT_TYPES.copy()

# Initialize categories and impact types - loaded once when module is imported
ENHANCED_FEEDBACK_CATEGORIES = load_categories()
IMPACT_TYPES_CONFIG = load_impact_types()

# Source URLs
MS_FABRIC_COMMUNITY_URL = "https://community.fabric.microsoft.com/t5/Fabric-platform-forums/ct-p/AC-Community"
REDDIT_SUBREDDIT = "MicrosoftFabric"
GITHUB_REPO_OWNER = "microsoft"
GITHUB_REPO_NAME = "Microsoft-Fabric-workload-development-sample"

# Additional GitHub Repositories (can be configured in web interface)
# Format: list of dicts with 'owner' and 'repo' keys
ADDITIONAL_GITHUB_REPOS = [
    # Examples:
    # {'owner': 'microsoft', 'repo': 'fabric-samples'},
    # {'owner': 'microsoft', 'repo': 'powerbi-desktop'},
]

# Feedback State Management Configuration
FEEDBACK_STATES = {
    'NEW': {
        'name': 'New',
        'description': 'Newly collected feedback that hasn\'t been reviewed',
        'color': '#6c757d',  # Gray
        'default': True
    },
    'TRIAGED': {
        'name': 'Triaged',
        'description': 'Feedback that has been reviewed and categorized',
        'color': '#007bff',  # Blue
        'default': False
    },
    'CLOSED': {
        'name': 'Closed',
        'description': 'Feedback that has been addressed and resolved',
        'color': '#28a745',  # Green
        'default': False
    },
    'IRRELEVANT': {
        'name': 'Irrelevant',
        'description': 'Feedback that doesn\'t apply to the product scope',
        'color': '#dc3545',  # Red
        'default': False
    }
}

# Default state for new feedback
DEFAULT_FEEDBACK_STATE = 'NEW'
# Processing Configuration
MAX_ITEMS_PER_RUN = 500
DEFAULT_STATUS = "New"
SYSTEM_USER = "FeedbackCollector"
