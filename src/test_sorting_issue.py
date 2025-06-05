#!/usr/bin/env python3
"""
Script to help test the date sorting issue.
Run this to see detailed debug output about date sorting.
"""

import requests
import time

BASE_URL = "http://localhost:5000"

print("=== Date Sorting Issue Test ===")
print("\nThis script will help you test the date sorting issue.")
print("Make sure the Flask app is running (python src/app.py)")
print("\nSteps to reproduce the issue:")
print("1. Visit the feedback viewer page")
print("2. Try sorting with 'All Sources' selected")
print("3. Check the console/terminal for debug logs")
print("\nThe enhanced logging will show:")
print("- Raw date values and their types")
print("- Whether dates are NaN/NaT values")
print("- How dates are being parsed")
print("- Date diversity in the data")
print("- Sample items before and after sorting")

input("\nPress Enter when the Flask app is running...")

print("\n--- Testing different sorting scenarios ---")

# Test URLs
test_urls = [
    ("All Sources - Newest First", f"{BASE_URL}/feedback?source=All&sort=newest"),
    ("All Sources - Oldest First", f"{BASE_URL}/feedback?source=All&sort=oldest"),
    ("Single Source - Newest First", f"{BASE_URL}/feedback?source=Reddit&sort=newest"),
    ("Single Source - Oldest First", f"{BASE_URL}/feedback?source=Reddit&sort=oldest"),
]

print("\nOpen these URLs in your browser and check the Flask console for debug logs:")
for name, url in test_urls:
    print(f"\n{name}:")
    print(f"  {url}")

print("\n\n--- What to look for in the logs ---")
print("1. Look for '=== Date Sorting Debug ===' sections")
print("2. Check if date values show as 'nan', 'NaT', or actual dates")
print("3. See if 'Low date diversity!' warning appears")
print("4. Compare parsed dates to see if they're all the same")
print("5. Check if the order actually changes between newest/oldest")

print("\n\n--- To run the enhanced debug script ---")
print("In another terminal, run:")
print("  python src/debug_date_sorting_enhanced.py")
print("\nThis will analyze your CSV data directly and show:")
print("- Date formats by source")
print("- Parsing results")
print("- Whether sorting is effective")