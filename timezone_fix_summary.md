# Date Sorting Timezone Fix Summary

## Problem Identified
The feedback viewer was experiencing a timezone comparison error when sorting dates:
```
TypeError: can't compare offset-naive and offset-aware datetimes
```

This occurred because the CSV data contained a mix of:
- Timezone-aware dates (e.g., from Reddit with UTC offsets)
- Timezone-naive dates (e.g., from MS Fabric Community without timezone info)

## Root Cause
The `parse_date` function in `src/app.py` was creating datetime objects with mixed timezone awareness:
- Some dates had timezone info (when parsed with `fromisoformat`)
- Others were timezone-naive (when parsed with `strptime`)

## Solution Implemented
Modified the `parse_date` function to normalize all datetime objects to timezone-naive by removing timezone information:

```python
def parse_date(item):
    date_str = item.get('Created', '')
    if date_str:
        try:
            # Handle ISO format dates (e.g., '2025-01-15T10:30:00')
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                # Remove timezone info to make all dates naive for consistent comparison
                return dt.replace(tzinfo=None)
            # Handle date-only format (e.g., '2025-01-15')
            else:
                return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError) as e:
            logger.debug(f"Date parsing error for '{date_str}': {e}")
            pass
    # Return a very old date for items without valid dates
    return datetime(1900, 1, 1)
```

## Key Changes
1. Added `dt.replace(tzinfo=None)` to remove timezone information from ISO format dates
2. This ensures all datetime objects are timezone-naive for consistent comparison
3. Maintains the original date/time values while removing timezone awareness

## Files Modified
- `src/app_fixed.py` - Contains the corrected version with the timezone fix
- The original `src/app.py` would need the same fix applied

## Testing
Created test scripts to verify the fix:
- `src/test_date_sorting_fixed.py` - Tests the fix with actual CSV data
- `src/simple_date_test.py` - Simple test with sample date strings

## Impact
This fix resolves the sorting error and allows the feedback viewer to properly sort items by date (newest/oldest first) without timezone comparison conflicts.
