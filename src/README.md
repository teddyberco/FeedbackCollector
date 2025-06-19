# Feedback Collector - Production Ready

## Overview
A comprehensive feedback collection application that gathers feedback from multiple sources including Reddit, Microsoft Fabric Community, GitHub Discussions, and Azure DevOps work items.

## Features
- **Multi-Source Collection**: Reddit, Fabric Community, GitHub, Azure DevOps
- **Rich Content**: Descriptions, categorization, and direct links
- **Smart Categorization**: Text-based analysis for accurate categorization
- **Web Interface**: Modern feedback viewer with filtering and sorting
- **Direct Navigation**: Click-through links to original sources

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.template` to `.env` and configure your API tokens:
```bash
cp .env.template .env
# Edit .env with your API credentials
```

### 3. Run Application
```bash
python run_web.py
```

### 4. Use the Application
1. Visit: http://localhost:5000
2. Click "Collect Feedback" to gather data
3. Click "View Feedback" to see results
4. Filter by source, category, or date
5. Click "View Source" to navigate to original items

## Configuration

### Required API Tokens
- **Reddit**: CLIENT_ID, CLIENT_SECRET, USER_AGENT
- **GitHub**: GITHUB_TOKEN (with repo scope + SSO enabled)
- **Azure DevOps**: AZURE_DEVOPS_PAT

### Azure DevOps Setup
- Set `ADO_PARENT_WORK_ITEM_ID` for specific work item children
- Default collects recent work items from past year
- Supports 200 work items with intelligent batching

## Features

### Azure DevOps Integration
- **200 Work Items**: Comprehensive collection from past year
- **Rich Descriptions**: Multi-field extraction with clean formatting
- **Smart Categorization**: Full content analysis (title + description)
- **Direct Links**: "View Source" navigation to ADO work items
- **Intelligent Batching**: Prevents server errors with large datasets

### Categorization
- UI/Usability
- Performance/Reliability
- Support/Documentation
- Security/Compliance
- Integration/Compatibility
- Feature Requests
- Accessibility
- Other/Uncategorized

### Data Export
- CSV export functionality
- Structured data format
- Timestamp tracking

## File Structure
```
src/
├── app.py                    # Main Flask application
├── working_ado_client.py     # Azure DevOps integration
├── collectors.py             # Reddit, Fabric, GitHub collectors
├── config.py                 # Configuration management
├── utils.py                  # Utility functions
├── fabric_writer.py          # Fabric data export
├── run_web.py               # Application launcher
├── templates/               # Web interface templates
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Production Ready
This application is production-ready with:
- Error handling and fallback strategies
- Intelligent batching for large datasets
- Clean, maintainable codebase
- Comprehensive logging
- Professional web interface

## Support
The application handles various edge cases:
- API rate limits and timeouts
- Large dataset processing
- Missing or invalid data
- Authentication failures
- Server errors with graceful fallbacks

## License
Microsoft Internal Use