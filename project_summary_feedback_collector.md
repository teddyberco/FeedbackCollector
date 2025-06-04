# Project Diary: Building and Debugging the Feedback Collector Application

This document summarizes the development and debugging journey of the Feedback Collector application, with a particular focus on integrating it with Microsoft Fabric.

## 1. Project Inception and Initial Goals

The primary goal was to create a Python-based application to:
1.  Collect feedback from various sources (initially Reddit).
2.  Store this feedback locally (e.g., CSV/JSON).
3.  Provide a simple web interface (Flask) to trigger collection, view feedback, and initiate writing to a centralized data store.
4.  Ultimately, write the collected feedback into a Delta table in Microsoft Fabric for analysis.

## 2. Initial Development & Local Functionality

The initial phase involved setting up:
*   A **Flask web application** (`app.py`, `main.py`) for basic UI and API endpoints.
*   **Collectors** (e.g., `RedditCollector` in `collectors.py`) to fetch data from sources like Reddit using PRAW.
*   **Local Storage** (`storage.py`) to save data to CSV files and manage an in-memory cache.
*   **HTML Templates** for the user interface.
*   **Configuration Management** (`config.py`, `.env`) for API keys and endpoints.

This allowed for successful collection and local viewing of feedback.

## 3. The Microsoft Fabric Integration Challenge

The next major step was to write the collected data to a Delta table in Microsoft Fabric. The chosen method was to use the Livy API to submit PySpark jobs. This led to the creation of `fabric_writer.py`.

### 3.1. Early Attempts and the Emergence of `JSONDecodeError`

The `FabricWriter` was designed to:
1.  Obtain an authentication token for Fabric.
2.  Start a Livy Spark session.
3.  Prepare a PySpark script:
    *   This script would take the list of feedback items (Python dictionaries) as a JSON string.
    *   It would then use Spark to create a DataFrame from this JSON data.
    *   Finally, it would write the DataFrame to the target Delta table.
4.  Submit this PySpark script as a statement to the Livy session.
5.  Poll for statement completion and close the session.

Almost immediately, we encountered a persistent error when the Spark job tried to parse the JSON data:

```
json.decoder.JSONDecodeError: Invalid control character at: line 1 column 109 (char 108)
```

This error indicated that Spark's `json.loads()` function was finding an unescaped control character within the JSON string it was trying to parse, specifically at character index 108 (0-indexed).

### 3.2. Iterative Debugging: Chasing the "Invalid Control Character"

This error became the central focus of an extensive debugging effort. Here's a summary of the steps taken:

**A. Data Sanitization:**
*   **Hypothesis:** The raw feedback data might contain unescaped control characters.
*   **Action:** Implemented `_sanitize_string_for_json` and `_sanitize_data_recursively` functions in `fabric_writer.py` to remove ASCII control characters (U+0000 to U+001F, except common whitespace like `\t`, `\n`, `\r`) and DEL (U+007F).
*   **Result:** The error persisted, suggesting the issue was not with the *original* raw data's control characters being passed through, or that sanitization wasn't catching the specific problematic character.

**B. `json.dumps` Parameters (`ensure_ascii`):**
*   **Hypothesis:** The `ensure_ascii` parameter of `json.dumps()` might be affecting how characters (especially non-ASCII or special characters) were being encoded, potentially leading to issues downstream in Spark.
*   **Action:** Experimented with `ensure_ascii=True` (default, escapes non-ASCII to `\uXXXX`) and `ensure_ascii=False` (passes UTF-8 characters through).
*   **Result:** The error persisted with both settings. We eventually settled on `ensure_ascii=True` as it produces a more restricted character set, which is generally safer for JSON. The problem was clearly not simple non-ASCII characters.

