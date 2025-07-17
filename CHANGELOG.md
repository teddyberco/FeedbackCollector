# Changelog

All notable changes to the Microsoft Fabric Workloads Feedback Collector project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.1.0] - 2025-07-17

### Fixed
- **Progress Bar Reset Issues**: Progress bars now properly reset to 0 when starting new collections
  - Fixed stale data guards that were preventing legitimate reset data from being processed
  - Enhanced server-side collection status reset with `collection_status.clear()` to remove all old values
  - Improved frontend stale data detection to allow initialization data through

- **Spinner State Management**: Collection completion properly stops all progress indicators
  - Added completion detection logic in `updateSourceProgress()` function
  - Fixed spinner states that continued running after collection completion
  - Enhanced progress element state handling for completion scenarios

- **Mode Detection on Feedback Page**: Fixed incorrect Online/Offline mode detection
  - Corrected logic error in `fabric_sql_connected` detection (changed `and` to `or`)
  - Fixed session state management to clear stale flags when in offline mode
  - Improved bearer token validation for proper mode determination

- **JSON Parsing Errors**: Resolved "Failed to load filtered data" errors
  - Added `clean_nan_values()` function to handle NaN values before JSON serialization
  - Enhanced ADO data collection with `safe_get()` function to prevent NaN values at source
  - Fixed all AJAX endpoints to properly clean data before sending responses

- **Collection Progress Synchronization**: Fixed issues where progress elements jumped to final values
  - Enhanced stale data guards with more sophisticated detection logic
  - Improved server-sent events filtering to prevent old data from interfering with new collections
  - Added completion detection to handle final progress updates correctly

### Enhanced
- **Error Handling**: Improved error handling throughout the application
  - Better handling of NaN values in data processing
  - Enhanced session state management for Fabric connections
  - Improved logging for debugging progress and state issues

- **Data Processing**: Enhanced data cleaning and validation
  - Added comprehensive NaN value cleaning for JSON serialization
  - Improved ADO data field validation with safe value extraction
  - Enhanced text processing for better data quality

### Technical Improvements
- Added `clean_nan_values()` recursive function for data sanitization
- Enhanced `updateSourceProgress()` with completion detection
- Improved `updateCollectionStatus()` with sophisticated stale data guards
- Fixed `fabric_sql_connected` logic in feedback viewer route
- Added session flag clearing for proper offline mode handling

## [4.0.0] - 2025-06-15

### Added
- **Fabric SQL Database Integration**: Direct connection to Fabric SQL Database for state persistence
- **Enhanced State Management**: Complete feedback lifecycle tracking with user context
- **Collaborative Workflow**: Multiple users can work on feedback simultaneously
- **Advanced Analytics**: State-based analytics and workflow insights
- **ODBC Driver Support**: Multiple driver compatibility for broad deployment

### Changed
- Major architecture overhaul for enterprise-scale deployment
- Enhanced text processing pipeline for better data quality
- Improved authentication system with Bearer token support

### Fixed
- Various stability and performance improvements
- Enhanced error handling and recovery mechanisms

## [3.0.0] - 2025-04-10

### Added
- Multi-source data collection (Reddit, GitHub, Fabric Community, Azure DevOps)
- Advanced categorization and sentiment analysis
- Real-time progress monitoring
- CSV export functionality

### Changed
- Complete UI redesign with Bootstrap 5
- Enhanced filtering and search capabilities

## [2.0.0] - 2025-02-20

### Added
- Web-based interface
- Basic state management
- Filtering capabilities

## [1.0.0] - 2025-01-15

### Added
- Initial release with basic feedback collection
- Reddit API integration
- Simple categorization
