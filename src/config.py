import os
import sys
from dotenv import load_dotenv
import json # Ensure json is imported

# Determine the correct path for .env file
if getattr(sys, 'frozen', False):
    # Running as compiled executable - .env must be next to FeedbackCollector.exe
    application_path = os.path.dirname(sys.executable)
    env_path = os.path.join(application_path, '.env')
    if os.path.exists(env_path):
        print(f"✅ Found .env file at: {env_path}")
    else:
        print(f"⚠️ .env file not found. Place your .env file next to FeedbackCollector.exe at: {env_path}")
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
            },
            'AGENTIC_EXPERIENCES': {
                'name': 'Agentic Experiences',
                'keywords': [
                    'copilot', 'knowledge base', 'instructions', 'instruction',
                    'agent', 'agentic', 'ai agent', 'autonomous agent', 'multi-agent',
                    'grounding', 'rag', 'retrieval augmented',
                    'system prompt', 'prompt engineering', 'orchestration',
                    'function calling', 'tool use',
                    'generative ai', 'gen ai', 'model endpoint',
                    'ai assumed', 'ai guidance', 'ai instruction',
                    'ai coding', 'ai implementation',
                    'hallucinate', 'hallucination',
                    'guidance to ai', 'questions to ask'
                ],
                'priority': 'high',
                'feature_area': 'Agentic AI'
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
            'retention', 'classification', 'data classification', 'metadata', 'catalog',
            'purview', 'unified catalog', 'data steward', 'data owner'
        ],
        'color': '#6f42c1'  # Purple
    },
    'USER_EXPERIENCE': {
        'name': 'User Experience',
        'description': 'UI/UX design, usability, accessibility, user workflows',
        'keywords': [
            'user experience', 'ux', 'interface', 'usability', 'accessibility',
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
            'token', 'oauth', 'saml', 'azure ad', 'active directory', 'mfa',
            'row level security', 'rls', 'cls', 'object level security'
        ],
        'color': '#dc3545'  # Red
    },
    'PERFORMANCE': {
        'name': 'Performance & Scalability',
        'description': 'Speed, scalability, optimization, resource usage, latency',
        'keywords': [
            'performance', 'speed', 'slow', 'fast', 'scalability', 'scale', 'optimization',
            'latency', 'response time', 'throughput', 'memory', 'cpu', 'resource',
            'timeout', 'lag', 'delay', 'bottleneck'
        ],
        'color': '#fd7e14'  # Orange
    },
    'INTEGRATION': {
        'name': 'Integration & APIs',
        'description': 'APIs, connectors, third-party integrations, data flow',
        'keywords': [
            'api', 'integration', 'connector', 'third-party', 'external',
            'webhook', 'rest api', 'graphql', 'endpoint', 'data flow',
            'sync', 'synchronization', 'federation', 'sharepoint', 'teams'
        ],
        'color': '#17a2b8'  # Cyan
    },
    'POWER_BI': {
        'name': 'Power BI',
        'description': 'Power BI reports, semantic models, DAX, Direct Lake, visuals, embedding',
        'keywords': [
            'power bi', 'pbi', 'semantic model', 'direct lake', 'dax', 'measure',
            'report', 'dashboard', 'visual', 'visualization', 'pbip', 'tmdl',
            'tabular editor', 'report builder', 'paginated', 'embed', 'embedding',
            'power bi copilot', 'copilot visual', 'smart narrative', 'q&a'
        ],
        'color': '#ffc107'  # Yellow
    },
    'DEVTOOLS': {
        'name': 'Developer Tooling',
        'description': 'VS Code extensions, IDE integrations, Fabric CLI, notebooks-as-code, dbt',
        'keywords': [
            'vs code', 'vscode', 'ide', 'fabric extension', 'fabric cli',
            'notebook vs code', 'live edit', 'local development', 'devcontainer',
            'dbt', 'dbt fabric', 'spark job definition', 'user data function',
            'fabric data engineering extension', 'synapse extension',
            'visual studio', 'intellisense', 'debugging', 'breakpoint'
        ],
        'color': '#007bff'  # Blue
    },
    'CICD': {
        'name': 'CI/CD & Deployment',
        'description': 'Deployment pipelines, Azure DevOps, GitHub Actions, fabric-cicd, git integration',
        'keywords': [
            'ci/cd', 'cicd', 'deployment pipeline', 'azure devops', 'ado',
            'github actions', 'fabric-cicd', 'fabric cicd', 'git integration',
            'git sync', 'source control', 'version control', 'yaml pipeline',
            'deployment', 'release pipeline', 'build pipeline', 'continuous integration',
            'continuous deployment', 'automated deployment'
        ],
        'color': '#a45b91'  # Magenta
    },
    'LICENSING': {
        'name': 'Licensing & Cost',
        'description': 'Pricing, capacity sizing, SKUs, PAYG, Pro/Free licensing, cost management',
        'keywords': [
            'pricing', 'cost', 'license', 'licensing', 'sku', 'capacity',
            'pay as you go', 'payg', 'f2', 'f4', 'f8', 'f16', 'f32', 'f64',
            'pro license', 'free license', 'premium', 'ppu',
            'billing', 'meter', 'cu', 'compute unit', 'cost management',
            'cost analysis', 'cost allocation', 'budget'
        ],
        'color': '#6c757d'  # Gray
    },
    'DATA_PLATFORM': {
        'name': 'Data Platform',
        'description': 'Lakehouse, Warehouse, OneLake, Spark, Delta, medallion architecture, data engineering',
        'keywords': [
            'lakehouse', 'warehouse', 'onelake', 'delta lake', 'delta table',
            'spark', 'pyspark', 'medallion', 'bronze', 'silver', 'gold',
            'data engineering', 'data pipeline', 'etl', 'elt', 'dataflow',
            'eventstream', 'eventhouse', 'kql', 'real-time intelligence',
            'shortcut', 'mirroring', 'sql analytics endpoint'
        ],
        'color': '#60919f'  # Slate
    }
}

