from flask import Flask, render_template, request, jsonify, send_from_directory, current_app
import pandas as pd
import os
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple
import json

from collectors import RedditCollector, FabricCommunityCollector, GitHubDiscussionsCollector, GitHubIssuesCollector
from ado_client import get_working_ado_items
import config
import utils
import state_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'feedback_collector_secret_key_2025'  # For session management

last_collected_feedback = []
last_collection_summary = {"reddit": 0, "fabric": 0, "github": 0, "github_issues": 0, "total": 0}

# Collection progress tracking
collection_status = {
    'status': 'ready',  # ready, running, completed, error
    'message': 'Ready to start collection',
    'start_time': None,
    'end_time': None,
    'total_items': 0,
    'current_source': None,
    'sources_completed': [],
    'error_message': None
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    logger.info(f"Created data directory: {DATA_DIR}")

def load_latest_feedback_from_csv():
    """Load feedback from the most recent CSV file if in-memory data is empty"""
    try:
        # Get all CSV files in the data directory
        csv_files = [f for f in os.listdir(DATA_DIR) if f.startswith('feedback_') and f.endswith('.csv')]
        if not csv_files:
            return []
        
        # Sort by filename (which includes timestamp) to get the latest
        latest_file = sorted(csv_files)[-1]
        filepath = os.path.join(DATA_DIR, latest_file)
        
        logger.info(f"Loading feedback from CSV: {filepath}")
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # Replace NaN with None to avoid JSON serialization issues and sorting errors
        df = df.where(pd.notnull(df), None)
        
        # Convert DataFrame to list of dictionaries
        feedback_items = df.to_dict('records')
        
        # Parse Matched_Keywords from string to list
        import ast
        for item in feedback_items:
            if 'Matched_Keywords' in item:
                try:
                    # Convert string representation of list back to actual list
                    if isinstance(item['Matched_Keywords'], str):
                        item['Matched_Keywords'] = ast.literal_eval(item['Matched_Keywords'])
                    elif pd.isna(item['Matched_Keywords']):
                        item['Matched_Keywords'] = []
                except (ValueError, SyntaxError):
                    item['Matched_Keywords'] = []
        
        logger.info(f"Loaded {len(feedback_items)} items from CSV")
        
        return feedback_items
    except Exception as e:
        logger.error(f"Error loading feedback from CSV: {e}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/insights')
def insights_page():
    return render_template('insights_page.html',
                         powerbi_report_id=config.POWERBI_REPORT_ID,
                         powerbi_tenant_id=config.POWERBI_TENANT_ID,
                         powerbi_embed_base_url=config.POWERBI_EMBED_BASE_URL)

@app.route('/api/keywords', methods=['GET', 'POST'])
def manage_keywords_route():
    if request.method == 'GET':
        keywords = config.load_keywords()
        return jsonify(keywords)
    elif request.method == 'POST':
        try:
            data = request.get_json()
            if data is None or 'keywords' not in data or not isinstance(data['keywords'], list):
                return jsonify({'status': 'error', 'message': 'Invalid keywords data. Expected a list.'}), 400
            
            valid_keywords = [str(k).strip() for k in data['keywords'] if str(k).strip()]
            
            config.save_keywords(valid_keywords)
            config.KEYWORDS = valid_keywords.copy() 
            logger.info(f"Keywords updated and saved: {valid_keywords}")
            return jsonify({'status': 'success', 'keywords': valid_keywords, 'message': 'Keywords saved successfully.'})
        except Exception as e:
            logger.error(f"Error saving keywords: {e}", exc_info=True)
            return jsonify({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/keywords/restore_default', methods=['POST'])
def restore_default_keywords_route():
    try:
        default_keywords = config.DEFAULT_KEYWORDS
        config.save_keywords(default_keywords)
        config.KEYWORDS = default_keywords.copy()
        logger.info(f"Default keywords restored and saved: {default_keywords}")
        return jsonify({'status': 'success', 'keywords': default_keywords, 'message': 'Default keywords restored and saved.'})
    except Exception as e:
        logger.error(f"Error restoring default keywords: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/categories', methods=['GET', 'POST'])
def manage_categories_route():
    """API endpoint for managing feedback categories."""
    if request.method == 'GET':
        categories = config.load_categories()
        return jsonify({'status': 'success', 'categories': categories})
    elif request.method == 'POST':
        try:
            data = request.get_json()
            if data is None or not isinstance(data, dict):
                return jsonify({'status': 'error', 'message': 'Invalid categories data. Expected a dictionary.'}), 400
            
            # Validate structure - each category must have required fields
            for category_id, category_data in data.items():
                if not isinstance(category_data, dict):
                    return jsonify({'status': 'error', 'message': f'Invalid category data for {category_id}.'}), 400
                if 'name' not in category_data or 'subcategories' not in category_data:
                    return jsonify({'status': 'error', 'message': f'Category {category_id} missing required fields.'}), 400
                if not isinstance(category_data['subcategories'], dict):
                    return jsonify({'status': 'error', 'message': f'Subcategories for {category_id} must be a dictionary.'}), 400
            
            config.save_categories(data)
            config.ENHANCED_FEEDBACK_CATEGORIES = data.copy()
            logger.info(f"Categories updated and saved with {len(data)} categories")
            return jsonify({'status': 'success', 'categories': data, 'message': 'Categories saved successfully.'})
        except Exception as e:
            logger.error(f"Error saving categories: {e}", exc_info=True)
            return jsonify({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/categories/restore_default', methods=['POST'])
def restore_default_categories_route():
    """Restore default categories configuration."""
    try:
        default_categories = config.DEFAULT_ENHANCED_FEEDBACK_CATEGORIES
        config.save_categories(default_categories)
        config.ENHANCED_FEEDBACK_CATEGORIES = default_categories.copy()
        logger.info(f"Default categories restored and saved")
        return jsonify({'status': 'success', 'categories': default_categories, 'message': 'Default categories restored and saved.'})
    except Exception as e:
        logger.error(f"Error restoring default categories: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/impact-types', methods=['GET', 'POST'])
def manage_impact_types_route():
    """API endpoint for managing impact types."""
    if request.method == 'GET':
        impact_types = config.load_impact_types()
        return jsonify({'status': 'success', 'impact_types': impact_types})
    elif request.method == 'POST':
        try:
            data = request.get_json()
            if data is None or not isinstance(data, dict):
                return jsonify({'status': 'error', 'message': 'Invalid impact types data. Expected a dictionary.'}), 400
            
            # Validate structure - each impact type must have required fields
            for impact_id, impact_data in data.items():
                if not isinstance(impact_data, dict):
                    return jsonify({'status': 'error', 'message': f'Invalid impact type data for {impact_id}.'}), 400
                if 'name' not in impact_data or 'keywords' not in impact_data:
                    return jsonify({'status': 'error', 'message': f'Impact type {impact_id} missing required fields.'}), 400
                if not isinstance(impact_data['keywords'], list):
                    return jsonify({'status': 'error', 'message': f'Keywords for {impact_id} must be a list.'}), 400
            
            config.save_impact_types(data)
            config.IMPACT_TYPES_CONFIG = data.copy()
            logger.info(f"Impact types updated and saved with {len(data)} types")
            return jsonify({'status': 'success', 'impact_types': data, 'message': 'Impact types saved successfully.'})
        except Exception as e:
            logger.error(f"Error saving impact types: {e}", exc_info=True)
            return jsonify({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/impact-types/restore_default', methods=['POST'])
def restore_default_impact_types_route():
    """Restore default impact types configuration."""
    try:
        default_impact_types = config.IMPACT_TYPES
        config.save_impact_types(default_impact_types)
        config.IMPACT_TYPES_CONFIG = default_impact_types.copy()
        logger.info(f"Default impact types restored and saved")
        return jsonify({'status': 'success', 'impact_types': default_impact_types, 'message': 'Default impact types restored and saved.'})
    except Exception as e:
        logger.error(f"Error restoring default impact types: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/collect', methods=['POST'])
def collect_feedback_route():
    """Enhanced collection route with source configuration support"""
    global last_collected_feedback, last_collection_summary, collection_status
    last_collected_feedback = []
    
    logger.info("🚀 COLLECTION STARTED: Beginning feedback collection process")
    
    # Completely reset collection status to running (clears all old values)
    collection_status.clear()
    collection_status.update({
        'status': 'running',
        'message': 'Collection in progress...',
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'total_items': 0,
        'current_source': 'Initializing',
        'sources_completed': [],
        'error_message': None,
        'progress': 0,
        'source_counts': {}
    })
    
    try:
        logger.info("Starting enhanced feedback collection process via API.")
        
        # Get configuration from request
        config = {}
        if request.is_json:
            config = request.get_json() or {}
        
        # Extract source configurations
        source_configs = config.get('sources', {})
        settings = config.get('settings', {})
        
        # Check if we're in online mode (connected to Fabric)
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        is_online_mode = stored_token and stored_token.strip() and stored_token != 'None'
        
        logger.info(f"🔍 COLLECTION MODE CHECK: {'ONLINE' if is_online_mode else 'OFFLINE'} - Token: {'Present' if stored_token else 'None'}")
        # Count enabled sources for progress tracking
        enabled_sources = [k for k, v in source_configs.items() if v.get('enabled', False)]
        total_sources = len(enabled_sources)
        
        # Prevent division by zero
        if total_sources == 0:
            logger.warning("No sources enabled for collection")
            collection_status.update({
                'status': 'error',
                'message': 'No sources enabled for collection',
                'end_time': datetime.now().isoformat(),
                'error_message': 'Please enable at least one data source'
            })
            return jsonify({"error": "No sources enabled for collection"}), 400
        
        logger.info(f"📋 COLLECTION CONFIG: {total_sources} sources enabled: {enabled_sources}")
        
        # Reload keywords, categories, and impact types from files before collection
        # This ensures we use the latest configuration set via the web UI
        import config as cfg
        cfg.KEYWORDS = cfg.load_keywords()
        cfg.ENHANCED_FEEDBACK_CATEGORIES = cfg.load_categories()
        cfg.IMPACT_TYPES_CONFIG = cfg.load_impact_types()
        logger.info(f"🔄 Reloaded config - Keywords: {len(cfg.KEYWORDS)}, Categories: {len(cfg.ENHANCED_FEEDBACK_CATEGORIES)}, Impact Types: {len(cfg.IMPACT_TYPES_CONFIG)}")
        logger.info(f"📝 Current keywords: {cfg.KEYWORDS}")
        
        all_feedback = []
        results = {}
        
        # Initialize all feedback variables to empty lists
        reddit_feedback = []
        fabric_feedback = []
        github_feedback = []
        github_issues_feedback = []
        ado_feedback = []
        
        # Collect from Reddit if enabled
        if source_configs.get('reddit', {}).get('enabled', False):
            collection_status['current_source'] = 'Reddit'
            collection_status['message'] = 'Collecting from Reddit...'
            reddit_config = source_configs['reddit']
            logger.info(f"🔴 REDDIT: Collecting from r/{reddit_config.get('subreddit', 'MicrosoftFabric')}")
            
            reddit_collector = RedditCollector()
            
            # Pass configuration to collector if it supports it
            if hasattr(reddit_collector, 'configure'):
                reddit_collector.configure({
                    'subreddit': reddit_config.get('subreddit', 'MicrosoftFabric'),
                    'sort': reddit_config.get('sort', 'new'),
                    'time_filter': reddit_config.get('timeFilter', 'month'),
                    'max_items': reddit_config.get('maxItems', 200)
                })
            
            reddit_feedback = reddit_collector.collect()
            logger.info(f"Reddit collector found {len(reddit_feedback)} items.")
            collection_status['sources_completed'].append('Reddit')
            if total_sources > 0:
                collection_status['progress'] = (len(collection_status['sources_completed']) / total_sources) * 100
            # Add source counts for real-time updates
            collection_status['source_counts'] = collection_status.get('source_counts', {})
            collection_status['source_counts']['reddit'] = len(reddit_feedback)
            all_feedback.extend(reddit_feedback)
            results['reddit'] = {'count': len(reddit_feedback), 'completed': True}
        
        # Collect from Fabric Community if enabled
        if source_configs.get('fabricCommunity', {}).get('enabled', False):
            collection_status['current_source'] = 'Fabric Community'
            collection_status['message'] = 'Collecting from Fabric Community...'
            fabric_config = source_configs['fabricCommunity']
            logger.info(f"🔷 FABRIC COMMUNITY: Collecting feedback")
            
            fabric_collector = FabricCommunityCollector()
            
            # Pass configuration to collector if it supports it
            if hasattr(fabric_collector, 'configure'):
                fabric_collector.configure({
                    'max_items': fabric_config.get('maxItems', 200)
                })
            
            fabric_feedback = fabric_collector.collect()
            logger.info(f"Fabric Community collector found {len(fabric_feedback)} items.")
            collection_status['sources_completed'].append('Fabric Community')
            if total_sources > 0:
                collection_status['progress'] = (len(collection_status['sources_completed']) / total_sources) * 100
            # Add source counts for real-time updates
            collection_status['source_counts'] = collection_status.get('source_counts', {})
            collection_status['source_counts']['fabricCommunity'] = len(fabric_feedback)
            all_feedback.extend(fabric_feedback)
            results['fabricCommunity'] = {'count': len(fabric_feedback), 'completed': True}
        
        # Collect from GitHub if enabled
        if source_configs.get('github', {}).get('enabled', False):
            collection_status['current_source'] = 'GitHub Discussions'
            collection_status['message'] = 'Collecting from GitHub Discussions...'
            github_config = source_configs['github']
            
            # Get list of repositories to collect from
            repositories = github_config.get('repositories', [])
            if not repositories:
                # Fallback to single repo config for backward compatibility
                repositories = [{
                    'owner': github_config.get('owner', 'microsoft'),
                    'repo': github_config.get('repo', 'Microsoft-Fabric-workload-development-sample'),
                    'enabled': True
                }]
            
            # Filter to only enabled repositories
            enabled_repos = [r for r in repositories if r.get('enabled', True)]
            logger.info(f"🐙 GITHUB DISCUSSIONS: Collecting from {len(enabled_repos)} repositories")
            
            github_feedback = []
            for repo_config in enabled_repos:
                repo_owner = repo_config.get('owner')
                repo_name = repo_config.get('repo')
                
                if not repo_owner or not repo_name:
                    logger.warning(f"Skipping invalid repository config: {repo_config}")
                    continue
                
                logger.info(f"  💬 Collecting from {repo_owner}/{repo_name}")
                
                github_collector = GitHubDiscussionsCollector()
                
                # Configure collector with specific repo
                if hasattr(github_collector, 'configure'):
                    github_collector.configure({
                        'owner': repo_owner,
                        'repo': repo_name,
                        'state': github_config.get('state', 'all'),
                        'max_items': github_config.get('maxItems', 200)
                    })
                
                repo_feedback = github_collector.collect()
                logger.info(f"  ✓ Found {len(repo_feedback)} items from {repo_owner}/{repo_name}")
                github_feedback.extend(repo_feedback)
            
            logger.info(f"GitHub Discussions collector found {len(github_feedback)} total items from {len(enabled_repos)} repositories.")
            collection_status['sources_completed'].append('GitHub Discussions')
            if total_sources > 0:
                collection_status['progress'] = (len(collection_status['sources_completed']) / total_sources) * 100
            # Add source counts for real-time updates
            collection_status['source_counts'] = collection_status.get('source_counts', {})
            collection_status['source_counts']['github'] = len(github_feedback)
            all_feedback.extend(github_feedback)
            results['github'] = {'count': len(github_feedback), 'completed': True, 'repositories': len(enabled_repos)}
        
        # Collect from GitHub Issues if enabled
        if source_configs.get('githubIssues', {}).get('enabled', False):
            collection_status['current_source'] = 'GitHub Issues'
            collection_status['message'] = 'Collecting from GitHub Issues...'
            github_issues_config = source_configs['githubIssues']
            
            # Get list of repositories to collect from
            repositories = github_issues_config.get('repositories', [])
            if not repositories:
                # Fallback to single repo config for backward compatibility
                repositories = [{
                    'owner': github_issues_config.get('owner', 'microsoft'),
                    'repo': github_issues_config.get('repo', 'Microsoft-Fabric-workload-development-sample'),
                    'enabled': True
                }]
            
            # Filter to only enabled repositories
            enabled_repos = [r for r in repositories if r.get('enabled', True)]
            logger.info(f"🐙 GITHUB ISSUES: Collecting from {len(enabled_repos)} repositories")
            
            github_issues_feedback = []
            for repo_config in enabled_repos:
                repo_owner = repo_config.get('owner')
                repo_name = repo_config.get('repo')
                
                if not repo_owner or not repo_name:
                    logger.warning(f"Skipping invalid repository config: {repo_config}")
                    continue
                
                logger.info(f"  📦 Collecting from {repo_owner}/{repo_name}")
                
                github_issues_collector = GitHubIssuesCollector()
                
                # Pass configuration to collector
                github_issues_collector.configure({
                    'owner': repo_owner,
                    'repo': repo_name,
                    'max_items': github_issues_config.get('maxItems', 200)
                })
                
                repo_feedback = github_issues_collector.collect()
                logger.info(f"  ✓ Found {len(repo_feedback)} items from {repo_owner}/{repo_name}")
                github_issues_feedback.extend(repo_feedback)
            
            logger.info(f"GitHub Issues collector found {len(github_issues_feedback)} total items from {len(enabled_repos)} repositories.")
            collection_status['sources_completed'].append('GitHub Issues')
            if total_sources > 0:
                collection_status['progress'] = (len(collection_status['sources_completed']) / total_sources) * 100
            # Add source counts for real-time updates
            collection_status['source_counts'] = collection_status.get('source_counts', {})
            collection_status['source_counts']['github_issues'] = len(github_issues_feedback)
            all_feedback.extend(github_issues_feedback)
            results['githubIssues'] = {'count': len(github_issues_feedback), 'completed': True, 'repositories': len(enabled_repos)}
        
        # Collect from Azure DevOps if enabled
        if source_configs.get('ado', {}).get('enabled', False):
            collection_status['current_source'] = 'Azure DevOps'
            collection_status['message'] = 'Collecting from Azure DevOps...'
            ado_config = source_configs['ado']
            parent_work_item_id = ado_config.get('parentWorkItem', config.get('ado_work_item_id', '1319103'))
            logger.info(f"🔗 AZURE DEVOPS: Collecting children of work item {parent_work_item_id}")
            
            # Get work items using the working client
            ado_workitems = get_working_ado_items(
                parent_work_item_id=parent_work_item_id, 
                top=ado_config.get('maxItems', 200)
            )
            logger.info(f"📊 Working client found {len(ado_workitems)} children work items")
            
            # Convert work items to feedback format
            ado_feedback = []
            for item in ado_workitems:
                work_item_id = item.get('id')
                title = item.get('title', '')
                description = item.get('description', '')
                ado_url = item.get('url')
                
                # Clean and handle None/NaN values
                def safe_get(obj, key, default=''):
                    import math
                    value = obj.get(key, default)
                    if value is None or (isinstance(value, float) and math.isnan(value)):
                        return default
                    return str(value) if value != default else default
                
                # Clean the text to remove HTML/CSS formatting
                cleaned_title = utils.clean_feedback_text(title)
                cleaned_description = utils.clean_feedback_text(description) if description and description != 'No description available' else ""
                
                # Use cleaned description + title for content
                full_content = cleaned_title
                if cleaned_description:
                    full_content += f"\n\n{cleaned_description}"
                
                # Enhanced categorization
                enhanced_cat = utils.enhanced_categorize_feedback(
                    full_content,
                    source='Azure DevOps',
                    scenario='Internal',
                    organization='ADO/WorkingClient'
                )
                
                # Analyze sentiment of the cleaned content
                sentiment_analysis = utils.analyze_sentiment(cleaned_description if cleaned_description else cleaned_title)
                
                ado_feedback.append({
                    'Title': f"[ADO-{work_item_id}] {cleaned_title}",
                    'Feedback_Gist': utils.generate_feedback_gist(full_content),
                    'Feedback': full_content,
                    'Content': full_content,
                    'Author': item.get('createdBy', ''),
                    'Created': item.get('createdDate', ''),
                    'Url': ado_url,
                    'URL': ado_url,
                    'Sources': 'Azure DevOps',
                    'Category': enhanced_cat['legacy_category'],
                    'Enhanced_Category': enhanced_cat['primary_category'],
                    'Subcategory': enhanced_cat['subcategory'],
                    'Audience': enhanced_cat['audience'],
                    'Priority': enhanced_cat['priority'],
                    'Feature_Area': enhanced_cat['feature_area'],
                    'Categorization_Confidence': enhanced_cat['confidence'],
                    'Domains': enhanced_cat.get('domains', []),
                    'Primary_Domain': enhanced_cat.get('primary_domain', None),
                    'Sentiment': sentiment_analysis['label'],
                    'Sentiment_Score': sentiment_analysis['polarity'],
                    'Sentiment_Confidence': sentiment_analysis['confidence'],
                    'ADO_ID': work_item_id,
                    'ADO_Type': safe_get(item, 'type', ''),
                    'ADO_State': safe_get(item, 'state', ''),
                    'ADO_AssignedTo': safe_get(item, 'assignedTo', '')
                })
            
            logger.info(f"🔗 Working ADO client found {len(ado_feedback)} children work items from parent {parent_work_item_id}.")
            collection_status['sources_completed'].append('Azure DevOps')
            if total_sources > 0:
                collection_status['progress'] = (len(collection_status['sources_completed']) / total_sources) * 100
            # Add source counts for real-time updates
            collection_status['source_counts'] = collection_status.get('source_counts', {})
            collection_status['source_counts']['ado'] = len(ado_feedback)
            all_feedback.extend(ado_feedback)
            results['ado'] = {'count': len(ado_feedback), 'completed': True}
        
        # Log sample work items
        if ado_feedback:
            logger.info("📋 Children work items found:")
            for item in ado_feedback[:3]:
                logger.info(f"  - {item['Title']} | URL: {item['URL']}")
        
        # Apply sentiment analysis to all feedback sources
        def add_sentiment_to_feedback(feedback_list, source_name):
            for item in feedback_list:
                if 'Sentiment_Score' not in item or item.get('Sentiment_Score') is None:
                    # Get the text content for sentiment analysis
                    text_content = item.get('Feedback', '') or item.get('Content', '') or item.get('Title', '')
                    sentiment_analysis = utils.analyze_sentiment(text_content)
                    
                    item['Sentiment'] = sentiment_analysis['label']
                    item['Sentiment_Score'] = sentiment_analysis['polarity']
                    item['Sentiment_Confidence'] = sentiment_analysis['confidence']
                    
                    logger.debug(f"Added sentiment analysis to {source_name} item: {sentiment_analysis['label']} ({sentiment_analysis['polarity']})")
            return feedback_list
        
        # Add sentiment analysis to all feedback sources
        reddit_feedback = add_sentiment_to_feedback(reddit_feedback, "Reddit")
        fabric_feedback = add_sentiment_to_feedback(fabric_feedback, "Fabric Community")
        github_feedback = add_sentiment_to_feedback(github_feedback, "GitHub Discussions")
        github_issues_feedback = add_sentiment_to_feedback(github_issues_feedback, "GitHub Issues")
        
        # Note: all_feedback was already built by extending with each source
        # No need to combine again as it would lose the items
        logger.info(f"Final feedback counts: Reddit={len(reddit_feedback)}, Fabric={len(fabric_feedback)}, GitHub Discussions={len(github_feedback)}, GitHub Issues={len(github_issues_feedback)}, ADO={len(ado_feedback)}, Total={len(all_feedback)}")
        
        # Generate deterministic IDs for all feedback items BEFORE state initialization
        from id_generator import FeedbackIDGenerator
        for feedback_item in all_feedback:
            if 'Feedback_ID' not in feedback_item or not feedback_item.get('Feedback_ID'):
                feedback_item['Feedback_ID'] = FeedbackIDGenerator.generate_id_from_feedback_dict(feedback_item)
                logger.info(f"Generated deterministic ID for item: {feedback_item['Feedback_ID']}")
                # Use the actual field names from collectors
                title = feedback_item.get('Feedback_Gist') or feedback_item.get('Title', 'N/A')
                content = feedback_item.get('Feedback') or feedback_item.get('Content', 'N/A')
                source = feedback_item.get('Sources') or feedback_item.get('Source', 'N/A')
                author = feedback_item.get('Customer') or feedback_item.get('Author', 'N/A')
                logger.info(f"  Title: {title}")
                logger.info(f"  Content: {str(content)[:100]}...")
                logger.info(f"  Source: {source}")
                logger.info(f"  Author: {author}")
        
        # Check if we're in online mode (connected to Fabric)
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        is_online_mode = stored_token and stored_token.strip() and stored_token != 'None'
        
        # OFFLINE COLLECTION MODE: Skip SQL state preservation to avoid authentication prompts
        # This prevents the collection process from prompting for Fabric authentication
        # State preservation will happen later when user explicitly syncs with Fabric
        logger.info("� COLLECTION MODE: Skipping SQL state preservation during collection to avoid authentication prompts")
        logger.info("ℹ️ Manual state updates will be preserved when you explicitly sync with Fabric after collection")
        
        # Initialize state management for all feedback items
        for feedback_item in all_feedback:
            state_manager.initialize_feedback_state(feedback_item)
        
        last_collected_feedback = all_feedback
        last_collection_summary = {
            "reddit": {"count": len(reddit_feedback), "completed": True},
            "fabric": {"count": len(fabric_feedback), "completed": True},
            "github": {"count": len(github_feedback), "completed": True},
            "github_issues": {"count": len(github_issues_feedback), "completed": True},
            "ado": {"count": len(ado_feedback), "completed": True},
            "total": len(all_feedback)
        }
        logger.info(f"Total feedback items collected: {len(all_feedback)}")

        if not all_feedback:
            logger.info("No feedback items collected in this run.")
            return jsonify(last_collection_summary)

        # Save to CSV
        try:
            df = pd.DataFrame(all_feedback)
            expected_columns = getattr(config, 'TABLE_COLUMNS', getattr(config, 'EXPECTED_COLUMNS', []))
            if not expected_columns:
                expected_columns = df.columns.tolist()
                logger.warning("TABLE_COLUMNS or EXPECTED_COLUMNS not found in config. Using DataFrame's columns.")

            for col in expected_columns:
                if col not in df.columns:
                    df[col] = None 

            df = df.reindex(columns=expected_columns)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"feedback_{timestamp}.csv"
            filepath = os.path.join(DATA_DIR, filename)
            
            df.to_csv(filepath, index=False, encoding='utf-8-sig') 
            logger.info(f"Feedback saved to {filepath}")
            
            current_app.config['LAST_CSV_FILE'] = filename
            
            # Add filename to summary for download link
            last_collection_summary['csv_filename'] = filename
            
        except Exception as e:
            logger.error(f"Error processing or saving feedback to CSV: {e}", exc_info=True)
            # Update status to error
            collection_status.update({
                'status': 'error',
                'message': 'Error saving feedback to CSV',
                'end_time': datetime.now().isoformat(),
                'error_message': str(e)
            })
            return jsonify({**last_collection_summary, "csv_error": str(e)}), 500
        
        # Update status to completed
        collection_status.update({
            'status': 'completed',
            'message': f'Collection completed successfully - {len(all_feedback)} items collected',
            'end_time': datetime.now().isoformat(),
            'total_items': len(all_feedback),
            'current_source': 'Completed',
            'progress': 100,
            'results': results  # Include results for client display
        })
            
        return jsonify(last_collection_summary)
        
    except Exception as e:
        import traceback
        full_traceback = traceback.format_exc()
        logger.error(f"Error in collection route: {e}")
        logger.error(f"Full traceback:\n{full_traceback}")
        # Update status to error
        collection_status.update({
            'status': 'error',
            'message': 'Collection failed',
            'end_time': datetime.now().isoformat(),
            'error_message': str(e)
        })
        return jsonify({"error": str(e)}), 500

@app.route('/feedback')
def feedback_viewer():
    """Full-featured feedback viewer with template rendering"""
    global last_collected_feedback
    
    try:
        import fabric_sql_writer
    except ImportError as e:
        logger.warning(f"Fabric SQL Writer not available (ODBC driver missing): {e}")
        fabric_sql_writer = None
    except Exception as e:
        logger.warning(f"Fabric SQL Writer failed to load: {e}")
        fabric_sql_writer = None
        
    import id_generator
    from id_generator import FeedbackIDGenerator
    
    # Multi-select filter parameter parsing
    def parse_filter_param(param_name, default='All'):
        """Parse filter parameter that can be single value or comma-separated list"""
        param_value = request.args.get(param_name, default)
        if param_value == 'All' or not param_value:
            return []
        return [item.strip() for item in param_value.split(',') if item.strip()]
    
    # Multi-select filters (new functionality)
    source_filters = parse_filter_param('source')
    enhanced_category_filters = parse_filter_param('enhanced_category')
    audience_filters = parse_filter_param('audience')
    priority_filters = parse_filter_param('priority')
    domain_filters = parse_filter_param('domain')
    sentiment_filters = parse_filter_param('sentiment')
    state_filters = parse_filter_param('state')
    
    # Legacy single-select filters (for backwards compatibility)
    source_filter = request.args.get('source', 'All')
    category_filter = request.args.get('category', 'All')
    enhanced_category_filter = request.args.get('enhanced_category', 'All')
    audience_filter = request.args.get('audience', 'All')
    priority_filter = request.args.get('priority', 'All')
    domain_filter = request.args.get('domain', 'All')
    sentiment_filter = request.args.get('sentiment', 'All')
    state_filter = request.args.get('state', 'All')
    sort_by = request.args.get('sort', 'newest')
    show_repeating = request.args.get('show_repeating', 'false').lower() == 'true'
    show_only_stored = request.args.get('show_only_stored', 'false').lower() == 'true'
    fabric_connected_param = request.args.get('fabric_connected', 'false').lower() == 'true'
    
    # Check authentication tokens and connection states
    from flask import session
    stored_token = session.get('fabric_bearer_token')  # Bearer token for lakehouse writes only
    
    # CRITICAL FIX: Balanced connection logic - conservative for new connections, preserving for valid sessions
    # Validate both new connections and existing sessions properly
    has_bearer_token = stored_token and stored_token.strip() and stored_token != 'None'
    has_session_flags = session.get('states_loaded') or session.get('sql_data_applied')
    
    # NEW CONNECTION: URL parameter + bearer token (fresh connection from sync)
    if fabric_connected_param and has_bearer_token:
        logger.info("🔗 NEW FABRIC CONNECTION: Valid parameter + bearer token detected - setting session flags for persistence.")
        fabric_sql_connected = True
        session['states_loaded'] = True
        session['sql_data_applied'] = True
    # EXISTING CONNECTION: Valid bearer token + session flags (preserve on page refresh)
    elif has_bearer_token and has_session_flags:
        logger.info("🔒 MAINTAINING CONNECTION: Valid bearer token + session flags - preserving connection state.")
        fabric_sql_connected = True
    # BEARER TOKEN ONLY: Valid token without session flags (partial connection state)
    elif has_bearer_token:
        logger.info("� PARTIAL CONNECTION: Bearer token exists but no session flags - enabling connection for domain updates.")
        fabric_sql_connected = True
        # Don't set session flags yet - let the sync process do that
    else:
        # No valid connection indicators - clear any stale session flags
        logger.info("❌ NO CONNECTION: No valid connection indicators found - clearing stale flags.")
        fabric_sql_connected = False
        session.pop('states_loaded', None)
        session.pop('sql_data_applied', None)
        
    # Online mode for lakehouse writes (bearer token based)
    is_online_mode = stored_token and stored_token.strip() and stored_token != 'None'
    
    logger.info(f"Bearer Token Mode: {'ONLINE' if is_online_mode else 'OFFLINE'} - Token: {'Present' if stored_token else 'None'}")
    logger.info(f"Fabric SQL Connected: {fabric_sql_connected} (states_loaded: {session.get('states_loaded')}, sql_data_applied: {session.get('sql_data_applied')})")
    logger.info(f"Fabric Connected Param: {fabric_connected_param}, Has Bearer Token: {bool(stored_token)}")
    
    # If no feedback in memory, try loading from the latest CSV
    if not last_collected_feedback:
        logger.info("No feedback in memory, loading from CSV.")
        last_collected_feedback = load_latest_feedback_from_csv()
        if last_collected_feedback:
            # Basic processing for CSV data
            for item in last_collected_feedback:
                if 'id' not in item or not item['id']:
                    item['id'] = FeedbackIDGenerator.generate_id_from_feedback_dict(item)
                state_manager.initialize_feedback_state(item)
    
    feedback_to_display = list(last_collected_feedback)
    
    logger.info(f"Feedback viewer - Bearer Token Mode: {'ONLINE' if is_online_mode else 'OFFLINE'}, Fabric SQL Connected: {fabric_sql_connected}, Count: {len(feedback_to_display)}")
    
    # ONLINE MODE: Sync with SQL database if connected
    if fabric_sql_connected:
        # Check if SQL data has already been applied to in-memory data
        sql_data_already_applied = session.get('sql_data_applied', False)
        
        if sql_data_already_applied:
            logger.info("SQL data already applied in this session. Skipping re-sync.")
        else:
            logger.info("First load with Fabric connection in this session. Syncing with SQL database.")
            try:
                feedback_to_display = fabric_sql_writer.sync_feedback_with_sql(feedback_to_display)
                session['sql_data_applied'] = True  # Mark as applied for this session
                logger.info("✅ Successfully synced with SQL database.")
            except Exception as e:
                logger.error(f"Error syncing with SQL database: {e}", exc_info=True)
                # Optionally, pass an error to the template
                # error_message = f"Error syncing with SQL: {e}"

    # Filtering logic (multi-select)
    if source_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Sources') or f.get('source')) in source_filters]
    if enhanced_category_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Enhanced_Category') or f.get('enhanced_category')) in enhanced_category_filters]
    if audience_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Audience') or f.get('audience')) in audience_filters]
    if priority_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Priority') or f.get('priority')) in priority_filters]
    if domain_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Primary_Domain') or f.get('domain')) in domain_filters]
    if sentiment_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Sentiment') or f.get('sentiment')) in sentiment_filters]
    if state_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('State') or f.get('state')) in state_filters]

    # Filtering logic (single-select, for backwards compatibility)
    if source_filter != 'All' and not source_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Sources') or f.get('source')) == source_filter]
    if category_filter != 'All':
        feedback_to_display = [f for f in feedback_to_display if (f.get('Category') or f.get('category')) == category_filter]
    if enhanced_category_filter != 'All' and not enhanced_category_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Enhanced_Category') or f.get('enhanced_category')) == enhanced_category_filter]
    if audience_filter != 'All' and not audience_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Audience') or f.get('audience')) == audience_filter]
    if priority_filter != 'All' and not priority_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Priority') or f.get('priority')) == priority_filter]
    if domain_filter != 'All' and not domain_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Primary_Domain') or f.get('domain')) == domain_filter]
    if sentiment_filter != 'All' and not sentiment_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('Sentiment') or f.get('sentiment')) == sentiment_filter]
    if state_filter != 'All' and not state_filters:
        feedback_to_display = [f for f in feedback_to_display if (f.get('State') or f.get('state')) == state_filter]

    # Show only stored feedback if requested
    if show_only_stored:
        feedback_to_display = [f for f in feedback_to_display if f.get('is_stored_in_sql', False)]

    # Handle repeating feedback
    if not show_repeating:
        # This logic needs to be robust
        pass

    # Sorting
    if sort_by == 'newest':
        feedback_to_display.sort(key=lambda x: x.get('Created') or x.get('timestamp', ''), reverse=True)
    elif sort_by == 'oldest':
        feedback_to_display.sort(key=lambda x: x.get('Created') or x.get('timestamp', ''))
    elif sort_by == 'priority':
        priority_map = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        feedback_to_display.sort(key=lambda x: priority_map.get((x.get('Priority') or x.get('priority', 'low')).lower(), 3))

    # Get unique values for filter dropdowns from the originally loaded data
    if last_collected_feedback:
        # Helper to safely get string values for sorting
        def safe_str(val):
            return str(val) if val is not None else ""

        all_sources = sorted(list(set(safe_str(item.get('Sources') or item.get('source')) for item in last_collected_feedback if item.get('Sources') or item.get('source'))))
        all_categories = sorted(list(set(safe_str(item.get('Category') or item.get('category')) for item in last_collected_feedback if item.get('Category') or item.get('category'))))
        all_enhanced_categories = sorted(list(set(safe_str(item.get('Enhanced_Category') or item.get('enhanced_category')) for item in last_collected_feedback if item.get('Enhanced_Category') or item.get('enhanced_category'))))
        all_subcategories = sorted(list(set(safe_str(item.get('Subcategory') or item.get('subcategory')) for item in last_collected_feedback if item.get('Subcategory') or item.get('subcategory'))))
        
        # Group subcategories by feature area for organized display
        subcategories_by_feature_area = {}
        for item in last_collected_feedback:
            feature_area = item.get('Feature_Area') or item.get('feature_area')
            subcategory = item.get('Subcategory') or item.get('subcategory')
            if feature_area and subcategory:
                if feature_area not in subcategories_by_feature_area:
                    subcategories_by_feature_area[feature_area] = set()
                subcategories_by_feature_area[feature_area].add(subcategory)
        # Convert sets to sorted lists and sort by feature area
        # Ensure safe sorting for both keys and values
        subcategories_by_feature_area = {
            k: sorted(list(v), key=safe_str) 
            for k, v in sorted(subcategories_by_feature_area.items(), key=lambda x: safe_str(x[0]))
        }
        
        all_impact_types = sorted(list(set(safe_str(item.get('Impacttype') or item.get('impacttype')) for item in last_collected_feedback if item.get('Impacttype') or item.get('impacttype'))))
        all_audiences = sorted(list(set(safe_str(item.get('Audience') or item.get('audience')) for item in last_collected_feedback if item.get('Audience') or item.get('audience'))))
        all_priorities = ['critical', 'high', 'medium', 'low']
        all_domains = sorted(list(set(safe_str(item.get('Primary_Domain') or item.get('domain')) for item in last_collected_feedback if item.get('Primary_Domain') or item.get('domain'))))
        all_sentiments = sorted(list(set(safe_str(item.get('Sentiment') or item.get('sentiment')) for item in last_collected_feedback if item.get('Sentiment') or item.get('sentiment'))))
        all_states = sorted(list(set(safe_str(item.get('State') or item.get('state')) for item in last_collected_feedback if item.get('State') or item.get('state'))))
        
        # Debug logging for filter data
        logger.info(f"🔍 FILTER DEBUG: Sources: {len(all_sources)}, Domains: {len(all_domains)}, States: {len(all_states)}")
        logger.info(f"🔍 DOMAINS FOUND: {all_domains[:10]}")  # Show first 10 domains
        logger.info(f"🔍 STATES FOUND: {all_states}")
        logger.info(f"🔍 AUDIENCES FOUND: {all_audiences}")
    else:
        all_sources, all_categories, all_enhanced_categories, all_subcategories, all_impact_types, all_audiences, all_priorities, all_domains, all_sentiments, all_states = [], [], [], [], [], [], [], [], [], []
        subcategories_by_feature_area = {}
        logger.warning("⚠️ NO FEEDBACK DATA: No last_collected_feedback available for filters")

    total_items = len(feedback_to_display)
    
    return render_template('feedback_viewer.html', 
                           feedback_items=feedback_to_display,
                           total_items=total_items,
                           sort_by=sort_by,
                           show_repeating=show_repeating,
                           show_only_stored=show_only_stored,
                           all_sources=all_sources,
                           all_categories=all_categories,
                           all_enhanced_categories=all_enhanced_categories,
                           all_subcategories=all_subcategories,
                           subcategories_by_feature_area=subcategories_by_feature_area,
                           all_impact_types=all_impact_types,
                           all_audiences=all_audiences,
                           all_priorities=all_priorities,
                           all_domains=all_domains,
                           all_sentiments=all_sentiments,
                           all_states=all_states,
                           source_filter=source_filter,
                           category_filter=category_filter,
                           enhanced_category_filter=enhanced_category_filter,
                           audience_filter=audience_filter,
                           priority_filter=priority_filter,
                           domain_filter=domain_filter,
                           sentiment_filter=sentiment_filter,
                           state_filter=state_filter,
                           source_filters=source_filters,
                           enhanced_category_filters=enhanced_category_filters,
                           audience_filters=audience_filters,
                           priority_filters=priority_filters,
                           domain_filters=domain_filters,
                           sentiment_filters=sentiment_filters,
                           state_filters=state_filters,
                           # Add selected filter variables for template compatibility
                           selected_sources=source_filters,
                           selected_enhanced_categories=enhanced_category_filters,
                           selected_audiences=audience_filters,
                           selected_priorities=priority_filters,
                           selected_domains=domain_filters,
                           selected_sentiments=sentiment_filters,
                           selected_states=state_filters,
                           fabric_sql_connected=fabric_sql_connected,
                           fabric_connected_param=fabric_connected_param,
                           is_online_mode=is_online_mode,
                           last_csv_file=current_app.config.get('LAST_CSV_FILE', ''))

@app.route('/api/session_state', methods=['GET'])
def get_session_state():
    """Get current session state for frontend"""
    from flask import session
    stored_token = session.get('fabric_bearer_token')
    
    # Use the SAME logic as feedback_viewer route for consistency
    has_bearer_token = stored_token and stored_token.strip() and stored_token != 'None'
    has_session_flags = session.get('states_loaded') or session.get('sql_data_applied')
    
    # Determine connection state using same logic as main route
    if has_bearer_token and has_session_flags:
        fabric_sql_connected = True
    elif has_bearer_token:
        fabric_sql_connected = True  # Partial connection
    else:
        fabric_sql_connected = False
    
    logger.info(f"📡 SESSION STATE API: Bearer: {bool(has_bearer_token)}, Flags: {bool(has_session_flags)}, Connected: {fabric_sql_connected}")
    
    return jsonify({
        'has_bearer_token': has_bearer_token,
        'fabric_sql_connected': fabric_sql_connected,
        'states_loaded': session.get('states_loaded', False),
        'sql_data_applied': session.get('sql_data_applied', False)
    })

@app.route('/api/clear_session', methods=['POST'])
def clear_session_state():
    """Clear session state to reset connection status"""
    from flask import session
    
    # Clear all Fabric-related session flags
    session.pop('fabric_bearer_token', None)
    session.pop('states_loaded', None)
    session.pop('sql_data_applied', None)
    
    logger.info("🧹 SESSION CLEARED: All Fabric session flags cleared")
    
    return jsonify({
        'status': 'success',
        'message': 'Session state cleared successfully'
    })

@app.route('/api/write_to_fabric', methods=['POST'])
def write_to_fabric_route():
    global last_collected_feedback
    if not last_collected_feedback:
        return jsonify({'status': 'error', 'message': 'No feedback data collected yet or last collection was empty.'}), 400

    try:
        data = request.get_json()
        fabric_token = data.get('fabric_token')
        if not fabric_token:
            return jsonify({'status': 'error', 'message': 'Fabric access token is required.'}), 400

        # Filter out feedback items without matched keywords
        filtered_feedback = [
            item for item in last_collected_feedback 
            if item.get('Matched_Keywords') and len(item.get('Matched_Keywords', [])) > 0
        ]
        
        if not filtered_feedback:
            return jsonify({'status': 'warning', 'message': 'No feedback items with matched keywords to write. All items were filtered out.'}), 200
        
        logger.info(f"Attempting to write {len(filtered_feedback)} items (filtered from {len(last_collected_feedback)}) to Fabric SQL Database.")
        
        # Use fabric_sql_writer for direct SQL writes
        try:
            from fabric_sql_writer import FabricSQLWriter
        except ImportError as ie:
            logger.error(f"Failed to import fabric_sql_writer module: {ie}")
            return jsonify({'status': 'error', 'message': f'Fabric SQL writer module not available: {str(ie)}'}), 500
        
        # Write to SQL database
        try:
            writer = FabricSQLWriter(bearer_token=fabric_token)
            result = writer.bulletproof_sync_with_deduplication(filtered_feedback)
            
            new_items = result.get('new_items', 0)
            existing_items = result.get('existing_items', 0)
            
            logger.info(f"Successfully wrote {new_items} new items to Fabric SQL Database ({existing_items} already existed)")
            return jsonify({
                'status': 'success', 
                'message': f'Successfully wrote {new_items} new items to Fabric SQL Database. {existing_items} items already existed. (Filtered from {len(last_collected_feedback)} total)',
                'new_items': new_items,
                'existing_items': existing_items
            })
        except Exception as write_error:
            logger.error(f"Failed to write data to Fabric SQL Database: {write_error}", exc_info=True)
            return jsonify({'status': 'error', 'message': f'Failed to write data to Fabric SQL Database: {str(write_error)}'}), 500

    except Exception as e:
        logger.error(f"Error writing to Fabric: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}), 500

# Global storage for async operations
fabric_operations = {}

@app.route('/api/write_to_fabric_async', methods=['POST'])
def write_to_fabric_async_endpoint():
    """Start asynchronous write to Fabric SQL Database with progress tracking"""
    try:
        import uuid
        import threading
        from datetime import datetime
        
        data = request.get_json()
        fabric_token = data.get('fabric_token')
        
        if not fabric_token:
            return jsonify({'status': 'error', 'message': 'Fabric token is required'}), 400
        
        global last_collected_feedback
        if not last_collected_feedback:
            return jsonify({'status': 'error', 'message': 'No feedback data collected yet or last collection was empty.'}), 400
        
        # Filter out feedback items without matched keywords
        filtered_feedback = [
            item for item in last_collected_feedback 
            if item.get('Matched_Keywords') and len(item.get('Matched_Keywords', [])) > 0
        ]
        
        if not filtered_feedback:
            return jsonify({'status': 'warning', 'message': 'No feedback items with matched keywords to write. All items were filtered out.'}), 200
        
        # Generate unique operation ID
        operation_id = str(uuid.uuid4())
        
        # Initialize operation tracking
        fabric_operations[operation_id] = {
            'status': 'starting',
            'progress': 0,
            'total_items': len(filtered_feedback),
            'processed_items': 0,
            'start_time': datetime.now(),
            'logs': [],
            'completed': False,
            'success': False,
            'message': '',
            'operation': 'Initializing...'
        }
        
        # Start background thread
        def fabric_write_worker():
            try:
                fabric_operations[operation_id]['logs'].append({
                    'message': f'🚀 Starting Fabric SQL write operation for {len(filtered_feedback)} items (filtered from {len(last_collected_feedback)} total)',
                    'type': 'info'
                })
                fabric_operations[operation_id]['status'] = 'in_progress'
                fabric_operations[operation_id]['operation'] = 'Writing to Fabric SQL Database...'
                
                from fabric_sql_writer import FabricSQLWriter
                
                # Call SQL writer
                fabric_operations[operation_id]['logs'].append({
                    'message': '📝 Writing to Fabric SQL Database...',
                    'type': 'info'
                })
                
                writer = FabricSQLWriter(bearer_token=fabric_token)
                result = writer.bulletproof_sync_with_deduplication(filtered_feedback)
                
                new_items = result.get('new_items', 0)
                existing_items = result.get('existing_items', 0)
                
                fabric_operations[operation_id]['completed'] = True
                fabric_operations[operation_id]['success'] = True
                fabric_operations[operation_id]['progress'] = 100
                fabric_operations[operation_id]['processed_items'] = len(filtered_feedback)
                fabric_operations[operation_id]['new_items'] = new_items
                fabric_operations[operation_id]['existing_items'] = existing_items
                
                fabric_operations[operation_id]['message'] = f'Successfully wrote {new_items} new items to Fabric SQL Database ({existing_items} already existed)'
                fabric_operations[operation_id]['logs'].append({
                    'message': '✅ Fabric SQL write operation completed successfully',
                    'type': 'success'
                })
                
                # Store token in session for feedback viewer
                from flask import session
                session['fabric_bearer_token'] = fabric_token
                session['states_loaded'] = True
                
            except Exception as e:
                fabric_operations[operation_id]['completed'] = True
                fabric_operations[operation_id]['success'] = False
                fabric_operations[operation_id]['message'] = f'Error: {str(e)}'
                fabric_operations[operation_id]['logs'].append({
                    'message': f'❌ Error during Fabric write: {str(e)}',
                    'type': 'danger'
                })
                logger.error(f"Error in Fabric write worker: {e}", exc_info=True)
        
        thread = threading.Thread(target=fabric_write_worker)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'operation_id': operation_id,
            'total_items': len(last_collected_feedback),
            'message': 'Fabric write operation started'
        }), 200
        
    except Exception as e:
        logger.error(f"Error starting async Fabric write: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to start operation: {str(e)}'}), 500

def load_states_after_fabric_write(fabric_token, operation_id):
    """Load existing states from Fabric after successful write operation"""
    global last_collected_feedback
    
    try:
        # Get all feedback IDs from the collected feedback
        feedback_ids = [item.get('Feedback_ID') for item in last_collected_feedback if item.get('Feedback_ID')]
        
        if not feedback_ids:
            logger.info("No feedback IDs found for state loading")
            return
        
        # TODO: Replace with actual Fabric Lakehouse query
        # For now, simulate loading states - in production this would query the Fabric table
        fabric_states = {}
        for feedback_id in feedback_ids:
            # Mock state loading - in production, this would be a real Fabric query
            # The fabric_writer.py would be extended to also read states
            fabric_states[feedback_id] = {
                'State': 'NEW',  # This would come from actual Fabric table
                'Feedback_Notes': '',  # This would come from actual Fabric table
                'Last_Updated': datetime.now().isoformat(),
                'Updated_By': 'System'
            }
        
        # Update in-memory feedback data with loaded states
        for item in last_collected_feedback:
            feedback_id = item.get('Feedback_ID')
            if feedback_id and feedback_id in fabric_states:
                state_data = fabric_states[feedback_id]
                item.update(state_data)
        
        fabric_operations[operation_id]['logs'].append({
            'message': f'📊 Loaded states for {len(fabric_states)} feedback items',
            'type': 'info'
        })
        
        logger.info(f"Successfully loaded states for {len(fabric_states)} feedback items after Fabric write")
        
    except Exception as e:
        logger.error(f"Error loading states after Fabric write: {e}")
        raise


@app.route('/api/fabric_progress/<operation_id>')
def get_fabric_progress(operation_id):
    """Get progress of Fabric write operation"""
    try:
        if operation_id not in fabric_operations:
            return jsonify({'error': 'Operation not found'}), 404
        
        operation = fabric_operations[operation_id]
        
        # Calculate stats
        stats = {
            'items': operation['processed_items']
        }
        
        # Get new logs since last check (simplified - returns all logs)
        logs = operation['logs']
        operation['logs'] = []  # Clear logs after sending
        
        return jsonify({
            'progress': operation['progress'],
            'status': operation['status'],
            'operation': operation['operation'],
            'stats': stats,
            'logs': logs,
            'completed': operation['completed'],
            'success': operation['success'],
            'message': operation['message'],
            'hide_duplicates': operation.get('hide_duplicates', False)
        })
        
    except Exception as e:
        logger.error(f"Error getting Fabric progress: {e}")
        return jsonify({'error': 'Failed to get progress'}), 500

@app.route('/api/fabric/stored_ids')
def get_stored_ids():
    """Get list of Feedback IDs that are stored in Fabric SQL database"""
    try:
        stored_ids = state_manager.get_stored_feedback_ids()
        total_collected = len(last_collected_feedback) if last_collected_feedback else 0
        
        return jsonify({
            'status': 'success',
            'stored_ids': stored_ids,
            'total_stored': len(stored_ids),
            'total_collected': total_collected
        })
    except Exception as e:
        logger.error(f"Error getting stored IDs: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/cancel_fabric_write/<operation_id>', methods=['POST'])
def cancel_fabric_write(operation_id):
    """Cancel Fabric write operation"""
    try:
        if operation_id in fabric_operations:
            fabric_operations[operation_id]['logs'].append({
                'message': 'Cancellation requested',
                'type': 'warning'
            })
            # Note: Actual cancellation would require more complex implementation
            return jsonify({'status': 'success', 'message': 'Cancellation requested'})
        else:
            return jsonify({'error': 'Operation not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Modern Filter API Endpoints

def clean_nan_values(data):
    """Clean NaN values from data for JSON serialization"""
    import math
    
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            cleaned[key] = clean_nan_values(value)
        return cleaned
    elif isinstance(data, list):
        return [clean_nan_values(item) for item in data]
    elif isinstance(data, float) and math.isnan(data):
        return None  # Convert NaN to None (null in JSON)
    else:
        return data

@app.route('/api/feedback/filtered', methods=['GET'])
def get_filtered_feedback():
    """AJAX endpoint for filtered feedback data without page reload"""
    global last_collected_feedback
    
    try:
        # Get filter parameters
        source_filters = [s.strip() for s in request.args.get('source', '').split(',') if s.strip()]
        audience_filters = [a.strip() for a in request.args.get('audience', '').split(',') if a.strip()]
        priority_filters = [p.strip() for p in request.args.get('priority', '').split(',') if p.strip()]
        state_filters = [s.strip() for s in request.args.get('state', '').split(',') if s.strip()]
        domain_filters = [d.strip() for d in request.args.get('domain', '').split(',') if d.strip()]
        sentiment_filters = [s.strip() for s in request.args.get('sentiment', '').split(',') if s.strip()]
        enhanced_category_filters = [c.strip() for c in request.args.get('enhanced_category', '').split(',') if c.strip()]
        subcategory_filters = [s.strip() for s in request.args.get('subcategory', '').split(',') if s.strip()]
        impacttype_filters = [i.strip() for i in request.args.get('impacttype', '').split(',') if i.strip()]
        
        # Search query
        search_query = request.args.get('search', '').strip()
        
        # Pagination
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Sort options
        sort_by = request.args.get('sort', 'newest')
        
        # Other options
        show_repeating = request.args.get('show_repeating', 'false').lower() == 'true'
        show_only_stored = request.args.get('show_only_stored', 'false').lower() == 'true'
        fabric_connected = request.args.get('fabric_connected', 'false').lower() == 'true'
        
        # Check session for Fabric connection
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        is_online_mode = stored_token and stored_token.strip() and stored_token != 'None'
        
        # Load feedback data if not available
        if not last_collected_feedback:
            logger.info("No feedback in memory, loading from CSV for AJAX request")
            last_collected_feedback = load_latest_feedback_from_csv()
            
            if last_collected_feedback:
                from id_generator import FeedbackIDGenerator
                # Generate IDs for CSV data
                for item in last_collected_feedback:
                    if 'Feedback_ID' not in item or not item.get('Feedback_ID'):
                        item['Feedback_ID'] = FeedbackIDGenerator.generate_id_from_feedback_dict(item)
        
        if not last_collected_feedback:
            return jsonify({
                'success': False,
                'message': 'No feedback data available'
            }), 404
        
        # Apply filtering logic (reuse existing logic)
        feedback_to_display = apply_filters_to_feedback(
            feedback_data=last_collected_feedback,
            source_filters=source_filters,
            audience_filters=audience_filters,
            priority_filters=priority_filters,
            state_filters=state_filters,
            domain_filters=domain_filters,
            sentiment_filters=sentiment_filters,
            enhanced_category_filters=enhanced_category_filters,
            subcategory_filters=subcategory_filters,
            impacttype_filters=impacttype_filters,
            search_query=search_query,
            show_repeating=show_repeating,
            show_only_stored=show_only_stored,
            sort_by=sort_by
        )
        
        # Apply pagination
        total_count = len(feedback_to_display)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_feedback = feedback_to_display[start_idx:end_idx]
        
        # Clean NaN values before JSON serialization
        paginated_feedback = clean_nan_values(paginated_feedback)
        
        # Analyze repeating requests if requested
        repeating_analysis = None
        if show_repeating and feedback_to_display:
            from utils import analyze_repeating_requests
            repeating_analysis = analyze_repeating_requests(feedback_to_display)
            logger.info(f"AJAX Repeating requests analysis: {repeating_analysis.get('cluster_count', 0)} clusters found from {len(feedback_to_display)} filtered items")
        
        # Get filter options for UI updates (use full dataset for filter options)
        filter_options = extract_filter_options(last_collected_feedback)
        
        # Get current Fabric state data if available
        fabric_state_data = {}
        try:
            if is_online_mode:
                # Try to load current state from Fabric if connected
                from fabric_state_writer import FabricStateWriter
                fabric_writer = FabricStateWriter(stored_token)
                fabric_state_data = fabric_writer.load_state_data()
                logger.info(f"Loaded {len(fabric_state_data)} state records for AJAX response")
        except Exception as e:
            logger.warning(f"Could not load Fabric state data for AJAX: {e}")
            fabric_state_data = {}
        
        # Return JSON response
        return jsonify({
            'success': True,
            'feedback': paginated_feedback,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'has_more': end_idx < total_count,
            'fabric_connected': fabric_connected or is_online_mode,
            'fabric_state_data': fabric_state_data,  # Include state data for proper rendering
            'filter_options': filter_options,
            'repeating_analysis': repeating_analysis,  # Include repeating analysis for AJAX requests
            'applied_filters': {
                'source': source_filters,
                'audience': audience_filters,
                'priority': priority_filters,
                'state': state_filters,
                'domain': domain_filters,
                'sentiment': sentiment_filters,
                'enhanced_category': enhanced_category_filters,
                'search': search_query,
                'sort': sort_by,
                'show_repeating': show_repeating,
                'show_only_stored': show_only_stored
            }
        })
        
    except Exception as e:
        logger.error(f"Error in filtered feedback API: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

def apply_filters_to_feedback(feedback_data, source_filters=None, audience_filters=None, 
                            priority_filters=None, state_filters=None, domain_filters=None,
                            sentiment_filters=None, enhanced_category_filters=None, 
                            subcategory_filters=None, impacttype_filters=None,
                            search_query='', show_repeating=False, show_only_stored=False, 
                            sort_by='newest'):
    """Extracted filtering logic for reuse between web and API routes"""
    
    if not feedback_data:
        return []
    
    filtered_feedback = list(feedback_data)  # Create a copy
    
    # Apply search filter
    if search_query:
        search_lower = search_query.lower()
        filtered_feedback = [
            item for item in filtered_feedback
            if search_lower in str(item.get('Feedback', '')).lower() or
               search_lower in str(item.get('Page_Title', '')).lower() or
               search_lower in str(item.get('Enhanced_Category', '')).lower()
        ]
    
    # Apply source filter
    if source_filters:
        filtered_feedback = [
            item for item in filtered_feedback
            if item.get('Sources') in source_filters
        ]
    
    # Apply audience filter
    if audience_filters:
        filtered_feedback = [
            item for item in filtered_feedback
            if item.get('Audience') in audience_filters
        ]
    
    # Apply priority filter
    if priority_filters:
        filtered_feedback = [
            item for item in filtered_feedback
            if item.get('Priority') in priority_filters
        ]
    
    # Apply state filter
    if state_filters:
        filtered_feedback = [
            item for item in filtered_feedback
            if item.get('State', 'NEW') in state_filters
        ]
    
    # Apply domain filter
    if domain_filters:
        # Handle special "Uncategorized" filter
        if 'Uncategorized' in domain_filters:
            # Include items that match other filters OR have no domain classification
            other_domains = [d for d in domain_filters if d != 'Uncategorized']
            filtered_feedback = [item for item in filtered_feedback if 
                              (item.get('Primary_Domain') in other_domains if other_domains else False) or
                              not item.get('Primary_Domain') or 
                              item.get('Primary_Domain') in ['', 'None', None]]
        else:
            # Normal domain filtering - only show items with matching domains
            filtered_feedback = [
                item for item in filtered_feedback
                if item.get('Primary_Domain') in domain_filters
            ]
    
    # Apply sentiment filter
    if sentiment_filters:
        filtered_feedback = [
            item for item in filtered_feedback
            if item.get('Sentiment') in sentiment_filters
        ]
    
    # Apply enhanced category filter
    if enhanced_category_filters:
        filtered_feedback = [
            item for item in filtered_feedback
            if item.get('Enhanced_Category') in enhanced_category_filters
        ]
    
    # Apply subcategory filter
    if subcategory_filters:
        filtered_feedback = [
            item for item in filtered_feedback
            if item.get('Subcategory') in subcategory_filters
        ]
    
    # Apply impact type filter
    if impacttype_filters:
        filtered_feedback = [
            item for item in filtered_feedback
            if item.get('Impacttype') in impacttype_filters
        ]
    
    # Apply sorting
    if sort_by == 'newest':
        # Debug: check some Created values before sorting
        sample_dates = [item.get('Created', '') for item in filtered_feedback[:3]]
        logger.info(f"DEBUG: Sorting newest - sample dates before: {sample_dates}")
        filtered_feedback.sort(key=lambda x: x.get('Created', ''), reverse=True)
        sample_dates_after = [item.get('Created', '') for item in filtered_feedback[:3]]
        logger.info(f"DEBUG: Sorting newest - sample dates after: {sample_dates_after}")
    elif sort_by == 'oldest':
        # Debug: check some Created values before sorting
        sample_dates = [item.get('Created', '') for item in filtered_feedback[:3]]
        logger.info(f"DEBUG: Sorting oldest - sample dates before: {sample_dates}")
    elif sort_by == 'priority':
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        filtered_feedback.sort(key=lambda x: priority_order.get(x.get('Priority', 'low').lower(), 4))
    
    return filtered_feedback

def extract_filter_options(feedback_data):
    """Extract available filter options from feedback data"""
    if not feedback_data:
        return {}
    
    # Helper to safely get string values for sorting
    def safe_str(val):
        return str(val) if val is not None else ""
    
    # Get states currently in the data
    data_states = set(safe_str(item.get('State', 'NEW')) for item in feedback_data)
    
    # Always include all possible states from config, regardless of what's in the data
    from config import FEEDBACK_STATES
    all_possible_states = set(FEEDBACK_STATES.keys())
    
    # Merge data states with all possible states to ensure comprehensive list
    comprehensive_states = sorted(list(all_possible_states.union(data_states)))
    
    options = {
        'sources': sorted(list(set(safe_str(item.get('Source', '')) for item in feedback_data if item.get('Source')))),
        'audiences': sorted(list(set(safe_str(item.get('Audience', '')) for item in feedback_data if item.get('Audience')))),
        'priorities': sorted(list(set(safe_str(item.get('Priority', '')) for item in feedback_data if item.get('Priority')))),
        'states': comprehensive_states,  # Always show all possible states
        'domains': sorted(list(set(safe_str(item.get('Enhanced_Domain', '')) for item in feedback_data if item.get('Enhanced_Domain')))),
        'sentiments': sorted(list(set(safe_str(item.get('Sentiment', '')) for item in feedback_data if item.get('Sentiment')))),
        'enhanced_categories': sorted(list(set(safe_str(item.get('Enhanced_Category', '')) for item in feedback_data if item.get('Enhanced_Category'))))
    }
    
    return options

# State Management API Endpoints

@app.route('/api/feedback/states', methods=['GET'])
def get_feedback_states():
    """Get all available feedback states"""
    try:
        states = state_manager.get_all_states()
        return jsonify({
            'status': 'success',
            'states': states
        })
    except Exception as e:
        logger.error(f"Error getting feedback states: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/feedback/state', methods=['POST'])
def update_feedback_state():
    """Update the state of a feedback item"""
    try:
        # Get bearer token for user identification
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'status': 'error', 'message': 'Authorization header required'}), 401
        
        # Extract user from token
        user = state_manager.extract_user_from_token(auth_header)
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        feedback_id = data.get('feedback_id')
        new_state = data.get('state')
        notes = data.get('notes', '')
        
        if not feedback_id or not new_state:
            return jsonify({'status': 'error', 'message': 'feedback_id and state are required'}), 400
        
        # Validate state
        if not state_manager.validate_state(new_state):
            return jsonify({'status': 'error', 'message': f'Invalid state: {new_state}'}), 400
        
        # Create state update
        update_data = state_manager.update_feedback_state(feedback_id, new_state, notes, user)
        
        # For now, update in memory (in production, this would update Fabric table)
        global last_collected_feedback
        for item in last_collected_feedback:
            if item.get('Feedback_ID') == feedback_id:
                item.update(update_data)
                break
        
        logger.info(f"Updated feedback {feedback_id} state to {new_state} by {user}")
        
        return jsonify({
            'status': 'success',
            'message': f'Feedback state updated to {new_state}',
            'data': update_data
        })
        
    except Exception as e:
        logger.error(f"Error updating feedback state: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/feedback/states/load', methods=['POST'])
def load_states_from_fabric():
    """Load all feedback states from Fabric Lakehouse"""
    try:
        # Get bearer token for authentication
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'status': 'error', 'message': 'Authorization header required'}), 401
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        feedback_ids = data.get('feedback_ids', [])
        if not feedback_ids:
            return jsonify({'status': 'error', 'message': 'feedback_ids array required'}), 400
        
        # Extract user from token
        user = state_manager.extract_user_from_token(auth_header)
        
        # TODO: Implement actual Fabric Lakehouse query to load states
        # For now, return mock data - this will be replaced with actual Fabric query
        fabric_states = {}
        for feedback_id in feedback_ids:
            # Mock: return random states for demonstration
            # In production, this would query the Fabric table for actual states
            fabric_states[feedback_id] = {
                'State': 'NEW',  # This would come from Fabric
                'Feedback_Notes': '',  # This would come from Fabric
                'Last_Updated': '2025-07-06T15:40:00Z',  # This would come from Fabric
                'Updated_By': 'System'  # This would come from Fabric
            }
        
        logger.info(f"Loaded states for {len(fabric_states)} feedback items from Fabric by {user}")
        
        return jsonify({
            'status': 'success',
            'message': f'Loaded {len(fabric_states)} feedback states from Fabric',
            'states': fabric_states
        })
        
    except Exception as e:
        logger.error(f"Error loading states from Fabric: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/store_session_token', methods=['POST'])
def store_session_token():
    """Store manually entered bearer token in session"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        token = data.get('token')
        if not token:
            return jsonify({'status': 'error', 'message': 'Token required'}), 400
        
        # Store token in session
        from flask import session
        session['fabric_bearer_token'] = token
        session['states_loaded'] = True
        
        logger.warning(f"🔑 STORED SESSION TOKEN: Token stored for session persistence")
        
        return jsonify({
            'status': 'success',
            'message': 'Token stored in session successfully'
        })
        
    except Exception as e:
        logger.error(f"Error storing session token: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/fabric/token/status', methods=['GET'])
def get_fabric_token_status():
    """Get current Fabric token status"""
    try:
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        last_validated = session.get('fabric_token_validated_at')
        session_starting = session.get('fabric_session_starting')
        session_id = session.get('fabric_session_id')
        
        # Check if has validated token
        if stored_token:
            return jsonify({
                'has_token': True,
                'last_validated': last_validated,
                'session_starting': session_starting or False,
                'session_id': session_id,
                'status': 'connected'
            })
        
        # No token
        return jsonify({
            'has_token': False,
            'status': 'disconnected'
        })
        
    except Exception as e:
        logger.error(f"Error getting token status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/fabric/token/validate', methods=['POST'])
def validate_fabric_token():
    """Validate Fabric token by testing SQL connection"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        token = data.get('token')
        if not token:
            return jsonify({'status': 'error', 'message': 'Token required'}), 400

        logger.info(f"🔥 FABRIC TOKEN VALIDATION: Testing token with SQL connection")
        
        # Test token with SQL connection
        from fabric_sql_writer import FabricSQLWriter
        
        try:
            writer = FabricSQLWriter(bearer_token=token)
            conn = writer.connect_with_token(token)
            
            if conn:
                conn.close()
                
                # Token is valid - store it
                from flask import session as flask_session
                flask_session['fabric_bearer_token'] = token
                flask_session['states_loaded'] = True
                flask_session['fabric_token_validated_at'] = datetime.now().isoformat()
                
                logger.info(f"✅ FABRIC TOKEN VALIDATION: Token validated successfully")
                
                return jsonify({
                    'status': 'success',
                    'message': 'Token validated successfully',
                    'validated_at': flask_session['fabric_token_validated_at']
                })
            else:
                logger.error(f"❌ FABRIC TOKEN VALIDATION: SQL connection failed")
                return jsonify({
                    'status': 'error',
                    'message': 'Token validation failed - could not connect to SQL database'
                }), 400
                
        except Exception as conn_error:
            logger.error(f"❌ FABRIC TOKEN VALIDATION: Connection error: {conn_error}")
            return jsonify({
                'status': 'error',
                'message': f'Token validation failed: {str(conn_error)}'
            }), 400
            
    except ImportError as ie:
        logger.error(f"❌ FABRIC TOKEN VALIDATION: fabric_sql_writer module not available: {ie}")
        return jsonify({
            'status': 'error',
            'message': 'Fabric SQL writer not available'
        }), 500
    except Exception as e:
        logger.error(f"❌ FABRIC TOKEN VALIDATION: Error validating token: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Token validation error: {str(e)}'
        }), 500

@app.route('/api/fabric/token/clear', methods=['POST'])
def clear_fabric_token():
    """Clear stored Fabric token"""
    try:
        from flask import session
        
        # Clear token from session
        session.pop('fabric_bearer_token', None)
        session.pop('states_loaded', None)
        session.pop('fabric_token_validated_at', None)
        
        logger.warning(f"🗑️ FABRIC TOKEN CLEARED: Token removed from session")
        
        return jsonify({
            'status': 'success',
            'message': 'Fabric token cleared successfully'
        })
        
    except Exception as e:
        logger.error(f"Error clearing token: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/collection-progress')
def collection_progress():
    """Server-Sent Events endpoint for real-time collection progress"""
    def generate():
        while True:
            yield f"data: {json.dumps(collection_status)}\n\n"
            
            # Stop streaming AFTER sending the final status
            if collection_status.get('status') in ['completed', 'error']:
                break
                
            time.sleep(1)
    
    return app.response_class(generate(), mimetype='text/event-stream')

@app.route('/api/collection_status', methods=['GET'])
def get_collection_status():
    """Get current collection operation status for badge synchronization"""
    try:
        global collection_status
        
        # Return current collection status
        return jsonify({
            'status': collection_status['status'],
            'message': collection_status['message'],
            'start_time': collection_status['start_time'],
            'end_time': collection_status['end_time'],
            'total_items': collection_status['total_items'],
            'current_source': collection_status['current_source'],
            'sources_completed': collection_status['sources_completed'],
            'error_message': collection_status['error_message'],
            'source_counts': collection_status.get('source_counts', {}),
            'progress': collection_status.get('progress', 0)
        })
        
    except Exception as e:
        logger.error(f"Error checking collection status: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Error checking collection status'
        }), 500

@app.route('/api/feedback/states/sync', methods=['POST'])
def sync_states_to_fabric():
    """Batch sync cached state changes to Fabric Lakehouse"""
    try:
        # Get bearer token for authentication
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'status': 'error', 'message': 'Authorization header required'}), 401
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        state_changes = data.get('state_changes', [])
        if not state_changes:
            return jsonify({'status': 'error', 'message': 'state_changes array required'}), 400
        
        # Extract user from token
        user = state_manager.extract_user_from_token(auth_header)
        
        # Validate all state changes
        for change in state_changes:
            feedback_id = change.get('feedback_id')
            new_state = change.get('state')
            
            if not feedback_id:
                return jsonify({'status': 'error', 'message': 'feedback_id required for all changes'}), 400
            
            if new_state and not state_manager.validate_state(new_state):
                return jsonify({'status': 'error', 'message': f'Invalid state: {new_state}'}), 400
        logger.info(f"🔥 FABRIC SQL SYNC: Writing {len(state_changes)} state changes to Fabric SQL Database")
        print(f"🔥 FABRIC SQL SYNC: Processing {len(state_changes)} state changes")
        
        # Update in Fabric SQL database using state_manager (no bearer token needed)
        success = state_manager.update_feedback_states_in_fabric_sql(
            auth_header.replace('Bearer ', ''),
            state_changes
        )
        
        if not success:
            logger.error("❌ FABRIC SQL SYNC FAILED: Could not write to Fabric SQL Database")
            return jsonify({
                'status': 'error',
                'message': 'Failed to write state changes to Fabric SQL Database'
            }), 500
            
        logger.warning("✅ FABRIC SQL SYNC SUCCESS: All state changes written to Fabric SQL Database")
        print("✅ FABRIC SQL SYNC COMPLETED SUCCESSFULLY")
        
        # Update in-memory data after successful Fabric write
        global last_collected_feedback
        updated_count = 0
        
        for change in state_changes:
            feedback_id = change.get('feedback_id')
            
            # Find and update the feedback item in memory
            for item in last_collected_feedback:
                if item.get('Feedback_ID') == feedback_id:
                    # Update all provided fields
                    if 'state' in change:
                        item['State'] = change['state']
                    if 'notes' in change:
                        item['Feedback_Notes'] = change['notes']
                    if 'domain' in change:
                        item['Primary_Domain'] = change['domain']
                    
                    # Update audit fields
                    item['Last_Updated'] = datetime.now().isoformat()
                    item['Updated_By'] = user
                    
                    updated_count += 1
                    break
        
        logger.info(f"Synced {updated_count} state changes to Fabric by {user}")
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully synced {updated_count} state changes to Fabric',
            'updated_count': updated_count
        })
        
    except Exception as e:
        logger.error(f"Error syncing states to Fabric: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/fabric/sync', methods=['POST'])
def sync_with_fabric():
    """Connect to Fabric SQL Database, write all feedback data, and load existing state data"""
    try:
        logger.info("🔄 Starting Fabric SQL sync process...")
        
        # Get request data early (before any processing)
        request_data = {}
        try:
            if request.is_json:
                request_data = request.get_json() or {}
        except Exception as json_error:
            logger.debug(f"No JSON body in request: {json_error}")
            request_data = {}
        
        # Import SQL writer
        import fabric_sql_writer
        
        # Test SQL connection and create writer
        writer = fabric_sql_writer.FabricSQLWriter()
        
        # Try to connect to SQL database (will prompt for Azure AD auth)
        try:
            conn = writer.connect_interactive()
            
            # Ensure both tables exist
            writer.ensure_feedback_table(conn)
            writer.ensure_feedback_state_table(conn)
            
            # Step 1: Bulletproof sync of cached feedback data to Feedback table
            global last_collected_feedback
            sync_result = {'new_items': 0, 'existing_items': 0, 'total_items': 0, 'id_regenerated': 0}
            if last_collected_feedback:
                logger.info(f"🔄 Bulletproof sync: Analyzing {len(last_collected_feedback)} feedback items...")
                
                # Use the bulletproof bulk writer with deterministic IDs
                sync_result = writer.write_feedback_bulk(last_collected_feedback, use_token=False)
                logger.info(f"✅ Bulletproof sync complete: {sync_result['new_items']} new, {sync_result['existing_items']} existing, {sync_result['id_regenerated']} IDs regenerated")
            
            # Step 2: Load all existing state data from FeedbackState table
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Feedback_ID, State, Feedback_Notes, Primary_Domain, Last_Updated, Updated_By
                FROM FeedbackState
            """)
            
            state_data = {}
            rows = cursor.fetchall()
            for row in rows:
                state_data[row[0]] = {
                    'state': row[1],
                    'notes': row[2],
                    'domain': row[3],
                    'last_updated': row[4].isoformat() if row[4] else None,
                    'updated_by': row[5]
                }
            
            conn.close()
            
            # CRITICAL FIX: Apply loaded state data to in-memory feedback items
            if state_data and last_collected_feedback:
                applied_states = 0
                applied_domains = 0
                applied_notes = 0
                
                for item in last_collected_feedback:
                    feedback_id = item.get('Feedback_ID')
                    if feedback_id and feedback_id in state_data:
                        sql_state = state_data[feedback_id]
                        
                        # Apply state from SQL (manual updates take precedence)
                        if sql_state.get('state'):
                            item['State'] = sql_state['state']
                            applied_states += 1
                        
                        # Apply domain from SQL (manual updates take precedence) 
                        if sql_state.get('domain'):
                            original_domain = item.get('Primary_Domain')
                            item['Primary_Domain'] = sql_state['domain']
                            logger.info(f"🔄 Applied domain update for {feedback_id}: {original_domain} → {sql_state['domain']}")
                            applied_domains += 1
                            
                        # Apply notes from SQL
                        if sql_state.get('notes'):
                            item['Feedback_Notes'] = sql_state['notes']
                            applied_notes += 1
                            
                        # Apply audit info
                        if sql_state.get('last_updated'):
                            item['Last_Updated'] = sql_state['last_updated']
                        if sql_state.get('updated_by'):
                            item['Updated_By'] = sql_state['updated_by']
                
                logger.info(f"✅ Applied SQL state data to in-memory feedback: {applied_states} states, {applied_domains} domains, {applied_notes} notes")
            
            # Set session flags to indicate successful SQL connection and data sync
            from flask import session
            session['states_loaded'] = True
            session['sql_data_applied'] = True  # New flag to indicate SQL data has been applied to in-memory data
            session['fabric_bearer_token'] = 'SQL_CONNECTED'  # Pseudo-token to enable domain updates
            
            logger.info(f"✅ Successfully completed Fabric sync: {sync_result['new_items']} new items + {len(state_data)} state records")
            logger.info("🔑 Set session flags and pseudo-bearer token for domain updates")
            
            # Check if recategorization is requested (request_data parsed at function start)
            recategorize_result = None
            if request_data.get('recategorize', False):
                logger.info("🔄 Starting automatic recategorization...")
                recategorize_result = writer.recategorize_all_feedback(use_token=False)
                logger.info(f"✅ Recategorization complete: {recategorize_result['recategorized']} items updated")
            
            # Create detailed success message
            message_parts = [
                f"Added {sync_result['new_items']} new items",
                f"skipped {sync_result['existing_items']} existing items",
                f"loaded {len(state_data)} state records"
            ]
            
            if sync_result.get('id_regenerated', 0) > 0:
                message_parts.append(f"regenerated {sync_result['id_regenerated']} deterministic IDs")
            
            if recategorize_result:
                message_parts.append(f"recategorized {recategorize_result['recategorized']} items")
            
            success_message = f"Connected to Fabric SQL Database. {', '.join(message_parts)}"
            
            response_data = {
                'status': 'success',
                'message': success_message,
                'sync_result': sync_result,
                'state_data': state_data,
                'connected': True
            }
            
            if recategorize_result:
                response_data['recategorize_result'] = recategorize_result
            
            return jsonify(response_data)
            
        except Exception as sql_error:
            logger.error(f"❌ SQL connection failed: {sql_error}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to connect to Fabric SQL Database: {str(sql_error)}',
                'connected': False
            }), 500
            
    except Exception as e:
        logger.error(f"Error in sync_with_fabric: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500



@app.route('/api/feedback/state/update', methods=['POST'])
def update_feedback_state_sql():
    """Update a single feedback state and immediately sync to SQL"""
    try:
        # Validate session and authentication
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        has_bearer_token = stored_token and stored_token.strip() and stored_token != 'None'
        
        if not has_bearer_token:
            logger.warning("❌ STATE UPDATE DENIED: No valid bearer token in session")
            return jsonify({'status': 'error', 'message': 'Not connected to Fabric. Please sync with Fabric first.'}), 403
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        feedback_id = data.get('feedback_id')
        if not feedback_id:
            return jsonify({'status': 'error', 'message': 'feedback_id required'}), 400
        
        logger.info(f"🔄 STATE UPDATE REQUEST: Updating {feedback_id} with data: {data}")
        
        # Validate state if provided
        new_state = data.get('state')
        if new_state and not state_manager.validate_state(new_state):
            return jsonify({'status': 'error', 'message': f'Invalid state: {new_state}'}), 400
        
        # Import SQL writer and update immediately
        import fabric_sql_writer
        
        # Create state change record
        state_change = {
            'feedback_id': feedback_id,
            'state': data.get('state'),
            'notes': data.get('notes'),
            'domain': data.get('domain'),
            'updated_by': 'user'  # TODO: Get from session or context
        }
        
        # Remove None values
        state_change = {k: v for k, v in state_change.items() if v is not None}
        
        logger.info(f"🔄 Updating state for feedback {feedback_id}: {state_change}")
        
        # Write to SQL database immediately
        writer = fabric_sql_writer.FabricSQLWriter()
        success = writer.update_feedback_states([state_change], use_token=False)
        
        if success:
            logger.info(f"✅ Successfully updated feedback {feedback_id} in SQL database")
            
            # Update in-memory cache
            global last_collected_feedback
            for item in last_collected_feedback:
                if item.get('Feedback_ID') == feedback_id:
                    if 'state' in data:
                        item['State'] = data['state']
                    if 'notes' in data:
                        item['Feedback_Notes'] = data['notes']
                    if 'domain' in data:
                        item['Primary_Domain'] = data['domain']
                    item['Last_Updated'] = datetime.now().isoformat()
                    break
            
            return jsonify({
                'status': 'success',
                'message': 'State updated successfully',
                'feedback_id': feedback_id
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update state in SQL database'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating feedback state: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/feedback/domain', methods=['POST'])
def update_feedback_domain():
    """Update the primary domain of a feedback item"""
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        feedback_id = data.get('feedback_id')
        new_domain = data.get('domain')
        
        if not feedback_id or not new_domain:
            return jsonify({'status': 'error', 'message': 'feedback_id and domain are required'}), 400
        
        logger.info(f"🔄 Updating domain for feedback {feedback_id}: {new_domain}")
        
        # Import SQL writer and update immediately
        import fabric_sql_writer
        
        # Create state change record for domain update
        state_change = {
            'feedback_id': feedback_id,
            'domain': new_domain,
            'updated_by': 'user'  # TODO: Get from session or context
        }
        
        logger.info(f"🔄 Updating domain for feedback {feedback_id}: {state_change}")
        
        # Write to SQL database immediately
        writer = fabric_sql_writer.FabricSQLWriter()
        success = writer.update_feedback_states([state_change], use_token=False)
        
        if success:
            logger.info(f"✅ Successfully updated domain for feedback {feedback_id} in SQL database")
            
            # Update in-memory cache
            global last_collected_feedback
            for item in last_collected_feedback:
                if item.get('Feedback_ID') == feedback_id:
                    item['Primary_Domain'] = new_domain
                    item['Last_Updated'] = datetime.now().isoformat()
                    break
            
            return jsonify({
                'status': 'success',
                'message': f'Feedback domain updated to {new_domain}',
                'feedback_id': feedback_id,
                'domain': new_domain
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update domain in SQL database'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating feedback domain: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/feedback/notes', methods=['POST'])
def update_feedback_notes():
    """Update the notes of a feedback item"""
    try:
        # Validate session and authentication
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        has_bearer_token = stored_token and stored_token.strip() and stored_token != 'None'
        
        if not has_bearer_token:
            logger.warning("❌ NOTES UPDATE DENIED: No valid bearer token in session")
            return jsonify({'status': 'error', 'message': 'Not connected to Fabric. Please sync with Fabric first.'}), 403
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        feedback_id = data.get('feedback_id')
        notes = data.get('notes', '')
        
        if not feedback_id:
            return jsonify({'status': 'error', 'message': 'feedback_id is required'}), 400
        
        logger.info(f"🔄 NOTES UPDATE REQUEST: Updating {feedback_id} notes: {notes[:50]}...")
        
        # Import SQL writer and update immediately
        import fabric_sql_writer
        
        # Create state change record for notes update
        state_change = {
            'feedback_id': feedback_id,
            'notes': notes,
            'updated_by': 'user'  # TODO: Get from session or context
        }
        
        logger.info(f"🔄 Updating notes for feedback {feedback_id}: {state_change}")
        
        # Write to SQL database immediately
        writer = fabric_sql_writer.FabricSQLWriter()
        success = writer.update_feedback_states([state_change], use_token=False)
        
        if success:
            logger.info(f"✅ Successfully updated notes for feedback {feedback_id} in SQL database")
            
            # Update in-memory cache
            global last_collected_feedback
            for item in last_collected_feedback:
                if item.get('Feedback_ID') == feedback_id:
                    item['Feedback_Notes'] = notes
                    item['Last_Updated'] = datetime.now().isoformat()
                    break
            
            return jsonify({
                'status': 'success',
                'message': 'Notes updated successfully',
                'feedback_id': feedback_id,
                'notes': notes
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update notes in SQL database'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating feedback notes: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
    except Exception as e:
        logger.error(f"Error updating feedback notes: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/update_domain_sql', methods=['POST'])
def update_domain_sql():
    """Update feedback domain directly in SQL database"""
    try:
        # Validate session and authentication
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        has_bearer_token = stored_token and stored_token.strip() and stored_token != 'None'
        
        if not has_bearer_token:
            logger.warning("❌ DOMAIN UPDATE DENIED: No valid bearer token in session")
            return jsonify({'success': False, 'message': 'Not connected to Fabric. Please sync with Fabric first.'}), 403
        
        data = request.get_json()
        feedback_id = data.get('feedback_id')
        new_domain = data.get('new_domain')
        
        if not feedback_id or not new_domain:
            return jsonify({'success': False, 'message': 'Missing feedback_id or new_domain'}), 400
        
        logger.info(f"🔄 DOMAIN UPDATE REQUEST: Updating {feedback_id} to domain {new_domain}")
        
        # Validate domain
        valid_domains = list(config.DOMAIN_CATEGORIES.keys())
        if new_domain not in valid_domains:
            return jsonify({'success': False, 'message': f'Invalid domain. Must be one of: {valid_domains}'}), 400
        
        # Map internal domain code to friendly name for storage
        domain_mapping = {code: details['name'] for code, details in config.DOMAIN_CATEGORIES.items()}
        
        # Convert internal code to friendly name
        friendly_domain_name = domain_mapping.get(new_domain, new_domain)
        
        # Update in Fabric SQL database using state_manager (no bearer token needed)
        success = state_manager.update_feedback_field_in_sql(feedback_id, 'Primary_Domain', friendly_domain_name, None)
        
        if success:
            logger.info(f"✅ Successfully updated domain for {feedback_id} to {friendly_domain_name} (from {new_domain})")
            return jsonify({'success': True, 'message': f'Domain updated to {friendly_domain_name}'})
        else:
            logger.error(f"❌ Failed to update domain in database for {feedback_id}")
            return jsonify({'success': False, 'message': 'Failed to update domain in database'}), 500
            
    except Exception as e:
        logger.error(f"Error updating domain: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update_category_sql', methods=['POST'])
def update_category_sql():
    """Update feedback category/subcategory metadata directly in SQL."""
    try:
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        has_bearer_token = stored_token and stored_token.strip() and stored_token != 'None'

        if not has_bearer_token:
            logger.warning("❌ CATEGORY UPDATE DENIED: No valid bearer token in session")
            return jsonify({'success': False, 'message': 'Not connected to Fabric. Please sync with Fabric first.'}), 403

        data = request.get_json() or {}
        feedback_id = data.get('feedback_id')

        if not feedback_id:
            return jsonify({'success': False, 'message': 'Missing feedback_id'}), 400

        def _clean(value):
            if isinstance(value, str):
                value = value.strip()
                return value if value else None
            return value

        category_name = _clean(data.get('category_name'))
        subcategory_name = _clean(data.get('subcategory_name'))
        feature_area = _clean(data.get('feature_area'))
        domain_code = _clean(data.get('domain_code'))

        success = state_manager.update_feedback_category_in_sql(
            feedback_id,
            category_name,
            subcategory_name,
            feature_area,
            domain_code
        )

        if success:
            friendly_category = category_name or 'None'
            message = f"Category updated to {friendly_category}"
            if subcategory_name:
                message += f" → {subcategory_name}"
            if domain_code:
                message += f" | Domain: {domain_code}"
            return jsonify({'success': True, 'message': message})

        logger.error(f"❌ Failed to update category metadata in database for {feedback_id}")
        return jsonify({'success': False, 'message': 'Failed to update category in database'}), 500

    except Exception as e:
        logger.error(f"Error updating category metadata: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update_audience_sql', methods=['POST'])
def update_audience_sql():
    """Update feedback audience directly in SQL database"""
    try:
        # Validate session and authentication
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        has_bearer_token = stored_token and stored_token.strip() and stored_token != 'None'
        
        if not has_bearer_token:
            logger.warning("❌ AUDIENCE UPDATE DENIED: No valid bearer token in session")
            return jsonify({'success': False, 'message': 'Not connected to Fabric. Please sync with Fabric first.'}), 403
        
        data = request.get_json()
        feedback_id = data.get('feedback_id')
        new_audience = data.get('new_audience')
        
        if not feedback_id or not new_audience:
            return jsonify({'success': False, 'message': 'Missing feedback_id or new_audience'}), 400
        
        logger.info(f"🔄 AUDIENCE UPDATE REQUEST: Updating {feedback_id} to audience {new_audience}")
        
        # Validate audience (only Developer or Customer)
        valid_audiences = ['Developer', 'Customer']
        if new_audience not in valid_audiences:
            return jsonify({'success': False, 'message': f'Invalid audience. Must be one of: {valid_audiences}'}), 400
        
        # Update in Fabric SQL database using state_manager (no bearer token needed)
        success = state_manager.update_feedback_field_in_sql(feedback_id, 'Audience', new_audience, None)
        
        if success:
            logger.info(f"✅ Successfully updated audience for {feedback_id} to {new_audience}")
            return jsonify({'success': True, 'message': f'Audience updated to {new_audience}'})
        else:
            logger.error(f"❌ Failed to update audience in database for {feedback_id}")
            return jsonify({'success': False, 'message': 'Failed to update audience in database'}), 500
            
    except Exception as e:
        logger.error(f"Error updating audience: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/feedback/query/getting_started', methods=['GET'])
def get_getting_started_feedback_ids():
    """Get all Feedback IDs that are tagged with 'Getting Started' domain"""
    try:
        import state_manager
        
        # Get all feedback states from SQL database
        all_states = state_manager.get_all_feedback_states()
        
        if not all_states:
            return jsonify({
                'status': 'success',
                'total_found': 0,
                'feedback_ids': [],
                'details': [],
                'delete_sql': '',
                'message': 'No feedback states found in database'
            })
        
        # Filter for Getting Started domain
        getting_started_ids = []
        getting_started_details = []
        
        for feedback_id, state_data in all_states.items():
            domain = state_data.get('domain', '')
            if domain and ('Getting Started' in domain or 'GETTING_STARTED' in domain):
                getting_started_ids.append(feedback_id)
                getting_started_details.append({
                    'feedback_id': feedback_id,
                    'domain': domain,
                    'state': state_data.get('state', ''),
                    'notes': state_data.get('notes', ''),
                    'last_updated': state_data.get('last_updated', ''),
                    'updated_by': state_data.get('updated_by', '')
                })
        
        # Generate SQL DELETE statement
        delete_sql = ""
        transaction_sql = ""
        
        if getting_started_ids:
            ids_list = "', '".join(getting_started_ids)
            delete_sql = f"DELETE FROM FeedbackState WHERE Feedback_ID IN ('{ids_list}');"
            
            # Create safer transaction version
            transaction_sql = f"""BEGIN TRANSACTION;

-- Preview what will be deleted
SELECT Feedback_ID, Primary_Domain, State, Feedback_Notes 
FROM FeedbackState 
WHERE Feedback_ID IN ('{ids_list}');

-- Uncomment the line below to actually delete (after reviewing the preview)
-- DELETE FROM FeedbackState WHERE Feedback_ID IN ('{ids_list}');

-- Commit or rollback as needed
-- COMMIT;
-- ROLLBACK;"""
        
        return jsonify({
            'status': 'success',
            'total_found': len(getting_started_ids),
            'total_stored': len(all_states),
            'feedback_ids': getting_started_ids,
            'details': getting_started_details,
            'delete_sql': delete_sql,
            'transaction_sql': transaction_sql,
            'message': f'Found {len(getting_started_ids)} feedback items tagged with Getting Started out of {len(all_states)} total items'
        })
        
    except Exception as e:
        logger.error(f"Error querying Getting Started feedback: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/debug/feedback_domains', methods=['GET'])
def debug_feedback_domains():
    """Debug endpoint to check domain values in memory"""
    try:
        global last_collected_feedback
        
        if not last_collected_feedback:
            return jsonify({
                'status': 'info',
                'message': 'No feedback in memory',
                'count': 0,
                'domains': {}
            })
        
        # Get domain distribution
        domain_counts = {}
        sample_items = []
        
        for item in last_collected_feedback[:10]:  # Show first 10 items
            domain = item.get('Primary_Domain', 'None')
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            
            sample_items.append({
                'feedback_id': item.get('Feedback_ID', 'No ID'),
                'title': item.get('Title', 'No Title')[:50] + '...' if len(item.get('Title', '')) > 50 else item.get('Title', 'No Title'),
                'domain': domain,
                'state': item.get('State', 'No State'),
                'last_updated': item.get('Last_Updated', 'Never')
            })
        
        from flask import session
        return jsonify({
            'status': 'success',
            'total_items': len(last_collected_feedback),
            'domain_counts': domain_counts,
            'sample_items': sample_items,
            'session_flags': {
                'has_token': bool(session.get('fabric_bearer_token')),
                'states_loaded': session.get('states_loaded', False),
                'sql_data_applied': session.get('sql_data_applied', False)
            }
        })
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/debug/feedback_status', methods=['GET'])
def debug_feedback_status():
    """Debug endpoint to inspect feedback data and SQL sync status"""
    from flask import session
    
    # Check session flags
    stored_token = session.get('fabric_bearer_token')
    is_online_mode = stored_token and stored_token.strip() and stored_token != 'None'
    sql_data_applied = session.get('sql_data_applied', False)
    states_loaded = session.get('states_loaded', False)
    
    # Check in-memory feedback
    feedback_count = len(last_collected_feedback)
    sample_feedback = last_collected_feedback[:3] if last_collected_feedback else []
    
    # Sample domains from in-memory data
    sample_domains = [item.get('Primary_Domain', 'None') for item in last_collected_feedback[:10]]
    sample_states = [item.get('State', 'None') for item in last_collected_feedback[:10]]
    
    # Check SQL data if online
    sql_record_count = 0
    sql_sample_domains = []
    if is_online_mode:
        try:
            sql_data = state_manager.get_all_feedback_states()
            sql_record_count = len(sql_data) if sql_data else 0
            sql_sample_domains = list(sql_data.values())[:5] if sql_data else []
        except Exception as e:
            sql_sample_domains = [f"Error: {str(e)}"]
    
    debug_info = {
        'session_info': {
            'is_online_mode': is_online_mode,
            'has_token': bool(stored_token),
            'sql_data_applied': sql_data_applied,
            'states_loaded': states_loaded
        },
        'memory_info': {
            'feedback_count': feedback_count,
            'sample_domains': sample_domains,
            'sample_states': sample_states,
            'sample_feedback_ids': [item.get('Feedback_ID', 'None') for item in sample_feedback]
        },
        'sql_info': {
            'sql_record_count': sql_record_count,
            'sql_sample_domains': sql_sample_domains
        },
        'sample_feedback': [
            {
                'id': item.get('Feedback_ID', 'None'),
                'title': item.get('Title', 'None')[:50] + '...' if item.get('Title') else 'None',
                'domain': item.get('Primary_Domain', 'None'),
                'state': item.get('State', 'None'),
                'source': item.get('Sources', 'None')
            } for item in sample_feedback
        ]
    }
    
    return jsonify(debug_info)
@app.route('/api/fabric/domains/sync', methods=['POST'])
def sync_domains_from_state():
    """Sync domain updates from FeedbackState to Feedback table"""
    try:
        logger.info("🔄 Starting domain sync from FeedbackState to Feedback table...")
        
        # Import SQL writer
        import fabric_sql_writer
        
        # Create writer and sync domains
        writer = fabric_sql_writer.FabricSQLWriter()
        updated_count = writer.sync_domains_from_state(use_token=False)
        
        if updated_count > 0:
            logger.info(f"✅ Domain sync complete: {updated_count} records updated")
            
            # Also update in-memory data to reflect the changes
            global last_collected_feedback
            if last_collected_feedback:
                # Load updated state data from database
                state_data = writer.load_feedback_states()
                
                # Apply domain updates to in-memory feedback
                applied_domains = 0
                for item in last_collected_feedback:
                    feedback_id = item.get('Feedback_ID')
                    if feedback_id and feedback_id in state_data:
                        sql_state = state_data[feedback_id]
                        if sql_state.get('domain'):
                            original_domain = item.get('Primary_Domain')
                            item['Primary_Domain'] = sql_state['domain']
                            logger.info(f"🔄 Applied domain update to memory for {feedback_id}: {original_domain} → {sql_state['domain']}")
                            applied_domains += 1
                
                logger.info(f"✅ Applied {applied_domains} domain updates to in-memory feedback")
            
            return jsonify({
                'status': 'success',
                'message': f'Successfully synced {updated_count} domain updates from FeedbackState to Feedback table',
                'updated_count': updated_count
            })
        else:
            return jsonify({
                'status': 'success',
                'message': 'No domain updates to sync',
                'updated_count': 0
            })
        
    except Exception as e:
        logger.error(f"Error syncing domains from state: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/data/<filename>')
def download_csv(filename):
    """Serve CSV files from the data directory"""
    try:
        # Validate filename to prevent directory traversal attacks
        if not filename.startswith('feedback_') or not filename.endswith('.csv'):
            return jsonify({'error': 'Invalid filename'}), 400
        
        # Construct the full path to the CSV file
        filepath = os.path.join(DATA_DIR, filename)
        
        # Check if file exists
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        # Send the file with proper headers
        return send_from_directory(
            DATA_DIR,
            filename,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
        
    except Exception as e:
        logger.error(f"Error serving CSV file {filename}: {e}")
        return jsonify({'error': 'Error serving file'}), 500