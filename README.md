# Microsoft Fabric Workloads Feedback Collector

An automated tool that collects feedback about Microsoft Fabric Workloads from multiple sources and stores it in CSV format.

## Features

- Collects feedback from multiple sources:
  - Reddit (r/MicrosoftFabric)
  - Microsoft Fabric Community Forums
  - GitHub Discussions (Microsoft-Fabric-workload-development-sample)
- Filters content based on relevant keywords:
  - "workload hub"
  - "workloads"
  - "Workload Development Kit"
- Automatically categorizes feedback by impact type and sentiment
- Stores data in CSV format locally
- Collects feedback on demand

## Prerequisites

- Python 3.8 or higher
- Reddit API credentials (see below for setup instructions)
- GitHub Personal Access Token with repo scope

## Setup

1. Clone the repository:
```bash
git clone [repository-url]
cd [repository-name]
```

2. Install dependencies:
```bash
pip install -r src/requirements.txt
```

3. Create environment file:
```bash
cp src/.env.template src/.env
```

4. Configure environment variables:
   - Edit `src/.env` with:
     * Reddit API credentials:
       1. Go to reddit.com/prefs/apps
       2. Create a new application (type: script)
       3. Copy the client_id and client_secret
       4. Add them to your .env file
     * GitHub token:
       1. Go to github.com/settings/tokens
       2. Generate a new token with 'repo' scope
       3. Add the token to your .env file
       4. Enable SAML SSO for the 'microsoft' organization:
          - Go back to github.com/settings/tokens
          - Find your token and click "Configure SSO"
          - Enable SSO for "microsoft" organization

## Usage

### Run

To collect feedback:

```bash
python src/main.py
```

This will:
1. Collect feedback from Reddit and MS Fabric Community
2. Analyze sentiment of each feedback item
3. Save results to a timestamped CSV file in the data directory

## Data Schema

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
