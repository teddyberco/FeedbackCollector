from flask import Flask, render_template, request, jsonify, send_from_directory, current_app
import pandas as pd
import os
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple
import json

from collectors import RedditCollector, FabricCommunityCollector, GitHubDiscussionsCollector
from ado_client import get_working_ado_items
import config
import utils
import state_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'feedback_collector_secret_key_2025'  # For session management

last_collected_feedback = []
last_collection_summary = {"reddit": 0, "fabric": 0, "github": 0, "total": 0}

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
        
        # Convert DataFrame to list of dictionaries
        feedback_items = df.to_dict('records')
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
        
        all_feedback = []
        results = {}
        
        # Initialize all feedback variables to empty lists
        reddit_feedback = []
        fabric_feedback = []
        github_feedback = []
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
            logger.info(f"🐙 GITHUB: Collecting from {github_config.get('owner', 'microsoft')}/{github_config.get('repo', 'Microsoft-Fabric-workload-development-sample')}")
            
            github_collector = GitHubDiscussionsCollector()
            
            # Pass configuration to collector if it supports it
            if hasattr(github_collector, 'configure'):
                github_collector.configure({
                    'owner': github_config.get('owner', 'microsoft'),
                    'repo': github_config.get('repo', 'Microsoft-Fabric-workload-development-sample'),
                    'state': github_config.get('state', 'all'),
                    'max_items': github_config.get('maxItems', 200)
                })
            
            github_feedback = github_collector.collect()
            logger.info(f"GitHub Discussions collector found {len(github_feedback)} items.")
            collection_status['sources_completed'].append('GitHub Discussions')
            if total_sources > 0:
                collection_status['progress'] = (len(collection_status['sources_completed']) / total_sources) * 100
            # Add source counts for real-time updates
            collection_status['source_counts'] = collection_status.get('source_counts', {})
            collection_status['source_counts']['github'] = len(github_feedback)
            all_feedback.extend(github_feedback)
            results['github'] = {'count': len(github_feedback), 'completed': True}
        
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
                    return str(value) if value != default else default                # Clean the text to remove HTML/CSS formatting
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
        github_feedback = add_sentiment_to_feedback(github_feedback, "GitHub")
        
        # Note: all_feedback was already built by extending with each source
        # No need to combine again as it would lose the items
        logger.info(f"Final feedback counts: Reddit={len(reddit_feedback)}, Fabric={len(fabric_feedback)}, GitHub={len(github_feedback)}, ADO={len(ado_feedback)}, Total={len(all_feedback)}")
        
        # Generate deterministic IDs for all feedback items BEFORE state initialization
        from id_generator import FeedbackIDGenerator
        for feedback_item in all_feedback:
            if 'Feedback_ID' not in feedback_item or not feedback_item.get('Feedback_ID'):
                feedback_item['Feedback_ID'] = FeedbackIDGenerator.generate_id_from_feedback_dict(feedback_item)
                logger.info(f"Generated deterministic ID for item: {feedback_item['Feedback_ID']}")
                logger.info(f"  Title: {feedback_item.get('Title', 'MISSING')}")
                logger.info(f"  Content: {str(feedback_item.get('Content', 'MISSING'))[:100]}...")
                logger.info(f"  Source: {feedback_item.get('Source', 'MISSING')}")
                logger.info(f"  Author: {feedback_item.get('Author', 'MISSING')}")
        
        # Check if we're in online mode (connected to Fabric)
        from flask import session
        stored_token = session.get('fabric_bearer_token')
        is_online_mode = stored_token and stored_token.strip() and stored_token != 'None'
        
        # CRITICAL FIX: Preserve manually updated domains and states from SQL database
        # This prevents collection from overwriting user's manual categorizations
        # ONLY attempt this in ONLINE mode to avoid database connections during offline collection
        if is_online_mode:
            try:
                logger.info("🔄 ONLINE MODE: Loading existing state data to preserve manual updates during collection")
                logger.warning("📡 DATABASE CONNECTION: About to connect to SQL database for state preservation")
                existing_state_data = state_manager.get_all_feedback_states()
                logger.info(f"📡 DATABASE CONNECTION: Successfully retrieved {len(existing_state_data) if existing_state_data else 0} state records from SQL")
                
                if existing_state_data:
                    preserved_count = 0
                    domain_preserved_count = 0
                    for feedback_item in all_feedback:
                        feedback_id = feedback_item.get('Feedback_ID')
                        if feedback_id and feedback_id in existing_state_data:
                            existing_state = existing_state_data[feedback_id]
                            
                            # Preserve manually updated domain (KEY FIX for the persistence issue)
                            if existing_state.get('domain'):
                                original_domain = feedback_item.get('Primary_Domain')
                                feedback_item['Primary_Domain'] = existing_state['domain']
                                logger.info(f"🔒 Preserved manual domain for {feedback_id}: {original_domain} → {existing_state['domain']}")
                                domain_preserved_count += 1
                            
                            # Preserve manually updated state
                            if existing_state.get('state'):
                                original_state = feedback_item.get('State', 'NEW')
                                feedback_item['State'] = existing_state['state']
                                logger.debug(f"🔒 Preserved manual state for {feedback_id}: {original_state} → {existing_state['state']}")
                                preserved_count += 1
                    
                    logger.info(f"✅ Preserved manual updates during collection: {preserved_count} states, {domain_preserved_count} domains")
                else:
                    logger.info("📊 No existing state data found - using fresh categorization")
            except Exception as e:
                logger.error(f"❌ Error preserving manual updates during collection: {e}")
        else:
            logger.info("📴 OFFLINE MODE: Skipping SQL state preservation during collection (no database access)")
        
        # Initialize state management for all feedback items
        for feedback_item in all_feedback:
            state_manager.initialize_feedback_state(feedback_item)
        
        last_collected_feedback = all_feedback
        last_collection_summary = {
            "reddit": {"count": len(reddit_feedback), "completed": True},
            "fabric": {"count": len(fabric_feedback), "completed": True},
            "github": {"count": len(github_feedback), "completed": True},
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
        logger.error(f"Error in collection route: {e}")
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
    
    # Check Fabric SQL connection state (for state management and UI features)
    # Use OR logic - if either flag is set, we consider SQL connected
    fabric_sql_connected = session.get('states_loaded', False) or session.get('sql_data_applied', False)
    
    # If fabric_connected parameter is present, it indicates a Fabric SQL connection was made
    if fabric_connected_param:
        logger.info("🔗 FABRIC CONNECTED parameter detected - Fabric SQL connection active")
        fabric_sql_connected = True
        
    # Online mode for lakehouse writes (bearer token based)
    is_online_mode = stored_token and stored_token.strip() and stored_token != 'None'
    
    logger.info(f"Bearer Token Mode: {'ONLINE' if is_online_mode else 'OFFLINE'} - Token: {'Present' if stored_token else 'None'}")
    logger.info(f"Fabric SQL Connected: {fabric_sql_connected} - Session states_loaded: {session.get('states_loaded', False)}, sql_data_applied: {session.get('sql_data_applied', False)}")
    
    # CRITICAL FIX: For normal collection viewing (without Fabric connection), we're in OFFLINE mode
    # Only set online mode if we actually have a bearer token AND are connected to Fabric
    if not is_online_mode:
        fabric_sql_connected = False
        # Clear potentially stale session flags when in offline mode
        session.pop('states_loaded', None)
        session.pop('sql_data_applied', None)
        logger.info("🔒 OFFLINE MODE: Forcing fabric_sql_connected to False and clearing session flags")
    
    # If no feedback in memory, try loading from CSV (OFFLINE MODE)
    if not last_collected_feedback:
        logger.info("No feedback in memory, loading from CSV (OFFLINE MODE)")
        last_collected_feedback = load_latest_feedback_from_csv()
        
        # Basic processing for CSV data (offline mode)
        if last_collected_feedback:
            from id_generator import FeedbackIDGenerator
            
            # Generate IDs and basic processing
            for item in last_collected_feedback:
                # Generate deterministic Feedback_ID if not present
                if 'Feedback_ID' not in item or not item.get('Feedback_ID'):
                    item['Feedback_ID'] = FeedbackIDGenerator.generate_id_from_feedback_dict(item)
                
                # Apply sentiment analysis if not already present
                if 'Sentiment_Score' not in item or item.get('Sentiment_Score') is None:
                    text_content = item.get('Feedback', '') or item.get('Content', '') or item.get('Title', '')
                    sentiment_analysis = utils.analyze_sentiment(text_content)
                    item['Sentiment'] = sentiment_analysis['label']
                    item['Sentiment_Score'] = sentiment_analysis['polarity']
                    item['Sentiment_Confidence'] = sentiment_analysis['confidence']
                
                # Basic categorization for display (offline mode)
                if not item.get('Enhanced_Category') or item.get('Enhanced_Category') in ['', 'nan', 'None', None]:
                    text_content = item.get('Feedback', '') or item.get('Content', '') or item.get('Title', '')
                    text_content = utils.clean_feedback_text(text_content)
                    
                    enhanced_cat = utils.enhanced_categorize_feedback(
                        text_content, 
                        item.get('Sources', ''), 
                        item.get('Scenario', ''), 
                        item.get('Organization', '')
                    )
                    
                    item['Enhanced_Category'] = enhanced_cat['primary_category']
                    item['Subcategory'] = enhanced_cat['subcategory']
                    item['Audience'] = enhanced_cat['audience']
                    item['Priority'] = enhanced_cat['priority']
                    item['Feature_Area'] = enhanced_cat['feature_area']
                    item['Categorization_Confidence'] = enhanced_cat['confidence']
                    item['Domains'] = enhanced_cat.get('domains', [])
                    item['Primary_Domain'] = enhanced_cat.get('primary_domain', None)
                
                # Set default state for offline mode
                if not item.get('State'):
                    item['State'] = 'NEW'
    
    feedback_to_display = list(last_collected_feedback)
    
    logger.info(f"Feedback viewer - Bearer Token Mode: {'ONLINE' if is_online_mode else 'OFFLINE'}, Fabric SQL Connected: {fabric_sql_connected}, Count: {len(feedback_to_display)}")
    
    # ONLINE MODE: Sync with SQL database when connected to Fabric
    if is_online_mode:
        # Check if SQL data has already been applied to in-memory data
        sql_data_already_applied = session.get('sql_data_applied', False)
        
        if sql_data_already_applied:
            logger.info("🔄 ONLINE MODE: SQL data already applied to in-memory feedback, skipping re-sync")
        else:
            try:
                logger.info("🔄 ONLINE MODE: Syncing with SQL database")
                
                # Get existing state data from SQL
                existing_sql_data = state_manager.get_all_feedback_states()
                feedback_ids_in_csv = {item.get('Feedback_ID') for item in feedback_to_display if item.get('Feedback_ID')}
                
                if existing_sql_data:
                    logger.info(f"📊 Found {len(existing_sql_data)} existing records in SQL database")
                    
                    # STEP 1: Update CSV items with SQL data (preserve manual updates)
                    sql_updated_count = 0
                    domain_updated_count = 0
                    for item in feedback_to_display:
                        feedback_id = item.get('Feedback_ID')
                        if feedback_id and feedback_id in existing_sql_data:
                            sql_state = existing_sql_data[feedback_id]
                            
                            # Apply state from SQL (manual updates take precedence)
                            if sql_state.get('state'):
                                item['State'] = sql_state['state']
                                sql_updated_count += 1
                            
                            # Apply domain from SQL (manual updates take precedence) 
                            if sql_state.get('domain'):
                                item['Primary_Domain'] = sql_state['domain']
                                domain_updated_count += 1
                    
                    logger.info(f"✅ Updated {sql_updated_count} states and {domain_updated_count} domains from SQL")
                    
                    # STEP 2: Identify new items that need to be written to SQL
                    feedback_ids_in_sql = set(existing_sql_data.keys())
                    new_feedback_ids = feedback_ids_in_csv - feedback_ids_in_sql
                    
                    if new_feedback_ids:
                        logger.info(f"📝 Found {len(new_feedback_ids)} new items to write to SQL database")
                        
                        # Write new items to SQL database
                        new_items = [item for item in feedback_to_display if item.get('Feedback_ID') in new_feedback_ids]
                        try:
                            # Use the fabric SQL writer to write new items
                            import fabric_sql_writer
                            sql_writer = fabric_sql_writer.FabricSQLWriter()
                            result = sql_writer.write_feedback_bulk(new_items, use_token=True)
                            
                            if result.get('written', 0) > 0:
                                logger.info(f"✅ Successfully wrote {result['written']} new items to SQL database")
                            else:
                                logger.warning(f"⚠️ No new items were written to SQL database")
                                
                        except Exception as e:
                            logger.error(f"❌ Error writing new items to SQL database: {e}")
                    else:
                        logger.info("📊 No new items to write - all feedback already exists in SQL database")
                else:
                    logger.info("📝 No existing data in SQL - will write all items when user syncs")
                    
                # Mark that we're in online mode and SQL data has been applied
                session['states_loaded'] = True
                session['sql_data_applied'] = True
                
            except Exception as e:
                logger.error(f"❌ Error syncing with SQL database: {e}")
                # Fall back to offline mode on error
                is_online_mode = False
    
    # Initialize default values for template variables
    all_sources = ['Reddit', 'GitHub', 'Fabric Community']
    all_categories = ['Feature Request', 'Bug Report', 'Performance Issue', 'Documentation', 'General Feedback']
    all_enhanced_categories = []
    all_audiences = ['Developer', 'Customer', 'ISV']
    all_priorities = ['critical', 'high', 'medium', 'low']
    all_domains = ['Getting Started', 'Governance', 'User Experience', 'Authentication & Security', 'Performance & Scalability', 'Integration & APIs', 'Analytics & Reporting']
    all_sentiments = ['positive', 'negative', 'neutral']
    
    # Initialize all_states with all possible states from config
    from config import FEEDBACK_STATES
    all_states = sorted(list(FEEDBACK_STATES.keys()))
    
    # Extract actual values from data if available (use full dataset for filters)
    if last_collected_feedback:
        all_sources = list(set([item.get('Sources') for item in last_collected_feedback
                               if item.get('Sources') and isinstance(item.get('Sources'), str)]))
        all_categories = list(set([item.get('Category') for item in last_collected_feedback
                                  if item.get('Category') and isinstance(item.get('Category'), str)]))
        all_enhanced_categories = list(set([item.get('Enhanced_Category') for item in last_collected_feedback
                                           if item.get('Enhanced_Category') and isinstance(item.get('Enhanced_Category'), str)]))
        all_audiences = list(set([item.get('Audience') for item in last_collected_feedback
                                 if item.get('Audience') and isinstance(item.get('Audience'), str)]))
        all_priorities = list(set([item.get('Priority') for item in last_collected_feedback
                                  if item.get('Priority') and isinstance(item.get('Priority'), str)]))
        all_domains = list(set([item.get('Primary_Domain') for item in last_collected_feedback
                               if item.get('Primary_Domain') and isinstance(item.get('Primary_Domain'), str)]))
        all_sentiments = list(set([item.get('Sentiment') for item in last_collected_feedback
                                  if item.get('Sentiment') and isinstance(item.get('Sentiment'), str)]))
        all_states = list(set([item.get('State', 'NEW') for item in last_collected_feedback
                              if isinstance(item.get('State', 'NEW'), str)]))
        
        # Always merge with all possible states from config to ensure comprehensive coverage
        from config import FEEDBACK_STATES
        all_possible_states = list(FEEDBACK_STATES.keys())
        all_states = sorted(list(set(all_states).union(set(all_possible_states))))
        
        # Add "Uncategorized" options for items without classifications
        uncategorized_enhanced_count = len([item for item in last_collected_feedback 
                                          if not item.get('Enhanced_Category') or 
                                          item.get('Enhanced_Category') in ['', 'None', None] or
                                          (pd and pd.isna(item.get('Enhanced_Category')))])
        if uncategorized_enhanced_count > 0:
            all_enhanced_categories.append('Uncategorized')
        
        uncategorized_domain_count = len([item for item in last_collected_feedback 
                                        if not item.get('Primary_Domain') or 
                                        item.get('Primary_Domain') in ['', 'None', None] or
                                        (pd and pd.isna(item.get('Primary_Domain')))])
        if uncategorized_domain_count > 0:
            all_domains.append('Uncategorized')
        
        # Sort all filter lists
        all_sources = sorted(all_sources)
        all_categories = sorted(all_categories)
        all_enhanced_categories = sorted(all_enhanced_categories) 
        all_audiences = sorted(all_audiences)
        all_priorities = sorted(all_priorities)
        all_domains = sorted(all_domains)
        all_sentiments = sorted(all_sentiments)
        all_states = sorted(all_states)
        
        # Apply fallbacks if needed
        if not all_sources:
            all_sources = ['Reddit', 'GitHub', 'Fabric Community']
        if not all_audiences:
            all_audiences = ['Developer', 'Customer', 'ISV']
        if not all_priorities:
            all_priorities = ['critical', 'high', 'medium', 'low']
        if not all_domains or (len(all_domains) == 1 and all_domains[0] == 'Uncategorized'):
            fallback_domains = ['Getting Started', 'Governance', 'User Experience', 'Authentication & Security', 'Performance & Scalability', 'Integration & APIs', 'Analytics & Reporting']
            if 'Uncategorized' in all_domains:
                all_domains = fallback_domains + ['Uncategorized']
            else:
                all_domains = fallback_domains
        if not all_sentiments:
            all_sentiments = ['positive', 'negative', 'neutral']
        if not all_states:
            # Use all possible states from config as fallback
            from config import FEEDBACK_STATES
            all_states = sorted(list(FEEDBACK_STATES.keys()))

    # Filter to show only items stored in Fabric SQL database if requested
    if show_only_stored:
        if is_online_mode:
            try:
                stored_ids = state_manager.get_stored_feedback_ids()
                if stored_ids:
                    original_count = len(feedback_to_display)
                    feedback_to_display = [item for item in feedback_to_display if item.get('Feedback_ID') in stored_ids]
                    filtered_count = len(feedback_to_display)
                    dropped_count = original_count - filtered_count
                    source_info_message = f"Displaying {filtered_count} items stored in Fabric SQL database. ({dropped_count} items hidden.)"
                else:
                    source_info_message = f"No items found in Fabric SQL database."
                    feedback_to_display = []
            except Exception as e:
                logger.error(f"Error filtering by stored items: {e}")
                source_info_message = f"Error checking stored items: {str(e)}"
        else:
            source_info_message = f"Cannot filter by stored items - not connected to Fabric. Switch to online mode first."
            feedback_to_display = []
    else:
        mode_text = "ONLINE" if is_online_mode else "OFFLINE"
        source_info_message = f"Displaying all {len(feedback_to_display)} collected items. (Mode: {mode_text})"

    # Debug logging
    logger.info(f"Feedback viewer - Mode: {'ONLINE' if is_online_mode else 'OFFLINE'}, Count: {len(feedback_to_display)}")

    # Multi-select filtering logic
    if source_filters:
        feedback_to_display = [item for item in feedback_to_display if item.get('Sources') in source_filters]
        logger.info(f"After source multi-filter {source_filters}: {len(feedback_to_display)} items")
    elif source_filter != 'All':  # Backwards compatibility
        feedback_to_display = [item for item in feedback_to_display if item.get('Sources') == source_filter]
        logger.info(f"After source filter '{source_filter}': {len(feedback_to_display)} items")
    
    if category_filter != 'All':  # Legacy filter remains single-select
        feedback_to_display = [item for item in feedback_to_display if item.get('Category') == category_filter]
        logger.info(f"After legacy category filter '{category_filter}': {len(feedback_to_display)} items")
    
    if enhanced_category_filters:
        # Handle special "Uncategorized" filter for enhanced categories
        if 'Uncategorized' in enhanced_category_filters:
            other_categories = [c for c in enhanced_category_filters if c != 'Uncategorized']
            feedback_to_display = [item for item in feedback_to_display if 
                                  (item.get('Enhanced_Category') in other_categories if other_categories else False) or
                                  not item.get('Enhanced_Category') or 
                                  item.get('Enhanced_Category') in ['', 'None', None]]
        else:
            feedback_to_display = [item for item in feedback_to_display if item.get('Enhanced_Category') in enhanced_category_filters]
        logger.info(f"After enhanced category multi-filter {enhanced_category_filters}: {len(feedback_to_display)} items")
    elif enhanced_category_filter != 'All':  # Backwards compatibility
        if enhanced_category_filter == 'Uncategorized':
            feedback_to_display = [item for item in feedback_to_display if 
                                  not item.get('Enhanced_Category') or 
                                  item.get('Enhanced_Category') in ['', 'None', None]]
        else:
            feedback_to_display = [item for item in feedback_to_display if item.get('Enhanced_Category') == enhanced_category_filter]
        logger.info(f"After enhanced category filter '{enhanced_category_filter}': {len(feedback_to_display)} items")
    
    if audience_filters:
        # No mapping - treat ISV as a separate audience
        feedback_to_display = [item for item in feedback_to_display if
                             item.get('Audience') in audience_filters]
        logger.info(f"After audience multi-filter {audience_filters}: {len(feedback_to_display)} items")
    elif audience_filter != 'All':  # Backwards compatibility
        feedback_to_display = [item for item in feedback_to_display if
                             item.get('Audience') == audience_filter]
        logger.info(f"After audience filter '{audience_filter}': {len(feedback_to_display)} items")
    
    if priority_filters:
        feedback_to_display = [item for item in feedback_to_display if item.get('Priority') in priority_filters]
        logger.info(f"After priority multi-filter {priority_filters}: {len(feedback_to_display)} items")
    elif priority_filter != 'All':  # Backwards compatibility
        feedback_to_display = [item for item in feedback_to_display if item.get('Priority') == priority_filter]
        logger.info(f"After priority filter '{priority_filter}': {len(feedback_to_display)} items")
    
    if domain_filters:
        # Handle special "Uncategorized" filter
        if 'Uncategorized' in domain_filters:
            # Include items that match other filters OR have no domain classification
            other_domains = [d for d in domain_filters if d != 'Uncategorized']
            feedback_to_display = [item for item in feedback_to_display if 
                                  (item.get('Primary_Domain') in other_domains if other_domains else False) or
                                  not item.get('Primary_Domain') or 
                                  item.get('Primary_Domain') in ['', 'None', None]]
        else:
            # Normal domain filtering - only show items with matching domains
            feedback_to_display = [item for item in feedback_to_display if item.get('Primary_Domain') in domain_filters]
        logger.info(f"After domain multi-filter {domain_filters}: {len(feedback_to_display)} items")
    elif domain_filter != 'All':  # Backwards compatibility
        if domain_filter == 'Uncategorized':
            # Show only uncategorized items
            feedback_to_display = [item for item in feedback_to_display if 
                                  not item.get('Primary_Domain') or 
                                  item.get('Primary_Domain') in ['', 'None', None]]
        else:
            # Normal domain filtering
            feedback_to_display = [item for item in feedback_to_display if item.get('Primary_Domain') == domain_filter]
        logger.info(f"After domain filter '{domain_filter}': {len(feedback_to_display)} items")
    
    if sentiment_filters:
        feedback_to_display = [item for item in feedback_to_display if item.get('Sentiment') in sentiment_filters]
        logger.info(f"After sentiment multi-filter {sentiment_filters}: {len(feedback_to_display)} items")
    elif sentiment_filter != 'All':  # Backwards compatibility
        feedback_to_display = [item for item in feedback_to_display if item.get('Sentiment') == sentiment_filter]
        logger.info(f"After sentiment filter '{sentiment_filter}': {len(feedback_to_display)} items")
    
    if state_filters:
        logger.info(f"🔍 Applying state multi-filter {state_filters} to {len(feedback_to_display)} items")
        # Log sample states before filtering
        sample_states = [item.get('State', 'NEW') for item in feedback_to_display[:5]]
        logger.info(f"Sample states before filtering: {sample_states}")
        
        feedback_to_display = [item for item in feedback_to_display if item.get('State', 'NEW') in state_filters]
        logger.info(f"After state multi-filter {state_filters}: {len(feedback_to_display)} items")
    elif state_filter != 'All':  # Backwards compatibility
        logger.info(f"🔍 Applying single state filter '{state_filter}' to {len(feedback_to_display)} items")
        # Log sample states before filtering
        sample_states = [item.get('State', 'NEW') for item in feedback_to_display[:5]]
        logger.info(f"Sample states before filtering: {sample_states}")
        
        feedback_to_display = [item for item in feedback_to_display if item.get('State', 'NEW') == state_filter]
        logger.info(f"After state filter '{state_filter}': {len(feedback_to_display)} items")

    # Sort by date - newest items first by default
    if feedback_to_display:
        try:
            def parse_date(item):
                date_str = item.get('Created', '')
                
                # Handle pandas NaT/NaN values
                if pd.isna(date_str):
                    logger.debug(f"Found NaT/NaN date value for item from {item.get('Sources', 'Unknown')}")
                    return datetime(1900, 1, 1)
                
                # Convert to string if needed
                date_str = str(date_str) if date_str else ''
                
                if date_str and date_str != 'nan' and date_str != 'NaT':
                    try:
                        # Handle ISO format dates (e.g., '2025-01-15T10:30:00')
                        if 'T' in date_str:
                            # Remove timezone info to make all datetimes naive for comparison
                            if '+' in date_str or 'Z' in date_str:
                                # Has timezone info - parse and convert to naive
                                parsed = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                # Convert to naive datetime by removing timezone info
                                parsed = parsed.replace(tzinfo=None)
                            else:
                                # No timezone info - parse as naive
                                parsed = datetime.fromisoformat(date_str)
                            return parsed
                        # Handle date-only format (e.g., '2025-01-15')
                        else:
                            parsed = datetime.strptime(date_str, '%Y-%m-%d')
                            return parsed
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Date parsing error for '{date_str}' from {item.get('Sources', 'Unknown')}: {e}")
                        pass
                # Return a very old date for items without valid dates
                logger.debug(f"Using default date for item from {item.get('Sources', 'Unknown')} with date '{date_str}'")
                return datetime(1900, 1, 1)
            
            reverse_order = sort_by == 'newest'
            feedback_to_display = sorted(feedback_to_display, key=parse_date, reverse=reverse_order)
            
            logger.info(f"Sorted {len(feedback_to_display)} items by date ({sort_by} first)")
            
        except Exception as e:
            logger.warning(f"Error sorting feedback by date: {e}")

    # Analyze repeating requests if requested
    repeating_analysis = None
    if show_repeating and feedback_to_display:
        from utils import analyze_repeating_requests
        repeating_analysis = analyze_repeating_requests(feedback_to_display)
        logger.info(f"Repeating requests analysis: {repeating_analysis.get('cluster_count', 0)} clusters found")

    # Generate category statistics
    category_stats = None
    if feedback_to_display:
        from utils import get_category_statistics
        category_stats = get_category_statistics(feedback_to_display)
        logger.info(f"Category statistics: {category_stats.get('total_items', 0)} items analyzed")

    if any(f != 'All' for f in [source_filter, category_filter, enhanced_category_filter, audience_filter, priority_filter, domain_filter, sentiment_filter]):
        filters_applied = []
        if source_filter != 'All':
            filters_applied.append(f"Source: {source_filter}")
        if category_filter != 'All':
            filters_applied.append(f"Legacy Category: {category_filter}")
        if enhanced_category_filter != 'All':
            filters_applied.append(f"Category: {enhanced_category_filter}")
        if audience_filter != 'All':
            filters_applied.append(f"Audience: {audience_filter}")
        if priority_filter != 'All':
            filters_applied.append(f"Priority: {priority_filter}")
        if domain_filter != 'All':
            filters_applied.append(f"Domain: {domain_filter}")
        if sentiment_filter != 'All':
            filters_applied.append(f"Sentiment: {sentiment_filter}")
        source_info_message = f"Filtered by {', '.join(filters_applied)}. Showing {len(feedback_to_display)} items."

    trending_category_name = None
    trending_category_count = 0
    if feedback_to_display:
        category_counts = pd.Series([item.get('Category', 'Uncategorized') for item in feedback_to_display]).value_counts()
        if not category_counts.empty:
            trending_category_name = category_counts.index[0]
            trending_category_count = int(category_counts.iloc[0])

    # Debug logging for template variables
    logger.info(f"📊 Template variables - all_domains: {all_domains}")
    logger.info(f"📊 Template variables - all_enhanced_categories: {all_enhanced_categories}")
    if 'Uncategorized' in all_domains:
        logger.info("✅ 'Uncategorized' is included in final domains list")
    if 'Uncategorized' in all_enhanced_categories:
        logger.info("✅ 'Uncategorized' is included in final enhanced categories list")
    logger.info(f"📊 Sample feedback items domains: {[item.get('Primary_Domain', 'None') for item in feedback_to_display[:5]]}")

    return render_template('feedback_viewer.html',
                           feedback_items=feedback_to_display,
                           source_info=source_info_message,
                           all_sources=all_sources,
                           current_source=source_filter,
                           all_categories=all_categories,
                           current_category=category_filter,
                           all_enhanced_categories=all_enhanced_categories,
                           current_enhanced_category=enhanced_category_filter,
                           all_audiences=all_audiences,
                           current_audience=audience_filter,
                           all_priorities=all_priorities,
                           current_priority=priority_filter,
                           all_domains=all_domains,
                           current_domain=domain_filter,
                           all_sentiments=all_sentiments,
                           current_sentiment=sentiment_filter,
                           all_states=all_states,
                           current_state=state_filter,
                           current_sort=sort_by,
                           show_repeating=show_repeating,
                           repeating_analysis=repeating_analysis,
                           category_stats=category_stats,
                           trending_category_name=trending_category_name,
                           trending_category_count=trending_category_count,
                           stored_token=stored_token,
                           states_already_loaded=fabric_sql_connected,  # This controls UI state management features (based on SQL connection, not bearer token)
                           is_online_mode=is_online_mode,  # Bearer token mode for lakehouse writes
                           fabric_sql_connected=fabric_sql_connected,  # New: explicit SQL connection indicator
                           fabric_connected_param=fabric_connected_param,  # URL parameter indicates Fabric connection
                           # Multi-select filter arrays
                           selected_sources=source_filters,
                           selected_enhanced_categories=enhanced_category_filters,
                           selected_audiences=audience_filters,
                           selected_priorities=priority_filters,
                           selected_domains=domain_filters,
                           selected_sentiments=sentiment_filters,
                           selected_states=state_filters
                           )

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

        logger.info(f"Attempting to write {len(last_collected_feedback)} items to Fabric Lakehouse.")
        
        # Import and use the fabric_writer module
        try:
            import fabric_writer
        except ImportError as ie:
            logger.error(f"Failed to import fabric_writer module: {ie}")
            return jsonify({'status': 'error', 'message': f'Fabric writer module not available: {str(ie)}'}), 500
        
        # Call the actual fabric_writer
        success = fabric_writer.write_data_to_fabric(fabric_token, last_collected_feedback)
        
        if success:
            logger.info(f"Successfully wrote {len(last_collected_feedback)} items to Fabric Lakehouse")
            return jsonify({'status': 'success', 'message': f'Successfully wrote {len(last_collected_feedback)} items to Fabric table {config.FABRIC_TARGET_TABLE_NAME}.'})
        else:
            logger.error("Failed to write data to Fabric Lakehouse")
            return jsonify({'status': 'error', 'message': 'Failed to write data to Fabric Lakehouse. Check logs for details.'}), 500

    except Exception as e:
        logger.error(f"Error writing to Fabric: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}), 500

# Global storage for async operations
fabric_operations = {}

@app.route('/api/write_to_fabric_async', methods=['POST'])
def write_to_fabric_async_endpoint():
    """Start asynchronous write to Fabric Lakehouse with progress tracking"""
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
        
        # Generate unique operation ID
        operation_id = str(uuid.uuid4())
        
        # Initialize operation tracking
        fabric_operations[operation_id] = {
            'status': 'starting',
            'progress': 0,
            'total_items': len(last_collected_feedback),
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
                    'message': f'🚀 Starting Fabric write operation for {len(last_collected_feedback)} items',
                    'type': 'info'
                })
                fabric_operations[operation_id]['status'] = 'in_progress'
                fabric_operations[operation_id]['operation'] = 'Writing to Fabric Lakehouse...'
                
                import fabric_writer
                
                def progress_callback(processed, total, operation, message):
                    fabric_operations[operation_id]['processed_items'] = processed
                    fabric_operations[operation_id]['progress'] = (processed / total) * 100 if total > 0 else 0
                    fabric_operations[operation_id]['operation'] = operation
                    if message:
                        fabric_operations[operation_id]['logs'].append({
                            'message': message,
                            'type': 'info'
                        })
                
                # Call fabric writer with progress callback
                fabric_operations[operation_id]['logs'].append({
                    'message': '📝 Calling Fabric writer module...',
                    'type': 'info'
                })
                
                success = fabric_writer.write_data_to_fabric(fabric_token, last_collected_feedback)
                
                fabric_operations[operation_id]['completed'] = True
                fabric_operations[operation_id]['success'] = success
                fabric_operations[operation_id]['progress'] = 100
                fabric_operations[operation_id]['processed_items'] = len(last_collected_feedback)
                
                if success:
                    fabric_operations[operation_id]['message'] = f'Successfully wrote {len(last_collected_feedback)} items to Fabric Lakehouse'
                    fabric_operations[operation_id]['logs'].append({
                        'message': '✅ Fabric write operation completed successfully',
                        'type': 'success'
                    })
                    
                    # After successful write, also load existing states
                    fabric_operations[operation_id]['logs'].append({
                        'message': '🔄 Loading existing feedback states from Fabric...',
                        'type': 'info'
                    })
                    fabric_operations[operation_id]['operation'] = 'Loading existing states...'
                    
                    try:
                        # Load states for all feedback items
                        load_states_after_fabric_write(fabric_token, operation_id)
                        
                        # Store token in session for feedback viewer
                        from flask import session
                        session['fabric_bearer_token'] = fabric_token
                        session['states_loaded'] = True
                        
                        fabric_operations[operation_id]['logs'].append({
                            'message': '✅ States loaded successfully - feedback viewer ready!',
                            'type': 'success'
                        })
                        fabric_operations[operation_id]['logs'].append({
                            'message': '🔄 Preparing to hide duplicate items from view...',
                            'type': 'info'
                        })
                        fabric_operations[operation_id]['message'] = f'Successfully wrote {len(last_collected_feedback)} items and loaded states'
                        fabric_operations[operation_id]['hide_duplicates'] = True
                        
                    except Exception as state_error:
                        fabric_operations[operation_id]['logs'].append({
                            'message': f'⚠️ States loading failed: {str(state_error)} (feedback still written successfully)',
                            'type': 'warning'
                        })
                        logger.warning(f"Failed to load states after fabric write: {state_error}")
                else:
                    fabric_operations[operation_id]['message'] = 'Failed to write data to Fabric Lakehouse'
                    fabric_operations[operation_id]['logs'].append({
                        'message': '❌ Fabric write operation failed',
                        'type': 'danger'
                    })
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
            logger.info(f"AJAX Repeating requests analysis: {repeating_analysis.get('cluster_count', 0)} clusters found")
        
        # Get filter options for UI updates
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
        filtered_feedback.sort(key=lambda x: x.get('Created', ''))
        sample_dates_after = [item.get('Created', '') for item in filtered_feedback[:3]]
        logger.info(f"DEBUG: Sorting oldest - sample dates after: {sample_dates_after}")
    elif sort_by == 'priority':
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        filtered_feedback.sort(key=lambda x: priority_order.get(x.get('Priority', 'low').lower(), 4))
    
    return filtered_feedback

def extract_filter_options(feedback_data):
    """Extract available filter options from feedback data"""
    if not feedback_data:
        return {}
    
    # Get states currently in the data
    data_states = set(item.get('State', 'NEW') for item in feedback_data)
    
    # Always include all possible states from config, regardless of what's in the data
    from config import FEEDBACK_STATES
    all_possible_states = set(FEEDBACK_STATES.keys())
    
    # Merge data states with all possible states to ensure comprehensive list
    comprehensive_states = sorted(list(all_possible_states.union(data_states)))
    
    options = {
        'sources': sorted(list(set(item.get('Source', '') for item in feedback_data if item.get('Source')))),
        'audiences': sorted(list(set(item.get('Audience', '') for item in feedback_data if item.get('Audience')))),
        'priorities': sorted(list(set(item.get('Priority', '') for item in feedback_data if item.get('Priority')))),
        'states': comprehensive_states,  # Always show all possible states
        'domains': sorted(list(set(item.get('Enhanced_Domain', '') for item in feedback_data if item.get('Enhanced_Domain')))),
        'sentiments': sorted(list(set(item.get('Sentiment', '') for item in feedback_data if item.get('Sentiment')))),
        'enhanced_categories': sorted(list(set(item.get('Enhanced_Category', '') for item in feedback_data if item.get('Enhanced_Category'))))
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
    """Fast validation: If Livy accepts session start request, token is valid"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        token = data.get('token')
        if not token:
            return jsonify({'status': 'error', 'message': 'Token required'}), 400

        logger.warning(f"🔥 FABRIC TOKEN FAST VALIDATION: Testing token with Livy session start")
        
        # Use new fast token test function
        import fabric_writer
        from config import FABRIC_LIVY_ENDPOINT
        
        # Fast test: If Livy accepts session creation, token is valid
        session_id = fabric_writer._test_fabric_token(token, FABRIC_LIVY_ENDPOINT)
        
        if session_id:
            # Session request accepted - token is valid!
            # Store token immediately since Livy accepted our authentication
            from flask import session as flask_session
            flask_session['fabric_bearer_token'] = token
            flask_session['states_loaded'] = True
            flask_session['fabric_token_validated_at'] = datetime.now().isoformat()
            flask_session['fabric_session_starting'] = True
            flask_session['fabric_session_id'] = session_id
            
            # Clear any previous validation state
            flask_session.pop('fabric_token_validating', None)
            flask_session.pop('fabric_validation_started_at', None)
            flask_session.pop('fabric_validation_status', None)
            
            logger.warning(f"✅ FABRIC TOKEN FAST VALIDATION: Token validated - Livy session {session_id} starting in background")
            
            # Don't close the session - let it start in background for immediate use
            
            return jsonify({
                'status': 'success',
                'message': 'Token validated - Livy session starting in background',
                'validated_at': flask_session['fabric_token_validated_at'],
                'session_status': 'starting',
                'session_id': session_id
            })
        else:
            # Clear any validation state on failure
            from flask import session as flask_session
            flask_session.pop('fabric_token_validating', None)
            flask_session.pop('fabric_validation_started_at', None)
            flask_session.pop('fabric_validation_status', None)
            
            logger.error(f"❌ FABRIC TOKEN FAST VALIDATION: Livy rejected session start - invalid token")
            return jsonify({
                'status': 'error',
                'message': 'Token validation failed - Livy rejected authentication'
            }), 400
            
    except ImportError:
        logger.error("❌ FABRIC TOKEN VALIDATION: fabric_writer module not available")
        return jsonify({
            'status': 'error',
            'message': 'Fabric validation not available - fabric_writer module missing'
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
            
            # Set session flag to indicate that state data has been loaded and applied
            from flask import session
            session['states_loaded'] = True
            session['sql_data_applied'] = True  # New flag to indicate SQL data has been applied to in-memory data
            
            logger.info(f"✅ Successfully completed Fabric sync: {sync_result['new_items']} new items + {len(state_data)} state records")
            
            # Create detailed success message
            message_parts = [
                f"Added {sync_result['new_items']} new items",
                f"skipped {sync_result['existing_items']} existing items",
                f"loaded {len(state_data)} state records"
            ]
            
            if sync_result.get('id_regenerated', 0) > 0:
                message_parts.append(f"regenerated {sync_result['id_regenerated']} deterministic IDs")
            
            success_message = f"Connected to Fabric SQL Database. {', '.join(message_parts)}"
            
            return jsonify({
                'status': 'success',
                'message': success_message,
                'sync_result': sync_result,
                'state_data': state_data,
                'connected': True
            })
            
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
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON data required'}), 400
        
        feedback_id = data.get('feedback_id')
        if not feedback_id:
            return jsonify({'status': 'error', 'message': 'feedback_id required'}), 400
        
       
        
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
        new_domain = data.get('domain')
        
        if not feedback_id or not new_domain:
            return jsonify({'status': 'error', 'message': 'feedback_id and domain are required'}), 400
        
        # Create domain update
        update_data = state_manager.update_feedback_domain(feedback_id, new_domain, user)
        
        # For now, update in memory (in production, this would update Fabric table)
        global last_collected_feedback
        for item in last_collected_feedback:
            if item.get('Feedback_ID') == feedback_id:
                item.update(update_data)
                break
        
        logger.info(f"Updated feedback {feedback_id} domain to {new_domain} by {user}")
        
        return jsonify({
            'status': 'success',
            'message': f'Feedback domain updated to {new_domain}',
            'data': update_data
        })
        
    except Exception as e:
        logger.error(f"Error updating feedback domain: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/feedback/notes', methods=['POST'])
def update_feedback_notes():
    """Update the notes of a feedback item"""
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
        notes = data.get('notes', '')
        
        if not feedback_id:
            return jsonify({'status': 'error', 'message': 'feedback_id is required'}), 400
        
        # Create notes update
        now = datetime.now().isoformat()
        update_data = {
            'Feedback_ID': feedback_id,
            'Feedback_Notes': notes,
            'Last_Updated': now,
            'Updated_By': user
        }
        
        # For now, update in memory (in production, this would update Fabric table)
        global last_collected_feedback
        for item in last_collected_feedback:
            if item.get('Feedback_ID') == feedback_id:
                item.update(update_data)
                break
        
        logger.info(f"Updated feedback {feedback_id} notes by {user}")
        
        return jsonify({
            'status': 'success',
            'message': 'Feedback notes updated',
            'data': update_data
        })
        
    except Exception as e:
        logger.error(f"Error updating feedback notes: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/update_domain_sql', methods=['POST'])
def update_domain_sql():
    """Update feedback domain directly in SQL database"""
    try:
        data = request.get_json()
        feedback_id = data.get('feedback_id')
        new_domain = data.get('new_domain')
        
        if not feedback_id or not new_domain:
            return jsonify({'success': False, 'message': 'Missing feedback_id or new_domain'}), 400
        
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
            return jsonify({'success': False, 'message': 'Failed to update domain in database'}), 500
            
    except Exception as e:
        logger.error(f"Error updating domain: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/update_audience_sql', methods=['POST'])
def update_audience_sql():
    """Update feedback audience directly in SQL database"""
    try:
        data = request.get_json()
        feedback_id = data.get('feedback_id')
        new_audience = data.get('new_audience')
        
        if not feedback_id or not new_audience:
            return jsonify({'success': False, 'message': 'Missing feedback_id or new_audience'}), 400
        
        # Validate audience (only Developer or Customer)
        valid_audiences = ['Developer', 'Customer']
        if new_audience not in valid_audiences:
            return jsonify({'success': False, 'message': f'Invalid audience. Must be one of: {valid_audiences}'}), 400
        
        # No bearer token needed for SQL database updates
        
        # Update in Fabric SQL database using state_manager (no bearer token needed)
        success = state_manager.update_feedback_field_in_sql(feedback_id, 'Audience', new_audience, None)
        
        if success:
            logger.info(f"✅ Successfully updated audience for {feedback_id} to {new_audience}")
            return jsonify({'success': True, 'message': f'Audience updated to {new_audience}'})
        else:
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