# Microsoft Fabric Workloads Feedback Collector

A comprehensive web-based tool that collects feedback about Microsoft Fabric Workloads from multiple sources, provides real-time progress tracking, and offers seamless integration with Microsoft Fabric Lakehouse for analytics.

## 🌟 Features

### **Multi-Source Data Collection**
- **Reddit**: r/MicrosoftFabric community discussions
- **Microsoft Fabric Community**: Official forums and discussions
- **GitHub Discussions**: Microsoft-Fabric-workload-development-sample repository
- **Azure DevOps**: Work items and task feedback

### **Intelligent Processing**
- **Smart Keyword Filtering**: "workload hub", "workloads", "Workload Development Kit"
- **Sentiment Analysis**: Automated categorization (Positive/Neutral/Negative)
- **Impact Classification**: Bug/Feature Request/Question/Feedback
- **Real-time Progress Tracking**: Live collection monitoring

### **Web Interface & User Experience**
- **Modern Web UI**: Bootstrap-powered responsive interface
- **Progress Drawer**: Real-time collection progress with detailed logging
- **Token Management**: Secure Bearer token handling for Fabric integration
- **Cross-Page State Persistence**: Seamless navigation without losing progress

### **Microsoft Fabric Integration**
- **Lakehouse Writing**: Direct integration with Fabric Lakehouse
- **Async Operations**: Non-blocking data transfers with progress monitoring
- **Bearer Token Authentication**: Secure API access management
- **Power BI Integration**: Ready-to-use analytics dashboard

## 🛠️ Prerequisites

- **Python 3.8+**
- **API Credentials**:
  - Reddit API (client_id, client_secret, user_agent)
  - GitHub Personal Access Token (repo scope)
  - Azure DevOps PAT (Work Items Read scope)
- **Microsoft Fabric Access**: Bearer token for Lakehouse operations

## 🚀 Quick Start

### 1. **Installation**
```bash
git clone [repository-url]
cd FeedbackCollector
pip install -r src/requirements.txt
```

### 2. **Environment Setup**
```bash
cp src/.env.template .env
# Edit .env with your API credentials
```

### 3. **Launch Web Interface**
```bash
cd src
python run_web.py
```

### 4. **Access Application**
- Open browser to `http://localhost:5000`
- Start collecting feedback with real-time progress tracking
- View collected data at `/feedback` endpoint
- Access Power BI insights at `/insights` endpoint

## 🔧 Configuration

### **Environment Variables (.env)**
```env
# Reddit API
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent

# GitHub API
GITHUB_TOKEN=your_github_token

# Azure DevOps
ADO_PAT=your_ado_personal_access_token
ADO_ORG_URL=https://dev.azure.com/your-org
ADO_PROJECT_NAME=your_project
ADO_PARENT_WORK_ITEM_ID=your_parent_item_id

# Power BI (Optional)
POWERBI_EMBED_BASE_URL=your_powerbi_url
POWERBI_REPORT_ID=your_report_id
POWERBI_TENANT_ID=your_tenant_id
```

### **API Credentials Setup**