**C. Detailed Logging (Flask/Python Side):**
*   **Hypothesis:** We needed to see exactly what the JSON string looked like *on the Flask side* before being sent to Spark, particularly around the problematic character index 108.
*   **Action:** Added `DEBUG_FW:` print statements in `_prepare_pyspark_payload` to log:
    *   The full JSON string length.
    *   A snippet of the JSON string.
    *   The character and its ordinal value at index 108.
    *   A small context window of characters and their ordinals around index 108.
*   **Key Flask-Side Log Snippet (after `json.dumps`):**
    ```
    DEBUG_FW: Character at index 108: '\', Ordinal value: 92
    DEBUG_FW: Ordinal values for segment 'ances\n\nH' (indices 103-112): [97, 110, 99, 101, 115, 92, 110, 92, 110, 72]
    ```
    This showed that on the Flask side, character 108 was a backslash (`\`, ordinal 92) and character 109 was 'n' (ordinal 110). This `\\n` sequence is the *correct* JSON representation for a newline character within a string value. This deepened the mystery, as `\\n` should be valid for `json.loads()`.

**D. Detailed Logging (Spark/PySpark Side):**
*   **Hypothesis:** We needed to see what the JSON string looked like *from Spark's perspective*, right before `json.loads()` was called.
*   **Action:** Modified the PySpark code template to include extensive `print()` statements (prefixed with `FATAL:` or `SPARK_DEBUG:`) within the `try...except json.JSONDecodeError` block. These prints would show the error message from Spark, the character position, a snippet of the string Spark was trying to parse, and the ordinal of the character at the error position.
*   **Challenge:** Initially, these Spark-side `print` statements weren't visible in the Livy logs returned to Flask when the statement failed with `output.status == 'error'`. We had to enhance `_poll_statement_status` to explicitly try and fetch `output.data['text/plain']` (which contains stdout) even on error.

**E. Isolating with a Single Data Item:**
*   **Hypothesis:** The issue might be related to the overall size of the JSON payload (132 items, ~800KB JSON string) or an issue specific to one of the later items.
*   **Action:** Modified `write_data_to_fabric` to send only the *first* data item: `data_to_write_for_spark = [data_to_write[0]]`.
*   **Result:** The error *still persisted* with a single item, and it was still `Invalid control character at: line 1 column 109 (char 108)`. This was a crucial step, as it ruled out payload size as the primary cause and confirmed the issue was present even in the first item's data representation.
*   **Breakthrough - Spark-Side Logs Became Visible:** With the single item and improved polling, we finally saw the detailed Spark-side logs:
    ```
    ERROR:fabric_writer:Spark stdout on error for statement 1:
    FATAL: Error decoding JSON data in Spark: Invalid control character at: line 1 column 109 (char 108)
    ...
    Ordinal of char at error_pos (108): 10
    ```
    **This was the "Aha!" moment!**
    *   Flask side: char 108 is `\` (ord 92), part of `\\n`.
    *   Spark side: char 108 (the one causing the error) is a literal Line Feed (`\n`, ord 10).

    This meant the `\\n` (two characters: backslash, n) generated by `json.dumps` in Flask was somehow being transformed into a single literal newline character by the time it reached `json.loads` inside the Spark script. A literal newline is an invalid control character within a JSON string value unless escaped.

**F. Investigating String Embedding in PySpark Code:**
*   **Hypothesis:** The way the `data_as_json_string` (from Flask) was embedded into the PySpark code string was the culprit. The initial method was:
    ```python
    # In fabric_writer.py
    pyspark_code = f"""
    import json
    # ...
    data_json_string = '''{data_as_json_string}''' # data_as_json_string contains "\\n"
    # ...
    data_list_for_df = json.loads(data_json_string)
    """
    ```
    We theorized that some layer of processing (Livy, or Python's own parsing of the triple-quoted string literal in the Spark environment) was interpreting the `\\n` from `data_as_json_string` as an escape sequence for a literal newline, rather than preserving it as a literal backslash followed by 'n'.

*   **The Solution - Using `repr()`:**
    *   **Action:** Change the embedding method to use Python's built-in `repr()` function. `repr(a_string)` generates a Python string literal that, when evaluated by a Python interpreter, faithfully reconstructs the original string, including all necessary escapes for special characters like backslashes and quotes.
    *   **Code Change in `_prepare_pyspark_payload`:**
        ```python
        data_as_python_literal_string = repr(data_as_json_string)
        # ...
        pyspark_code = f"""
        # ...
        data_json_string = {data_as_python_literal_string} # No extra quotes around this
        # ...
        """
        ```
        If `data_as_json_string` was `"[{\"key\": \"value with \\n newline\"}]"`,
        `repr(data_as_json_string)` would produce something like `'[{\"key\": \"value with \\\\n newline\"}]'` (note the outer single quotes from `repr` and `\\n` becoming `\\\\n`).
        When the Spark Python interpreter executes `data_json_string = '[{\"key\": \"value with \\\\n newline\"}]'`, the variable `data_json_string` correctly becomes `[{"key": "value with \\n newline"}]`, which is what `json.loads()` needs.

*   **Result of `repr()` fix:**
    1.  **Test with Single Item:** SUCCESS! The Spark-side logs confirmed that `data_json_string` now contained `\\n` (ord 92 at char 108), and `json.loads()` worked.
        ```
        SPARK_DEBUG: Spark-side context around char 108: 'ances\n\nHi', ordinals: [97, 110, 99, 101, 115, 92, 110, 92, 110, 72, 105]
        Attempting to write 1 rows to table 'FeedbackCollector' in mode 'overwrite'.
        Successfully wrote data to table 'FeedbackCollector'.
        ```
    2.  **Test with Full Dataset (132 items):** SUCCESS! The `repr()` solution scaled correctly. The `data_as_python_literal_string` grew (e.g., from ~827KB to ~877KB), and the total PySpark code length was ~880KB, but Livy and Spark handled it.
        ```
        DEBUG_FW: Python-side data_as_json_string (length: 826989 chars).
        DEBUG_FW: data_as_python_literal_string for Spark (length: 876783 chars).
        INFO:fabric_writer:Submitting Spark statement ... Code length: 880453 chars.
        SPARK_DEBUG: Length of data_json_string in Spark: 826989
        Attempting to write 132 rows to table 'FeedbackCollector' in mode 'overwrite'.
        Successfully wrote data to table 'FeedbackCollector'.
        ```

## 4. Architectural Discussions & Presentation Preparation

After resolving the main technical hurdle, we discussed:
*   **Presentation Outline:** Structuring the development journey and the "war story" of debugging the `JSONDecodeError` for an audience of technical PMs.
*   **Key Message:** Emphasizing the importance of building robust, automated solutions for recurring PM tasks.
*   **Diagram Sketches:** Outlining visual representations for:
    1.  Initial architecture with local CSV storage.
    2.  Enhanced architecture with Fabric integration, highlighting the Livy/Spark pathway.

## 5. Conclusion and Key Learnings

The Feedback Collector application is now successfully writing data to Microsoft Fabric. The journey to resolve the `JSONDecodeError` was challenging but yielded important learnings:

*   **String Escaping is Critical:** When passing string data (especially complex strings like serialized JSON) between systems or through layers of interpretation (Python script -> Livy -> Spark Python interpreter), meticulous attention to escaping is paramount.
*   **`repr()` is Your Friend:** For embedding a string into Python code such that it reconstructs perfectly, `repr()` is a robust tool.
*   **Comparative Logging:** In distributed or multi-step processes, logging the state of data *at each significant step* and *from the perspective of each component* is crucial for pinpointing where transformations or corruptions occur.
*   **Systematic Debugging:** Isolating variables (like payload size) and forming clear hypotheses for each test helps narrow down complex problems.

This project demonstrates a practical approach to automating feedback collection and integrating it with a powerful analytics platform, while also serving as a case study in tackling subtle data representation issues.
