import requests
import time
import json
import logging
import sys # Added for direct print debugging
from config import FABRIC_LIVY_ENDPOINT, FABRIC_TARGET_TABLE_NAME, FABRIC_WRITE_MODE, TABLE_COLUMNS

logger = logging.getLogger(__name__)

# Default Spark session configuration (can be customized if needed)
DEFAULT_SPARK_CONF = {
    "spark.submit.deployMode": "cluster", # Or "client" if appropriate, though cluster is typical for Livy
    # "spark.driver.memory": "2g",
    # "spark.executor.memory": "2g",
    # "spark.executor.instances": "2",
}

def _sanitize_string_for_json(s: str) -> str:
    """
    Removes ASCII control characters (U+0000 to U+001F) except for common whitespace 
    like tab (U+0009), newline (U+000A), and carriage return (U+000D).
    Also removes DEL (U+007F).
    """
    if not isinstance(s, str):
        return s # Return non-strings as is
    
    s = s.replace(chr(0), '') # Remove null characters (U+0000)
    
    cleaned_chars = []
    for char_val in s:
        char_ord = ord(char_val)
        if char_val in ('\t', '\n', '\r'): # Allow tab, newline, carriage return
            cleaned_chars.append(char_val)
        elif char_ord >= 32 and char_ord != 127: # Allow printable ASCII (space to ~), excluding DEL
            cleaned_chars.append(char_val)
        elif char_ord > 127: # Allow non-ASCII characters (UTF-8)
            cleaned_chars.append(char_val)
    return "".join(cleaned_chars)

def _sanitize_data_recursively(data: any) -> any:
    """
    Recursively traverses a data structure (list or dict) and sanitizes all string values.
    """
    if isinstance(data, list):
        return [_sanitize_data_recursively(item) for item in data]
    elif isinstance(data, dict):
        return {key: _sanitize_data_recursively(value) for key, value in data.items()}
    elif isinstance(data, str):
        return _sanitize_string_for_json(data)
    return data