# Workload Categories - official Microsoft Fabric workloads
WORKLOAD_CATEGORIES = {
    'POWER_BI': {
        'name': 'Power BI',
        'description': 'Find insights, track progress, and make decisions faster using rich visualizations',
        'keywords': [
            'power bi', 'pbi', 'semantic model', 'dataset', 'direct lake',
            'dax', 'measure', 'calculated column', 'report', 'dashboard',
            'visual', 'visualization', 'chart', 'slicer', 'filter',
            'paginated report', 'report builder', 'pbix', 'pbip', 'tmdl',
            'tabular editor', 'embed', 'embedding', 'power bi service',
            'power bi desktop', 'power bi copilot', 'copilot visual',
            'smart narrative', 'q&a', 'decomposition tree',
            'import mode', 'directquery', 'composite model',
            'row level security', 'rls', 'power bi gateway',
            'power bi premium', 'power bi pro', 'power bi free',
            'power bi mobile', 'power bi app', 'power bi workspace',
            'datamart'
        ],
        'color': '#F2C811'  # Power BI Yellow
    },
    'DATA_ENGINEERING': {
        'name': 'Data Engineering',
        'description': 'Create a lakehouse and operationalize your workflow to build, transform, and share your data estate',
        'keywords': [
            'lakehouse', 'notebook', 'spark', 'pyspark', 'delta lake',
            'delta table', 'medallion', 'bronze', 'silver', 'gold',
            'data engineering', 'spark job', 'spark job definition',
            'v-order', 'optimize', 'vacuum', 'merge', 'z-order',
            'spark session', 'spark pool', 'spark cluster',
            'scala', 'spark sql', 'spark streaming',
            'lakehouse sql endpoint', 'table maintenance',
            'user data function', 'udf',
            'onelake', 'shortcut', 'mirroring',
            'onelake file explorer', 'onelake storage',
            'delta', 'parquet', 'iceberg'
        ],
        'color': '#0078D4'  # Azure Blue
    },
    'DATA_FACTORY': {
        'name': 'Data Factory',
        'description': 'Solve complex data ingestion, transformation, and orchestration scenarios using cloud-scale data movement and transformation services',
        'keywords': [
            'data factory', 'pipeline', 'dataflow', 'dataflow gen2',
            'copy activity', 'data orchestration', 'data integration',
            'for each', 'foreach', 'lookup activity', 'web activity',
            'get metadata', 'if condition', 'switch activity',
            'data movement', 'copy job', 'pipeline run',
            'pipeline schedule', 'trigger', 'tumbling window',
            'incremental refresh', 'incremental load', 'watermark',
            'connector', 'on-premises data gateway', 'gateway',
            'etl', 'elt', 'data flow'
        ],
        'color': '#4CA6A8'  # Factory Teal
    },
    'DATA_SCIENCE': {
        'name': 'Data Science',
        'description': 'Unlock powerful insights using AI and machine learning technology',
        'keywords': [
            'data science', 'machine learning', 'ml model', 'mlflow',
            'experiment', 'prediction', 'training', 'inference',
            'scikit-learn', 'sklearn', 'synapseml', 'model registry',
            'model deployment', 'batch prediction', 'feature engineering',
            'automl', 'deep learning', 'neural network', 'pytorch',
            'tensorflow', 'model scoring', 'predict'
        ],
        'color': '#E8488B'  # Science Pink
    },
    'DATA_WAREHOUSE': {
        'name': 'Data Warehouse',
        'description': 'Scale up your insights by storing and analyzing data in a secure SQL warehouse with top-tier performance at petabyte scale in an open-data format',
        'keywords': [
            'data warehouse', 'warehouse', 'synapse warehouse',
            't-sql', 'tsql', 'sql endpoint', 'sql analytics endpoint',
            'cross-database', 'cross database query', 'stored procedure',
            'table clone', 'ingestion', 'ctas', 'insert into',
            'warehouse performance', 'warehouse capacity',
            'ingest', 'warehouse table', 'warehouse schema',
            'data warehousing', 'dw', 'star schema', 'fact table',
            'dimension table'
        ],
        'color': '#5B5FC7'  # Warehouse Purple
    },
    'DATABASES': {
        'name': 'Databases',
        'description': 'Create operational databases seamlessly for transactional workloads',
        'keywords': [
            'sql database', 'fabric sql database', 'sql db',
            'mirrored database', 'mirrored cosmos', 'mirrored sql',
            'mirrored snowflake', 'mirrored postgres',
            'cosmos db', 'postgresql', 'mysql', 'snowflake mirror',
            'database mirroring', 'azure sql', 'sql server',
            'fabric database', 'operational database', 'transactional',
            'oltp'
        ],
        'color': '#2E86AB'  # Database Blue
    },
    'GRAPH': {
        'name': 'Graph',
        'description': 'Visualize your data with a Graph to drive deeper insights and reveal richer context at lightning speed',
        'keywords': [
            'graph', 'graph database', 'knowledge graph', 'graph analytics',
            'graph visualization', 'graph query', 'graph model',
            'graph insight', 'graph context', 'relationship graph',
            'node', 'edge', 'graph traversal', 'cypher',
            'fabric graph', 'graph workload'
        ],
        'color': '#2D9B83'  # Graph Green
    },
    'INDUSTRY_SOLUTIONS': {
        'name': 'Industry Solutions',
        'description': 'Use out-of-the-box industry data solutions and resources',
        'keywords': [
            'industry solution', 'industry solutions', 'industry data',
            'healthcare', 'retail', 'financial services', 'sustainability',
            'manufacturing', 'energy', 'supply chain',
            'industry template', 'out-of-the-box', 'industry accelerator',
            'vertical solution', 'industry vertical',
            'fabric industry', 'prebuilt solution'
        ],
        'color': '#4B8BBE'  # Industry Blue
    },
    'IQ': {
        'name': 'IQ',
        'description': 'Create a unified semantic layer that organizes your core business concepts and rules, connects them to OneLake data and existing semantic models',
        'keywords': [
            'fabric iq', 'iq', 'unified semantic layer', 'business concept',
            'business rule', 'semantic layer', 'business glossary',
            'data mesh', 'domain model', 'business ontology'
        ],
        'color': '#7B68EE'  # IQ Medium Slate Blue
    },
    'COPILOT_AI': {
        'name': 'Copilot & AI',
        'description': 'AI-powered experiences across Fabric including Copilot, Data Agents, AI Skills, and foundational AI infrastructure',
        'keywords': [
            'copilot', 'copilot for fabric', 'fabric copilot',
            'copilot notebook', 'copilot sql', 'copilot dax', 'copilot report',
            'copilot visual', 'copilot chat',
            'data agent', 'fabric data agent', 'ai agent',
            'foundry agent', 'ai foundry',
            'ai skill', 'ai skills',
            'text to sql', 'text-to-sql', 'natural language query',
            'natural language', 'ai assistant', 'ai chat',
            'llm', 'gpt', 'azure openai', 'openai', 'prompt', 'ai-powered',
            'mcp', 'model context protocol', 'mcp server',
            'fabric mcp', 'power bi mcp'
        ],
        'color': '#9B59B6'  # AI Purple
    },
    'FABRIC_PLATFORM': {
        'name': 'Fabric Platform',
        'description': 'Core Fabric platform capabilities including capacity management, administration, governance, and lifecycle management',
        'keywords': [
            'fabric platform', 'fabric admin', 'admin portal',
            'capacity', 'capacity unit', 'capacity units', 'fabric capacity',
            'f sku', 'tenant', 'tenant settings',
            'governance', 'purview', 'information protection', 'sensitivity label',
            'monitoring hub', 'capacity metrics', 'billing', 'cost management',
            'pricing', 'license', 'licensing', 'fabric trial', 'trial capacity',
            'git integration', 'deployment pipeline', 'cicd', 'ci/cd',
            'lifecycle management', 'alm', 'domains', 'endorsement',
            'lineage', 'impact analysis', 'fabric rest api', 'rest api',
            'workspace settings', 'workspace identity', 'managed identity',
            'fabric api', 'fabric sdk'
        ],
        'color': '#1A1A2E'  # Platform Dark Navy
    },
    'REAL_TIME_INTELLIGENCE': {
        'name': 'Real-Time Intelligence',
        'description': 'Discover insights from your streaming data. Quickly ingest, index, and partition any data source or format, then query the data and create visualizations',
        'keywords': [
            'real-time intelligence', 'real time intelligence', 'rti',
            'eventhouse', 'kql', 'kusto', 'kql database', 'kql queryset',
            'eventstream', 'event stream', 'real-time hub', 'real time hub',
            'data activator', 'reflex', 'real-time dashboard',
            'real-time analytics', 'streaming', 'event processing',
            'kafka', 'event hub', 'eventhub', 'iot', 'time series',
            'kql function', 'materialized view'
        ],
        'color': '#FF6F61'  # Coral Red
    }
}

