from flask import Flask, render_template, request, jsonify, send_from_directory, current_app
import pandas as pd
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple 
import json 

from collectors import RedditCollector, FabricCommunityCollector, GitHubDiscussionsCollector
import config 
# Removed: from utils import get_keywords, save_keywords_to_file, get_default_keywords
# utils.py is still used for other functions like categorize_feedback, generate_feedback_gist if needed by collectors
# but keyword management functions will now come from config.py

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')

last_collected_feedback: List[Dict[str, Any]] = []
last_collection_summary: Dict[str, int] = {"reddit": 0, "fabric": 0, "github": 0, "total": 0}

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
    return render_template('insights_page.html')

@app.route('/api/keywords', methods=['GET', 'POST'])
def manage_keywords_route():
    if request.method == 'GET':
        keywords = config.load_keywords() # Changed from get_keywords()
        return jsonify(keywords)
    elif request.method == 'POST':
        try:
            data = request.get_json()
            if data is None or 'keywords' not in data or not isinstance(data['keywords'], list):
                return jsonify({'status': 'error', 'message': 'Invalid keywords data. Expected a list.'}), 400
            
            valid_keywords = [str(k).strip() for k in data['keywords'] if str(k).strip()]
            
            config.save_keywords(valid_keywords) # Changed from save_keywords_to_file()
            # Update the global KEYWORDS in config module as well, so collectors use the new ones immediately
            config.KEYWORDS = valid_keywords.copy() 
            logger.info(f"Keywords updated and saved: {valid_keywords}")
            return jsonify({'status': 'success', 'keywords': valid_keywords, 'message': 'Keywords saved successfully.'})
        except Exception as e:
            logger.error(f"Error saving keywords: {e}", exc_info=True)
            return jsonify({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/keywords/restore_default', methods=['POST'])
def restore_default_keywords_route():
    try:
        default_keywords = config.DEFAULT_KEYWORDS # Changed from get_default_keywords()
        config.save_keywords(default_keywords) # Changed from save_keywords_to_file()
        # Update the global KEYWORDS in config module as well
        config.KEYWORDS = default_keywords.copy()
        logger.info(f"Default keywords restored and saved: {default_keywords}")
        return jsonify({'status': 'success', 'keywords': default_keywords, 'message': 'Default keywords restored and saved.'})
    except Exception as e:
        logger.error(f"Error restoring default keywords: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/collect', methods=['POST'])
def collect_feedback_route():
    global last_collected_feedback, last_collection_summary
    last_collected_feedback = [] 

    logger.info("Starting feedback collection process via API.")
    
    # Reload keywords from file in case they were changed by another process
    # or to ensure the most current set is used by collectors.
    # The config.KEYWORDS is updated by save_keywords and restore_default_keywords routes.
    # So, collectors should already be using the latest if they import config.KEYWORDS.
    # However, explicit reloading here can be a safeguard if needed, but might be redundant
    # if config.KEYWORDS is dynamically updated correctly.
    # For now, relying on config.KEYWORDS being up-to-date.
    # config.KEYWORDS = config.load_keywords() # Optional: force reload if concerned about external changes

    reddit_collector = RedditCollector()
    fabric_collector = FabricCommunityCollector()
    github_collector = GitHubDiscussionsCollector()

    reddit_feedback = reddit_collector.collect()
    logger.info(f"Reddit collector found {len(reddit_feedback)} items.")
    
    fabric_feedback = fabric_collector.collect()
    logger.info(f"Fabric Community collector found {len(fabric_feedback)} items.")
    
    github_feedback = github_collector.collect()
    logger.info(f"GitHub Discussions collector found {len(github_feedback)} items.")

    all_feedback = reddit_feedback + fabric_feedback + github_feedback
    
    last_collected_feedback = all_feedback
    last_collection_summary = {
        "reddit": len(reddit_feedback),
        "fabric": len(fabric_feedback),
        "github": len(github_feedback),
        "total": len(all_feedback)
    }
    logger.info(f"Total feedback items collected: {len(all_feedback)}")

    if not all_feedback:
        logger.info("No feedback items collected in this run.")
        return jsonify(last_collection_summary)

    try:
        df = pd.DataFrame(all_feedback)
        expected_columns = getattr(config, 'TABLE_COLUMNS', getattr(config, 'EXPECTED_COLUMNS', [])) # Check for both names
        if not expected_columns: # Fallback if not defined in config
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

@app.route('/feedback')
def feedback_viewer():
    global last_collected_feedback
    
    source_filter = request.args.get('source', 'All')
    category_filter = request.args.get('category', 'All')
    sort_by = request.args.get('sort', 'newest')  # Default to newest first
    
    # If no feedback in memory, try loading from CSV
    if not last_collected_feedback:
        logger.info("No feedback in memory, attempting to load from CSV")
        last_collected_feedback = load_latest_feedback_from_csv()
    
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

    # Sort by date - newest items first by default
    if feedback_to_display:
        try:
            # Enhanced debug logging for date sorting issue
            logger.info(f"=== Date Sorting Debug for source_filter='{source_filter}' ===")
            
            # Debug: show sample dates and types before sorting
            sample_dates = []
            for i, item in enumerate(feedback_to_display[:5]):
                date_val = item.get('Created', 'No date')
                date_type = type(date_val).__name__
                is_nan = pd.isna(date_val) if pd.api.types.is_scalar(date_val) else False
                sample_dates.append(f"Item {i}: value='{date_val}', type={date_type}, is_nan={is_nan}, source={item.get('Sources', 'Unknown')}")
            logger.info(f"Sample items before sorting: {sample_dates}")
            
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
            
            # Check date distribution before sorting
            parsed_dates = []
            for item in feedback_to_display[:10]:  # Sample first 10 items
                parsed = parse_date(item)
                parsed_dates.append((parsed, item.get('Sources', 'Unknown')))
            
            unique_parsed = set(d[0] for d in parsed_dates)
            logger.info(f"Unique parsed dates in sample: {len(unique_parsed)}")
            if len(unique_parsed) <= 2:
                logger.warning(f"Low date diversity! Parsed dates: {[(d[0].isoformat(), d[1]) for d in parsed_dates[:3]]}")
            
            reverse_order = sort_by == 'newest'
            feedback_to_display = sorted(feedback_to_display, key=parse_date, reverse=reverse_order)
            
            # Debug: show sample dates after sorting with more detail
            sample_dates_after = []
            for i, item in enumerate(feedback_to_display[:5]):
                date_str = item.get('Created', 'No date')
                parsed = parse_date(item)
                sample_dates_after.append(f"Item {i}: raw='{date_str}', parsed='{parsed.isoformat()}', source={item.get('Sources', 'Unknown')}")
            logger.info(f"Sorted {len(feedback_to_display)} items by date ({sort_by} first)")
            logger.info(f"Sample items after sorting: {sample_dates_after}")
            logger.info("=== End Date Sorting Debug ===")
        except Exception as e:
            logger.warning(f"Error sorting feedback by date: {e}")

    if source_filter != 'All' or category_filter != 'All':
        filters_applied = []
        if source_filter != 'All':
            filters_applied.append(f"Source: {source_filter}")
        if category_filter != 'All':
            filters_applied.append(f"Category: {category_filter}")
        source_info_message = f"Filtered by {', '.join(filters_applied)}. Showing {len(feedback_to_display)} items."

    all_sources = sorted(list(set(item.get('Sources', 'Unknown') for item in last_collected_feedback if item.get('Sources'))))
    all_categories = sorted(list(set(item.get('Category', 'Uncategorized') for item in last_collected_feedback if item.get('Category'))))

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
        
        logger.info("Simulating successful write to Fabric Lakehouse.")
        time_to_simulate_work = len(last_collected_feedback) * 0.05 
        import time
        time.sleep(min(time_to_simulate_work, 5)) 

        return jsonify({'status': 'success', 'message': f'Successfully wrote {len(last_collected_feedback)} items to Fabric table {config.FABRIC_TARGET_TABLE_NAME} (simulated).'})

    except Exception as e:
        logger.error(f"Error writing to Fabric: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