def _prepare_pyspark_payload(data_list: list, table_name: str, write_mode: str) -> str:
    """
    Prepares the PySpark code payload to ingest data into a Fabric Delta table.
    """
    print(f"DEBUG_FW: _prepare_pyspark_payload called with {len(data_list)} items.", file=sys.stderr)
    if not data_list:
        print(f"DEBUG_FW: _prepare_pyspark_payload returning early as data_list is empty.", file=sys.stderr)
        return ""

    try:
        # Sanitization is still good practice, though not the cause of the main error
        sanitized_data_list = _sanitize_data_recursively(data_list)
    except Exception as e:
        logger.error(f"Error during data sanitization: {e}", exc_info=True) 
        print(f"DEBUG_FW: Exception during sanitization: {e}", file=sys.stderr)
        raise ValueError("Could not sanitize data for PySpark payload.") from e
        
    try:
        data_as_json_string = json.dumps(sanitized_data_list, ensure_ascii=True)
        
        log_snippet_length = 250
        print(f"DEBUG_FW: Python-side data_as_json_string (length: {len(data_as_json_string)} chars).", file=sys.stderr)
        print(f"DEBUG_FW: Python-side data_as_json_string (first {log_snippet_length} chars): {data_as_json_string[:log_snippet_length]}...", file=sys.stderr)
        # Optional: Keep detailed char 108 check for one more run if paranoid, then remove.
        # problem_char_index = 108 
        # if len(data_as_json_string) > problem_char_index + 5: 
        #     context_str_py = data_as_json_string[problem_char_index-5 : problem_char_index+6]
        #     ordinals_py = [ord(c) for c in context_str_py]
        #     print(f"DEBUG_FW: Python-side context around char {problem_char_index}: '{context_str_py}', ordinals: {ordinals_py}", file=sys.stderr)
        
    except Exception as e:
        logger.error(f"Error serializing sanitized data to JSON: {e}", exc_info=True)
        print(f"DEBUG_FW: Exception during json.dumps: {e}", file=sys.stderr)
        raise ValueError("Could not serialize sanitized data for PySpark payload.") from e

    # Use repr() to create a Python string literal for embedding in PySpark code.
    # This ensures all special characters in data_as_json_string are correctly escaped
    # for the Python parser in Spark. This was the key fix.
    data_as_python_literal_string = repr(data_as_json_string)
    print(f"DEBUG_FW: data_as_python_literal_string for Spark (length: {len(data_as_python_literal_string)} chars).", file=sys.stderr)
    print(f"DEBUG_FW: data_as_python_literal_string (first {log_snippet_length} chars): {data_as_python_literal_string[:log_snippet_length]}...", file=sys.stderr)


    schema_fields_str = []
    for col_name in TABLE_COLUMNS:
        field_type = "StringType()" 
        schema_fields_str.append(f"StructField('{col_name}', {field_type}, True)")
    schema_definition_str = f"StructType([{', '.join(schema_fields_str)}])"

    pyspark_code = f"""
import json
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, IntegerType, BooleanType

# Assign the JSON data string using its Python literal representation
data_json_string = {data_as_python_literal_string}

target_table_name = "{table_name}"
target_write_mode = "{write_mode}"

spark = SparkSession.builder.appName("FeedbackIngestionFromLivy").getOrCreate()

try:
    # For debugging: print type and snippet of what Spark's Python sees for data_json_string
    print(f"SPARK_DEBUG: Type of data_json_string: {{type(data_json_string)}}")
    print(f"SPARK_DEBUG: Length of data_json_string in Spark: {{len(data_json_string)}}")
    spark_snippet_len = 250
    print(f"SPARK_DEBUG: data_json_string in Spark (first {{spark_snippet_len}} chars): {{data_json_string[:spark_snippet_len]}}...")
    # Optional: Keep detailed char 108 check for one more run if paranoid, then remove.
    # if len(data_json_string) > 113: 
    #     spark_context_str = data_json_string[108-5 : 108+6]
    #     spark_ordinals = [ord(c) for c in spark_context_str]
    #     print(f"SPARK_DEBUG: Spark-side context around char 108: '{{spark_context_str}}', ordinals: {{spark_ordinals}}")
        
    data_list_for_df = json.loads(data_json_string)
except json.JSONDecodeError as e:
    print(f"FATAL: Error decoding JSON data in Spark: {{e}}")
    error_pos = e.pos
    context_before = 50
    context_after = 50
    start_snippet = max(0, error_pos - context_before)
    end_snippet = min(len(data_json_string), error_pos + context_after)
    print(f"Error occurred at char position (0-indexed): {{error_pos}}")
    print(f"Snippet around error (chars {{start_snippet}}-{{end_snippet-1}}):")
    print(data_json_string[start_snippet:end_snippet])
    print(f"--- End of snippet ---")
    if error_pos < len(data_json_string):
        print(f"Ordinal of char at error_pos ({{error_pos}}): {{ord(data_json_string[error_pos])}}")
    else:
        print(f"Error position {{error_pos}} is out of bounds for string length {{len(data_json_string)}}.")
    raise

if not data_list_for_df:
    print("No data to write: JSON parsed to an empty list or initial data was empty.")
else:
    defined_schema = {schema_definition_str}
    try:
        df = spark.createDataFrame(data=data_list_for_df, schema=defined_schema)
        print(f"Attempting to write {{df.count()}} rows to table '{{target_table_name}}' in mode '{{target_write_mode}}'.")
        writer = df.write.format("delta").mode(target_write_mode)
        if target_write_mode == "overwrite":
            print("Overwrite mode detected. Enabling overwriteSchema to replace table schema if different.")
            writer = writer.option("overwriteSchema", "true")
        writer.saveAsTable(target_table_name)
        print(f"Successfully wrote data to table '{{target_table_name}}'.")
    except Exception as e:
        print(f"Error during DataFrame creation or writing to table '{{target_table_name}}': {{e}}")
        raise
"""
    return pyspark_code

