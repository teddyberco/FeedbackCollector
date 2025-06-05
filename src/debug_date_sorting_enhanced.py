#!/usr/bin/env python3
"""Enhanced debug script to diagnose date sorting issues with All Sources filter"""

import pandas as pd
import os
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

def parse_date(item):
    """Parse date from item - enhanced version with NaT handling"""
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
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            # Handle date-only format (e.g., '2025-01-15')
            else:
                return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError) as e:
            logger.warning(f"Date parsing error for '{date_str}': {e}")
            pass
    # Return a very old date for items without valid dates
    return datetime(1900, 1, 1)

def analyze_date_sorting():
    """Analyze date sorting behavior with focus on All Sources scenario"""
    print("\n=== Enhanced Date Sorting Analysis ===\n")
    
    # Get the latest CSV file
    csv_files = [f for f in os.listdir(DATA_DIR) if f.startswith('feedback_') and f.endswith('.csv')]
    if not csv_files:
        print("No CSV files found in data directory")
        return
    
    latest_file = sorted(csv_files)[-1]
    filepath = os.path.join(DATA_DIR, latest_file)
    print(f"Loading data from: {filepath}\n")
    
    # Load CSV
    df = pd.read_csv(filepath, encoding='utf-8-sig')
    print(f"DataFrame shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}\n")
    
    # Check Created column info
    print("--- Created Column Analysis ---")
    print(f"Data type: {df['Created'].dtype}")
    print(f"Null values: {df['Created'].isnull().sum()}")
    print(f"Empty strings: {(df['Created'] == '').sum()}")
    print(f"Unique values: {df['Created'].nunique()}\n")
    
    # Convert to list of dicts (like the app does)
    feedback_items = df.to_dict('records')
    
    # Group by source
    sources_data = {}
    for item in feedback_items:
        source = item.get('Sources', 'Unknown')
        if source not in sources_data:
            sources_data[source] = []
        sources_data[source].append(item)
    
    print("--- Date Analysis by Source ---")
    for source, items in sources_data.items():
        print(f"\n{source} ({len(items)} items):")
        # Sample first few dates
        sample_dates = []
        for i, item in enumerate(items[:3]):
            created = item.get('Created')
            date_type = type(created).__name__
            is_nan = pd.isna(created)
            sample_dates.append(f"  - '{created}' (type: {date_type}, is_nan: {is_nan})")
        print('\n'.join(sample_dates))
    
    print("\n--- Testing Date Parsing ---")
    # Test parsing for each source
    for source, items in sources_data.items():
        print(f"\n{source}:")
        parsed_dates = []
        for item in items:
            try:
                parsed = parse_date(item)
                parsed_dates.append(parsed)
            except Exception as e:
                print(f"  ERROR parsing date: {e}")
        
        if parsed_dates:
            unique_dates = set(parsed_dates)
            print(f"  Unique parsed dates: {len(unique_dates)}")
            if len(unique_dates) <= 2:
                print(f"  WARNING: Low date diversity!")
                print(f"  Sample parsed dates: {[d.isoformat() for d in list(unique_dates)[:3]]}")
    
    print("\n--- Testing Sorting (All Sources) ---")
    print(f"Total items: {len(feedback_items)}")
    
    # Sort by newest first
    sorted_newest = sorted(feedback_items, key=parse_date, reverse=True)
    print("\nNewest first (top 5):")
    for i, item in enumerate(sorted_newest[:5]):
        created = item.get('Created', 'No date')
        parsed = parse_date(item)
        source = item.get('Sources', 'Unknown')
        print(f"  {i+1}. {source}: '{created}' -> {parsed.isoformat()}")
    
    # Sort by oldest first
    sorted_oldest = sorted(feedback_items, key=parse_date, reverse=False)
    print("\nOldest first (top 5):")
    for i, item in enumerate(sorted_oldest[:5]):
        created = item.get('Created', 'No date')
        parsed = parse_date(item)
        source = item.get('Sources', 'Unknown')
        print(f"  {i+1}. {source}: '{created}' -> {parsed.isoformat()}")
    
    # Check if sorting actually changed the order
    print("\n--- Sorting Effectiveness Check ---")
    if [item.get('Created') for item in sorted_newest[:5]] == [item.get('Created') for item in sorted_oldest[:5]]:
        print("WARNING: Sorting did not change the order of items!")
        print("This suggests all dates might be parsing to the same value.")
    else:
        print("Sorting appears to be working (order changed between newest/oldest)")
    
    # Compare with source-specific sorting
    print("\n--- Comparing All Sources vs Single Source Sorting ---")
    for source, items in list(sources_data.items())[:1]:  # Test with first source
        if len(items) > 5:
            sorted_source = sorted(items, key=parse_date, reverse=True)
            print(f"\n{source} only - Newest first (top 3):")
            for i, item in enumerate(sorted_source[:3]):
                created = item.get('Created', 'No date')
                parsed = parse_date(item)
                print(f"  {i+1}. '{created}' -> {parsed.isoformat()}")

if __name__ == "__main__":
    analyze_date_sorting()