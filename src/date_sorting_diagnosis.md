# Date Sorting Issue Diagnosis

## Problem Description
The "Sort by Date" feature isn't working when filtering by "All Sources" in the feedback viewer.

## Diagnosis Approach

### 1. Identified Potential Sources
After analyzing the code, I identified these potential causes:

1. **Pandas NaT/NaN handling** - When loading from CSV, pandas might introduce NaT (Not a Time) values
2. **Date format inconsistency** - Different sources might use different date formats
3. **Data type issues** - CSV loading might change date types
4. **Empty or invalid dates** - Some items might have missing dates
5. **String conversion issues** - Dates might be stored as 'nan' or 'NaT' strings

### 2. Most Likely Causes
Based on code analysis, the two most likely causes are:
- **Pandas NaT values not being handled properly** in the parse_date function
- **Date values being converted to string 'nan' or 'NaT'** during CSV operations

### 3. Changes Made for Diagnosis

#### Enhanced app.py logging
Added detailed debug logging to the feedback_viewer function that shows:
- Raw date values and their types
- Whether values are NaN/NaT
- Date parsing results for each item
- Date diversity warnings
- Source information for problematic dates

#### Created debug_date_sorting_enhanced.py
A standalone script that analyzes CSV data to:
- Check date column data types
- Group dates by source
- Test date parsing logic
- Compare sorting effectiveness
- Identify if all dates parse to the same value

#### Created test_sorting_issue.py
A helper script that guides you through testing the issue with clear instructions.

## How to Diagnose

### Step 1: Run the enhanced debug script
```bash
python src/debug_date_sorting_enhanced.py
```

This will analyze your CSV data and show:
- How dates are stored in the CSV
- Whether different sources have different date formats
- If date parsing is working correctly
- Whether sorting is actually changing the order

### Step 2: Test in the web app
1. Start the Flask app: `python src/app.py`
2. Open the feedback viewer: http://localhost:5000/feedback
3. Try these scenarios and watch the console logs:
   - All Sources + Newest First
   - All Sources + Oldest First
   - Single Source + Newest First
   - Single Source + Oldest First

### Step 3: Look for these indicators in the logs

**Good signs:**
- Dates show as actual date strings (e.g., "2025-01-15T10:30:00")
- "Unique parsed dates" shows multiple different dates
- Order changes between newest/oldest sorting

**Problem indicators:**
- Dates show as 'nan', 'NaT', or empty strings
- "Low date diversity!" warning
- "WARNING: All dates parsed to the same value!"
- Same order for newest and oldest sorting

## Next Steps

Once you run the diagnostic tools and share the output, I can:
1. Confirm the exact cause of the issue
2. Implement the appropriate fix
3. Test the solution

The fix will likely involve:
- Better handling of pandas NaT values
- Improved date string validation
- Possibly preserving original date formats during CSV operations