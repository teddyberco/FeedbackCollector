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
    """Handles writing feedback state changes to Fabric SQL Database.
    
    Supports dynamic database targeting via project configuration.
    If db_config is provided, it overrides the global env vars.
    """
    
    def __init__(self, bearer_token: str = None, db_config: Dict[str, str] = None):
        self.bearer_token = bearer_token
        self.current_user = None  # Will be set after connection
        
        if db_config:
            # Use project-specific database configuration
            self.server = db_config.get('server', '')
            self.database = db_config.get('database_name', '')
            self.auth_method = db_config.get('authentication', 'ActiveDirectoryInteractive')
            self.connection_string = db_config.get('connection_string', '')
        else:
            # Fallback to global env vars
            self.server = FABRIC_SQL_SERVER
            self.database = FABRIC_SQL_DATABASE
            self.auth_method = FABRIC_SQL_AUTHENTICATION
            self.connection_string = ''
        
        # Validate that required configuration is present
        if not self.connection_string and (not self.server or not self.database):
            raise ValueError(
                "Database connection not configured. Either provide a connection_string "
                "or set FABRIC_SQL_SERVER and FABRIC_SQL_DATABASE in .env / project config."
            )

    
    def connect_interactive(self):
        """Connect using interactive Azure AD authentication (for development)"""
        
        # If a full connection string is provided (e.g. from project config), use it directly
        if self.connection_string:
            try:
                logger.info(f"Connecting with project connection string to {self.database}")
                conn = pyodbc.connect(self.connection_string)
                logger.info(f"Successfully connected using project connection string")
                return conn
            except Exception as e:
                logger.warning(f"Direct connection string failed: {e}, falling back to driver iteration")
        
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
                Feedback_ID NVARCHAR(100) PRIMARY KEY,
                State NVARCHAR(20),
                Feedback_Notes NTEXT,
                Primary_Domain NVARCHAR(100),
                Category NVARCHAR(100),
                Subcategory NVARCHAR(200),
                Feature_Area NVARCHAR(200),
                Last_Updated DATETIME2 DEFAULT GETDATE(),
                Updated_By NVARCHAR(100)
            );
            """
            
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("FeedbackState table created successfully")
        else:
            logger.info("FeedbackState table already exists - checking for missing columns...")
            self.migrate_feedback_state_table(conn)

    def migrate_feedback_state_table(self, conn):
        """Add missing columns to existing FeedbackState table"""
        cursor = conn.cursor()
        
        # List of new columns to add
        new_columns = [
            "Category NVARCHAR(100)",
            "Subcategory NVARCHAR(200)",
            "Feature_Area NVARCHAR(200)"
        ]
        
        for column_def in new_columns:
            column_name = column_def.split()[0]
            try:
                # Check if column exists
                cursor.execute("""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'FeedbackState' AND COLUMN_NAME = ?
                """, [column_name])
                
                column_exists = cursor.fetchone()[0] > 0
                
                if not column_exists:
                    # Add the missing column
                    alter_sql = f"ALTER TABLE FeedbackState ADD {column_def}"
                    cursor.execute(alter_sql)
                    conn.commit()
                    logger.info(f"✅ Added missing column to FeedbackState: {column_name}")
                else:
                    logger.debug(f"Column {column_name} already exists in FeedbackState")
                    
            except Exception as e:
                logger.error(f"❌ Error adding column {column_name} to FeedbackState: {e}")
    
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
            logger.info("Creating new Feedback table with simplified schema (v2)...")
            
            create_table_sql = """
            CREATE TABLE Feedback (
                Feedback_ID NVARCHAR(100) PRIMARY KEY,
                Title NVARCHAR(500),
                Feedback_Gist NVARCHAR(1000),
                Feedback NTEXT,
                Source NVARCHAR(50),
                Url NVARCHAR(1000),
                Author NVARCHAR(100),
                Created_Date DATETIME2,
                Sentiment NVARCHAR(20),
                Impacttype NVARCHAR(100),
                Scenario NVARCHAR(50),
                Area NVARCHAR(100),
                Tag NVARCHAR(1000),
                Organization NVARCHAR(200),
                Category NVARCHAR(200),
                Subcategory NVARCHAR(200),
                Feature_Area NVARCHAR(200),
                Categorization_Confidence FLOAT,
                Audience NVARCHAR(50),
                Priority NVARCHAR(20),
                Primary_Domain NVARCHAR(100),
                Primary_Workload NVARCHAR(100),
                Matched_Keywords NTEXT,
                Rawfeedback NTEXT,
                Collected_Date DATETIME2 DEFAULT GETDATE()
            );
            """
            
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("✅ New Feedback table created successfully with all columns")
        else:
            logger.info("Feedback table exists - checking for missing columns...")
            self.migrate_feedback_table(conn)
    
    def migrate_feedback_table(self, conn):
        """Add missing columns to existing Feedback table (v2 schema)"""
        cursor = conn.cursor()
        
        # v2 schema columns - ensure these exist
        v2_columns = [
            "Feedback_Gist NVARCHAR(1000)",
            "Feedback NTEXT",
            "Url NVARCHAR(1000)",
            "Author NVARCHAR(100)",
            "Area NVARCHAR(100)",
            "Impacttype NVARCHAR(100)",
            "Scenario NVARCHAR(50)",
            "Tag NVARCHAR(1000)",
            "Organization NVARCHAR(200)",
            "Category NVARCHAR(200)",
            "Subcategory NVARCHAR(200)",
            "Feature_Area NVARCHAR(200)",
            "Categorization_Confidence FLOAT",
            "Audience NVARCHAR(50)",
            "Priority NVARCHAR(20)",
            "Primary_Domain NVARCHAR(100)",
            "Primary_Workload NVARCHAR(100)",
            "Matched_Keywords NTEXT",
            "Rawfeedback NTEXT",
        ]
        
        for column_def in v2_columns:
            column_name = column_def.split()[0]
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'Feedback' AND COLUMN_NAME = ?
                """, [column_name])
                
                column_exists = cursor.fetchone()[0] > 0
                
                if not column_exists:
                    alter_sql = f"ALTER TABLE Feedback ADD {column_def}"
                    cursor.execute(alter_sql)
                    conn.commit()
                    logger.info(f"✅ Added missing column: {column_name}")
                else:
                    logger.debug(f"Column {column_name} already exists")
                    
            except Exception as e:
                logger.error(f"❌ Error adding column {column_name}: {e}")
        
        # Migrate data from old column names to new names if old columns exist
        rename_map = [
            ('Content', 'Feedback'),
            ('Source_URL', 'Url'),
            ('Enhanced_Category', 'Category'),
        ]
        for old_col, new_col in rename_map:
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'Feedback' AND COLUMN_NAME = ?
                """, [old_col])
                old_exists = cursor.fetchone()[0] > 0
                if old_exists:
                    cursor.execute(f"""
                        UPDATE Feedback SET [{new_col}] = [{old_col}]
                        WHERE [{new_col}] IS NULL AND [{old_col}] IS NOT NULL
                    """)
                    if cursor.rowcount > 0:
                        conn.commit()
                        logger.info(f"✅ Migrated data: {old_col} → {new_col} ({cursor.rowcount} rows)")
            except Exception as e:
                logger.debug(f"Migration {old_col}→{new_col}: {e}")
        
        # Standardize audience values (legacy mode only — skip if project has custom audiences)
        import config as _cfg
        _active_proj = _cfg.get_active_project_id()
        _has_custom_audiences = False
        if _active_proj:
            try:
                import project_manager as _pm
                _proj = _pm.load_project(_active_proj)
                if _proj.get('audience_config', {}).get('audiences'):
                    _has_custom_audiences = True
            except Exception:
                pass
        
        if not _has_custom_audiences:
            try:
                cursor.execute("UPDATE Feedback SET Audience = 'Developer' WHERE Audience IN ('ISV', 'Platform')")
                updated_rows = cursor.rowcount
                if updated_rows > 0:
                    conn.commit()
                    logger.info(f"✅ Updated {updated_rows} rows: ISV/Platform → Developer")
            except Exception as e:
                logger.error(f"❌ Error updating audience values: {e}")
        
        logger.info("🔄 Feedback table migration completed (v2)")
    
    def load_feedback_states(self):
        """Load state data from FeedbackState table for server-side filtering"""
        try:
            # Connect to database using same pattern as other methods
            conn = None
            if self.bearer_token:
                try:
                    conn = self.connect_with_token(self.bearer_token)
                except Exception as token_error:
                    logger.warning(f"Bearer token authentication failed: {token_error}")
                    logger.info("Falling back to interactive authentication...")
                    conn = self.connect_interactive()
            else:
                conn = self.connect_interactive()
            
            if not conn:
                logger.error("❌ Cannot load feedback states - no database connection")
                return {}
            
            cursor = conn.cursor()
            
            # Query to get all state data with correct column names
            # Use COALESCE to fallback to Feedback.Primary_Domain if FeedbackState.Primary_Domain is NULL
            query = """
                SELECT 
                    fs.Feedback_ID, 
                    fs.State, 
                    COALESCE(fs.Primary_Domain, f.Primary_Domain) as Primary_Domain,
                    fs.Feedback_Notes, 
                    fs.Last_Updated, 
                    fs.Updated_By
                FROM FeedbackState fs
                LEFT JOIN Feedback f ON fs.Feedback_ID = f.Feedback_ID
                ORDER BY fs.Last_Updated DESC
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
            
            # Get ALL existing feedback (ID, Title, Feedback hash) for comprehensive duplicate checking
            # Try new schema column name first, fall back to old 'Content' column
            try:
                cursor.execute("""
                    SELECT Feedback_ID, Title, CAST(LEFT(CAST(Feedback AS NVARCHAR(MAX)), 200) AS NVARCHAR(200))
                    FROM Feedback
                """)
            except Exception:
                cursor.execute("""
                    SELECT Feedback_ID, Title, CAST(LEFT(CAST(Content AS NVARCHAR(MAX)), 200) AS NVARCHAR(200))
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
            
            # Collect new items for bulk insert
            new_items_params = []
            
            # Source-based ID prefixes that indicate a stable source ID
            SOURCE_ID_PREFIXES = ('reddit-', 'community-', 'ghissue-', 'ghdisc-', 'ado-')
            
            for feedback in feedback_data:
                try:
                    # Use source-based ID if present, otherwise generate content-hash fallback
                    original_id = feedback.get('Feedback_ID') or feedback.get('id', '')
                    
                    if original_id and original_id.startswith(SOURCE_ID_PREFIXES):
                        # Source-based ID is stable - use it directly
                        deterministic_id = original_id
                    else:
                        # No source ID — generate deterministic content-hash ID
                        deterministic_id = FeedbackIDGenerator.generate_id_from_feedback_dict(feedback)
                        if deterministic_id != original_id:
                            id_regenerated += 1
                            logger.info(f"🔄 ID regenerated: {original_id} → {deterministic_id}")
                    
                    # Update feedback with the resolved ID
                    feedback['Feedback_ID'] = deterministic_id
                    
                    # Check for duplicates by ID - UPDATE if exists to add keywords
                    if deterministic_id in existing_items_db:
                        existing_items += 1
                        logger.debug(f"✅ Item already exists by ID: {deterministic_id} - checking for keyword updates")
                        
                        # Extract and serialize keywords for update
                        import json
                        matched_keywords_raw = feedback.get('Matched_Keywords', [])
                        if isinstance(matched_keywords_raw, list):
                            matched_keywords = json.dumps(matched_keywords_raw)
                        elif isinstance(matched_keywords_raw, str):
                            matched_keywords = matched_keywords_raw
                        else:
                            matched_keywords = '[]'
                        
                        # Update existing record with keywords if they're not empty
                        if matched_keywords and matched_keywords != '[]':
                            try:
                                cursor.execute("""
                                    UPDATE Feedback 
                                    SET Matched_Keywords = ?
                                    WHERE Feedback_ID = ?
                                    AND (Matched_Keywords IS NULL OR DATALENGTH(Matched_Keywords) = 0)
                                """, [matched_keywords, deterministic_id])
                                if cursor.rowcount > 0:
                                    logger.info(f"🔄 Updated keywords for existing item: {deterministic_id}")
                            except Exception as update_error:
                                logger.warning(f"⚠️ Could not update keywords for {deterministic_id}: {update_error}")
                        
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
                    
                    # Extract all fields for new item — v2 simplified schema
                    # Unified field mapping: accept both old CSV names and new SQL names
                    feedback_text = feedback.get('Feedback') or feedback.get('Content') or ''
                    source = feedback.get('Source') or feedback.get('Sources', '')
                    source_url = feedback.get('Url') or feedback.get('Source_URL', '')
                    author = feedback.get('Author') or feedback.get('Customer', '')
                    created_date = feedback.get('Created_Date') or feedback.get('Created')
                    sentiment = feedback.get('Sentiment', '')
                    impacttype = feedback.get('Impacttype', '')
                    scenario = feedback.get('Scenario', '')
                    area = feedback.get('Area', '')
                    tag = feedback.get('Tag', '')
                    organization = feedback.get('Organization', '')
                    # Category: prefer Enhanced_Category (more specific), fall back to Category
                    category = feedback.get('Enhanced_Category') or feedback.get('Category', '')
                    subcategory = feedback.get('Subcategory', '')
                    feature_area = feedback.get('Feature_Area', '')
                    categorization_confidence = feedback.get('Categorization_Confidence', 0.0)
                    audience = feedback.get('Audience', '')
                    priority = feedback.get('Priority', '')
                    feedback_gist = feedback.get('Feedback_Gist', '')
                    primary_domain = feedback.get('Primary_Domain', '')
                    primary_workload = feedback.get('Primary_Workload', '')
                    rawfeedback = feedback.get('Rawfeedback', '')
                    
                    # Serialize Matched_Keywords as JSON string
                    import json
                    matched_keywords_raw = feedback.get('Matched_Keywords', [])
                    if isinstance(matched_keywords_raw, list):
                        matched_keywords = json.dumps(matched_keywords_raw)
                    elif isinstance(matched_keywords_raw, str):
                        matched_keywords = matched_keywords_raw
                    else:
                        matched_keywords = '[]'
                    
                    # Standardize audience values based on project config
                    import config as _cfg
                    _audience_cfg = None
                    _active_proj = _cfg.get_active_project_id()
                    if _active_proj:
                        try:
                            import project_manager as _pm
                            _proj = _pm.load_project(_active_proj)
                            _audience_cfg = _proj.get('audience_config')
                        except Exception:
                            pass
                    
                    if _audience_cfg and 'audiences' in _audience_cfg:
                        # Project mode: allow project-defined audience labels
                        valid_audiences = list(_audience_cfg['audiences'].keys())
                        default_aud = _audience_cfg.get('default_audience', valid_audiences[0] if valid_audiences else 'User')
                        if audience not in valid_audiences:
                            audience = default_aud
                    else:
                        # Legacy mode: Developer/Customer/ISV
                        if audience in ['ISV', 'Platform']:
                            audience = 'Developer'
                        elif audience not in ['Developer', 'Customer']:
                            audience = 'Customer'
                    
                    # Convert date if needed
                    if isinstance(created_date, str):
                        try:
                            from datetime import datetime
                            created_date = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                        except:
                            created_date = None
                    
                    # Add to batch params — 24 columns (v2 schema)
                    new_items_params.append([
                        deterministic_id, title, feedback_gist, feedback_text,
                        source, source_url, author, created_date,
                        sentiment, impacttype, scenario, area, tag, organization,
                        category, subcategory, feature_area, categorization_confidence,
                        audience, priority,
                        primary_domain, primary_workload,
                        matched_keywords, rawfeedback
                    ])
                    
                    # Add to existing sets to prevent duplicates within this batch
                    existing_items_db[deterministic_id] = {'title': title, 'content': content}
                    existing_content_hashes.add(content_sig)
                    
                    new_items += 1
                    logger.debug(f"📝 Added new item to batch: {deterministic_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing feedback: {e}")
                    continue
            
            # Execute bulk insert if there are new items
            if new_items_params:
                logger.info(f"🚀 Executing bulk insert for {len(new_items_params)} items...")
                cursor.executemany("""
                    INSERT INTO Feedback (
                        Feedback_ID, Title, Feedback_Gist, Feedback,
                        Source, Url, Author, Created_Date,
                        Sentiment, Impacttype, Scenario, Area, Tag, Organization,
                        Category, Subcategory, Feature_Area, Categorization_Confidence,
                        Audience, Priority,
                        Primary_Domain, Primary_Workload,
                        Matched_Keywords, Rawfeedback
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, new_items_params)
                logger.info("✅ Bulk insert completed")
            
            conn.commit()
            
            # Sync domain updates from FeedbackState to Feedback table
            # This ensures that domain updates are not lost when the table is recreated
            if new_items > 0:
                logger.info("🔄 Syncing domain updates from FeedbackState to Feedback table...")
                synced_domains = self.sync_domains_from_state_to_feedback(conn)
                if synced_domains > 0:
                    conn.commit()
                    logger.info(f"✅ Domain sync complete: {synced_domains} records updated in Feedback table")
            
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
    
    # Alias for backward compatibility
    bulletproof_sync_with_deduplication = write_feedback_bulk
    
    def sync_domains_from_state_to_feedback(self, conn):
        """
        Sync domain updates from FeedbackState table to Feedback table
        This ensures that when the Feedback table is recreated, domain updates are not lost
        """
        try:
            cursor = conn.cursor()
            
            # Update Feedback table with domain values from FeedbackState where they exist
            update_query = """
            UPDATE f
            SET f.Primary_Domain = fs.Primary_Domain
            FROM Feedback f
            INNER JOIN FeedbackState fs ON f.Feedback_ID = fs.Feedback_ID
            WHERE fs.Primary_Domain IS NOT NULL 
            AND fs.Primary_Domain != ''
            AND (f.Primary_Domain IS NULL OR f.Primary_Domain != fs.Primary_Domain)
            """
            
            cursor.execute(update_query)
            updated_rows = cursor.rowcount
            
            if updated_rows > 0:
                logger.info(f"✅ Synced {updated_rows} domain updates from FeedbackState to Feedback table")
            else:
                logger.debug("No domain updates to sync from FeedbackState to Feedback table")
                
            cursor.close()
            return updated_rows
            
        except Exception as e:
            logger.error(f"❌ Error syncing domains from state to feedback: {e}")
            return 0
    
    def sync_domains_from_state(self, use_token: bool = True) -> int:
        """
        Manually sync domain updates from FeedbackState to Feedback table
        
        Args:
            use_token: Whether to use bearer token (True) or interactive auth (False)
            
        Returns:
            int: Number of records updated
        """
        try:
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
            
            if not conn:
                logger.error("❌ Cannot sync domains - no database connection")
                return 0
            
            # Ensure both tables exist
            self.ensure_feedback_table(conn)
            self.ensure_feedback_state_table(conn)
            
            # Sync domains
            updated_count = self.sync_domains_from_state_to_feedback(conn)
            
            if updated_count > 0:
                conn.commit()
                logger.info(f"✅ Domain sync complete: {updated_count} records updated")
            
            conn.close()
            return updated_count
            
        except Exception as e:
            logger.error(f"❌ Error in domain sync: {e}")
            return 0

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
                
                # Also update Primary_Domain in Feedback table if present to keep them in sync
                if change.get('domain'):
                    try:
                        cursor.execute("UPDATE Feedback SET Primary_Domain = ? WHERE Feedback_ID = ?", 
                                      [change.get('domain'), feedback_id])
                        logger.info(f"Synced Primary_Domain to Feedback table for feedback_id: {feedback_id}")
                    except Exception as e:
                        logger.warning(f"Failed to sync Primary_Domain to Feedback table: {e}")

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
    
    def recategorize_all_feedback(self, use_token: bool = True) -> Dict[str, int]:
        """
        Recategorize all feedback items using current category and impact type configurations.
        Only recategorizes items that have not been manually modified by users.
        
        Args:
            use_token: Whether to use bearer token (True) or interactive auth (False)
            
        Returns:
            dict: {'recategorized': X, 'skipped_user_modified': Y, 'total_processed': Z}
        """
        try:
            from utils import enhanced_categorize_feedback
            from datetime import datetime
            
            logger.info("🔄 Starting automatic recategorization of all feedback...")
            
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
            
            if not conn:
                logger.error("Failed to connect to database for recategorization")
                return {'recategorized': 0, 'skipped_user_modified': 0, 'total_processed': 0}
            
            cursor = conn.cursor()
            
            # Get all feedback for recategorization
            cursor.execute("""
                SELECT f.Feedback_ID, CAST(f.Feedback AS NVARCHAR(MAX)), f.Source, f.Scenario, f.Organization
                FROM Feedback f
                LEFT JOIN FeedbackState fs ON f.Feedback_ID = fs.Feedback_ID
                WHERE fs.Category IS NULL
            """)
            
            feedback_items = cursor.fetchall()
            total_items = len(feedback_items)
            recategorized_count = 0
            skipped_count = 0
            
            logger.info(f"📊 Found {total_items} feedback items to recategorize (skipping items with user-set categories in FeedbackState)")
            
            for row in feedback_items:
                try:
                    feedback_id = row[0]
                    content = row[1] or ""
                    source = row[2] or ""
                    scenario = row[3] or ""
                    organization = row[4] or ""
                    
                    # Recategorize
                    result = enhanced_categorize_feedback(content, source, scenario, organization)
                    
                    # Update the feedback with new categorization
                    cursor.execute("""
                        UPDATE Feedback
                        SET Category = ?,
                            Subcategory = ?,
                            Feature_Area = ?,
                            Audience = ?,
                            Priority = ?,
                            Impacttype = ?,
                            Categorization_Confidence = ?
                        WHERE Feedback_ID = ?
                    """, [
                        result.get('primary_category', 'Other'),
                        result.get('subcategory', 'Uncategorized'),
                        result.get('feature_area', 'General'),
                        result.get('audience', 'Customer'),
                        result.get('priority', 'medium'),
                        result.get('impact_type', 'FEEDBACK'),
                        result.get('confidence', 0.0),
                        feedback_id
                    ])
                    
                    recategorized_count += 1
                    
                    if recategorized_count % 100 == 0:
                        logger.info(f"Progress: {recategorized_count}/{total_items - skipped_count} items recategorized")
                    
                except Exception as e:
                    logger.error(f"❌ Error recategorizing item {feedback_id}: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            result = {
                'recategorized': recategorized_count,
                'skipped_user_modified': skipped_count,
                'total_processed': total_items
            }
            
            logger.info(f"✅ Recategorization complete: {recategorized_count} recategorized, {skipped_count} skipped (user-modified)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in recategorize_all_feedback: {e}")
            return {'recategorized': 0, 'skipped_user_modified': 0, 'total_processed': 0}

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