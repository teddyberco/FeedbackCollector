import uuid
import json
import base64
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from config import FEEDBACK_STATES, DEFAULT_FEEDBACK_STATE

logger = logging.getLogger(__name__)

def generate_feedback_id() -> str:
    """Generate a unique feedback ID using UUID4"""
    return str(uuid.uuid4())

def extract_user_from_token(bearer_token: str) -> str:
    """
    Extract user information from Fabric bearer token.
    This is a simplified implementation - in production you might want to
    decode the JWT token properly to get user claims.
    """
    try:
        # For now, we'll use a simple approach
        # In a real implementation, you'd decode the JWT token
        # For demonstration, we'll extract a simple identifier
        
        # Remove 'Bearer ' prefix if present
        token = bearer_token.replace('Bearer ', '').strip()
        
        # Try to decode as JWT token (simplified)
        try:
            # Split JWT token into parts
            parts = token.split('.')
            if len(parts) >= 2:
                # Decode the payload (second part)
                # Add padding if needed for base64 decoding
                payload = parts[1]
                padding = len(payload) % 4
                if padding:
                    payload += '=' * (4 - padding)
                
                decoded = base64.urlsafe_b64decode(payload)
                payload_json = json.loads(decoded)
                
                # Try to extract user identifier from common JWT claims
                user_id = (payload_json.get('upn') or 
                          payload_json.get('email') or 
                          payload_json.get('preferred_username') or
                          payload_json.get('name') or
                          payload_json.get('sub', 'Unknown User'))
                
                return str(user_id)
        except Exception as e:
            logger.debug(f"Could not decode JWT token: {e}")
            
        # Fallback: use a hash of the token for consistency
        return f"User-{abs(hash(token)) % 10000}"
        
    except Exception as e:
        logger.error(f"Error extracting user from token: {e}")
        return "Unknown User"

def validate_state(state: str) -> bool:
    """Validate if the given state is valid"""
    return state in FEEDBACK_STATES

def get_state_info(state: str) -> Dict[str, Any]:
    """Get information about a specific state"""
    return FEEDBACK_STATES.get(state, {})

def get_all_states() -> List[Dict[str, Any]]:
    """Get all available states with their information"""
    return [
        {
            'key': key,
            'name': info['name'],
            'description': info['description'],
            'color': info['color'],
            'default': info['default']
        }
        for key, info in FEEDBACK_STATES.items()
    ]

