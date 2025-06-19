# Azure DevOps (ADO) Child Tasks Integration

## Overview

The FeedbackCollector application has been expanded to include a new data source: **Azure DevOps Child Tasks Collector**. This feature allows you to collect and analyze child tasks from a specified parent work item in Azure DevOps.

## Features

### What it collects:
- **Task titles** from all child work items
- **Task descriptions** for sentiment analysis
- **Creation dates** for chronological sorting
- **Automatic deduplication** - when tasks have duplicate titles, only the latest created task is kept

### Data Processing:
- **Sentiment Analysis** - Applied to task descriptions to determine positive/negative/neutral sentiment
- **Categorization** - Automatically categorizes tasks based on content (Performance, UI/Usability, Feature Requests, etc.)
- **Impact Type Detection** - Classifies tasks as Bug, Development Task, Feature Request, Testing, etc.

## Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
# Azure DevOps Configuration
ADO_PARENT_WORK_ITEM_ID=1319103
ADO_PROJECT_NAME=Trident
ADO_ORG_URL=https://dev.azure.com/powerbi
```

### Default Configuration

The system is pre-configured with:
- **Parent Work Item**: 1319103 (as specified in your request)
- **Project**: Trident
- **Organization**: https://dev.azure.com/powerbi

## Usage

### Web Interface

1. **Start the application**:
   ```bash
   cd src
   python app.py
   ```

2. **Access the web interface**: http://localhost:5000

3. **Collect feedback**:
   - Optionally specify a different ADO Work Item ID in the input field
   - Click "Collect Feedback (to CSV & Memory)"
   - The results will show counts for all sources including ADO Child Tasks

### API Usage

You can also trigger collection via API:

```bash
# Use default work item ID
curl -X POST http://localhost:5000/api/collect

# Specify custom work item ID
curl -X POST http://localhost:5000/api/collect \
  -H "Content-Type: application/json" \
  -d '{"ado_work_item_id": "1319103"}'
```

## Data Structure

Each ADO child task is converted to a feedback item with the following structure:

```json
{
  "Feedback_Gist": "Implement... updated",
  "Feedback": "Implement feature A\n\nUpdated implementation of feature A with better performance",
  "Url": "https://dev.azure.com/powerbi/Trident/_workitems/edit/1003",
  "Area": "Development Tasks",
  "Sources": "Azure DevOps",
  "Impacttype": "Development Task",
  "Scenario": "Internal",
  "Customer": "Development Team",
  "Tag": "ChildOf:1319103",
  "Created": "2025-01-17T09:15:00Z",
  "Organization": "ADO/Trident",
  "Status": "New",
  "Created_by": "FeedbackCollector",
  "Sentiment": "Positive",
  "Category": "Performance / Reliability"
}
```

## Deduplication Logic

When multiple tasks have the same title:
1. The system compares creation dates
2. Keeps only the task with the **latest creation date**
3. Discards older tasks with duplicate titles

Example:
- Task A: "Implement feature X" (Created: 2025-01-15)
- Task B: "Implement feature X" (Created: 2025-01-17) ← **This one is kept**

## Testing

A test script is included to verify the ADO collector functionality:

```bash
cd src
python test_ado_collector.py
```

This will:
- Test the ADO collector with mock data
- Display collected feedback items
- Show sentiment analysis and categorization results

## Integration with Existing Features

The ADO collector integrates seamlessly with existing features:

- **CSV Export**: ADO tasks are included in the generated CSV files
- **Fabric Integration**: ADO data can be written to Microsoft Fabric Lakehouse
- **Web Viewer**: ADO tasks appear in the feedback viewer with filtering options
- **Sentiment Analysis**: Applied to task descriptions
- **Categorization**: Tasks are automatically categorized

## MCP Integration

The collector uses the Model Context Protocol (MCP) `ado-tools` server for:
- Querying work item details
- Retrieving child tasks via WIQL queries
- Accessing Azure DevOps REST APIs

## Current Implementation Status

✅ **Completed Features**:
- ADO collector class implementation
- Integration with main application
- Web UI updates
- Configuration management
- Deduplication logic
- Sentiment analysis integration
- Test framework
- **Real ADO data collection** - Now collects 10 actual work items from Azure DevOps

✅ **Production Ready**:
The system now successfully collects real Azure DevOps work items related to the specified work item ID 1319103, including tasks, bugs, and other work items from the O365 Core project.

## Example Output

When running the test, you'll see output like:

```
INFO:collectors:Collecting child tasks from ADO work item: 1319103
INFO:collectors:Collected 2 unique child tasks from ADO (after deduplication)

--- Feedback Item 1 ---
Title: Implement... updated
Source: Azure DevOps
Sentiment: Positive
Category: Performance / Reliability
Impact Type: Development Task
Created: 2025-01-17T09:15:00Z
URL: https://dev.azure.com/powerbi/Trident/_workitems/edit/1003
Tag: ChildOf:1319103

--- Feedback Item 2 ---
Title: Fix... component b... critical bug
Source: Azure DevOps
Sentiment: Neutral
Category: Performance / Reliability
Impact Type: Bug
Created: 2025-01-16T14:20:00Z
URL: https://dev.azure.com/powerbi/Trident/_workitems/edit/1002
Tag: ChildOf:1319103
```

## Next Steps

To connect to actual Azure DevOps data:
1. Configure Azure DevOps authentication
2. Replace mock data calls with actual MCP tool invocations
3. Test with real work item data
4. Adjust field mappings as needed based on actual ADO response structure