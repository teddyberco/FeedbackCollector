"""
Fabric SQL Database Writer for feedback state management
Uses direct SQL operations instead of complex PySpark/Lakehouse operations
Much more reliable and faster than the lakehouse approach
"""

import pyodbc
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Any
from config import FABRIC_SQL_SERVER, FABRIC_SQL_DATABASE, FABRIC_SQL_AUTHENTICATION

logger = logging.getLogger(__name__)

class FabricSQLWriter:
    """Handles writing feedback state changes to Fabric SQL Database"""
    
    def __init__(self, bearer_token: str = None):
        self.bearer_token = bearer_token
        self.server = FABRIC_SQL_SERVER
        self.database = FABRIC_SQL_DATABASE
        self.auth_method = FABRIC_SQL_AUTHENTICATION
        self.current_user = None  # Will be set after connection
        
        # Validate that required configuration is present
        if not self.server or not self.database:
            raise ValueError("FABRIC_SQL_SERVER and FABRIC_SQL_DATABASE must be configured in .env file")
    
    def connect_interactive(self):
        """Connect using interactive Azure AD authentication (for development)"""
        
        # Try multiple driver names in order of preference
        drivers_to_try = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server"
        ]
        
        for driver_name in drivers_to_try:
            try:
                logger.info(f"Trying to connect with driver: {driver_name}")
                
                if driver_name == "SQL Server":
                    # Older driver doesn't support Azure AD Interactive, try different approach
                    connection_string = f"""
                    DRIVER={{{driver_name}}};
                    SERVER={self.server};
                    DATABASE={self.database};
                    Encrypt=yes;
                    TrustServerCertificate=no;
                    Integrated Security=SSPI;
                    """
                else:
                    # Modern drivers support Azure AD Interactive
                    connection_string = f"""
                    DRIVER={{{driver_name}}};
                    SERVER={self.server};
                    DATABASE={self.database};
                    Encrypt=yes;
                    TrustServerCertificate=no;
                    Authentication=ActiveDirectoryInteractive;
                    """
                
                conn = pyodbc.connect(connection_string)
                logger.info(f"Successfully connected to Fabric SQL database using driver: {driver_name}")
                return conn
                
            except Exception as e:
                logger.warning(f"Driver {driver_name} failed: {e}")
                continue
        
        # If all drivers failed
        raise Exception(f"Failed to connect with any available driver. Available drivers: {pyodbc.drivers()}")
    
    def connect_with_token(self, bearer_token: str):
        """Connect using bearer token (for production)"""
        
        # Try multiple driver names in order of preference
        drivers_to_try = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server Native Client 11.0"
        ]
        
        for driver_name in drivers_to_try:
            try:
                logger.info(f"Trying to connect with bearer token using driver: {driver_name}")
                
                connection_string = f"""
                DRIVER={{{driver_name}}};
                SERVER={self.server};
                DATABASE={self.database};
                Encrypt=yes;
                TrustServerCertificate=no;
                """
                
                # Convert bearer token to bytes for ODBC
                token_bytes = bearer_token.encode('utf-16-le')
                
                # Use token for authentication (SQL_COPT_SS_ACCESS_TOKEN = 1256)
                conn = pyodbc.connect(connection_string, attrs_before={1256: token_bytes})
                logger.info(f"Successfully connected to Fabric SQL database using bearer token with driver: {driver_name}")
                return conn
                
            except Exception as e:
                logger.warning(f"Bearer token connection with driver {driver_name} failed: {e}")
                continue
        
        # If all drivers failed
        raise Exception(f"Failed to connect with bearer token using any available driver. Available drivers: {pyodbc.drivers()}")
    
    def ensure_feedback_state_table(self, conn):
        """Create FeedbackState table if it doesn't exist"""
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'FeedbackState'
        """)
        
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            logger.info("Creating FeedbackState table...")
            
            create_table_sql = """
            CREATE TABLE FeedbackState (
                Feedback_ID NVARCHAR(50) PRIMARY KEY,
                State NVARCHAR(20),
                Feedback_Notes NTEXT,
                Primary_Domain NVARCHAR(100),
                Last_Updated DATETIME2 DEFAULT GETDATE(),
                Updated_By NVARCHAR(100)
            );
            """
            
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("FeedbackState table created successfully")
        else:
            logger.info("FeedbackState table already exists")
    
    def get_current_user(self, conn):
        """Get the current authenticated user from SQL connection"""
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT SUSER_NAME()")
            result = cursor.fetchone()
            if result:
                user = result[0]
                self.current_user = user
                logger.info(f"Current SQL user: {user}")
                return user
            else:
                self.current_user = "unknown_user"
                return "unknown_user"
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            self.current_user = "unknown_user"
            return "unknown_user"
    
    def ensure_feedback_table(self, conn):
        """Create main Feedback table if it doesn't exist, or migrate existing table"""
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'Feedback'
        """)
        
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            logger.info("Creating new Feedback table with all columns...")
            
            create_table_sql = """
            CREATE TABLE Feedback (
                Feedback_ID NVARCHAR(50) PRIMARY KEY,
                Title NVARCHAR(500),
                Content NTEXT,
                Source NVARCHAR(50),
                Source_URL NVARCHAR(1000),
                Author NVARCHAR(100),
                Created_Date DATETIME2,
                Sentiment NVARCHAR(20),
                Primary_Category NVARCHAR(100),
                Enhanced_Category NVARCHAR(200),
                Audience NVARCHAR(50),
                Priority NVARCHAR(20),
                -- Additional fields from collectors
                Feedback_Gist NVARCHAR(1000),
                Area NVARCHAR(100),
                Impacttype NVARCHAR(100),
                Scenario NVARCHAR(50),
                Tag NVARCHAR(200),
                Organization NVARCHAR(200),
                Status NVARCHAR(50),
                Created_by NVARCHAR(100),
                Rawfeedback NTEXT,
                Category NVARCHAR(100),
                Subcategory NVARCHAR(200),
                Feature_Area NVARCHAR(200),
                Categorization_Confidence FLOAT,
                Primary_Domain NVARCHAR(100),
                Domains NTEXT, -- Store as JSON string
                Collected_Date DATETIME2 DEFAULT GETDATE(),
                CONSTRAINT UK_Feedback_ID UNIQUE (Feedback_ID)
            );
            """
            
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("✅ New Feedback table created successfully with all columns")
        else:
            logger.info("Feedback table exists - checking for missing columns...")
            self.migrate_feedback_table(conn)
    
    def migrate_feedback_table(self, conn):
        """Add missing columns to existing Feedback table"""
        cursor = conn.cursor()
        
        # List of new columns to add
        new_columns = [
            "Feedback_Gist NVARCHAR(1000)",
            "Area NVARCHAR(100)",
            "Impacttype NVARCHAR(100)",
            "Scenario NVARCHAR(50)",
            "Tag NVARCHAR(200)",
            "Organization NVARCHAR(200)",
            "Status NVARCHAR(50)",
            "Created_by NVARCHAR(100)",
            "Rawfeedback NTEXT",
            "Category NVARCHAR(100)",
            "Subcategory NVARCHAR(200)",
            "Feature_Area NVARCHAR(200)",
            "Categorization_Confidence FLOAT",
            "Primary_Domain NVARCHAR(100)",
            "Domains NTEXT"
        ]
        
        for column_def in new_columns:
            column_name = column_def.split()[0]
            try:
                # Check if column exists
                cursor.execute("""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'Feedback' AND COLUMN_NAME = ?
                """, [column_name])
                
                column_exists = cursor.fetchone()[0] > 0
                
                if not column_exists:
                    # Add the missing column
                    alter_sql = f"ALTER TABLE Feedback ADD {column_def}"
                    cursor.execute(alter_sql)
                    conn.commit()
                    logger.info(f"✅ Added missing column: {column_name}")
                else:
                    logger.debug(f"Column {column_name} already exists")
                    
            except Exception as e:
                logger.error(f"❌ Error adding column {column_name}: {e}")
        
        # Update ISV/Platform to Developer in existing data
        try:
            cursor.execute("UPDATE Feedback SET Audience = 'Developer' WHERE Audience IN ('ISV', 'Platform')")
            updated_rows = cursor.rowcount
            if updated_rows > 0:
                conn.commit()
                logger.info(f"✅ Updated {updated_rows} rows: ISV/Platform → Developer")
        except Exception as e:
            logger.error(f"❌ Error updating audience values: {e}")
        
        logger.info("🔄 Feedback table migration completed")
    
    def load_feedback_states(self):
        """Load state data from FeedbackState table for server-side filtering"""
        try:
            conn = self.create_connection()
            if not conn:
                logger.error("❌ Cannot load feedback states - no database connection")
                return {}
            
            cursor = conn.cursor()
            
            # Query to get all state data
            query = """
                SELECT feedback_id, state, domain, notes, last_updated, updated_by
                FROM FeedbackState
                ORDER BY last_updated DESC
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Convert to dictionary for easy lookup
            state_data = {}
            for row in rows:
                feedback_id = row[0]
                state_data[feedback_id] = {
                    'state': row[1],
                    'domain': row[2],
                    'notes': row[3],
                    'last_updated': row[4].isoformat() if row[4] else None,
                    'updated_by': row[5]
                }
            
            cursor.close()
            conn.close()
            
            logger.info(f"📊 Loaded {len(state_data)} state records from FeedbackState table")
            return state_data
            
        except Exception as e:
            logger.error(f"❌ Error loading feedback states: {e}")
            return {}
    
    def write_feedback_bulk(self, feedback_data: List[Dict[str, Any]], use_token: bool = True) -> Dict[str, int]:
        """
        Bulletproof bulk write with deterministic IDs and true duplicate prevention
        
        Args:
            feedback_data: List of feedback dictionaries from cache
            use_token: Whether to use bearer token (True) or interactive auth (False)
            
        Returns:
            dict: {'new_items': X, 'existing_items': Y, 'total_items': Z, 'id_regenerated': W}
        """
        if not feedback_data:
            logger.info("No feedback data to write")
            return {'new_items': 0, 'existing_items': 0, 'total_items': 0, 'id_regenerated': 0}
        
        try:
            # Import deterministic ID generator
            from id_generator import FeedbackIDGenerator
            
            logger.info(f"🔄 Bulletproof sync: Processing {len(feedback_data)} feedback items")
            
            # Connect to database
            conn = None
            if use_token and self.bearer_token:
                try:
                    conn = self.connect_with_token(self.bearer_token)
                except Exception as token_error:
                    logger.warning(f"Bearer token authentication failed: {token_error}")
                    logger.info("Falling back to interactive authentication...")
                    conn = self.connect_interactive()
            else:
                conn = self.connect_interactive()
            
            # Get current user for proper attribution
            current_user = self.get_current_user(conn)
            
            # Ensure table exists
            self.ensure_feedback_table(conn)
            
            cursor = conn.cursor()
            
            # Get ALL existing feedback (ID, Title, Content hash) for comprehensive duplicate checking
            cursor.execute("""
                SELECT Feedback_ID, Title, Content
                FROM Feedback
            """)
            
            existing_items_db = {}
            existing_content_hashes = set()
            
            for row in cursor.fetchall():
                existing_items_db[row[0]] = {'title': row[1], 'content': row[2]}
                # Create content signature for duplicate detection - handle float/NaN values
                title_safe = str(row[1]) if row[1] is not None and not (isinstance(row[1], float) and pd.isna(row[1])) else ""
                content_safe = str(row[2]) if row[2] is not None and not (isinstance(row[2], float) and pd.isna(row[2])) else ""
                content_sig = f"{title_safe.lower().strip()}|{content_safe[:200].lower().strip()}"
                existing_content_hashes.add(content_sig)
            
            logger.info(f"📊 Found {len(existing_items_db)} existing items in database")
            
            # Process each feedback item
            new_items = 0
            existing_items = 0
            id_regenerated = 0
            
            for feedback in feedback_data:
                try:
                    # Generate deterministic ID based on content
                    deterministic_id = FeedbackIDGenerator.generate_id_from_feedback_dict(feedback)
                    original_id = feedback.get('Feedback_ID') or feedback.get('id', '')
                    
                    if deterministic_id != original_id:
                        id_regenerated += 1
                        logger.info(f"🔄 ID regenerated: {original_id} → {deterministic_id}")
                    
                    # Update feedback with deterministic ID
                    feedback['Feedback_ID'] = deterministic_id
                    
                    # Check for duplicates by ID
                    if deterministic_id in existing_items_db:
                        existing_items += 1
                        logger.debug(f"✅ Item already exists by ID: {deterministic_id}")
                        continue
                    
                    # Check for duplicates by content using proper field mapping - handle float/NaN values
                    title_raw = feedback.get('Title') or feedback.get('Feedback_Gist') or feedback.get('Feedback', '')
                    content_raw = feedback.get('Content') or feedback.get('Feedback') or ''
                    
                    # Safely handle potential float/NaN values
                    title = str(title_raw)[:100] if title_raw is not None and not (isinstance(title_raw, float) and pd.isna(title_raw)) else ""
                    content = str(content_raw) if content_raw is not None and not (isinstance(content_raw, float) and pd.isna(content_raw)) else ""
                    
                    content_sig = f"{title.lower().strip()}|{content[:200].lower().strip()}"
                    
                    if content_sig in existing_content_hashes:
                        existing_items += 1
                        logger.debug(f"✅ Item already exists by content: {title[:50]}...")
                        continue
                    
                    # Extract all fields for new item with proper field mapping
                    source = feedback.get('Source') or feedback.get('Sources', '')
                    source_url = feedback.get('Source_URL') or feedback.get('Url', '')
                    author = feedback.get('Author') or feedback.get('Customer', '')
                    created_date = feedback.get('Created_Date') or feedback.get('Created')
                    sentiment = feedback.get('Sentiment', '')
                    primary_category = feedback.get('Primary_Category') or feedback.get('Category', '')
                    enhanced_category = feedback.get('Enhanced_Category', '')
                    audience = feedback.get('Audience', '')
                    priority = feedback.get('Priority', '')
                    
                    # New fields from collectors
                    feedback_gist = feedback.get('Feedback_Gist', '')
                    area = feedback.get('Area', '')
                    impacttype = feedback.get('Impacttype', '')
                    scenario = feedback.get('Scenario', '')
                    tag = feedback.get('Tag', '')
                    organization = feedback.get('Organization', '')
                    status = feedback.get('Status', '')
                    created_by = feedback.get('Created_by', '')
                    rawfeedback = feedback.get('Rawfeedback', '')
                    category = feedback.get('Category', '')
                    subcategory = feedback.get('Subcategory', '')
                    feature_area = feedback.get('Feature_Area', '')
                    categorization_confidence = feedback.get('Categorization_Confidence', 0.0)
                    primary_domain = feedback.get('Primary_Domain', '')
                    domains = str(feedback.get('Domains', [])) if feedback.get('Domains') else ''
                    
                    # Map ISV/Platform to Developer for audience standardization
                    if audience in ['ISV', 'Platform']:
                        audience = 'Developer'
                    elif audience not in ['Developer', 'Customer']:
                        audience = 'Customer'  # Default fallback
                    
                    # Convert date if needed
                    if isinstance(created_date, str):
                        try:
                            from datetime import datetime
                            created_date = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                        except:
                            created_date = None
                    
                    # Insert new record with all fields
                    cursor.execute("""
                        INSERT INTO Feedback (
                            Feedback_ID, Title, Content, Source, Source_URL, Author,
                            Created_Date, Sentiment, Primary_Category, Enhanced_Category,
                            Audience, Priority, Feedback_Gist, Area, Impacttype, Scenario,
                            Tag, Organization, Status, Created_by, Rawfeedback, Category,
                            Subcategory, Feature_Area, Categorization_Confidence, Primary_Domain, Domains
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        deterministic_id, title, content, source, source_url, author,
                        created_date, sentiment, primary_category, enhanced_category,
                        audience, priority, feedback_gist, area, impacttype, scenario,
                        tag, organization, status, created_by, rawfeedback, category,
                        subcategory, feature_area, categorization_confidence, primary_domain, domains
                    ])
                    
                    # Add to existing sets to prevent duplicates within this batch
                    existing_items_db[deterministic_id] = {'title': title, 'content': content}
                    existing_content_hashes.add(content_sig)
                    
                    new_items += 1
                    logger.debug(f"📝 Added new item: {deterministic_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing feedback: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            result = {
                'new_items': new_items,
                'existing_items': existing_items,
                'total_items': len(feedback_data),
                'id_regenerated': id_regenerated
            }
            
            logger.info(f"✅ Bulletproof sync complete: {new_items} new, {existing_items} existing, {id_regenerated} IDs regenerated")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in bulletproof sync: {e}")
            return {'new_items': 0, 'existing_items': 0, 'total_items': len(feedback_data), 'id_regenerated': 0}
    
    def update_feedback_states(self, state_changes: List[Dict[str, Any]], use_token: bool = True) -> bool:
        """
        Update feedback states in Fabric SQL database
        
        Args:
            state_changes: List of state change dictionaries
            use_token: Whether to use bearer token (True) or interactive auth (False)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not state_changes:
            logger.info("No state changes to update")
            return True
        
        try:
            logger.info(f"Updating {len(state_changes)} feedback states in Fabric SQL database")
            
            # Try bearer token first, then fallback to interactive
            conn = None
            if use_token and self.bearer_token:
                try:
                    conn = self.connect_with_token(self.bearer_token)
                except Exception as token_error:
                    logger.warning(f"Bearer token authentication failed: {token_error}")
                    logger.info("Falling back to interactive authentication...")
                    conn = self.connect_interactive()
            else:
                conn = self.connect_interactive()
            
            # Ensure table exists
            self.ensure_feedback_state_table(conn)
            
            cursor = conn.cursor()
            
            # Process each state change
            updated_count = 0
            for change in state_changes:
                feedback_id = change.get('feedback_id')
                if not feedback_id:
                    logger.warning(f"Skipping change without feedback_id: {change}")
                    continue
                
                logger.info(f"Processing state change for feedback_id: {feedback_id}")
                
                # Check if record exists
                cursor.execute("SELECT COUNT(*) FROM FeedbackState WHERE Feedback_ID = ?", [feedback_id])
                exists = cursor.fetchone()[0] > 0
                
                if exists:
                    # Update existing record
                    update_sql = """
                    UPDATE FeedbackState 
                    SET State = COALESCE(?, State),
                        Feedback_Notes = COALESCE(?, Feedback_Notes),
                        Primary_Domain = COALESCE(?, Primary_Domain),
                        Updated_By = COALESCE(?, Updated_By),
                        Last_Updated = GETDATE()
                    WHERE Feedback_ID = ?
                    """
                    
                    cursor.execute(update_sql, [
                        change.get('state'),
                        change.get('notes'),
                        change.get('domain'),
                        self.current_user or change.get('updated_by') or 'unknown_user',
                        feedback_id
                    ])
                    
                    logger.info(f"Updated existing record for feedback_id: {feedback_id}")
                    
                else:
                    # Insert new record
                    insert_sql = """
                    INSERT INTO FeedbackState (Feedback_ID, State, Feedback_Notes, Primary_Domain, Updated_By, Last_Updated)
                    VALUES (?, ?, ?, ?, ?, GETDATE())
                    """
                    
                    cursor.execute(insert_sql, [
                        feedback_id,
                        change.get('state', 'NEW'),
                        change.get('notes'),
                        change.get('domain'),
                        self.current_user or change.get('updated_by') or 'unknown_user'
                    ])
                    
                    logger.info(f"Inserted new record for feedback_id: {feedback_id}")
                
                updated_count += 1
            
            # Commit all changes
            conn.commit()
            conn.close()
            
            logger.info(f"Successfully updated {updated_count} feedback states in Fabric SQL database")
            return True
            
        except Exception as e:
            logger.error(f"Error updating feedback states in Fabric SQL database: {e}")
            return False
    
    def get_feedback_state(self, feedback_id: str, use_token: bool = True) -> Dict[str, Any]:
        """Get current state of a feedback item from SQL database"""
        try:
            # Connect to database
            if use_token and self.bearer_token:
                conn = self.connect_with_token(self.bearer_token)
            else:
                conn = self.connect_interactive()
            
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT Feedback_ID, State, Feedback_Notes, Primary_Domain, Last_Updated, Updated_By
                FROM FeedbackState 
                WHERE Feedback_ID = ?
            """, [feedback_id])
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'feedback_id': row[0],
                    'state': row[1],
                    'notes': row[2],
                    'domain': row[3],
                    'last_updated': row[4],
                    'updated_by': row[5]
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting feedback state from SQL database: {e}")
            return None

def update_feedback_states_in_fabric_sql(bearer_token: str, state_changes: List[Dict[str, Any]]) -> bool:
    """
    Convenience function to update feedback states in Fabric SQL database
    This replaces the problematic lakehouse/PySpark approach
    
    Args:
        bearer_token: Fabric bearer token for authentication
        state_changes: List of state changes to apply
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Always try interactive authentication for now since bearer token has issues
        logger.info("Using interactive authentication for SQL database (bearer token method needs refinement)")
        writer = FabricSQLWriter()
        return writer.update_feedback_states(state_changes, use_token=False)
        
    except Exception as e:
        logger.error(f"Error in update_feedback_states_in_fabric_sql: {e}")
        
        # Check if it's ODBC driver issue
        if "Data source name not found" in str(e) or "ODBC Driver Manager" in str(e):
            logger.warning("ODBC Driver not available")
            return False  # Let the main app.py handle lakehouse fallback
        
        logger.error(f"SQL database authentication failed: {e}")
        return False

if __name__ == "__main__":
    # Test the SQL writer
    print("Testing Fabric SQL Writer...")
    
    test_changes = [
        {
            'feedback_id': 'test-123',
            'state': 'TRIAGED',
            'notes': 'Test feedback note',
            'domain': 'PowerBI',
            'updated_by': 'test-user'
        }
    ]
    
    success = update_feedback_states_in_fabric_sql(None, test_changes)
    if success:
        print("SUCCESS: Fabric SQL Writer test passed!")
    else:
        print("ERROR: Fabric SQL Writer test failed")