def initialize_feedback_state(feedback_item: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize state-related fields for a new feedback item"""
    now = datetime.now().isoformat()
    
    # Add unique ID if not present
    if 'Feedback_ID' not in feedback_item or not feedback_item['Feedback_ID']:
        feedback_item['Feedback_ID'] = generate_feedback_id()
    
    # Set default state
    feedback_item['State'] = DEFAULT_FEEDBACK_STATE
    feedback_item['Feedback_Notes'] = ''
    feedback_item['Last_Updated'] = now
    feedback_item['Updated_By'] = 'System'
    
    return feedback_item

def update_feedback_state(feedback_id: str, new_state: str, notes: str, user: str) -> Dict[str, Any]:
    """
    Create a state update record for a feedback item.
    This returns the update data that should be applied to the feedback record.
    """
    if not validate_state(new_state):
        raise ValueError(f"Invalid state: {new_state}")
    
    now = datetime.now().isoformat()
    
    return {
        'Feedback_ID': feedback_id,
        'State': new_state,
        'Feedback_Notes': notes,
        'Last_Updated': now,
        'Updated_By': user
    }

def update_feedback_domain(feedback_id: str, new_domain: str, user: str) -> Dict[str, Any]:
    """
    Create a domain update record for a feedback item.
    """
    now = datetime.now().isoformat()
    
    return {
        'Feedback_ID': feedback_id,
        'Primary_Domain': new_domain,
        'Last_Updated': now,
        'Updated_By': user
    }

def format_state_for_display(state: str) -> Dict[str, str]:
    """Format state information for UI display"""
    state_info = get_state_info(state)
    if not state_info:
        return {'name': state, 'color': '#6c757d'}
    
    return {
        'name': state_info['name'],
        'color': state_info['color'],
        'description': state_info.get('description', '')
    }

def get_stored_feedback_ids() -> List[str]:
    """
    Get all Feedback_IDs that are stored in the Fabric SQL database.
    Returns a list of Feedback_IDs that actually exist in the database.
    """
    try:
        import fabric_sql_writer
        
        # Create SQL writer and get connection
        writer = fabric_sql_writer.FabricSQLWriter()
        conn = writer.connect_interactive()
        
        if not conn:
            logger.error("Could not establish SQL connection to check stored feedback IDs")
            return []
        
        cursor = conn.cursor()
        
        # Query to get all distinct Feedback_IDs from the database
        query = "SELECT DISTINCT Feedback_ID FROM Feedback WHERE Feedback_ID IS NOT NULL AND Feedback_ID != ''"
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Extract Feedback_IDs from results
        stored_ids = [row[0] for row in results if row[0]]
        
        logger.info(f"Found {len(stored_ids)} feedback items stored in Fabric SQL database")
        
        cursor.close()
        conn.close()
        
        return stored_ids
        
    except Exception as e:
        logger.error(f"Error querying stored feedback IDs from Fabric SQL: {e}")
        return []

def get_all_feedback_states() -> Dict[str, Dict[str, Any]]:
    """
    Get all feedback states from the FeedbackState table.
    Returns a dictionary mapping feedback_id to state data.
    """
    try:
        import fabric_sql_writer
        
        # Create SQL writer and get connection
        writer = fabric_sql_writer.FabricSQLWriter()
        conn = writer.connect_interactive()
        
        if not conn:
            logger.error("Could not establish SQL connection to get feedback states")
            return {}
        
        cursor = conn.cursor()
        
        # Query to get all state data from FeedbackState table with correct column names
        # Use COALESCE to fallback to Feedback.Primary_Domain if FeedbackState.Primary_Domain is NULL
        query = """
            SELECT 
                fs.Feedback_ID, 
                fs.State, 
                COALESCE(fs.Primary_Domain, f.Primary_Domain) as Primary_Domain,
                fs.Feedback_Notes, 
                fs.Last_Updated, 
                fs.Updated_By,
                COALESCE(fs.Category, f.Category) as Category,
                COALESCE(fs.Subcategory, f.Subcategory) as Subcategory,
                COALESCE(fs.Feature_Area, f.Feature_Area) as Feature_Area
            FROM FeedbackState fs
            LEFT JOIN Feedback f ON fs.Feedback_ID = f.Feedback_ID
            WHERE fs.Feedback_ID IS NOT NULL AND fs.Feedback_ID != ''
            ORDER BY fs.Last_Updated DESC
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Convert to dictionary for easy lookup
        state_data = {}
        for row in results:
            feedback_id = row[0]
            state_data[feedback_id] = {
                'state': row[1],
                'domain': row[2],  # Primary_Domain
                'notes': row[3],   # Feedback_Notes
                'last_updated': row[4].isoformat() if row[4] else None,
                'updated_by': row[5],
                'category': row[6],
                'subcategory': row[7],
                'feature_area': row[8]
            }
        
        logger.info(f"Loaded {len(state_data)} feedback states from FeedbackState table")
        
        cursor.close()
        conn.close()
        
        return state_data
        
    except Exception as e:
        logger.error(f"Error querying feedback states from Fabric SQL: {e}")
        return {}

def update_feedback_field_in_sql(feedback_id: str, field_name: str, new_value: str, bearer_token: str) -> bool:
    """
    Update a specific field for a feedback item directly in Fabric SQL database.
    
    Args:
        feedback_id: The Feedback_ID to update
        field_name: The field name to update (e.g., 'Primary_Domain', 'Audience')
        new_value: The new value for the field
        bearer_token: Fabric bearer token for authentication
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        import fabric_sql_writer
        
        # Create SQL writer and get connection
        writer = fabric_sql_writer.FabricSQLWriter()
        conn = writer.connect_interactive()
        
        if not conn:
            logger.error(f"Could not establish SQL connection to update {field_name}")
            return False
        
        cursor = conn.cursor()
        
        # Validate field name to prevent SQL injection
        allowed_fields = ['Primary_Domain', 'Audience', 'State', 'Feedback_Notes', 'Category', 'Subcategory', 'Feature_Area']
        if field_name not in allowed_fields:
            logger.error(f"Field {field_name} not allowed for updates")
            return False
        
        # Update the specific field in the appropriate table
        now = datetime.now().isoformat()
        
        # For Primary_Domain and Category fields, we need to update BOTH tables:
        # 1. Feedback table (for data integrity and original categorization)
        # 2. FeedbackState table (for UI display and audit trail)
        if field_name in ['Primary_Domain', 'Category', 'Subcategory', 'Feature_Area']:
            # Update main Feedback table
            feedback_query = f"UPDATE Feedback SET {field_name} = ? WHERE Feedback_ID = ?"
            cursor.execute(feedback_query, [new_value, feedback_id])
            feedback_rows_updated = cursor.rowcount
            
            # Update or insert into FeedbackState table for audit trail and UI
            state_update_query = f"UPDATE FeedbackState SET {field_name} = ?, Last_Updated = ?, Updated_By = ? WHERE Feedback_ID = ?"
            cursor.execute(state_update_query, [new_value, now, 'user', feedback_id])
            
            # If no rows were affected in FeedbackState, insert a new record
            if cursor.rowcount == 0:
                state_insert_query = f"""
                    INSERT INTO FeedbackState (Feedback_ID, {field_name}, Last_Updated, Updated_By)
                    VALUES (?, ?, ?, ?)
                """
                cursor.execute(state_insert_query, [feedback_id, new_value, now, 'user'])
                
            logger.info(f"✅ Updated {field_name} in both Feedback table ({feedback_rows_updated} rows) and FeedbackState table")
            
        elif field_name == 'Audience':
            # Audience only goes to main Feedback table (no audit trail needed)
            query = f"UPDATE Feedback SET {field_name} = ? WHERE Feedback_ID = ?"
            cursor.execute(query, [new_value, feedback_id])
        else:
            # State management fields (State, Feedback_Notes) go to FeedbackState table only
            update_query = f"UPDATE FeedbackState SET {field_name} = ?, Last_Updated = ?, Updated_By = ? WHERE Feedback_ID = ?"
            cursor.execute(update_query, [new_value, now, 'user', feedback_id])
            
            # If no rows were affected, insert a new record for state fields
            if cursor.rowcount == 0:
                insert_query = f"""
                    INSERT INTO FeedbackState (Feedback_ID, {field_name}, Last_Updated, Updated_By)
                    VALUES (?, ?, ?, ?)
                """
                cursor.execute(insert_query, [feedback_id, new_value, now, 'user'])
        
        # Check if any rows were affected
        if cursor.rowcount > 0:
            conn.commit()
            logger.info(f"✅ Successfully updated {field_name} to '{new_value}' for feedback {feedback_id}")
            cursor.close()
            conn.close()
            return True
        else:
            logger.warning(f"⚠️ No rows updated - feedback {feedback_id} not found in database")
            cursor.close()
            conn.close()
            return False
        
    except Exception as e:
        logger.error(f"Error updating {field_name} for feedback {feedback_id}: {e}", exc_info=True)
        try:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        except:
            pass
        return False

def update_feedback_state_in_sql(feedback_id: str, new_state: str, bearer_token: str) -> bool:
    """
    Update feedback state directly in Fabric SQL database.
    
    Args:
        feedback_id: The Feedback_ID to update
        new_state: The new state value
        bearer_token: Fabric bearer token for authentication
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    if not validate_state(new_state):
        logger.error(f"Invalid state: {new_state}")
        return False
        
    return update_feedback_field_in_sql(feedback_id, 'State', new_state, bearer_token)


def update_feedback_category_in_sql(
    feedback_id: str,
    category_name: Optional[str],
    subcategory_name: Optional[str],
    feature_area: Optional[str],
    domain_code: Optional[str] = None,
) -> bool:
    """Update enhanced category metadata for a feedback item."""
    try:
        import fabric_sql_writer
        from datetime import datetime

        writer = fabric_sql_writer.FabricSQLWriter()
        conn = writer.connect_interactive()

        if not conn:
            logger.error("Could not establish SQL connection to update category metadata")
            return False

        cursor = conn.cursor()
        now = datetime.now().isoformat()

        # 1. Update Feedback table
        updates = ["User_Modified_Categorization = 1"]
        params = []

        # Update both Category and Enhanced_Category to keep them in sync
        updates.append("Enhanced_Category = ?")
        params.append(category_name.strip() if category_name and category_name.strip() else None)
        
        updates.append("Category = ?")
        params.append(category_name.strip() if category_name and category_name.strip() else None)

        updates.append("Subcategory = ?")
        params.append(subcategory_name.strip() if subcategory_name and subcategory_name.strip() else None)

        updates.append("Feature_Area = ?")
        params.append(feature_area.strip() if feature_area and feature_area.strip() else None)

        if domain_code is not None:
            updates.append("Primary_Domain = ?")
            params.append(domain_code.strip() if domain_code and domain_code.strip() else None)

        update_sql = f"UPDATE Feedback SET {', '.join(updates)} WHERE Feedback_ID = ?"
        params.append(feedback_id)

        cursor.execute(update_sql, params)
        feedback_rows = cursor.rowcount
        
        # 2. Update FeedbackState table (for UI consistency and audit)
        # Check if record exists in FeedbackState
        cursor.execute("SELECT COUNT(*) FROM FeedbackState WHERE Feedback_ID = ?", [feedback_id])
        exists = cursor.fetchone()[0] > 0
        
        state_params = []
        if exists:
            state_updates = ["Last_Updated = ?", "Updated_By = ?"]
            state_params.extend([now, 'user'])
            
            state_updates.append("Category = ?")
            state_params.append(category_name.strip() if category_name and category_name.strip() else None)
            
            state_updates.append("Subcategory = ?")
            state_params.append(subcategory_name.strip() if subcategory_name and subcategory_name.strip() else None)
            
            state_updates.append("Feature_Area = ?")
            state_params.append(feature_area.strip() if feature_area and feature_area.strip() else None)
            
            if domain_code is not None:
                state_updates.append("Primary_Domain = ?")
                state_params.append(domain_code.strip() if domain_code and domain_code.strip() else None)
                
            state_params.append(feedback_id)
            
            state_sql = f"UPDATE FeedbackState SET {', '.join(state_updates)} WHERE Feedback_ID = ?"
            cursor.execute(state_sql, state_params)
            state_rows = cursor.rowcount
        else:
            # Insert new record
            cols = ["Feedback_ID", "Last_Updated", "Updated_By", "Category", "Subcategory", "Feature_Area"]
            vals = ["?", "?", "?", "?", "?", "?"]
            state_params = [feedback_id, now, 'user', 
                           category_name.strip() if category_name and category_name.strip() else None,
                           subcategory_name.strip() if subcategory_name and subcategory_name.strip() else None,
                           feature_area.strip() if feature_area and feature_area.strip() else None]
            
            if domain_code is not None:
                cols.append("Primary_Domain")
                vals.append("?")
                state_params.append(domain_code.strip() if domain_code and domain_code.strip() else None)
                
            state_sql = f"INSERT INTO FeedbackState ({', '.join(cols)}) VALUES ({', '.join(vals)})"
            cursor.execute(state_sql, state_params)
            state_rows = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        if feedback_rows > 0 or state_rows > 0:
            logger.info(
                "✅ Updated category metadata for %s in Feedback (%d rows) and FeedbackState (%d rows)",
                feedback_id, feedback_rows, state_rows
            )
            return True

        logger.warning("No rows updated while changing category metadata for %s", feedback_id)
        return False

    except Exception as e:
        logger.error(f"Error updating category metadata for feedback {feedback_id}: {e}")
        try:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        except Exception:
            pass
        return False