#### **Reddit API**
1. Visit [reddit.com/prefs/apps](https://reddit.com/prefs/apps)
2. Create new application (type: script)
3. Copy client_id and client_secret

#### **GitHub Token**
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Generate token with 'repo' scope
3. Enable SAML SSO for 'microsoft' organization

#### **Azure DevOps PAT**
1. Visit your ADO organization settings
2. Create Personal Access Token
3. Grant "Work Items (Read)" permissions

## 📊 Web Interface

### **Home Page (`/`)**
- **Feedback Collection**: Start collection with real-time progress
- **Progress Drawer**: Live monitoring with detailed logs
- **Fabric Integration**: Write collected data to Lakehouse
- **Token Management**: Secure token input and persistence

### **Data Viewer (`/feedback`)**
- **Table View**: Paginated feedback data display
- **Filtering**: Search and filter capabilities
- **Export Options**: Download collected data

### **Insights Dashboard (`/insights`)**
- **Power BI Integration**: Embedded analytics dashboard
- **Bearer Token Setup**: Manual token configuration
- **Real-time Sync**: Direct data pipeline to Fabric

## 🏗️ Architecture

### **Backend Components**
- **Flask Web Server**: RESTful API endpoints
- **Data Collectors**: Modular source-specific collectors
- **Fabric Writer**: Async Lakehouse integration
- **Progress Tracking**: Real-time operation monitoring

### **Frontend Features**
- **Bootstrap UI**: Modern, responsive design
- **Progress Drawer**: Collapsible real-time monitoring
- **State Persistence**: LocalStorage-based progress recovery
- **Cross-page Navigation**: Seamless user experience

## 📁 Project Structure
```
FeedbackCollector/
├── src/
│   ├── app.py                    # Main Flask application
│   ├── collectors.py             # Data collection logic
│   ├── fabric_writer.py          # Fabric Lakehouse integration
│   ├── ado_client.py             # Azure DevOps integration
│   ├── config.py                 # Configuration management
│   ├── run_web.py               # Web server launcher
│   ├── utils.py                 # Utility functions
│   ├── keywords.json            # Search keywords configuration
│   ├── requirements.txt         # Python dependencies
│   ├── .env.template           # Environment template
│   └── templates/               # HTML templates
│       ├── index.html           # Main interface
│       ├── feedback_viewer.html # Data viewer
│       └── insights_page.html   # Power BI dashboard
├── data/                        # CSV output files
├── .env                         # Environment variables
└── README.md                    # Project documentation
```

## 📋 Data Schema

### **CSV Output Format**
Each feedback item contains the following fields:

| Field | Description | Example |
|-------|-------------|---------|
| `Feedback` | Processed main content | "Workload development is challenging..." |
| `Area` | Topic area classification | "Workloads", "Development", "Performance" |
| `Sources` | Origin platform | "Reddit", "Fabric Community", "GitHub", "ADO" |
| `Impacttype` | Issue classification | "Bug", "Feature Request", "Question", "Feedback" |
| `Partner/Customer` | Source identification | "Community", "Microsoft", "Partner" |
| `Customer` | User identification | Username or anonymized ID |
| `Tag` | Relevant keywords | "workload hub", "development kit" |
| `Created` | Original timestamp | "2025-06-20 15:30:45" |
| `Organization` | Platform name | "Reddit", "Microsoft" |
| `Status` | Processing status | "Processed", "New", "Updated" |
| `Created_by` | System identifier | "FeedbackCollector v2.0" |
| `Rawfeedback` | Original content | Unprocessed raw text |
| `Sentiment` | AI-analyzed sentiment | "Positive", "Neutral", "Negative" |

### **Fabric Lakehouse Schema**
When written to Microsoft Fabric, data follows the same schema with additional metadata:
- `ingestion_timestamp`: When data was written to Fabric
- `source_collection_id`: Unique identifier for collection batch
- `processing_version`: Schema/processing version

## 💾 Data Storage

### **Local Storage**
- **Location**: `data/` directory
- **Format**: CSV files with timestamp
- **Naming**: `feedback_YYYYMMDD_HHMMSS.csv`
- **Retention**: Automatically manages recent files (keeps latest 5)

### **Microsoft Fabric Lakehouse**
- **Integration**: Direct API-based ingestion
- **Authentication**: Bearer token-based security
- **Processing**: Asynchronous batch uploads
- **Monitoring**: Real-time progress tracking in web interface

## 🔍 Monitoring & Logging

### **Web Interface Logging**
- **Real-time Progress**: Live collection status in progress drawer
- **Detailed Logs**: Timestamped operation logs with color coding
- **Error Tracking**: Comprehensive error reporting and troubleshooting
- **State Persistence**: Progress survives page navigation

### **Backend Logging**
- **Console Output**: Structured logging with timestamps
- **Error Handling**: Graceful degradation with detailed error messages
- **API Monitoring**: Request/response logging for debugging
- **Performance Metrics**: Collection timing and throughput data

## 🛡️ Error Handling & Resilience

### **Network Resilience**
- ✅ **Automatic Retries**: Failed API requests are automatically retried
- ✅ **Graceful Degradation**: Partial failures don't stop entire collection
- ✅ **Connection Recovery**: Handles temporary network issues
- ✅ **Rate Limiting**: Respects API rate limits with backoff

### **Data Integrity**
- ✅ **Validation**: Input validation and sanitization
- ✅ **Error Logging**: Comprehensive error tracking
- ✅ **Rollback Support**: Failed operations can be safely retried
- ✅ **State Recovery**: Progress can be resumed after interruption

### **User Experience**
- ✅ **Progress Persistence**: Collection progress survives navigation
- ✅ **Token Security**: Secure handling of authentication tokens
- ✅ **Clear Feedback**: Detailed error messages and troubleshooting tips
- ✅ **Cancellation Support**: Users can cancel operations safely

## 🚀 API Endpoints

### **Web Interface**
- `GET /` - Main collection interface
- `GET /feedback` - Data viewer and export
- `GET /insights` - Power BI dashboard

### **REST API**
- `POST /api/collect` - Start feedback collection
- `POST /api/write_to_fabric_async` - Write to Fabric Lakehouse
- `GET /api/fabric_progress/{id}` - Monitor Fabric operation progress

## 🤝 Contributing

### **Development Setup**
1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Make changes with appropriate tests
4. Commit: `git commit -m "Add your feature"`
5. Push: `git push origin feature/your-feature`
6. Create Pull Request

### **Code Standards**
- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings for public functions
- Include error handling and logging

## 📄 License

This project is proprietary and confidential. Unauthorized copying, distribution, or modification is prohibited.

---

## 🆘 Support & Troubleshooting

### **Common Issues**
- **Token Errors**: Verify Bearer token validity and permissions
- **Collection Failures**: Check API credentials and network connectivity
- **Progress Loss**: Use the progress drawer to monitor and resume operations

### **Getting Help**
- Check the progress drawer logs for detailed error information
- Verify all environment variables are properly configured
- Ensure API tokens have required permissions and are not expired

**Last Updated**: June 2025 | **Version**: 2.0

The collected feedback is stored with the following schema:

- `Feedback`: Processed main content
- `Area`: Topic area (e.g., Workloads)
- `Sources`: Origin of feedback (Reddit/MS Fabric Community)
- `Impacttype`: Categorized as Bug/Feature Request/Question/Feedback
- `Partner/Customer`: Source identification
- `Customer`: User identification
- `Tag`: Relevant keywords found
- `Created`: Original post timestamp
- `Organization`: Platform name
- `Status`: Processing status
- `Created_by`: System identifier
- `Rawfeedback`: Original unprocessed content
- `Sentiment`: Analyzed sentiment (Positive/Neutral/Negative) based on feedback content

## Storage Location

Data is stored locally in CSV format in the `data` directory. Each collection run creates a new timestamped file:
```
data/feedback_YYYYMMDD_HHMMSS.csv
```

## Logging

The application logs its operations to the console with timestamps and log levels. Important events and errors are captured for monitoring and debugging.

## Error Handling

- Failed API requests are logged and won't crash the application
- Invalid feedback items are skipped and logged
- Connection issues trigger automatic retries
- All exceptions are caught and logged appropriately

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is proprietary and confidential. Unauthorized copying or distribution is prohibited.
