# Changelog

All notable changes to the Chase Statement Analyzer project.

## [Current Version] - 2025-01-09

### Added
- **Multi-Format Support**: Added support for 4 different statement formats:
  - 1250: Bank of America statements
  - 0801: Chase statements (format 1)
  - 5136: Chase statements (format 2)  
  - 8635: Chase statements (format 3)

### Enhanced
- **Statement Month Display**: All formats now show "📅 STATEMENT MONTH: Month YYYY" instead of raw date ranges
  - 1250 format: Uses statement period end date
  - 0801/5136/8635 formats: Use "Opening/Closing Date" closing date
  - Automatic 2-digit to 4-digit year conversion for Chase formats

- **Date Extraction Logic**: 
  - Payment Due Date extraction for Bank of America (1250) format
  - Opening/Closing Date extraction for Chase formats (0801, 5136, 8635)
  - Smart date parsing with format detection

- **Verification System**: Format-specific verification logic
  - 1250: Uses "New Balance Total" 
  - 0801/5136: Uses statement balance
  - 8635: Uses net change + payments
  - Automatic MISC category adjustments for small discrepancies

### Improved
- **Master Categorization**: Enhanced pattern matching for vendor categorization
- **Batch Processing**: Updated run_all.sh to process all 4 statement formats
- **Error Handling**: Improved parsing robustness across different PDF formats
- **Documentation**: Comprehensive README with usage examples and format specifications

### Technical Changes
- Enhanced `detect_statement_format()` method to identify all 4 formats
- Added format-specific transaction extraction methods
- Unified `get_statement_month()` logic across all formats
- Updated display logic for consistent formatting
- Improved PDF text parsing with better error handling

### Files Modified
- `chase_analysis.py`: Core analyzer with multi-format support
- `run_all.sh`: Updated to process all directories (0801, 1250, 5136, 8635)
- `README.md`: Comprehensive documentation (new)
- `CHANGELOG.md`: Project history documentation (new)

### Bug Fixes
- Fixed statement parsing conflicts between different formats
- Resolved regex pattern matching issues
- Improved credit vs purchase transaction handling
- Enhanced balance verification accuracy

## Previous Versions

### Legacy Version
- Supported basic 0801 and 5136 Chase statement formats
- Basic categorization system
- Manual processing workflow
- Limited documentation