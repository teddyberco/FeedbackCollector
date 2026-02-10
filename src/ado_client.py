"""
Working ADO Client - Gets children of specific parent work item from past year
"""

import os
import requests
import base64
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import config

# .env is loaded centrally by config.py - no need to load again here

logger = logging.getLogger(__name__)

def get_working_ado_items(parent_work_item_id: str = None, top: int = 20) -> List[Dict[str, Any]]:
    """Get ADO work items that are children of specific parent work item from past year"""
    try:
        # Get parent work item ID from config if not provided
        if not parent_work_item_id:
            parent_work_item_id = config.ADO_PARENT_WORK_ITEM_ID
        
        logger.info(f"Getting children of parent work item: {parent_work_item_id}")
        
        # Get PAT token
        pat_token = config.ADO_PAT or os.getenv('AZURE_DEVOPS_PAT') or os.getenv('ADO_PAT')
        if not pat_token:
            logger.error("No PAT token found")
            return []
        
        # Create auth header
        auth_string = f":{pat_token}"
        auth_bytes = base64.b64encode(auth_string.encode('ascii')).decode('ascii')
        headers = {
            'Authorization': f'Basic {auth_bytes}',
            'Content-Type': 'application/json'
        }
        
        # Calculate date one year ago
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        # Step 1: Try to get children using REST API relations
        relations_url = f"https://dev.azure.com/powerbi/Trident/_apis/wit/workitems/{parent_work_item_id}?$expand=relations&api-version=7.1-preview.3"
        
        logger.info(f"Getting relations for parent work item {parent_work_item_id}")
        
        response = requests.get(relations_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Failed to get parent work item: {response.status_code} - {response.text}")
            # Fallback: get recent work items instead
            logger.info("Falling back to recent work items from past year")
            
            wiql_url = f"https://dev.azure.com/powerbi/Trident/_apis/wit/wiql?$top={top}&api-version=7.1-preview.2"
            fallback_query = f'SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.TeamProject] = "Trident" AND [System.CreatedDate] >= \'{one_year_ago}T00:00:00.000Z\' ORDER BY [System.CreatedDate] DESC'
            
            fallback_response = requests.post(wiql_url, json={"query": fallback_query}, headers=headers, timeout=30)
            
            if fallback_response.status_code != 200:
                logger.error(f"Fallback query failed: {fallback_response.status_code}")
                return []
            
            wiql_result = fallback_response.json()
            work_item_refs = wiql_result.get('workItems', [])
        else:
            # Extract children from relations
            parent_data = response.json()
            relations = parent_data.get('relations', [])
            
            child_ids = []
            for relation in relations:
                # Look for child relationships (different link types possible)
                if (relation.get('rel') == 'System.LinkTypes.Hierarchy-Forward' or
                    'child' in relation.get('rel', '').lower()):
                    url = relation.get('url', '')
                    if url:
                        # Extract work item ID from URL
                        work_item_id = url.split('/')[-1]
                        if work_item_id.isdigit():
                            child_ids.append(work_item_id)
            
            if not child_ids:
                logger.info(f"No child relationships found for parent {parent_work_item_id}")
                # Fallback: get recent work items
                logger.info("Falling back to recent work items from past year")
                
                wiql_url = f"https://dev.azure.com/powerbi/Trident/_apis/wit/wiql?$top={top}&api-version=7.1-preview.2"
                fallback_query = f'SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.TeamProject] = "Trident" AND [System.CreatedDate] >= \'{one_year_ago}T00:00:00.000Z\' ORDER BY [System.CreatedDate] DESC'
                
                fallback_response = requests.post(wiql_url, json={"query": fallback_query}, headers=headers, timeout=30)
                
                if fallback_response.status_code != 200:
                    logger.error(f"Fallback query failed: {fallback_response.status_code}")
                    return []
                
                wiql_result = fallback_response.json()
                work_item_refs = wiql_result.get('workItems', [])
            else:
                work_item_refs = [{'id': child_id} for child_id in child_ids]
        
        if not work_item_refs:
            logger.info("No work items found")
            return []
        
        logger.info(f"Found {len(work_item_refs)} work items")
        
        # Step 2: Get detailed work item information including description
        # Limit to first 'top' items and batch requests to avoid 500 errors
        # Ensure top is an integer
        top = int(top) if top is not None else 20
        limited_refs = work_item_refs[:top]
        ids = [str(item['id']) for item in limited_refs]
        
        logger.info(f"Getting details for {len(ids)} work items (limited from {len(work_item_refs)})")
        
        # Batch requests to avoid server errors (max 200 items per request)
        batch_size = 200
        all_work_items = []
        
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            ids_string = ','.join(batch_ids)
            
            # Request additional fields including description
            details_url = f"https://dev.azure.com/powerbi/Trident/_apis/wit/workitems?ids={ids_string}&$expand=all&api-version=7.1-preview.3"
            
            logger.info(f"Requesting details for batch {i//batch_size + 1}: {len(batch_ids)} items")
            
            details_response = requests.get(details_url, headers=headers, timeout=30)
            
            if details_response.status_code != 200:
                logger.error(f"Details query failed for batch {i//batch_size + 1}: {details_response.status_code}")
                logger.error(f"Response: {details_response.text[:200]}")
                continue  # Skip this batch but continue with others
            
            details_result = details_response.json()
            batch_work_items = details_result.get('value', [])
            all_work_items.extend(batch_work_items)
            
            logger.info(f"Successfully retrieved {len(batch_work_items)} items from batch {i//batch_size + 1}")
        
        work_items = all_work_items
        logger.info(f"Retrieved details for {len(work_items)} total work items")
        
        # Step 3: Format work items for feedback display
        formatted_items = []
        for item in work_items:
            fields = item.get('fields', {})
            work_item_id = item.get('id')
            
            # Extract user display names
            def extract_user(user_field):
                if not user_field:
                    return "Unassigned"
                if isinstance(user_field, dict):
                    return user_field.get('displayName', 'Unknown')
                return str(user_field)
            
            # Get description from multiple possible fields
            description = ''
            
            # Try different description fields
            desc_fields = [
                'System.Description',
                'Microsoft.VSTS.Common.AcceptanceCriteria',
                'Microsoft.VSTS.Common.ReproSteps',
                'System.History',
                'Microsoft.VSTS.TCM.Steps'
            ]
            
            for field in desc_fields:
                if fields.get(field):
                    description = str(fields.get(field, ''))
                    break
            
            # Clean HTML tags and format description
            import re
            if description:
                # Remove HTML tags
                description = re.sub(r'<[^>]+>', '', description)
                # Remove extra whitespace and newlines
                description = re.sub(r'\s+', ' ', description).strip()
                # Limit length for display
                if len(description) > 500:
                    description = description[:500] + '...'
            
            if not description or description.strip() == '':
                description = 'No description available'
            
            logger.debug(f"Work item {work_item_id}: Description length = {len(description)}")
            
            formatted_item = {
                'id': work_item_id,
                'type': fields.get('System.WorkItemType', 'Unknown'),
                'title': fields.get('System.Title', 'No Title'),
                'description': description,
                'state': fields.get('System.State', 'Unknown'),
                'assignedTo': extract_user(fields.get('System.AssignedTo')),
                'createdBy': extract_user(fields.get('System.CreatedBy')),
                'createdDate': fields.get('System.CreatedDate', ''),
                'areaPath': fields.get('System.AreaPath', ''),
                'url': f"https://dev.azure.com/powerbi/Trident/_workitems/edit/{work_item_id}"
            }
            formatted_items.append(formatted_item)
        
        logger.info(f"Successfully formatted {len(formatted_items)} work items with descriptions")
        return formatted_items
        
    except Exception as e:
        logger.error(f"Error getting ADO work items: {e}")
        return []

def test_working_client():
    """Test the working client"""
    items = get_working_ado_items(5)
    print(f"Working client returned: {len(items)} items")
    
    if items:
        print("SUCCESS! Work items:")
        for item in items[:3]:
            print(f"  - {item['id']}: {item['title']} ({item['type']})")
        return True
    else:
        print("Working client returned 0 items")
        return False

if __name__ == "__main__":
    test_working_client()