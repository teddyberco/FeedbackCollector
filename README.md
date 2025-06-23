# Microsoft Fabric Workloads Feedback Collector

A comprehensive web-based tool that collects feedback about Microsoft Fabric Workloads from multiple sources, provides intelligent categorization with domain analysis, and offers seamless integration with Microsoft Fabric Lakehouse for analytics.

## 🌟 Features

### **Multi-Source Data Collection**
- **Reddit**: r/MicrosoftFabric community discussions
- **Microsoft Fabric Community**: Official forums and discussions
- **GitHub Discussions**: Microsoft-Fabric-workload-development-sample repository
- **Azure DevOps**: Work items and task feedback with advanced text cleaning

### **Enhanced Intelligence**
- **Domain-Aware Categorization**: Maps feedback to 6 cross-cutting business domains
- **Smart Audience Detection**: Automatically identifies Developer/Customer/ISV feedback
- **Enhanced Text Processing**: Removes CSS, HTML, and email content from ADO items
- **Duplicate Detection**: Identifies repeating requests with 30% similarity threshold
- **Priority Classification**: Automatic priority assignment based on content analysis
- **Confidence Scoring**: Provides categorization confidence levels

### **Web Interface & User Experience**
- **Modern Web UI**: Bootstrap-powered responsive interface
- **Enhanced Feedback Viewer**: Advanced filtering by category, audience, domain, and priority
- **Statistical Insights**: Comprehensive analytics with cross-tabulation matrices
- **Progress Drawer**: Real-time collection monitoring with detailed logging
- **Token Management**: Secure Bearer token handling for Fabric integration

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
cp src/.env.template src/.env
# Edit src/.env with your API credentials
```

### 3. **Launch Web Interface**
```bash
cd src
python run_web.py
```

### 4. **Access Application**
- Open browser to `http://localhost:5000`
- Start collecting feedback with real-time progress tracking
- View collected data at `/feedback` endpoint with enhanced filtering
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

## 📊 Enhanced Features

### **Intelligent Categorization System**
- **Primary Categories**: 7 main categories including Developer Experience, Customer Experience, Technical Issues
- **Subcategories**: Detailed subcategorization for precise classification
- **Domain Mapping**: 6 cross-cutting domains:
  - Governance & Compliance
  - User Experience & Design
  - Authentication & Security
  - Performance & Scalability
  - Integration & Interoperability
  - Analytics & Reporting

### **Advanced Text Processing**
- **CSS/HTML Removal**: Cleans ADO feedback from formatting artifacts
- **Email Filtering**: Removes email headers, signatures, and threading
- **Smart Text Extraction**: Preserves meaningful content while removing noise
- **Description Pattern Removal**: Eliminates redundant "Description:" prefixes

### **Statistical Analysis**
- **Category Distribution**: Visual breakdown of feedback by category
- **Audience Segmentation**: Developer vs Customer vs ISV analysis
- **Priority Matrix**: High/Medium/Low priority distribution
- **Domain Coverage**: Cross-domain impact analysis
- **Confidence Metrics**: Categorization reliability scoring

## 📁 Project Structure
```
FeedbackCollector/
├── src/
│   ├── app.py                    # Main Flask application with enhanced ADO
│   ├── collectors.py             # Data collection with text cleaning
│   ├── fabric_writer.py          # Fabric Lakehouse integration
│   ├── ado_client.py             # Azure DevOps integration
│   ├── config.py                 # Configuration management
│   ├── run_web.py               # Web server launcher
│   ├── utils.py                 # Enhanced categorization & text processing
│   ├── keywords.json            # Domain and category keywords
│   ├── requirements.txt         # Python dependencies
│   ├── .env.template           # Environment template
│   └── templates/               # HTML templates
│       ├── index.html           # Main interface
│       ├── feedback_viewer.html # Enhanced data viewer
│       └── insights_page.html   # Power BI dashboard
├── data/                        # CSV output files (gitignored)
├── .gitignore                   # Enhanced git exclusions
├── README.md                    # This file
└── Final_Implementation_Summary.md # Detailed feature documentation
```

