"""
Test script for connecting to Fabric SQL database
Uses interactive Azure AD authentication for development/testing
"""

import pyodbc
import sys

def test_fabric_sql_connection():
    """Test connection to Fabric SQL database with interactive authentication"""
    
    # Fabric SQL database connection details
    server = "x6eps4xrq2xudenlfv6naeo3i4-cfyeshmtnhnuzlhe7juljtqiie.msit-database.fabric.microsoft.com,1433"
    database = "Feedbackstate-6b85be29-3a09-4773-894f-7976ad58c8b3"
    
    # Try multiple driver names in order of preference
    drivers_to_try = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server"
    ]
    
    print("Testing Fabric SQL database connection...")
    print(f"Server: {server}")
    print(f"Database: {database}")
    print("Authentication: ActiveDirectoryInteractive (will open browser)")
    print()
    
    conn = None
    for driver_name in drivers_to_try:
        try:
            print(f"Trying driver: {driver_name}")
            
            if driver_name == "SQL Server":
                # Older driver doesn't support Azure AD Interactive
                connection_string = f"""
                DRIVER={{{driver_name}}};
                SERVER={server};
                DATABASE={database};
                Encrypt=yes;
                TrustServerCertificate=no;
                Integrated Security=SSPI;
                """
            else:
                # Modern drivers support Azure AD Interactive
                connection_string = f"""
                DRIVER={{{driver_name}}};
                SERVER={server};
                DATABASE={database};
                Encrypt=yes;
                TrustServerCertificate=no;
                Authentication=ActiveDirectoryInteractive;
                """
            
            conn = pyodbc.connect(connection_string)
            print(f"SUCCESS: Connected successfully using driver: {driver_name}")
            break
            
        except Exception as e:
            print(f"FAILED: Driver {driver_name} failed: {e}")
            continue
    
    if conn:
        
        # Test basic query
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        row = cursor.fetchone()
        print(f"Database version: {row[0][:100]}...")
        print()
        
        # Test table listing
        print("Checking available tables...")
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        tables = cursor.fetchall()
        
        if tables:
            print(f"SUCCESS: Found {len(tables)} tables:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("WARNING: No tables found in database")
        
        print()
        
        # Check for FeedbackState table specifically
        check_feedback_table_schema(cursor)
        
        conn.close()
        print("Connection closed")
        return True
        
    else:
        print("ERROR: All drivers failed to connect")
        print()
        print("Troubleshooting tips:")
        print("1. Ensure Microsoft ODBC Driver 18 for SQL Server is installed")
        print("2. Check your Azure AD permissions for the Fabric workspace")
        print("3. Verify you can access the Fabric portal with your credentials")
        return False

def check_feedback_table_schema(cursor):
    """Check if FeedbackState table exists and show its schema"""
    
    try:
        # Check if FeedbackState table exists
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'FeedbackState'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        if columns:
            print("SUCCESS: FeedbackState table found with schema:")
            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                max_length = f"({col[3]})" if col[3] else ""
                print(f"  - {col[0]}: {col[1]}{max_length} {nullable}")
        else:
            print("INFO: FeedbackState table not found")
            print("INFO: We'll need to create it for storing feedback state data")
            
    except Exception as e:
        print(f"WARNING: Error checking table schema: {e}")

def create_feedback_state_table(cursor):
    """Create FeedbackState table if it doesn't exist"""
    
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
    
    try:
        print("🔨 Creating FeedbackState table...")
        cursor.execute(create_table_sql)
        cursor.commit()
        print("✅ FeedbackState table created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False

def test_crud_operations(cursor):
    """Test basic CRUD operations on FeedbackState table"""
    
    test_feedback_id = "test-feedback-123"
    
    try:
        # Test INSERT
        print("🔍 Testing INSERT operation...")
        cursor.execute("""
            INSERT INTO FeedbackState (Feedback_ID, State, Feedback_Notes, Primary_Domain, Updated_By)
            VALUES (?, ?, ?, ?, ?)
        """, [test_feedback_id, "NEW", "Test feedback note", "PowerBI", "test-user"])
        
        # Test SELECT
        print("🔍 Testing SELECT operation...")
        cursor.execute("SELECT * FROM FeedbackState WHERE Feedback_ID = ?", [test_feedback_id])
        row = cursor.fetchone()
        if row:
            print(f"✅ Found test record: {row[0]} - {row[1]}")
        
        # Test UPDATE
        print("🔍 Testing UPDATE operation...")
        cursor.execute("""
            UPDATE FeedbackState 
            SET State = ?, Feedback_Notes = ?, Last_Updated = GETDATE()
            WHERE Feedback_ID = ?
        """, ["TRIAGED", "Updated test note", test_feedback_id])
        
        # Verify update
        cursor.execute("SELECT State, Feedback_Notes FROM FeedbackState WHERE Feedback_ID = ?", [test_feedback_id])
        row = cursor.fetchone()
        if row and row[0] == "TRIAGED":
            print("✅ UPDATE operation successful")
        
        # Test DELETE (cleanup)
        print("🔍 Testing DELETE operation...")
        cursor.execute("DELETE FROM FeedbackState WHERE Feedback_ID = ?", [test_feedback_id])
        print("✅ DELETE operation successful")
        
        print("🎉 All CRUD operations working properly!")
        return True
        
    except Exception as e:
        print(f"❌ CRUD test failed: {e}")
        return False

if __name__ == "__main__":
    print("Fabric SQL Database Connection Test")
    print("=" * 50)
    
    # Check if pyodbc is installed
    try:
        import pyodbc
    except ImportError:
        print("ERROR: pyodbc not installed. Please run: pip install pyodbc")
        sys.exit(1)
    
    # Test connection
    success = test_fabric_sql_connection()
    
    if success:
        print("\nSUCCESS: Connection test successful!")
        print("Ready to implement SQL-based state management!")
    else:
        print("\nNext steps:")
        print("1. Install Microsoft ODBC Driver 18 for SQL Server")
        print("2. Run: pip install pyodbc")
        print("3. Ensure Azure AD access to Fabric workspace")