# Table Schema
TABLE_COLUMNS = [
    'Feedback_ID',  # NEW: Unique identifier for each feedback item
    'Title',  # Thread/post title (preserved from source)
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
    'Workloads',  # Fabric workloads addressed by this feedback (JSON array)
    'Primary_Workload',  # Primary Fabric workload classification
    'Matched_Keywords',  # Keywords that matched this feedback (JSON array)
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
    "Workload Development Kit",
    "WDK",
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

# ─── Active Project Configuration ───────────────────────────────
# The active project ID controls which taxonomy, keywords, and database are used.
# Changed at runtime via API or UI project switcher.
ACTIVE_PROJECT_ID = 'copilot_ai_experiences'  # Default project: Copilot & AI Experiences

def get_active_project_id():
    """Get the currently active project ID."""
    return ACTIVE_PROJECT_ID

def set_active_project(project_id):
    """Switch the active project, reloading taxonomy into global config variables.
    
    IMPORTANT: We mutate lists/dicts in-place rather than reassigning, because
    other modules (e.g. utils.py) hold references obtained via 'from config import X'.
    Reassigning would leave those modules with stale references.
    
    Args:
        project_id: Project ID to activate, or None for legacy mode.
    """
    global ACTIVE_PROJECT_ID
    
    if project_id is None:
        # Revert to legacy mode
        ACTIVE_PROJECT_ID = None
        KEYWORDS.clear()
        KEYWORDS.extend(load_keywords())
        ENHANCED_FEEDBACK_CATEGORIES.clear()
        ENHANCED_FEEDBACK_CATEGORIES.update(load_categories())
        IMPACT_TYPES_CONFIG.clear()
        IMPACT_TYPES_CONFIG.update(load_impact_types())
        print(f"🔄 Switched to legacy mode (global config)")
        return
    
    import project_manager as pm
    try:
        project_data = pm.load_project(project_id)
        
        ACTIVE_PROJECT_ID = project_id
        KEYWORDS.clear()
        KEYWORDS.extend(project_data['keywords'])
        ENHANCED_FEEDBACK_CATEGORIES.clear()
        ENHANCED_FEEDBACK_CATEGORIES.update(project_data['categories'])
        IMPACT_TYPES_CONFIG.clear()
        IMPACT_TYPES_CONFIG.update(project_data['impact_types'])
        
        # Apply per-project audience config if available
        audience_cfg = project_data.get('audience_config')
        if audience_cfg and 'audiences' in audience_cfg:
            AUDIENCE_DETECTION_KEYWORDS.clear()
            AUDIENCE_DETECTION_KEYWORDS.update(audience_cfg['audiences'])
            print(f"   Audience config: {list(AUDIENCE_DETECTION_KEYWORDS.keys())} (project-specific)")
        else:
            # Reset to default audience keywords
            AUDIENCE_DETECTION_KEYWORDS.clear()
            AUDIENCE_DETECTION_KEYWORDS.update({
                'Developer': [
                    'wdk', 'sdk', 'development kit', 'api', 'develop', 'developing', 'developer',
                    'code', 'programming', 'build', 'compile', 'debug', 'visual studio', 'ide',
                    'git', 'version control', 'deployment', 'testing', 'unit test',
                    'devgateway', 'dev gateway', 'developer gateway', 'dev portal', 'developer portal',
                    'dev tools', 'developer tools', 'development tools', 'cicd', 'ci/cd',
                    'continuous integration', 'continuous deployment', 'azure devops', 'ado',
                    'github', 'source control', 'npm', 'nuget', 'package manager', 'maven',
                    'gradle', 'pip', 'conda', 'frontend', 'backend',
                    'workload development sample', 'fabric wdk', 'quickstart'
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
            })
        
        print(f"🔄 Switched to project: {project_id} "
              f"({len(KEYWORDS)} keywords, {len(ENHANCED_FEEDBACK_CATEGORIES)} categories)")
    except Exception as e:
        print(f"❌ Error switching to project {project_id}: {e}")
        raise

def get_active_db_config():
    """Get database config for the active project, or fallback to env vars."""
    if ACTIVE_PROJECT_ID:
        import project_manager as pm
        return pm.get_project_db_config(ACTIVE_PROJECT_ID)
    
    # Legacy mode - use env vars
    return {
        'server': FABRIC_SQL_SERVER,
        'database_name': FABRIC_SQL_DATABASE,
        'authentication': FABRIC_SQL_AUTHENTICATION,
    }

def get_active_sources():
    """Get source configuration for the active project, or None for legacy."""
    if ACTIVE_PROJECT_ID:
        import project_manager as pm
        return pm.get_project_sources(ACTIVE_PROJECT_ID)
    return None
