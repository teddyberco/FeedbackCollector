import os
import csv
import logging
from datetime import datetime
from typing import List, Dict, Any
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_storage():
    """Initialize storage directory."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info(f"Storage directory initialized at: {os.path.abspath(OUTPUT_DIR)}")

def save_feedback_items(feedback_items: List[Dict[str, Any]]) -> None:
    """Save feedback items to a CSV file."""
    try:
        if not feedback_items:
            logger.info("No feedback items to save")
            return

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(OUTPUT_DIR, f"feedback_{timestamp}.csv")
        logger.info(f"Saving feedback items to: {os.path.abspath(filename)}")
            
        # Ensure all items have all columns in correct order
        formatted_items = [
            {col: str(item.get(col, '')) for col in TABLE_COLUMNS}
            for item in feedback_items
        ]
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Write to CSV
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=TABLE_COLUMNS)
            writer.writeheader()
            writer.writerows(formatted_items)
        
        logger.info(f"Successfully saved {len(feedback_items)} feedback items")
        logger.info(f"CSV file created at: {os.path.abspath(filename)}")
    
    except Exception as e:
        logger.error(f"Error saving feedback to CSV: {str(e)}")
        raise

def validate_feedback_item(item: Dict[str, Any]) -> bool:
    """Validate that a feedback item contains all required fields."""
    return all(column in item for column in TABLE_COLUMNS)

def format_feedback_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all required fields are present with default values if needed."""
    formatted_item = {}
    
    for column in TABLE_COLUMNS:
        if column not in item:
            if column == 'Status':
                formatted_item[column] = DEFAULT_STATUS
            elif column == 'Created_by':
                formatted_item[column] = SYSTEM_USER
            elif column == 'Created':
                formatted_item[column] = datetime.now().isoformat()
            else:
                formatted_item[column] = ''
        else:
            formatted_item[column] = item[column]
            
    return formatted_item

# Initialize storage on module import
init_storage()
