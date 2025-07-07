from flask import Flask, render_template, request, jsonify, send_from_directory, current_app
import pandas as pd
import os
import logging
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
    """Main collection route using only real data collectors"""
    global last_collected_feedback, last_collection_summary, collection_status
    last_collected_feedback = []
    
    # Update collection status to running
    collection_status.update({
        'status': 'running',
        'message': 'Collection in progress...',
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'total_items': 0,
        'current_source': 'Initializing',
        'sources_completed': [],
        'error_message': None
    })
    
    try:
        logger.info("Starting feedback collection process via API.")
        
        # Get optional ADO work item ID from request
        ado_work_item_id = None
        if request.is_json:
            data = request.get_json()
            ado_work_item_id = data.get('ado_work_item_id') if data else None
        
        # Collect from all sources using proper collectors
        reddit_collector = RedditCollector()
        fabric_collector = FabricCommunityCollector()
        github_collector = GitHubDiscussionsCollector()
        
        # Collect from Reddit
        collection_status['current_source'] = 'Reddit'
        reddit_feedback = reddit_collector.collect()
        logger.info(f"Reddit collector found {len(reddit_feedback)} items.")
        collection_status['sources_completed'].append('Reddit')
        
        # Collect from Fabric Community
        collection_status['current_source'] = 'Fabric Community'
        fabric_feedback = fabric_collector.collect()
        logger.info(f"Fabric Community collector found {len(fabric_feedback)} items.")
        collection_status['sources_completed'].append('Fabric Community')
        
        # Collect from GitHub
        collection_status['current_source'] = 'GitHub Discussions'
        github_feedback = github_collector.collect()
        logger.info(f"GitHub Discussions collector found {len(github_feedback)} items.")
        collection_status['sources_completed'].append('GitHub Discussions')
        
        # Use working ADO client to get children of parent work item
        logger.info("🔗 WORKING ADO CLIENT: Collecting children work items from Azure DevOps")
        
        # Get work items using the working client (children of parent work item from past year)
        ado_workitems = get_working_ado_items(parent_work_item_id=ado_work_item_id, top=200)
        logger.info(f"📊 Working client found {len(ado_workitems)} children work items")
        
        # Convert work items to feedback format with descriptions and proper categorization
        ado_feedback = []
        for item in ado_workitems:
            work_item_id = item.get('id')
            title = item.get('title', '')
            description = item.get('description', '')
            ado_url = item.get('url')  # Already formatted in working client
            
            # Clean the text to remove HTML/CSS formatting (like the updated collector)
            cleaned_title = utils.clean_feedback_text(title)
            cleaned_description = utils.clean_feedback_text(description) if description and description != 'No description available' else ""
            
            # Use cleaned description + title for content
            full_content = cleaned_title
            if cleaned_description:
                full_content += f"\n\n{cleaned_description}"
            
            # Enhanced categorization (like the updated collector)
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
                'Feedback_Gist': utils.generate_feedback_gist(full_content),  # For card title
                'Feedback': full_content,  # This is what shows in the card content (now cleaned!)
                'Content': full_content,  # Backup field
                'Author': item.get('createdBy', ''),
                'Created': item.get('createdDate', ''),
                'Url': ado_url,  # Proper field name for "View Source" button
                'URL': ado_url,  # Backup field
                'Sources': 'Azure DevOps',
                'Category': enhanced_cat['legacy_category'],  # Backward compatibility
                'Enhanced_Category': enhanced_cat['primary_category'],  # Enhanced categorization
                'Subcategory': enhanced_cat['subcategory'],
                'Audience': enhanced_cat['audience'],  # This should now be "Developer"!
                'Priority': enhanced_cat['priority'],
                'Feature_Area': enhanced_cat['feature_area'],
                'Categorization_Confidence': enhanced_cat['confidence'],
                'Domains': enhanced_cat.get('domains', []),
                'Primary_Domain': enhanced_cat.get('primary_domain', None),
                'Sentiment': sentiment_analysis['label'],
                'Sentiment_Score': sentiment_analysis['polarity'],
                'Sentiment_Confidence': sentiment_analysis['confidence'],
                'ADO_ID': work_item_id,
                'ADO_Type': item.get('type', ''),
                'ADO_State': item.get('state', ''),
                'ADO_AssignedTo': item.get('assignedTo', '')
            })
        
        logger.info(f"🔗 Working ADO client found {len(ado_feedback)} children work items from parent {ado_work_item_id}.")
        
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
        
        # Combine all feedback
        all_feedback = reddit_feedback + fabric_feedback + github_feedback + ado_feedback
        
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
        
        # Initialize state management for all feedback items
        for feedback_item in all_feedback:
            state_manager.initialize_feedback_state(feedback_item)
        
        last_collected_feedback = all_feedback
        last_collection_summary = {
            "reddit": len(reddit_feedback),
            "fabric": len(fabric_feedback),
            "github": len(github_feedback),
            "ado": len(ado_feedback),
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
            'current_source': 'Completed'
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
    category_filter = request.args.get('category', 'All')  # Legacy category filter
    enhanced_category_filter = request.args.get('enhanced_category', 'All')  # New enhanced category filter
    audience_filter = request.args.get('audience', 'All')  # New audience filter
    priority_filter = request.args.get('priority', 'All')  # New priority filter
    domain_filter = request.args.get('domain', 'All')  # New domain filter
    sentiment_filter = request.args.get('sentiment', 'All')
    state_filter = request.args.get('state', 'All')  # New state filter
    sort_by = request.args.get('sort', 'newest')  # Default to newest first
    show_repeating = request.args.get('show_repeating', 'false').lower() == 'true'  # Show repeating requests
    show_only_stored = request.args.get('show_only_stored', 'false').lower() == 'true'  # Show only items stored in Fabric
    
    # If no feedback in memory, try loading from CSV
    if not last_collected_feedback:
        logger.info("No feedback in memory, attempting to load from CSV")
        last_collected_feedback = load_latest_feedback_from_csv()
        
        # Apply sentiment analysis and generate deterministic IDs for loaded feedback
        if last_collected_feedback:
            from id_generator import FeedbackIDGenerator
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
    
    # Check if bearer token is available in session (from previous Fabric write)
    from flask import session
    stored_token = session.get('fabric_bearer_token')
    states_already_loaded = session.get('states_loaded', False)
    
    logger.info(f"Session check - Token: {'Present' if stored_token else 'None'}, States loaded: {states_already_loaded}")
    
    # Debug logging for session state
    if stored_token:
        logger.warning(f"🔑 SESSION TOKEN FOUND - Token available for state management")
    else:
        logger.warning(f"🔑 NO SESSION TOKEN - Banner will be shown")
    
    feedback_to_display = list(last_collected_feedback)  # Create a copy to avoid modifying the original
    
    # Initialize default values for template variables to prevent errors
    all_sources = ['Reddit', 'GitHub', 'Fabric Community']
    all_categories = ['Feature Request', 'Bug Report', 'Performance Issue', 'Documentation', 'General Feedback']
    all_enhanced_categories = []
    all_audiences = ['Developer', 'Customer']
    all_priorities = ['critical', 'high', 'medium', 'low']
    all_domains = ['GOVERNANCE', 'USER_EXPERIENCE', 'AUTHENTICATION', 'PERFORMANCE', 'INTEGRATION', 'ANALYTICS']
    all_sentiments = ['positive', 'negative', 'neutral']
    all_states = ['NEW', 'TRIAGED', 'CLOSED', 'IRRELEVANT']
    category_stats = None
    repeating_analysis = None
    trending_category_name = None
    trending_category_count = 0
    source_info_message = None
    
    # Extract actual values from data if available
    if feedback_to_display:
        # Safely extract values, filtering out None, NaN, and non-string values
        all_sources = list(set([item.get('Sources') for item in feedback_to_display
                               if item.get('Sources') and isinstance(item.get('Sources'), str)]))
        all_categories = list(set([item.get('Category') for item in feedback_to_display
                                  if item.get('Category') and isinstance(item.get('Category'), str)]))
        all_enhanced_categories = list(set([item.get('Enhanced_Category') for item in feedback_to_display
                                           if item.get('Enhanced_Category') and isinstance(item.get('Enhanced_Category'), str)]))
        all_audiences = list(set([item.get('Audience') for item in feedback_to_display
                                 if item.get('Audience') and isinstance(item.get('Audience'), str)]))
        all_priorities = list(set([item.get('Priority') for item in feedback_to_display
                                  if item.get('Priority') and isinstance(item.get('Priority'), str)]))
        all_domains = list(set([item.get('Primary_Domain') for item in feedback_to_display
                               if item.get('Primary_Domain') and isinstance(item.get('Primary_Domain'), str)]))
        all_sentiments = list(set([item.get('Sentiment') for item in feedback_to_display
                                  if item.get('Sentiment') and isinstance(item.get('Sentiment'), str)]))
        all_states = list(set([item.get('State', 'NEW') for item in feedback_to_display
                              if isinstance(item.get('State', 'NEW'), str)]))
        
        # Fallback to defaults if no valid data found
        if not all_sources:
            all_sources = ['Reddit', 'GitHub', 'Fabric Community']
        if not all_audiences:
            all_audiences = ['Developer', 'Customer']
        if not all_priorities:
            all_priorities = ['critical', 'high', 'medium', 'low']
        if not all_domains:
            all_domains = ['GOVERNANCE', 'USER_EXPERIENCE', 'AUTHENTICATION', 'PERFORMANCE', 'INTEGRATION', 'ANALYTICS']
        if not all_sentiments:
            all_sentiments = ['positive', 'negative', 'neutral']
        if not all_states:
            all_states = ['NEW', 'TRIAGED', 'CLOSED', 'IRRELEVANT']
    
    # Filter to show only items stored in Fabric SQL database if requested
    if show_only_stored:
        try:
            stored_ids = state_manager.get_stored_feedback_ids()
            if stored_ids:
                original_count = len(feedback_to_display)
                feedback_to_display = [item for item in feedback_to_display if item.get('Feedback_ID') in stored_ids]
                filtered_count = len(feedback_to_display)
                dropped_count = original_count - filtered_count
                source_info_message = f"Displaying {filtered_count} items stored in Fabric SQL database. ({dropped_count} duplicate items hidden.)"
                logger.info(f"Fabric filter applied - Showing {filtered_count} stored items, hiding {dropped_count} duplicates")
            else:
                source_info_message = f"Displaying all {len(feedback_to_display)} collected items. (No stored items found in Fabric.)"
                logger.warning("No stored items found in Fabric SQL database")
        except Exception as e:
            logger.error(f"Error filtering by stored items: {e}")
            source_info_message = f"Displaying all {len(feedback_to_display)} collected items. (Error checking stored items: {str(e)})"
    else:
        source_info_message = f"Displaying all {len(feedback_to_display)} collected items."

    # Debug logging
    logger.info(f"Feedback viewer - Initial count: {len(feedback_to_display)}, Source: {source_filter}, Enhanced Category: {enhanced_category_filter}, Audience: {audience_filter}, Priority: {priority_filter}, Sort: {sort_by}, Show only stored: {show_only_stored}")
    
    # Check if user should have SQL state data loaded based on various indicators
    should_load_states = False
    
    # Check 1: Session token available
    if stored_token and stored_token.strip() and stored_token != 'None':
        should_load_states = True
        logger.info("🔑 Session token available - will load SQL state data")
    
    # Check 2: Request parameter indicating fabric connection
    elif request.args.get('fabric_connected') == 'true':
        should_load_states = True
        logger.info("🔗 Fabric connection parameter found - will load SQL state data")
    
    # Check 3: States already loaded in session
    elif states_already_loaded:
        should_load_states = True
        logger.info("📊 States already loaded in session - will load SQL state data")
    
    if should_load_states:
        try:
            logger.info("🔄 Loading state data from state_manager for server-side filtering")
            
            # Get state data using existing state_manager
            state_data = state_manager.get_all_feedback_states()
            if state_data:
                logger.info(f"📊 Loaded {len(state_data)} state records from state_manager")
                
                # Apply state data to feedback items before filtering
                updated_count = 0
                for item in feedback_to_display:
                    feedback_id = item.get('Feedback_ID')
                    if feedback_id and feedback_id in state_data:
                        sql_state = state_data[feedback_id]
                        if sql_state.get('state'):
                            original_state = item.get('State', 'NEW')
                            item['State'] = sql_state['state']
                            logger.debug(f"Applied SQL state to {feedback_id}: {original_state} → {sql_state['state']}")
                            updated_count += 1
                        if sql_state.get('domain'):
                            item['Primary_Domain'] = sql_state['domain']
                            logger.debug(f"Applied SQL domain to {feedback_id}: {sql_state['domain']}")
                
                logger.info(f"✅ Applied state data from SQL to {updated_count}/{len(feedback_to_display)} items before filtering")
            else:
                logger.info("📊 No state data found in state_manager")
                
        except Exception as e:
            logger.error(f"❌ Error loading state data from state_manager: {e}")
    else:
        logger.info("🔒 No indicators for SQL state loading - using original data states")

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
        feedback_to_display = [item for item in feedback_to_display if item.get('Enhanced_Category') in enhanced_category_filters]
        logger.info(f"After enhanced category multi-filter {enhanced_category_filters}: {len(feedback_to_display)} items")
    elif enhanced_category_filter != 'All':  # Backwards compatibility
        feedback_to_display = [item for item in feedback_to_display if item.get('Enhanced_Category') == enhanced_category_filter]
        logger.info(f"After enhanced category filter '{enhanced_category_filter}': {len(feedback_to_display)} items")
    
    if audience_filters:
        # Map ISV/Platform to Developer for filtering
        mapped_filters = []
        for aud in audience_filters:
            if aud in ['ISV', 'Platform']:
                mapped_filters.append('Developer')
            else:
                mapped_filters.append(aud)
        feedback_to_display = [item for item in feedback_to_display if
                             (item.get('Audience') in mapped_filters or
                              (item.get('Audience') in ['ISV', 'Platform'] and 'Developer' in mapped_filters))]
        logger.info(f"After audience multi-filter {audience_filters} (mapped: {mapped_filters}): {len(feedback_to_display)} items")
    elif audience_filter != 'All':  # Backwards compatibility
        if audience_filter in ['ISV', 'Platform']:
            audience_filter = 'Developer'  # Map legacy values
        feedback_to_display = [item for item in feedback_to_display if
                             (item.get('Audience') == audience_filter or
                              (item.get('Audience') in ['ISV', 'Platform'] and audience_filter == 'Developer'))]
        logger.info(f"After audience filter '{audience_filter}': {len(feedback_to_display)} items")
    
    if priority_filters:
        feedback_to_display = [item for item in feedback_to_display if item.get('Priority') in priority_filters]
        logger.info(f"After priority multi-filter {priority_filters}: {len(feedback_to_display)} items")
    elif priority_filter != 'All':  # Backwards compatibility
        feedback_to_display = [item for item in feedback_to_display if item.get('Priority') == priority_filter]
        logger.info(f"After priority filter '{priority_filter}': {len(feedback_to_display)} items")
    
    if domain_filters:
        feedback_to_display = [item for item in feedback_to_display if item.get('Primary_Domain') in domain_filters]
        logger.info(f"After domain multi-filter {domain_filters}: {len(feedback_to_display)} items")
    elif domain_filter != 'All':  # Backwards compatibility
        feedback_to_display = [item for item in feedback_to_display if item.get('Primary_Domain') == domain_filter]
        logger.info(f"After domain filter '{domain_filter}': {len(feedback_to_display)} items")
    
    if sentiment_filters:
        feedback_to_display = [item for item in feedback_to_display if item.get('Sentiment') in sentiment_filters]
        logger.info(f"After sentiment multi-filter {sentiment_filters}: {len(feedback_to_display)} items")
    elif sentiment_filter != 'All':  # Backwards compatibility
        feedback_to_display = [item for item in feedback_to_display if item.get('Sentiment') == sentiment_filter]
        logger.info(f"After sentiment filter '{sentiment_filter}': {len(feedback_to_display)} items")
    
    if state_filters:
        feedback_to_display = [item for item in feedback_to_display if item.get('State', 'NEW') in state_filters]
        logger.info(f"After state multi-filter {state_filters}: {len(feedback_to_display)} items")
    elif state_filter != 'All':  # Backwards compatibility
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

    all_sources = sorted(list(set(item.get('Sources', 'Unknown') for item in last_collected_feedback if item.get('Sources'))))
    all_categories = sorted(list(set(item.get('Category', 'Uncategorized') for item in last_collected_feedback if item.get('Category'))))
    # Safely extract and sort values, filtering out None, NaN, and non-string values
    all_enhanced_categories = sorted(list(set([item.get('Enhanced_Category') for item in last_collected_feedback
                                              if item.get('Enhanced_Category') and isinstance(item.get('Enhanced_Category'), str)])))
    all_audiences = sorted(list(set([item.get('Audience') for item in last_collected_feedback
                                    if item.get('Audience') and isinstance(item.get('Audience'), str)])))
    all_priorities = sorted(list(set([item.get('Priority') for item in last_collected_feedback
                                     if item.get('Priority') and isinstance(item.get('Priority'), str)])))
    all_domains = sorted(list(set([item.get('Primary_Domain') for item in last_collected_feedback
                                  if item.get('Primary_Domain') and isinstance(item.get('Primary_Domain'), str)])))
    all_sentiments = sorted(list(set([item.get('Sentiment') for item in last_collected_feedback
                                     if item.get('Sentiment') and isinstance(item.get('Sentiment'), str)])))
    all_states = ['NEW', 'TRIAGED', 'CLOSED', 'IRRELEVANT']  # Available states

    trending_category_name = None
    trending_category_count = 0
    if feedback_to_display:
        category_counts = pd.Series([item.get('Category', 'Uncategorized') for item in feedback_to_display]).value_counts()
        if not category_counts.empty:
            trending_category_name = category_counts.index[0]
            trending_category_count = int(category_counts.iloc[0])

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
                           states_already_loaded=states_already_loaded,
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
                'message': '🛑 Cancellation requested (operation will stop at next checkpoint)',
                'type': 'warning'
            })
            # Note: Actual cancellation would require more complex implementation
            return jsonify({'status': 'success', 'message': 'Cancellation requested'})
        else:
            return jsonify({'error': 'Operation not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
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
            'error_message': collection_status['error_message']
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
        
        # Write state changes to Fabric SQL Database (much more reliable than lakehouse)
        try:
            import fabric_sql_writer
            
            # Add user information to each change
            for change in state_changes:
                change['updated_by'] = user
            
            logger.warning(f"🔥 FABRIC SQL SYNC: Writing {len(state_changes)} state changes to Fabric SQL Database")
            print(f"🔥 FABRIC SQL SYNC: Processing {len(state_changes)} state changes")
            
            # Use new SQL-based fabric writer (much more reliable)
            fabric_success = fabric_sql_writer.update_feedback_states_in_fabric_sql(
                auth_header.replace('Bearer ', ''),
                state_changes
            )
            
            if not fabric_success:
                logger.error("❌ FABRIC SQL SYNC FAILED: Could not write to Fabric SQL Database")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to write state changes to Fabric SQL Database'
                }), 500
                
            logger.warning("✅ FABRIC SQL SYNC SUCCESS: All state changes written to Fabric SQL Database")
            print("✅ FABRIC SQL SYNC COMPLETED SUCCESSFULLY")
            
        except ImportError:
            logger.error("❌ FABRIC SQL WRITER NOT FOUND: fabric_sql_writer.py not available")
            fabric_success = False
            
        # If SQL failed (including ODBC driver issues), try lakehouse fallback
        if not fabric_success:
            try:
                import fabric_writer
                logger.warning("🔄 FABRIC SQL FAILED - Falling back to lakehouse writer...")
                
                fabric_success = fabric_writer.update_feedback_states_in_fabric(
                    auth_header.replace('Bearer ', ''),
                    state_changes
                )
                
                if fabric_success:
                    logger.warning("✅ FABRIC LAKEHOUSE FALLBACK SUCCESS")
                else:
                    raise Exception("Lakehouse fallback also failed")
                    
            except Exception as fallback_error:
                logger.error(f"❌ BOTH SQL AND LAKEHOUSE FAILED: {fallback_error}")
                return jsonify({
                    'status': 'error',
                    'message': 'Both SQL and Lakehouse writers failed'
                }), 500
                
        
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
        logger.error(f"Error updating feedback state: {e}")
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
        valid_domains = ['GOVERNANCE', 'USER_EXPERIENCE', 'AUTHENTICATION', 'PERFORMANCE', 'INTEGRATION', 'ANALYTICS']
        if new_domain not in valid_domains:
            return jsonify({'success': False, 'message': f'Invalid domain. Must be one of: {valid_domains}'}), 400
        
        # Update in Fabric SQL database using state_manager (no bearer token needed)
        success = state_manager.update_feedback_field_in_sql(feedback_id, 'Primary_Domain', new_domain, None)
        
        if success:
            logger.info(f"✅ Successfully updated domain for {feedback_id} to {new_domain}")
            return jsonify({'success': True, 'message': f'Domain updated to {new_domain}'})
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')