## 📋 Enhanced Data Schema

### **CSV Output Format**
Each feedback item contains the following fields:

| Field | Description | Example |
|-------|-------------|---------|
| `Feedback` | Cleaned, processed content | "Workload development challenges..." |
| `Feedback_Gist` | Smart summary of feedback | "Issue with workload deployment" |
| `Area` | Topic area classification | "Workloads", "Development" |
| `Sources` | Origin platform | "Azure DevOps", "Reddit", "GitHub" |
| `Audience` | Target audience | "Developer", "Customer", "ISV" |
| `Enhanced_Category` | Primary category | "Developer Experience Requests" |
| `Subcategory` | Detailed subcategory | "Development Tools" |
| `Priority` | Assigned priority | "high", "medium", "low" |
| `Domains` | Related business domains | ["Performance", "Security"] |
| `Primary_Domain` | Main domain | "Performance & Scalability" |
| `Categorization_Confidence` | Classification confidence | 0.85 |
| `Impacttype` | Issue classification | "Bug", "Feature Request" |
| `Sentiment` | AI-analyzed sentiment | "Positive", "Neutral", "Negative" |
| `Created` | Original timestamp | "2025-06-20 15:30:45" |
| `Organization` | Platform/org name | "ADO/FabricPlatform" |

## 🔍 Monitoring & Analytics

### **Built-in Analytics**
- **Category Statistics**: Distribution charts and percentages
- **Audience Breakdown**: Developer/Customer/ISV segmentation
- **Priority Analysis**: Impact assessment across categories
- **Domain Coverage**: Cross-functional impact visualization
- **Duplicate Detection**: Identifies patterns in repeated feedback
- **Trend Analysis**: Time-based feedback patterns

### **Web Interface Features**
- **Advanced Filtering**: Multi-dimensional filtering capabilities
- **Export Options**: CSV export with selected filters
- **Real-time Updates**: Live data refresh capabilities
- **Statistical Summaries**: At-a-glance metrics and KPIs

## 🛡️ Error Handling & Resilience

### **Enhanced Processing**
- ✅ **Text Cleaning Pipeline**: Robust handling of malformed HTML/CSS
- ✅ **Email Content Filtering**: Removes sensitive email information
- ✅ **Smart Fallbacks**: Graceful degradation for categorization
- ✅ **Confidence Thresholds**: Flags low-confidence classifications

### **Data Quality**
- ✅ **Duplicate Detection**: Prevents redundant entries
- ✅ **Content Validation**: Ensures meaningful feedback extraction
- ✅ **Source Verification**: Validates data source integrity
- ✅ **Encoding Handling**: Manages various text encodings

## 🚀 API Endpoints

### **Web Interface**
- `GET /` - Main collection interface
- `GET /feedback` - Enhanced data viewer with statistics
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
- Maintain backwards compatibility

## 📄 License

This project is proprietary and confidential. Unauthorized copying, distribution, or modification is prohibited.

---

## 🆘 Support & Troubleshooting

### **Common Issues**
- **ADO Text Issues**: Verify text cleaning is working in utils.py
- **Categorization Errors**: Check keywords.json for domain mappings
- **Token Errors**: Verify Bearer token validity and permissions
- **Collection Failures**: Check API credentials and network connectivity

### **Getting Help**
- Check the progress drawer logs for detailed error information
- Verify all environment variables are properly configured
- Ensure API tokens have required permissions and are not expired
- Review Final_Implementation_Summary.md for detailed feature documentation

**Last Updated**: June 2025 | **Version**: 3.0

### **Key Enhancements in v3.0**
- Domain-aware categorization system
- Enhanced ADO text processing
- Advanced audience detection
- Statistical analysis and insights
- Duplicate request identification
- Improved UX with comprehensive filtering
