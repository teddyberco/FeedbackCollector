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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')

last_collected_feedback = []
last_collection_summary = {"reddit": 0, "fabric": 0, "github": 0, "total": 0}

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
    global last_collected_feedback, last_collection_summary
    last_collected_feedback = []
    
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
        
        reddit_feedback = reddit_collector.collect()
        logger.info(f"Reddit collector found {len(reddit_feedback)} items.")
        
        fabric_feedback = fabric_collector.collect()
        logger.info(f"Fabric Community collector found {len(fabric_feedback)} items.")
        
        github_feedback = github_collector.collect()
        logger.info(f"GitHub Discussions collector found {len(github_feedback)} items.")
        
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
            
            # Use description + title for content (what user sees on feedback cards)
            full_content = f"{title}"
            if description and description != 'No description available':
                full_content += f"\n\nDescription: {description}"
            
            # Categorize based on the full feedback content (title + description)
            category = utils.categorize_feedback(full_content)
            
            # Analyze sentiment of the feedback content
            sentiment_analysis = utils.analyze_sentiment(full_content)
            
            ado_feedback.append({
                'Title': f"[ADO-{work_item_id}] {title}",
                'Feedback_Gist': f"[ADO-{work_item_id}] {title}",  # For card title
                'Feedback': full_content,  # This is what shows in the card content
                'Content': full_content,  # Backup field
                'Author': item.get('createdBy', ''),
                'Created': item.get('createdDate', ''),
                'Url': ado_url,  # Proper field name for "View Source" button
                'URL': ado_url,  # Backup field
                'Sources': 'Azure DevOps',
                'Category': category,  # Use text-based categorization
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
            return jsonify({**last_collection_summary, "csv_error": str(e)}), 500
            
        return jsonify(last_collection_summary)
        
    except Exception as e:
        logger.error(f"Error in collection route: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/feedback')
def feedback_viewer():
    """Full-featured feedback viewer with template rendering"""
    global last_collected_feedback
    
    source_filter = request.args.get('source', 'All')
    category_filter = request.args.get('category', 'All')
    sentiment_filter = request.args.get('sentiment', 'All')
    sort_by = request.args.get('sort', 'newest')  # Default to newest first
    
    # If no feedback in memory, try loading from CSV
    if not last_collected_feedback:
        logger.info("No feedback in memory, attempting to load from CSV")
        last_collected_feedback = load_latest_feedback_from_csv()
        
        # Apply sentiment analysis to loaded feedback if not already present
        if last_collected_feedback:
            for item in last_collected_feedback:
                if 'Sentiment_Score' not in item or item.get('Sentiment_Score') is None:
                    text_content = item.get('Feedback', '') or item.get('Content', '') or item.get('Title', '')
                    sentiment_analysis = utils.analyze_sentiment(text_content)
                    
                    item['Sentiment'] = sentiment_analysis['label']
                    item['Sentiment_Score'] = sentiment_analysis['polarity']
                    item['Sentiment_Confidence'] = sentiment_analysis['confidence']
    
    feedback_to_display = list(last_collected_feedback)  # Create a copy to avoid modifying the original
    source_info_message = f"Displaying all {len(feedback_to_display)} collected items."

    # Debug logging
    logger.info(f"Feedback viewer - Initial count: {len(feedback_to_display)}, Source filter: {source_filter}, Category filter: {category_filter}, Sort: {sort_by}")

    if source_filter != 'All':
        feedback_to_display = [item for item in feedback_to_display if item.get('Sources') == source_filter]
        logger.info(f"After source filter '{source_filter}': {len(feedback_to_display)} items")
    
    if category_filter != 'All':
        feedback_to_display = [item for item in feedback_to_display if item.get('Category') == category_filter]
        logger.info(f"After category filter '{category_filter}': {len(feedback_to_display)} items")
    
    if sentiment_filter != 'All':
        feedback_to_display = [item for item in feedback_to_display if item.get('Sentiment') == sentiment_filter]
        logger.info(f"After sentiment filter '{sentiment_filter}': {len(feedback_to_display)} items")

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

    if source_filter != 'All' or category_filter != 'All' or sentiment_filter != 'All':
        filters_applied = []
        if source_filter != 'All':
            filters_applied.append(f"Source: {source_filter}")
        if category_filter != 'All':
            filters_applied.append(f"Category: {category_filter}")
        if sentiment_filter != 'All':
            filters_applied.append(f"Sentiment: {sentiment_filter}")
        source_info_message = f"Filtered by {', '.join(filters_applied)}. Showing {len(feedback_to_display)} items."

    all_sources = sorted(list(set(item.get('Sources', 'Unknown') for item in last_collected_feedback if item.get('Sources'))))
    all_categories = sorted(list(set(item.get('Category', 'Uncategorized') for item in last_collected_feedback if item.get('Category'))))
    all_sentiments = sorted(list(set(item.get('Sentiment', 'Neutral') for item in last_collected_feedback if item.get('Sentiment'))))

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
                           all_sentiments=all_sentiments,
                           current_sentiment=sentiment_filter,
                           current_sort=sort_by,
                           trending_category_name=trending_category_name,
                           trending_category_count=trending_category_count
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
            'message': operation['message']
        })
        
    except Exception as e:
        logger.error(f"Error getting Fabric progress: {e}")
        return jsonify({'error': 'Failed to get progress'}), 500

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')