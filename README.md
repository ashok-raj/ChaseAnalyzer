# Chase Statement Analyzer

A comprehensive Python tool for analyzing credit card statements from multiple financial institutions, with advanced categorization and reporting capabilities.

## Supported Statement Formats

The analyzer supports four different credit card statement formats:

### 1250 Format - Bank of America
- **File Pattern**: `eStmt_YYYY-MM-DD.pdf`
- **Statement Month**: Extracted from statement period end date (e.g., "July 25 - August 24, 2025" → "August 2025")
- **Date Format**: Full text dates (e.g., "August 24, 2025")
- **Verification**: Uses "New Balance Total" for statement verification

### 0801 Format - Chase Statements (Format 1)
- **File Pattern**: `YYYYMMDD-statements-0801-.pdf`
- **Statement Month**: Extracted from "Opening/Closing Date" closing date
- **Date Format**: MM/DD/YY (converted to 4-digit year)
- **Verification**: Uses statement balance for verification

### 5136 Format - Chase Statements (Format 2)
- **File Pattern**: `YYYYMMDD-statements-5136-.pdf`
- **Statement Month**: Extracted from "Opening/Closing Date" closing date
- **Date Format**: MM/DD/YY (converted to 4-digit year)
- **Verification**: Uses statement balance for verification

### 8635 Format - Chase Statements (Format 3)
- **File Pattern**: `YYYYMMDD-statements-8635-.pdf`
- **Statement Month**: Extracted from "Opening/Closing Date" closing date
- **Date Format**: MM/DD/YY (converted to 4-digit year)
- **Verification**: Uses net change + payments for verification

## Features

### 🏷️ Master Categorization System
- **Automatic Learning**: New vendors are automatically added to the master categories file
- **Pattern Matching**: Uses intelligent pattern matching for merchant names
- **Interactive Mode**: Allows manual categorization of new vendors
- **Shared Categories**: All formats use the same `categories.master` file

### 📊 Statement Analysis
- **Transaction Extraction**: Purchases, payments, and credits are properly identified
- **Balance Verification**: Automatic verification against statement totals
- **MISC Adjustments**: Automatic adjustment for small discrepancies
- **Multiple Cardholders**: Support for statements with multiple cardholders

### 📅 Smart Date Handling
- **Statement Month Display**: Shows "📅 STATEMENT MONTH: January 2025" for all formats
- **Automatic Date Parsing**: Handles different date formats across statement types
- **Payment Due Date**: Extracts and displays payment due dates where available

### 📈 Reporting
- **Category Breakdown**: Detailed breakdown by spending category
- **Summary Mode**: Condensed view with just totals and categories
- **CSV Export**: All transactions exported to CSV with categories
- **Category Analysis**: Separate `.categories` file with category summaries

## Usage

### Single Statement Analysis
```bash
# Detailed analysis
python3 chase_analysis.py path/to/statement.pdf

# Summary mode only
python3 chase_analysis.py path/to/statement.pdf --summary
```

### Batch Processing
```bash
# Process all statements in all directories
./run_all.sh

# The script processes statements in: 0801/, 1250/, 5136/, 8635/
```

## File Structure

```
ChaseAnalyzer/
├── chase_analysis.py          # Main analyzer script
├── run_all.sh                 # Batch processing script
├── categories.master          # Master categorization rules
├── 0801/                      # Chase format 1 statements
│   ├── *.pdf                  # Input PDF statements
│   ├── *.csv                  # Generated transaction CSVs
│   └── *.categories          # Generated category summaries
├── 1250/                      # Bank of America statements
├── 5136/                      # Chase format 2 statements
├── 8635/                      # Chase format 3 statements
└── utils/                     # Utility scripts
```

## Output Files

For each processed statement, the following files are generated:

### CSV Transaction File
- **Filename**: `[original-name].csv`
- **Content**: All transactions with date, cardholder, merchant, amount, type, category, and original category
- **Format**: Standard CSV with headers

### Category Summary File
- **Filename**: `[original-name].categories`
- **Content**: 
  - Statement metadata (date, totals, transaction count)
  - Category breakdown with transaction counts and amounts
  - Verification status

## Categories

The system uses a comprehensive categorization system:

- **AUTO**: Vehicle-related expenses
- **DINING**: Restaurants and food delivery
- **GROCERIES**: Grocery stores and food shopping
- **MAINTENANCE**: Personal care, household items
- **MEDICAL/HEALTH**: Healthcare expenses
- **SERVICES**: Professional services
- **TRAVEL**: Transportation, hotels, travel expenses
- **UTILITIES**: Phone, internet, electricity bills
- **SHOPPING**: General retail purchases
- **SUBSCRIPTIONS**: Recurring service subscriptions
- **GAS/FUEL**: Gasoline and fuel purchases
- **OTHER**: Uncategorized transactions
- **MISC**: Automatic adjustment category for balance discrepancies

## Requirements

- Python 3.x
- pdfplumber library
- Standard Python libraries (csv, re, os, sys, argparse, datetime, collections)

## Installation

```bash
# Install required dependencies
pip install pdfplumber

# Make run_all.sh executable
chmod +x run_all.sh
```

## Advanced Features

### Interactive Categorization
When running in interactive mode, the system will prompt for categories for new vendors:
```
🆕 New vendor found: STARBUCKS
   Original category: OTHER
   Enter new category (or press Enter to keep original):
   Common categories: GROCERIES, DINING, SERVICES, UTILITIES, MAINTENANCE, AUTO, TRAVEL
   Category: DINING
```

### Balance Verification
The system automatically verifies that extracted transactions match statement totals:
- ✅ **Perfect Match**: All totals match exactly
- ❌ **Mismatch**: Discrepancies are automatically adjusted with MISC category
- 📊 **Multiple Verification**: Checks against different statement totals based on format

### Statement Month Logic
Each format uses appropriate date extraction:
- **1250**: Statement period end date
- **0801/5136/8635**: Opening/Closing date closing date
- **Display**: Consistent "STATEMENT MONTH: Month YYYY" format

## Troubleshooting

### Common Issues
1. **PDF Parsing Errors**: Ensure PDF files are not corrupted or password-protected
2. **Date Format Issues**: The system handles various date formats automatically
3. **Balance Mismatches**: Small discrepancies are automatically adjusted with MISC category
4. **Missing Categories**: New vendors are added to categories.master automatically

### Debug Mode
For detailed debugging information, run without `--summary` flag to see:
- PDF parsing details
- Transaction extraction process
- Pattern matching results
- Balance verification steps

## Contributing

When adding support for new statement formats:
1. Add format detection logic in `detect_statement_format()`
2. Create extraction method for the new format
3. Update verification logic for the format's totals
4. Add format to statement month extraction logic
5. Update documentation