# Quick Start Guide

## Basic Usage

### Analyze a Single Statement
```bash
# Full detailed analysis
python3 chase_analysis.py path/to/statement.pdf

# Summary view only
python3 chase_analysis.py path/to/statement.pdf --summary
```

### Process All Statements
```bash
# Process all PDFs in all directories (0801, 1250, 5136, 8635)
./run_all.sh
```

## Expected Output

### Summary Mode Example
```
📅 STATEMENT MONTH: January 2025
📊 STATEMENT TOTALS
==================================================
Statement Total: $4,107.99
Calculated Total: $4,107.99
Status: ✅ MATCH

================================================================================
CATEGORY BREAKDOWN TABLE
================================================================================
Category             Count    Amount          % of Total  
--------------------------------------------------------------------------------
OTHER                23       $3,147.69       76.6       %
UTILITIES            3        $540.96         13.2       %
SHOPPING             5        $245.38         6.0        %
SUBSCRIPTIONS        4        $103.96         2.5        %
TRAVEL/DINING        2        $70.00          1.7        %
--------------------------------------------------------------------------------
TOTAL                37       $4,107.99       100.0      %
================================================================================
```

## Directory Structure Setup

Organize your statement PDFs in format-specific directories:

```
ChaseAnalyzer/
├── 0801/                      # Chase statements ending in -0801-
│   ├── 20250106-statements-0801-.pdf
│   └── 20250206-statements-0801-.pdf
├── 1250/                      # Bank of America statements
│   ├── eStmt_2025-01-24.pdf
│   └── eStmt_2025-02-24.pdf
├── 5136/                      # Chase statements ending in -5136-
│   ├── 20250114-statements-5136-.pdf
│   └── 20250214-statements-5136-.pdf
└── 8635/                      # Chase statements ending in -8635-
    ├── 20250113-statements-8635-.pdf
    └── 20250213-statements-8635-.pdf
```

## File Naming Conventions

### Chase Formats (0801, 5136, 8635)
- **Pattern**: `YYYYMMDD-statements-XXXX-.pdf`
- **Example**: `20250106-statements-0801-.pdf`
- **Date**: Represents the statement closing date

### Bank of America Format (1250)
- **Pattern**: `eStmt_YYYY-MM-DD.pdf`  
- **Example**: `eStmt_2025-01-24.pdf`
- **Date**: Represents the statement closing date

## Command Line Options

```bash
# Basic analysis
python3 chase_analysis.py statement.pdf

# With specific master categories file
python3 chase_analysis.py -m categories.master statement.pdf

# Generate CSV output
python3 chase_analysis.py --csv statement.pdf

# Summary mode only
python3 chase_analysis.py --summary statement.pdf

# Combine options
python3 chase_analysis.py -m categories.master --csv --summary statement.pdf
```

## Generated Files

For each processed statement, you'll get:

1. **CSV File**: `statement-name.csv`
   - All transactions with categories
   - Headers: date, cardholder, merchant, amount, type, category, original_category

2. **Categories File**: `statement-name.categories` 
   - Summary analysis with category breakdown
   - Statement metadata and verification status

## Tips

1. **First Run**: The system will create `categories.master` if it doesn't exist
2. **New Vendors**: System automatically learns and adds new vendor patterns
3. **Balance Issues**: Small discrepancies are automatically adjusted with MISC category
4. **Interactive Mode**: Remove `--summary` flag to see detailed processing steps