def _start_livy_session(token: str, livy_endpoint: str, spark_conf: dict = None) -> str:
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    session_payload = {'name': 'FeedbackCollectorSession', 'kind': 'pyspark', 'conf': spark_conf or DEFAULT_SPARK_CONF}
    try:
        logger.info(f"Starting Livy session at {livy_endpoint} with payload: {json.dumps(session_payload)}")
        response = requests.post(livy_endpoint, headers=headers, json=session_payload, timeout=60)
        response.raise_for_status() 
        session_data = response.json()
        session_id = session_data.get('id')
        session_state = session_data.get('state')
        if session_id is None: logger.error(f"Livy session ID not found: {session_data}"); return None
        logger.info(f"Livy session created: ID {session_id}, State {session_state}")
        session_url = f"{livy_endpoint}/{session_id}"
        for _ in range(30): 
            time.sleep(10)
            logger.info(f"Polling session {session_id} state...")
            r = requests.get(session_url, headers=headers, timeout=30)
            r.raise_for_status()
            current_state = r.json().get('state')
            logger.info(f"Session {session_id} current state: {current_state}")
            if current_state == 'idle': logger.info(f"Session {session_id} is idle."); return session_id
            if current_state in ['error', 'dead', 'shutting_down']:
                logger.error(f"Session {session_id} failed: {current_state}. Log: {r.json().get('log')}")
                return None
        logger.error(f"Session {session_id} timed out becoming idle.")
        _close_livy_session(token, livy_endpoint, session_id)
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error starting Livy session: {e}. URL: {e.request.url if e.request else 'N/A'}")
        if e.response is not None: logger.error(f"Response Status: {e.response.status_code}. Response Text: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e: logger.error(f"RequestException starting Livy session: {e}"); return None
    except Exception as e: logger.error(f"Unexpected error starting Livy session: {e}", exc_info=True); return None

def _submit_spark_statement(token: str, livy_endpoint: str, session_id: int, spark_code: str) -> str:
    if not spark_code: logger.error("No Spark code to submit."); return None
    statement_url = f"{livy_endpoint}/{session_id}/statements"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'code': spark_code, 'kind': 'pyspark'}
    try:
        # Log the size of the code payload being sent to Livy
        logger.info(f"Submitting Spark statement to session {session_id}. Code length: {len(spark_code)} chars.")
        response = requests.post(statement_url, headers=headers, json=payload, timeout=180) # Increased timeout for potentially larger code
        response.raise_for_status()
        statement_id = response.json().get('id')
        if statement_id is None: logger.error(f"Statement ID not found: {response.json()}"); return None
        logger.info(f"Spark statement submitted: ID {statement_id}")
        return str(statement_id)
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error submitting Spark statement: {e}. URL: {e.request.url if e.request else 'N/A'}")
        if e.response is not None: logger.error(f"Response Status: {e.response.status_code}. Response Text: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e: logger.error(f"RequestException submitting Spark statement: {e}"); return None
    except Exception as e: logger.error(f"Unexpected error submitting Spark statement: {e}", exc_info=True); return None

def _poll_statement_status(token: str, livy_endpoint: str, session_id: int, statement_id: str) -> bool:
    status_url = f"{livy_endpoint}/{session_id}/statements/{statement_id}"
    headers = {'Authorization': f'Bearer {token}'}
    logger.info(f"Polling statement {statement_id} at {status_url}...")
    # Increased polling time for potentially longer jobs with more data
    for i in range(180): # Poll for up to 30 minutes (180 * 10s)
        try:
            time.sleep(10)
            response = requests.get(status_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            state = data.get('state')
            progress = data.get('progress', 0.0)
            logger.info(f"Statement {statement_id} state: {state}, Progress: {progress*100:.2f}% (Attempt {i+1}/180)")
            
            spark_stdout = ""
            if data.get('output') and data['output'].get('data') and data['output']['data'].get('text/plain'):
                spark_stdout = data['output']['data']['text/plain']

            if state == 'available':
                output = data.get('output', {})
                if output and output.get('status') == 'ok':
                    logger.info(f"Statement {statement_id} successful.")
                    if spark_stdout: logger.info(f"Spark stdout (first 1000 chars):\n{spark_stdout[:1000]}")
                    # Check for application-level errors in stdout even on "ok" status
                    if "FATAL: Error decoding JSON data in Spark" in spark_stdout or \
                       "Error during DataFrame creation or writing to table" in spark_stdout:
                        logger.error(f"Spark job reported an application error in its output for statement {statement_id}.")
                        if spark_stdout: logger.error(f"Full Spark stdout for statement {statement_id}:\n{spark_stdout}")
                        return False
                    return True
                elif output and output.get('status') == 'error':
                    logger.error(f"Statement {statement_id} error. Name: {output.get('ename')}, Value: {output.get('evalue')}\nTraceback: {''.join(output.get('traceback', []))}")
                    if spark_stdout: logger.error(f"Spark stdout on error for statement {statement_id}:\n{spark_stdout}")
                    return False
                else: 
                    logger.warning(f"Statement {statement_id} available, unexpected output: {output}")
                    if spark_stdout: logger.warning(f"Spark stdout for unexpected output:\n{spark_stdout}")
                    return False # Treat unexpected 'available' status as an error
            elif state in ['error', 'cancelled', 'cancelling']:
                logger.error(f"Statement {statement_id} failed/cancelled. State: {state}. Output: {data.get('output')}")
                if spark_stdout: logger.error(f"Spark stdout on failure/cancellation:\n{spark_stdout}")
                return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error polling statement: {e}. Status: {e.response.status_code if e.response else 'N/A'}. Text: {e.response.text if e.response else 'N/A'}")
            if e.response and e.response.status_code == 404 and i < 10 : 
                 logger.warning(f"Statement {statement_id} not found yet (attempt {i+1}), continuing poll.")
            else: time.sleep(20) 
        except requests.exceptions.RequestException as e: logger.error(f"RequestException polling statement: {e}"); time.sleep(20)
        except Exception as e: logger.error(f"Unexpected error polling statement: {e}", exc_info=True); return False
    logger.error(f"Statement {statement_id} timed out after {180*10/60} minutes.")
    return False

def _close_livy_session(token: str, livy_endpoint: str, session_id: int) -> bool:
    url = f"{livy_endpoint}/{session_id}"
    headers = {'Authorization': f'Bearer {token}'}
    try:
        logger.info(f"Closing Livy session {session_id}...")
        response = requests.delete(url, headers=headers, timeout=60)
        response.raise_for_status()
        logger.info(f"Livy session {session_id} closed.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error closing Livy session {session_id}: {e}" + (f"\nResponse: {e.response.text}" if e.response else ""))
        return False
    except Exception as e: logger.error(f"Unexpected error closing Livy session {session_id}: {e}", exc_info=True); return False

def write_data_to_fabric(token: str, data_to_write: list) -> bool:
    if not token: logger.error("Fabric access token not provided."); return False
    if not data_to_write: logger.info("No data provided to write to Fabric."); return True

    # Re-enable processing for all data items with the repr() fix
    data_to_write_for_spark = data_to_write
    print(f"DEBUG_FW: Processing {len(data_to_write_for_spark)} items for Spark.", file=sys.stderr)

    session_id = None
    try:
        session_id = _start_livy_session(token, FABRIC_LIVY_ENDPOINT)
        if not session_id: return False
        
        spark_code = _prepare_pyspark_payload(data_to_write_for_spark, FABRIC_TARGET_TABLE_NAME, FABRIC_WRITE_MODE)
        if not spark_code: logger.info("PySpark payload is empty. Skipping submission."); return True
        
        statement_id = _submit_spark_statement(token, FABRIC_LIVY_ENDPOINT, session_id, spark_code)
        if not statement_id: return False
        
        success = _poll_statement_status(token, FABRIC_LIVY_ENDPOINT, session_id, statement_id)
        if not success: logger.error(f"Spark statement {statement_id} processing failed."); return False
        
        logger.info("Data processing via Spark completed successfully.")
        return True
    except ValueError as ve: 
        logger.error(f"ValueError in write_data_to_fabric: {ve}") 
        print(f"DEBUG_FW: ValueError in write_data_to_fabric: {ve}", file=sys.stderr)
        return False
    except Exception as e:
        logger.error(f"Overall error in write_data_to_fabric: {e}", exc_info=True)
        print(f"DEBUG_FW: Exception in write_data_to_fabric: {e}", file=sys.stderr)
        return False
    finally:
        if session_id:
            logger.info(f"Attempting to close Livy session {session_id} in finally block.")
            _close_livy_session(token, FABRIC_LIVY_ENDPOINT, session_id)

if __name__ == '__main__':
    # if not logging.getLogger().hasHandlers():
    #    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - [%(filename)s:%(lineno)d] - %(message)s')
    print("Running fabric_writer.py direct test (requires manual token and .env setup)...")
    manual_test_token = "YOUR_MANUALLY_EXTRACTED_FABRIC_TOKEN" 
    if manual_test_token == "YOUR_MANUALLY_EXTRACTED_FABRIC_TOKEN":
        print("Please replace 'YOUR_MANUALLY_EXTRACTED_FABRIC_TOKEN' with a real token to test.")
    else:
        # Test with a few items to simulate a slightly larger payload for direct testing
        sample_data_list = []
        for i in range(3): 
            item = {col: f"Sample {col} Value {i+1}" for col in TABLE_COLUMNS}
            if 'FeedbackText' in item:
                 item['FeedbackText'] = f"Sample text for item {i+1} with newline\n and unicode éà here. Also 'single quotes' and \"double quotes\"." 
            item['Created'] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            sample_data_list.append(item)
        
        print(f"Sample data to write ({len(sample_data_list)} items): {json.dumps(sample_data_list, indent=2, ensure_ascii=False)}")
        print(f"Target Livy Endpoint: {FABRIC_LIVY_ENDPOINT}")
        print(f"Target Table: {FABRIC_TARGET_TABLE_NAME}, Mode: {FABRIC_WRITE_MODE}")
        success = write_data_to_fabric(manual_test_token, sample_data_list)
        if success: print("Test write_data_to_fabric reported SUCCESS.")
        else: print("Test write_data_to_fabric reported FAILURE.")
