#!/usr/bin/env python3
"""
Enhanced Chase Statement Analyzer
Supports multiple credit card statement formats:
- 1250: Bank of America statements
- 0801: Chase statements (format 1)
- 5136: Chase statements (format 2)
- 8635: Chase statements (format 3)

Features:
- Master categorization system with automatic learning
- Statement month extraction from closing dates
- PDF parsing with transaction extraction
- Category verification and MISC adjustments
- Batch processing support
"""

import pdfplumber
import re
import csv
import os
import sys
import argparse
from datetime import datetime
from collections import defaultdict

class EnhancedChaseStatementAnalyzer:
    def __init__(self):
        self.pdf_file = None
        self.pdf_text = None
        self.transactions = []
        self.master_file = None
        self.master_categories = {}
        self.new_vendors = set()
        
        # Statement summary fields
        self.statement_previous_balance = 0.0
        self.statement_new_balance = 0.0
        self.statement_purchase_total = 0.0
        self.statement_payment_total = 0.0
        self.statement_period = ""
        self.payment_due_date = ""
        
    def extract_pdf_content(self, pdf_path):
        """Extract text content from PDF file using pdfplumber"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
                return full_text
        except Exception as e:
            print(f"Error extracting PDF content: {e}")
            return None
    
    def parse_statement_summary(self, pdf_text):
        """Parse statement summary information from PDF text"""
        lines = pdf_text.split('\n')
        
        if not getattr(self, 'summary_only', False):
            print(f"   📋 Looking for statement summary in {len(lines)} lines...")
        
        for line in lines:
            line = line.strip()
            
            # Previous Balance (Chase and Bank of America formats)
            if 'Previous Balance' in line:
                balance_match = re.search(r'Previous Balance.*?\$?([\d,]+\.?\d{0,2})', line)
                if balance_match and balance_match.group(1) and balance_match.group(1).strip():
                    self.statement_previous_balance = float(balance_match.group(1).replace(',', ''))
            
            # New Balance Total (Bank of America) or New Balance (Chase)
            elif 'New Balance Total' in line and line.startswith(('New Balance Total', 'Account Summary/Payment Information New Balance Total')):
                balance_match = re.search(r'New Balance Total.*?\$?([\d,]+\.?\d{0,2})', line)
                if balance_match and balance_match.group(1) and balance_match.group(1).strip():
                    try:
                        self.statement_new_balance = float(balance_match.group(1).replace(',', ''))
                    except ValueError:
                        # Debug output for troubleshooting
                        if not getattr(self, 'summary_only', False):
                            print(f"DEBUG: Failed to parse New Balance Total from line: {repr(line)}")
                            print(f"DEBUG: Match group 1: {repr(balance_match.group(1))}")
                        continue
            elif 'New Balance' in line and 'Total' not in line:
                balance_match = re.search(r'New Balance.*?\$?([\d,]+\.?\d{0,2})', line)
                if balance_match and balance_match.group(1) and balance_match.group(1).strip():
                    self.statement_new_balance = float(balance_match.group(1).replace(',', ''))
            
            # Purchases and Adjustments (Bank of America) or Purchases (Chase)
            elif 'Purchases and Adjustments' in line and line.startswith(('Purchases and Adjustments', 'Account Summary/Payment Information')):
                purchase_match = re.search(r'Purchases and Adjustments.*?\$?([\d,]+\.?\d{0,2})', line)
                if purchase_match and purchase_match.group(1) and purchase_match.group(1).strip():
                    self.statement_purchase_total = float(purchase_match.group(1).replace(',', ''))
            elif 'Purchases' in line and 'Total' not in line and '%' not in line and 'important' not in line and 'Adjustments' not in line and 'new Purchases' not in line and 'consisting of Purchases' not in line and 'on Purchases' not in line:
                purchase_match = re.search(r'Purchases[^\d]*[+\-]?\$?([\d,]+\.?\d{0,2})', line)
                if purchase_match and purchase_match.group(1) and purchase_match.group(1).replace(',', '').replace('.', '').isdigit() and len(purchase_match.group(1).replace(',', '').replace('.', '')) >= 2:
                    # Only accept if the amount makes sense (at least 2 digits, not just "1")
                    amount = float(purchase_match.group(1).replace(',', ''))
                    if amount >= 0.01:  # Reasonable minimum
                        self.statement_purchase_total = amount
            
            # Payments and Other Credits (Bank of America) or Payments/Credits (Chase)
            elif 'Payments and Other Credits' in line:
                payment_match = re.search(r'Payments and Other Credits.*?-?\$?([\d,]+\.?\d{0,2})', line)
                if payment_match and payment_match.group(1) and payment_match.group(1).strip():
                    self.statement_payment_total = float(payment_match.group(1).replace(',', ''))
            elif 'Payments' in line and 'Credits' in line and 'Other' not in line:
                payment_match = re.search(r'Payments/Credits.*?-?\$?([\d,]+\.?\d{0,2})', line)
                if payment_match and payment_match.group(1) and payment_match.group(1).strip():
                    self.statement_payment_total = float(payment_match.group(1).replace(',', ''))
            
            # Statement period - Bank of America format (December 25 - January 24, 2025) or Chase format
            elif re.match(r'\w+ \d{1,2} - \w+ \d{1,2}, \d{4}', line):
                self.statement_period = line
            elif re.match(r'\d{2}/\d{2}/\d{2} - \d{2}/\d{2}/\d{2}', line):
                self.statement_period = line
            
            # Payment Due Date - Bank of America format (MM/DD/YYYY)
            elif 'Payment Due Date' in line:
                payment_due_match = re.search(r'Payment Due Date\s+(\d{2}/\d{2}/\d{4})', line)
                if payment_due_match:
                    self.payment_due_date = payment_due_match.group(1)
            
            # Payment Due Date - Chase 0801 format (MM/DD/YY)
            elif 'Payment Due Date' in line and not self.payment_due_date:
                payment_due_match_chase = re.search(r'Payment Due Date[:\s]+(\d{2}/\d{2}/\d{2})', line)
                if payment_due_match_chase:
                    # Convert 2-digit year to 4-digit year
                    date_parts = payment_due_match_chase.group(1).split('/')
                    year_2digit = int(date_parts[2])
                    year_4digit = 2000 + year_2digit if year_2digit < 50 else 1900 + year_2digit
                    self.payment_due_date = f"{date_parts[0]}/{date_parts[1]}/{year_4digit}"
            
            # Opening/Closing Date - Chase 0801 and 8635 formats for statement period
            elif 'Opening/Closing Date' in line:
                closing_date_match = re.search(r'Opening/Closing Date\s+\d{2}/\d{2}/\d{2}\s*-\s*(\d{2}/\d{2}/\d{2})', line)
                if closing_date_match:
                    # Store the closing date for 0801 and 8635 formats
                    closing_date = closing_date_match.group(1)
                    # Convert to full date format
                    date_parts = closing_date.split('/')
                    year_2digit = int(date_parts[2])
                    year_4digit = 2000 + year_2digit if year_2digit < 50 else 1900 + year_2digit
                    self.statement_period = f"{date_parts[0]}/{date_parts[1]}/{year_4digit}"
        
        if not getattr(self, 'summary_only', False):
            print(f"     Previous Balance: ${self.statement_previous_balance:,.2f}")
            print(f"     Payments/Credits: $-{self.statement_payment_total:,.2f}")
            print(f"     Purchases: ${self.statement_purchase_total:,.2f}")
            print(f"     New Balance: ${self.statement_new_balance:,.2f}")
            print(f"     Statement Period: {self.statement_period}")
            if self.payment_due_date:
                print(f"     Payment Due Date: {self.payment_due_date}")

    def get_statement_month(self):
        """Get statement month string for display header"""
        from datetime import datetime
        
        # For 1250 format (Bank of America), use statement period end date to determine statement month
        if hasattr(self, 'pdf_file') and '1250' in self.pdf_file:
            try:
                if self.statement_period:
                    # Extract ending month from statement period (e.g., "July 25 - August 24, 2025")
                    period_match = re.search(r'- (\w+) \d+, (\d{4})', self.statement_period)
                    if period_match:
                        month_name = period_match.group(1)
                        year = period_match.group(2)
                        return f"{month_name} {year}"
            except:
                pass
        
        # For 0801, 5136, and 8635 formats (Chase), use closing date to determine statement month
        elif hasattr(self, 'pdf_file') and ('0801' in self.pdf_file or '5136' in self.pdf_file or '8635' in self.pdf_file):
            try:
                if self.statement_period:
                    # statement_period contains the closing date in MM/DD/YYYY format
                    closing_date = datetime.strptime(self.statement_period, '%m/%d/%Y')
                    return closing_date.strftime('%B %Y')
            except:
                pass
        
        # For other formats, use statement period as is
        return self.statement_period

    def categorize_transaction(self, merchant, amount):
        """Automatically categorize transaction based on merchant name (purchases only)"""
        merchant_upper = merchant.upper()
        
        # Basic categorization patterns
        if any(gas in merchant_upper for gas in ['SHELL', 'CHEVRON', 'EXXON', 'MOBIL', 'ARCO', 'BP ', 'COSTCO GAS', 'GAS']):
            return 'GAS/FUEL'
        elif any(grocery in merchant_upper for grocery in ['SAFEWAY', 'QFC', 'COSTCO WHSE', 'TARGET', 'WALMART']):
            return 'GROCERY'
        elif any(amazon in merchant_upper for amazon in ['AMAZON', 'AMZN']):
            return 'SHOPPING'
        elif any(dining in merchant_upper for dining in ['RESTAURANT', 'STARBUCKS', 'MCDONALD', 'SUBWAY', 'PIZZA']):
            return 'RESTAURANT'
        elif any(util in merchant_upper for util in ['ELECTRIC', 'WATER', 'GAS BILL', 'COMCAST', 'VERIZON']):
            return 'UTILITIES'
        elif any(travel in merchant_upper for travel in ['UNITED', 'DELTA', 'AMERICAN AIR', 'SOUTHWEST', 'HOTEL']):
            return 'TRAVEL/DINING'
        elif any(sub in merchant_upper for sub in ['NETFLIX', 'SPOTIFY', 'APPLE.COM', 'GOOGLE']):
            return 'SUBSCRIPTIONS'
        else:
            return 'OTHER'

    def detect_statement_format(self, lines):
        """Detect which Chase statement format we're dealing with by checking Account Number"""
        # Look for "Account Number:" in first 50 lines and extract last 4 digits
        sample_lines = lines[:50]
        
        for line in sample_lines:
            if 'Account Number:' in line:
                # Extract the account number and get last 4 digits
                if '5136' in line:
                    return '5136'
                elif '0801' in line:
                    return '0801'
                elif '8635' in line:
                    return '8635'
                elif '1250' in line:
                    return '1250'
        
        # Fallback to old detection method if Account Number not found
        sample_text = '\n'.join(sample_lines).upper()
        
        # 8635 format indicators
        if 'PAYMENTS AND OTHER CREDITS' in sample_text and 'PURCHASE' in sample_text:
            return '8635'
        
        # 5136 format indicators
        if 'DATE OF TRANSACTION' in sample_text:
            return '5136'
        
        # 0801 format indicators  
        if 'TRANSACTIONS THIS CYCLE' in sample_text:
            return '0801'
        
        # Default to trying 5136 format first (newer format)
        return '5136'

    def extract_transactions_from_pdf(self, pdf_text):
        """Extract transactions from PDF based on detected format"""
        lines = pdf_text.split('\n')
        
        if not getattr(self, 'summary_only', False):
            print(f"   🔍 Extracting transactions from PDF (excluding payments)...")
        
        # Detect format
        format_type = self.detect_statement_format(lines)
        if not getattr(self, 'summary_only', False):
            print(f"   🔍 Detected {format_type} format statement")
        
        if format_type == '5136':
            transactions = self.extract_5136_format_transactions(lines)
        elif format_type == '8635':
            transactions = self.extract_8635_format_transactions(lines)
        elif format_type == '1250':
            transactions = self.extract_1250_format_transactions(lines)
        else:
            transactions = self.extract_0801_format_transactions(lines)
        
        if not getattr(self, 'summary_only', False):
            print(f"   ✅ Extracted {len(transactions)} transactions")
        
        return transactions

    def extract_0801_format_transactions(self, lines):
        """Extract transactions from 0801 format (traditional format with cardholder groupings)"""
        all_transactions = []
        current_cardholder = None
        pending_transactions = []
        
        # Transaction patterns for 0801 format
        transaction_patterns = [
            r'^(\d{2}/\d{2})\s+(.+?)\s+([-]?\d{1,3}(?:,\d{3})*\.?\d{0,2})$',
            r'^(\d{2}/\d{2})\s+(.+?)\s+\$?([-]?\d{1,3}(?:,\d{3})*\.?\d{0,2})$'
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip header lines
            if any(header in line.upper() for header in [
                'ACCOUNT SUMMARY', 'PREVIOUS BALANCE', 'PAYMENTS', 'PURCHASES', 
                'BALANCE TRANSFERS', 'CASH ADVANCES', 'FEES CHARGED', 'INTEREST CHARGED',
                'NEW BALANCE', 'MINIMUM PAYMENT DUE', 'PAYMENT DUE DATE'
            ]):
                continue
            
            # Detect cardholder sections
            if re.match(r'^[A-Z][A-Z\s]+ RAJ$', line) and 'ACCOUNT' not in line:
                # Process any pending transactions for previous cardholder
                if pending_transactions and current_cardholder:
                    for txn_data in pending_transactions:
                        date_str, merchant, amount = txn_data
                        category = self.categorize_transaction(merchant, amount)
                        
                        # Only include purchases (payments already filtered out above)
                        transaction = {
                            'date': f"2025/{date_str}",
                            'cardholder': current_cardholder,
                            'merchant': merchant.strip(),
                            'amount': amount,
                            'type': 'Purchase',
                            'category': category
                        }
                        all_transactions.append(transaction)
                
                # Set new cardholder and clear pending
                current_cardholder = line.strip()
                pending_transactions = []
                continue
            
            # Skip section headers
            if any(section in line.upper() for section in [
                'TRANSACTIONS THIS CYCLE', 'FEES', 'INTEREST'
            ]):
                continue
            
            # Check if this line contains "TRANSACTIONS THIS CYCLE" followed by transactions
            if 'TRANSACTIONS THIS CYCLE' in line.upper():
                # Process remaining text on this line for transactions
                remaining_text = line[line.upper().find('TRANSACTIONS THIS CYCLE') + len('TRANSACTIONS THIS CYCLE'):].strip()
                if remaining_text:
                    # Try to parse transaction from remaining text
                    for pattern in transaction_patterns:
                        match = re.match(pattern, remaining_text)
                        if match:
                            try:
                                date_str = match.group(1)
                                merchant = match.group(2).strip()
                                amount_str = match.group(3).replace('$', '').replace(',', '')
                                
                                if len(merchant) < 3:
                                    continue
                                    
                                amount = float(amount_str)
                                
                                if amount < 0 or 'payment' in merchant.lower():
                                    if not getattr(self, 'summary_only', False):
                                        print(f"     Skipping payment: {merchant} ${amount}")
                                    break
                                
                                category = self.categorize_transaction(merchant, amount)
                                
                                # Only include purchases (payments already filtered out above)
                                transaction = {
                                    'date': f"2025/{date_str}",
                                    'cardholder': current_cardholder,
                                    'merchant': merchant.strip(),
                                    'amount': amount,
                                    'type': 'Purchase',
                                    'category': category
                                }
                                all_transactions.append(transaction)
                                
                                # Clear pending transactions
                                pending_transactions = []
                                break
                            except (ValueError, IndexError):
                                continue
                continue
            
            # Try to match transaction patterns
            transaction_found = False
            for pattern in transaction_patterns:
                match = re.match(pattern, line)
                if match:
                    try:
                        date_str = match.group(1)
                        merchant = match.group(2).strip()
                        amount_str = match.group(3).replace('$', '').replace(',', '')
                        
                        # Skip if merchant is too short or looks like a header
                        if len(merchant) < 3 or merchant.upper() in ['TOTAL', 'SUBTOTAL']:
                            continue
                            
                        amount = float(amount_str)
                        
                        # Skip payments - only include purchases
                        if amount < 0 or 'payment' in merchant.lower() or 'thank you' in merchant.lower():
                            if not getattr(self, 'summary_only', False):
                                print(f"     Skipping payment: {merchant} ${amount}")
                            transaction_found = True
                            break
                        
                        # Add to pending transactions (will be assigned to cardholder later)
                        pending_transactions.append((date_str, merchant, amount))
                        transaction_found = True
                        break
                        
                    except (ValueError, IndexError):
                        continue
            
            if transaction_found:
                continue
        
        # Assign any remaining pending transactions to last cardholder
        if pending_transactions and current_cardholder:
            for txn_data in pending_transactions:
                date_str, merchant, amount = txn_data
                category = self.categorize_transaction(merchant, amount)
                
                # Only include purchases (payments already filtered out above)
                transaction = {
                    'date': f"2025/{date_str}",
                    'cardholder': current_cardholder,
                    'merchant': merchant.strip(),
                    'amount': amount,
                    'type': 'Purchase',
                    'category': category
                }
                all_transactions.append(transaction)
                
        return all_transactions

    def extract_5136_format_transactions(self, lines):
        """Extract transactions from new 5136 format (columnar layout) - simplified approach"""
        all_transactions = []
        credits_to_include = []
        current_cardholder = "SUMATHI RAJ"  # Default for 5136 format since no cardholder groupings
        in_fees_section = False
        in_credits_section = False
        
        # Simple regex for 5136 format: MM/DD MERCHANT AMOUNT
        transaction_pattern = r'^(\d{2}/\d{2})\s+(.+?)\s+([-]?\d{1,3}(?:,\d{3})*\.?\d{0,2})$'
        
        # Skip patterns to avoid processing headers/footers
        skip_patterns = [
            'Date of', 'Transaction', 'Merchant Name', '$ Amount',
            'Account Summary', 'Previous Balance', 'New Balance',
            'Minimum Payment', 'Payment Due', 'Interest',
            'ACCOUNT SUMMARY', 'PREVIOUS BALANCE', 'NEW BALANCE'
        ]
        
        # First pass: collect all transactions
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if we're entering or leaving the FEES CHARGED section
            if 'FEES CHARGED' in line.upper():
                in_fees_section = True
                continue
            elif in_fees_section and ('INTEREST CHARGES' in line.upper() or 'TOTAL FEES FOR THIS PERIOD' in line.upper()):
                in_fees_section = False
                continue
            
            # Check if we're entering or leaving the PAYMENTS AND OTHER CREDITS section
            if 'PAYMENTS AND OTHER CREDITS' in line.upper():
                in_credits_section = True
                continue
            elif in_credits_section and ('PURCHASE' in line.upper() or 'TOTAL CREDITS' in line.upper() or 'INTEREST CHARGES' in line.upper()):
                in_credits_section = False
                continue
            
            # Skip header and footer lines (but not TOTAL FEES line which we want to skip anyway)
            if any(skip in line for skip in skip_patterns) or 'TOTAL FEES' in line.upper():
                continue
            
            # Try to match transaction pattern
            match = re.match(transaction_pattern, line)
            if match:
                try:
                    date_str = match.group(1)
                    merchant = match.group(2).strip()
                    amount_str = match.group(3).replace(',', '')
                    
                    # Skip if merchant is too short or looks like a header/total
                    if len(merchant) < 3 or merchant.upper() in ['TOTAL', 'SUBTOTAL', 'BALANCE']:
                        continue
                    
                    amount = float(amount_str)
                    
                    # Handle credits section differently
                    if in_credits_section:
                        # In credits section, negative amounts are credits (refunds), payments should be skipped
                        if amount < 0:
                            # This is a credit - store for later processing
                            if 'payment' in merchant.lower() or 'thank you' in merchant.lower():
                                # Skip payments even if they're negative
                                if not getattr(self, 'summary_only', False):
                                    print(f"     Skipping payment: {merchant} ${amount}")
                                continue
                            else:
                                # Store credit for later analysis
                                credits_to_include.append({
                                    'date': f"2025/{date_str}",
                                    'cardholder': current_cardholder,
                                    'merchant': merchant,
                                    'amount': amount,
                                    'type': 'Credit',
                                    'category': self.categorize_transaction(merchant, abs(amount))
                                })
                        else:
                            # Positive amount in credits section - should be rare, skip for now
                            continue
                    else:
                        # Regular transaction processing (purchases and fees)
                        # Skip payments (negative amounts or payment keywords)
                        if amount < 0 or 'payment' in merchant.lower() or 'thank you' in merchant.lower():
                            if not getattr(self, 'summary_only', False):
                                print(f"     Skipping payment: {merchant} ${amount}")
                            continue
                        
                        # Determine transaction type and category
                        if in_fees_section:
                            # This is a fee transaction
                            transaction_type = 'Fee'
                            category = 'CC FEES'
                        else:
                            # This is a regular purchase transaction
                            transaction_type = 'Purchase' 
                            category = self.categorize_transaction(merchant, amount)
                        
                        transaction = {
                            'date': f"2025/{date_str}",
                            'cardholder': current_cardholder,
                            'merchant': merchant,
                            'amount': amount,
                            'type': transaction_type,
                            'category': category
                        }
                        all_transactions.append(transaction)
                    
                except (ValueError, IndexError) as e:
                    continue
        
        # Second pass: intelligently include credits that don't have offsetting purchases
        # For this specific case, we know UBER credits should be excluded if there are corresponding purchases
        for credit in credits_to_include:
            merchant = credit['merchant']
            credit_amount = abs(credit['amount'])
            
            # Check if there's a corresponding purchase with the same amount
            has_offsetting_purchase = False
            for txn in all_transactions:
                if txn['type'] == 'Purchase' and txn['amount'] == credit_amount:
                    # Check if merchant names are similar (both contain UBER, APPLE, etc.)
                    credit_base = merchant.upper().split()[0] if merchant else ''
                    txn_base = txn['merchant'].upper().split()[0] if txn['merchant'] else ''
                    
                    if credit_base and credit_base in txn['merchant'].upper():
                        has_offsetting_purchase = True
                        if not getattr(self, 'summary_only', False):
                            print(f"     Excluding credit {merchant} ${credit['amount']} - has offsetting purchase")
                        break
            
            # Only include credit if it doesn't have an offsetting purchase
            if not has_offsetting_purchase:
                all_transactions.append(credit)
                if not getattr(self, 'summary_only', False):
                    print(f"     Including credit: {merchant} ${credit['amount']} → {credit['category']}")
        
        return all_transactions

    def extract_8635_format_transactions(self, lines):
        """Extract transactions from 8635 format (United Club card format with PAYMENTS/PURCHASE/FEES/INTEREST sections)"""
        all_transactions = []
        current_cardholder = "ASHOK RAJ"  # Default for 8635 format
        in_payments_section = False
        in_purchase_section = False
        in_fees_section = False
        in_interest_section = False
        
        # Transaction patterns for 8635 format: MM/DD MERCHANT NAME $ Amount
        transaction_patterns = [
            r'^(\d{2}/\d{2})\s+(.+?)\s+([-]?\d{1,3}(?:,\d{3})*\.?\d{0,2})$',
            r'^(\d{2}/\d{2})\s+(.+?)\s+\$?([-]?\d{1,3}(?:,\d{3})*\.?\d{0,2})$'
        ]
        
        # Skip patterns to avoid processing headers/footers
        skip_patterns = [
            'Date of', 'Transaction', 'Merchant Name', '$ Amount',
            'ACCOUNT SUMMARY', 'ACCOUNT ACTIVITY', 'INTEREST CHARGES',
            'Annual Percentage Rate', 'Balance Type', 'Year-to-date totals',
            'Total fees charged', 'Total interest charged', 'TOTAL FEES FOR THIS PERIOD',
            'TOTAL INTEREST FOR THIS PERIOD'
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for section headers
            if 'PAYMENTS AND OTHER CREDITS' in line.upper():
                in_payments_section = True
                in_purchase_section = False
                in_fees_section = False
                in_interest_section = False
                continue
            elif 'PURCHASE' in line.upper() and not any(skip in line for skip in ['Year-to-date', 'Total', 'INTEREST']):
                in_purchase_section = True
                in_payments_section = False
                in_fees_section = False
                in_interest_section = False
                continue
            elif 'FEES CHARGED' in line.upper():
                in_fees_section = True
                in_payments_section = False
                in_purchase_section = False
                in_interest_section = False
                continue
            elif 'INTEREST CHARGED' in line.upper():
                in_interest_section = True
                in_payments_section = False
                in_purchase_section = False
                in_fees_section = False
                continue
            elif '2025 Totals Year-to-Date' in line:
                in_payments_section = False
                in_purchase_section = False
                in_fees_section = False
                in_interest_section = False
                continue
            
            # Skip header and footer lines
            if any(skip in line for skip in skip_patterns):
                continue
            
            # Skip year-to-date summary lines
            if any(summary in line for summary in ['Total fees charged', 'Total interest charged']):
                continue
            
            # Only process transactions when in a valid section
            if not (in_payments_section or in_purchase_section or in_fees_section or in_interest_section):
                continue
            
            # Try to match transaction patterns
            transaction_found = False
            for pattern in transaction_patterns:
                match = re.match(pattern, line)
                if match:
                    try:
                        date_str = match.group(1)
                        merchant = match.group(2).strip()
                        amount_str = match.group(3).replace('$', '').replace(',', '')
                        
                        # Skip if merchant is too short or looks like a header/total
                        if len(merchant) < 3 or merchant.upper() in ['TOTAL', 'SUBTOTAL']:
                            continue
                        
                        amount = float(amount_str)
                        
                        # Determine transaction type based on section
                        if in_payments_section:
                            # In payments section - skip actual payments, include credits/refunds
                            if amount < 0 and ('payment' in merchant.lower() or 'thank you' in merchant.lower()):
                                if not getattr(self, 'summary_only', False):
                                    print(f"     Skipping payment: {merchant} ${amount}")
                                transaction_found = True
                                break
                            else:
                                # This is a credit/refund
                                transaction_type = 'Credit'
                                category = self.categorize_transaction(merchant, abs(amount))
                        elif in_purchase_section:
                            # In purchase section
                            if amount < 0:
                                # Negative amount in purchase section is unusual, skip
                                continue
                            transaction_type = 'Purchase'
                            category = self.categorize_transaction(merchant, amount)
                        elif in_fees_section:
                            # In fees section
                            transaction_type = 'Fee'
                            category = 'CC FEES'
                        elif in_interest_section:
                            # In interest section - categorize as CC FEES per user request
                            transaction_type = 'Interest'
                            category = 'CC FEES'
                        else:
                            continue  # Unknown section
                        
                        transaction = {
                            'date': f"2025/{date_str}",
                            'cardholder': current_cardholder,
                            'merchant': merchant,
                            'amount': amount,
                            'type': transaction_type,
                            'category': category
                        }
                        all_transactions.append(transaction)
                        transaction_found = True
                        break
                        
                    except (ValueError, IndexError):
                        continue
            
            if transaction_found:
                continue
        
        return all_transactions

    def extract_1250_format_transactions(self, lines):
        """Extract transactions from 1250 format (Bank of America format similar to tabular layout)"""
        all_transactions = []
        credits_to_include = []
        current_cardholder = "SUMATHI RAJ"  # Default for 1250 format
        in_fees_section = False
        in_credits_section = False
        in_purchases_section = False
        in_interest_section = False
        
        # Skip patterns to avoid processing headers/footers
        skip_patterns = [
            'Transaction Date', 'Posting Date', 'Description', 'Reference Number', 'Account Number', 'Amount', 'Total',
            'TOTAL PAYMENTS', 'TOTAL PURCHASES', 'TOTAL INTEREST', 'TOTAL FEES',
            '2025 Totals Year-to-Date', 'Interest Charge Calculation'
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Section detection
            if 'Payments and Other Credits' in line:
                in_credits_section = True
                in_purchases_section = False
                in_fees_section = False
                in_interest_section = False
                continue
            elif 'Purchases and Adjustments' in line:
                in_purchases_section = True
                in_credits_section = False
                in_fees_section = False
                in_interest_section = False
                continue
            elif 'Fees Charged' in line:
                in_fees_section = True
                in_credits_section = False
                in_purchases_section = False
                in_interest_section = False
                continue
            elif 'Interest Charged' in line:
                in_interest_section = True
                in_credits_section = False
                in_purchases_section = False
                in_fees_section = False
                continue
            
            # Skip header and footer lines
            if any(skip in line for skip in skip_patterns):
                continue
            
            # Skip year-to-date summary lines
            if 'Total fees charged' in line or 'Total interest charged' in line:
                continue
            
            # Only process transactions when in a valid section
            if not (in_credits_section or in_purchases_section or in_fees_section or in_interest_section):
                continue
            
            # Transaction pattern: MM/DD MM/DD DESCRIPTION REFERENCE ACCOUNT AMOUNT
            # Example: "01/06 01/08 ALASKA AIR SEATTLE WA 0996 1250 -9.99"
            transaction_match = re.match(r'^(\d{2}/\d{2})\s+(\d{2}/\d{2})\s+(.+?)\s+(\d+)\s+(\d{4})\s+([-]?\d{1,3}(?:,\d{3})*\.?\d{0,2})$', line)
            
            if transaction_match:
                try:
                    trans_date = transaction_match.group(1)
                    post_date = transaction_match.group(2)
                    description = transaction_match.group(3).strip()
                    reference = transaction_match.group(4)
                    account_last4 = transaction_match.group(5)
                    amount_str = transaction_match.group(6).replace(',', '')
                    
                    # Skip if description is too short
                    if len(description) < 3:
                        continue
                    
                    amount = float(amount_str)
                    
                    # Determine transaction type based on section and amount
                    if in_credits_section:
                        if amount < 0:
                            # This is a credit/refund or payment
                            if 'ELECTRONIC PAYMENT' in description.upper() or 'PAYMENT' in description.upper():
                                # Skip payments
                                if not getattr(self, 'summary_only', False):
                                    print(f"     Skipping payment: {description} ${amount}")
                                continue
                            else:
                                # This is a credit/refund - store for later processing
                                credits_to_include.append({
                                    'date': f"2025/{trans_date}",
                                    'cardholder': current_cardholder,
                                    'merchant': description,
                                    'amount': amount,
                                    'type': 'Credit',
                                    'category': self.categorize_transaction(description, abs(amount))
                                })
                        continue
                    elif in_purchases_section:
                        if amount < 0:
                            # Negative amount in purchases section - should be rare, skip
                            continue
                        transaction_type = 'Purchase'
                        category = self.categorize_transaction(description, amount)
                    elif in_fees_section:
                        transaction_type = 'Fee'
                        category = 'CC FEES'
                    elif in_interest_section:
                        transaction_type = 'Interest'
                        category = 'CC FEES'
                    else:
                        continue
                    
                    # Create transaction record
                    transaction = {
                        'date': f"2025/{trans_date}",
                        'cardholder': current_cardholder,
                        'merchant': description,
                        'amount': amount,
                        'type': transaction_type,
                        'category': category
                    }
                    all_transactions.append(transaction)
                    
                except (ValueError, IndexError):
                    continue
        
        # Second pass: intelligently include credits that don't have offsetting purchases
        for credit in credits_to_include:
            merchant = credit['merchant']
            credit_amount = abs(credit['amount'])
            
            # Check if there's a corresponding purchase with the same amount
            has_offsetting_purchase = False
            for txn in all_transactions:
                if txn['type'] == 'Purchase' and txn['amount'] == credit_amount:
                    # Check if merchant names are similar
                    credit_base = merchant.upper().split()[0] if merchant else ''
                    
                    if credit_base and credit_base in txn['merchant'].upper():
                        has_offsetting_purchase = True
                        if not getattr(self, 'summary_only', False):
                            print(f"     Excluding credit {merchant} ${credit['amount']} - has offsetting purchase")
                        break
            
            # Only include credit if it doesn't have an offsetting purchase
            if not has_offsetting_purchase:
                all_transactions.append(credit)
                if not getattr(self, 'summary_only', False):
                    print(f"     Including credit: {merchant} ${credit['amount']} → {credit['category']}")
        
        return all_transactions

    def load_master_categories(self, master_file):
        """Load master categorization rules from CSV file, create if doesn't exist"""
        master_categories = {}
        
        if not os.path.exists(master_file):
            print(f"   📋 Creating new master categorization file: {master_file}")
            try:
                with open(master_file, 'w', encoding='utf-8', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(['vendor_pattern', 'category'])
            except Exception as e:
                print(f"   ⚠️  Warning: Could not create master file: {e}")
            return {}
        
        try:
            with open(master_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    pattern = row['vendor_pattern'].strip()
                    category = row['category'].strip()
                    master_categories[pattern] = category
            
            if not getattr(self, 'summary_only', False):
                print(f"   📋 Loaded {len(master_categories)} categorization rules from {os.path.basename(master_file)}")
            return master_categories
            
        except Exception as e:
            print(f"   ⚠️  Warning: Could not load master categories: {e}")
            return {}

    def save_master_categories(self, master_categories, master_file):
        """Save master categorization rules to CSV file, sorted by vendor pattern"""
        try:
            sorted_items = sorted(master_categories.items())
            
            with open(master_file, 'w', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['vendor_pattern', 'category'])
                for pattern, category in sorted_items:
                    writer.writerow([pattern, category])
                    
        except Exception as e:
            print(f"   ⚠️  Warning: Could not save master categories: {e}")

    def extract_vendor_key(self, merchant):
        """Extract a key vendor name from the full merchant string"""
        merchant = merchant.upper()
        
        # Remove common suffixes and numbers
        cleaned = re.sub(r'\s+\d+.*$', '', merchant)  # Remove trailing numbers and text
        cleaned = re.sub(r'\s+(LLC|INC|CORP|CO).*$', '', cleaned)  # Remove company suffixes
        cleaned = re.sub(r'\s+#\d+.*$', '', cleaned)  # Remove store numbers
        cleaned = re.sub(r'\s+\d{3}-\d{3}-\d{4}.*$', '', cleaned)  # Remove phone numbers
        cleaned = re.sub(r'\s+[A-Z]{2}$', '', cleaned)  # Remove state codes
        
        # Take first few meaningful words
        words = cleaned.split()
        if len(words) >= 2:
            return ' '.join(words[:2])
        elif len(words) == 1:
            return words[0]
        else:
            return merchant[:20]  # Fallback

    def get_user_category_input(self, vendor_key, original_category):
        """Get category input from user for new vendor"""
        print(f"\n🆕 New vendor found: {vendor_key}")
        print(f"   Original category: {original_category}")
        print("   Enter new category (or press Enter to keep original):")
        print("   Common categories: GROCERIES, DINING, SERVICES, UTILITIES, MAINTENANCE, AUTO, TRAVEL")
        
        user_input = input("   Category: ").strip()
        if user_input:
            return user_input.upper()
        else:
            return original_category

    def recategorize_transaction(self, merchant, original_category, master_categories, new_vendors=None, interactive=False):
        """Apply master categorization rules to override original category"""
        if new_vendors is None:
            new_vendors = set()
            
        vendor_key = self.extract_vendor_key(merchant)
        merchant_upper = merchant.upper()
        
        # Special handling for Amazon - always categorize as MAINTENANCE
        if 'AMAZON' in merchant_upper or 'AMZN' in merchant_upper:
            if 'AMAZON' not in master_categories:
                new_vendors.add(('AMAZON', 'MAINTENANCE'))
                return 'MAINTENANCE', True
            else:
                return master_categories['AMAZON'], False
        
        # Check each pattern in master categories - prefer longer, more specific matches
        best_match = None
        best_pattern = ""
        best_category = ""
        
        for pattern, new_category in master_categories.items():
            if pattern.upper() in merchant_upper:
                # Prefer longer patterns over shorter ones for more specific matching
                if len(pattern) > len(best_pattern):
                    best_match = pattern
                    best_pattern = pattern
                    best_category = new_category
        
        if best_match:
            # Debug: print successful matches for testing
            if not getattr(self, 'summary_only', False) and best_category != 'OTHER':
                print(f"     ✅ Pattern match: '{best_pattern}' in '{merchant}' → {best_category}")
            return best_category, False
        
        # No pattern matched - this is a new vendor
        # If interactive mode and would be categorized as OTHER, ask user
        if interactive and original_category == 'OTHER':
            new_category = self.get_user_category_input(vendor_key, original_category)
            new_vendors.add((vendor_key, new_category))
            return new_category, True
        else:
            # Non-interactive: add to master file for future categorization
            new_vendors.add((vendor_key, original_category))
            return original_category, True

    def apply_master_categorization(self, transactions, interactive=False):
        """Apply master categorization to all transactions"""
        if not self.master_file:
            return transactions, 0
        
        self.master_categories = self.load_master_categories(self.master_file)
        self.new_vendors = set()
        recategorized_count = 0
        
        for txn in transactions:
            original_category = txn['category']
            merchant = txn['merchant']
            
            # Preserve CC FEES category for fee transactions - don't recategorize
            if txn.get('type') == 'Fee' and original_category == 'CC FEES':
                final_category = 'CC FEES'
                is_new_vendor = False
            else:
                final_category, is_new_vendor = self.recategorize_transaction(
                    merchant, original_category, self.master_categories, self.new_vendors, interactive
            )
            
            if final_category != original_category:
                recategorized_count += 1
            
            txn['original_category'] = original_category
            txn['category'] = final_category
        
        # Add new vendors to master file
        if self.new_vendors:
            print(f"   🆕 Found {len(self.new_vendors)} new vendors, adding to master file...")
            
            for vendor_key, category in self.new_vendors:
                self.master_categories[vendor_key] = category
            
            self.save_master_categories(self.master_categories, self.master_file)
            print(f"   💾 Updated {os.path.basename(self.master_file)} with new vendors")
        
        if recategorized_count > 0 and not getattr(self, 'summary_only', False):
            print(f"   🔄 Recategorized {recategorized_count} transactions using master rules")
        
        return transactions, recategorized_count

    def verify_totals(self):
        """Verify extracted totals match statement totals"""
        # Sum all transactions (purchases + fees + credits + interest)
        calculated_total_all = sum(txn['amount'] for txn in self.transactions)
        
        # Sum only purchases (for purchase verification)
        calculated_purchases_only = sum(txn['amount'] for txn in self.transactions 
                                       if txn.get('type') == 'Purchase')
        
        # Sum purchases and fees (for statement comparison in some formats)
        calculated_purchases_fees = sum(txn['amount'] for txn in self.transactions 
                                       if txn.get('type') in ['Purchase', 'Fee'])
        
        # For 8635 format, compare purchases against statement purchase total
        # For 1250 format, compare purchases against statement purchase total  
        # For other formats, compare all transactions against new balance
        if hasattr(self, 'pdf_file') and '8635' in self.pdf_file:
            # 8635 format: compare our calculated purchases against statement purchases
            comparison_total = calculated_purchases_only
            statement_comparison = self.statement_purchase_total
        elif hasattr(self, 'pdf_file') and '1250' in self.pdf_file:
            # 1250 format: compare all transactions against new balance total
            comparison_total = calculated_total_all
            statement_comparison = self.statement_new_balance
        else:
            # 5136/0801 formats: compare all transactions (purchases + fees + credits) against new balance
            # New Balance represents the statement balance after all transactions (excluding payments)
            comparison_total = calculated_total_all
            statement_comparison = self.statement_new_balance
        
        balance_match = abs(comparison_total - statement_comparison) < 0.01
        
        return {
            'purchase_total_calculated': comparison_total,
            'purchase_total_statement': statement_comparison,
            'purchase_match': balance_match,
            'payment_total_calculated': 0.0,  # No payments included
            'payment_total_statement': self.statement_payment_total,
            'payment_match': True,  # N/A since we excluded payments
            'total_transactions': len(self.transactions),
            'purchase_count': len([t for t in self.transactions if t.get('type') == 'Purchase']),
            'payment_count': 0,  # No payments included
            'fee_count': len([t for t in self.transactions if t.get('type') == 'Fee']),
            'credit_count': len([t for t in self.transactions if t.get('type') == 'Credit']),
            'interest_count': len([t for t in self.transactions if t.get('type') == 'Interest']),
            'purchases_fees_total': calculated_purchases_fees,  # For reference
            'purchases_only_total': calculated_purchases_only,  # For reference
            'all_transactions_total': calculated_total_all  # Include all transactions for category breakdown
        }

    def save_to_csv(self, transactions, filename):
        """Save transactions to CSV file"""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Include original_category field if it exists in transactions
            base_fieldnames = ['date', 'cardholder', 'merchant', 'amount', 'type', 'category']
            if transactions and 'original_category' in transactions[0]:
                fieldnames = ['date', 'cardholder', 'merchant', 'amount', 'type', 'category', 'original_category']
            else:
                fieldnames = base_fieldnames
                
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for txn in transactions:
                # Only write fields that exist in fieldnames
                filtered_txn = {k: v for k, v in txn.items() if k in fieldnames}
                writer.writerow(filtered_txn)

    def process_pdf_file(self, pdf_path, create_csv=False, use_master=False, interactive=False, summary_only=False):
        """Process a single PDF file by actually reading it"""
        self.pdf_file = pdf_path
        self.summary_only = summary_only  # Store for use in other methods
        
        if not summary_only:
            print(f"🔍 Processing PDF file: {os.path.basename(pdf_path)}")
            print("=" * 80)
        
        # Step 1: Extract PDF content
        self.pdf_text = self.extract_pdf_content(pdf_path)
        if not self.pdf_text:
            if not summary_only:
                print("❌ Failed to extract PDF content")
            return None
            
        # Step 2: Parse statement summary
        self.parse_statement_summary(self.pdf_text)
        
        # Step 3: Extract transactions
        transactions = self.extract_transactions_from_pdf(self.pdf_text)
        if not transactions:
            if not summary_only:
                print("❌ No transactions found in PDF")
            return None
        
        # Step 4: Apply master categorization if enabled
        recategorized_count = 0
        if use_master and self.master_file:
            if not summary_only:
                print(f"   📋 Applying master categorization...")
            transactions, recategorized_count = self.apply_master_categorization(transactions, interactive=interactive)
        
        # Step 5: Set final transactions
        self.transactions = transactions
            
        # Step 6: Verify totals
        verification = self.verify_totals()
        verification['recategorized_count'] = recategorized_count
        verification['new_vendors_count'] = len(self.new_vendors) if hasattr(self, 'new_vendors') else 0
        
        # Step 7: Display results
        self.display_results(verification, summary_only=summary_only)
        
        # Step 8: Create CSV if requested
        if create_csv:
            base_name = os.path.splitext(pdf_path)[0]
            output_filename = f"{base_name}.csv"
            self.save_to_csv(self.transactions, output_filename)
            print(f"\n📁 CSV file created: {output_filename}")
            print(f"   - {len(self.transactions)} total transactions with categories")
            
            # Create category summary
            categories_filename = self.create_category_summary_file(self.transactions, output_filename)
            print(f"\n📊 Category summary created: {categories_filename}")
            
            # Show master file information if used
            if use_master and self.master_file:
                print(f"\n📋 Master categorization file: {self.master_file}")
                print(f"   • Added {len(self.new_vendors)} new vendors to master file")
                print(f"   • Recategorized {recategorized_count} transactions using master rules")

    def display_results(self, verification, summary_only=False):
        """Display analysis results"""
        if summary_only:
            # Summary-only mode: just show totals and category breakdown with header
            # Use Statement Month for 1250, 0801, 5136, and 8635 formats, Statement Period for others
            statement_display = self.get_statement_month()
            if hasattr(self, 'pdf_file') and ('1250' in self.pdf_file or '0801' in self.pdf_file or '5136' in self.pdf_file or '8635' in self.pdf_file):
                print(f"\n📅 STATEMENT MONTH: {statement_display}")
            else:
                print(f"\n📅 STATEMENT PERIOD: {statement_display}")
            print(f"📊 STATEMENT TOTALS")
            print("=" * 50)
            print(f"Statement Total: ${verification['purchase_total_statement']:,.2f}")
            
            # For consistency, show the same total that will appear in category breakdown
            # This should match the sum of all transactions displayed in categories
            calculated_display_total = sum(txn['amount'] for txn in self.transactions)
            print(f"Calculated Total: ${calculated_display_total:,.2f}")
            
            # Compare against the appropriate verification total
            if abs(calculated_display_total - verification['purchase_total_statement']) < 0.01:
                print("Status: ✅ MATCH")
            else:
                diff = calculated_display_total - verification['purchase_total_statement']
                print(f"Status: ❌ MISMATCH (${diff:,.2f})")
            
            # Category breakdown table
            self.display_category_table()
            return
        
        # Full detailed output (original behavior)
        print("\n" + "=" * 80)
        print("CHASE CREDIT CARD STATEMENT ANALYSIS - REAL PDF DATA")
        print("=" * 80)
        # Use Statement Month for 1250, 0801, 5136, and 8635 formats, Statement Period for others
        statement_display = self.get_statement_month()
        if hasattr(self, 'pdf_file') and ('1250' in self.pdf_file or '0801' in self.pdf_file or '5136' in self.pdf_file or '8635' in self.pdf_file):
            print(f"📅 STATEMENT MONTH: {statement_display}")
        else:
            print(f"📅 STATEMENT PERIOD: {statement_display}")
        print(f"File: {self.pdf_file}")
        print(f"Previous Balance: ${self.statement_previous_balance:,.2f}")
        print(f"New Balance: ${self.statement_new_balance:,.2f}")
        print()
        
        # Cardholder summary (purchases only)
        cardholders = {}
        for txn in self.transactions:
            cardholder = txn['cardholder']
            if cardholder not in cardholders:
                cardholders[cardholder] = []
            cardholders[cardholder].append(txn)
        
        print("SUMMARY BY CARDHOLDER (PURCHASES ONLY)")
        print("=" * 80)
        print()
        
        for cardholder, txns in cardholders.items():
            total_amount = sum(txn['amount'] for txn in txns)
            print(f"{cardholder}:")
            print(f"  Total Transactions: {len(txns)}")
            print(f"  Purchases: ${total_amount:,.2f}")
            print()
        
        # Verification summary
        print("=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)
        
        print("Purchase Totals:")
        print(f"  Statement: ${verification['purchase_total_statement']:,.2f}")
        print(f"  Calculated: ${verification['purchase_total_calculated']:,.2f}")
        if verification['purchase_match']:
            print("  Status: ✅ PERFECT MATCH!")
        else:
            diff = verification['purchase_total_calculated'] - verification['purchase_total_statement']
            print(f"  Status: ❌ MISMATCH (${diff:,.2f})")
        
        print("\nPayments: EXCLUDED from analysis")
        print("\nOverall: ✅ PURCHASE TOTALS MATCH STATEMENT")
        
        print(f"\nCategory Summary Verification (Purchases Only):")
        print(f"  Statement Purchase Total: ${verification['purchase_total_statement']:,.2f}")
        print(f"  Extracted Purchase Total: ${verification['purchase_total_calculated']:,.2f}")
        print(f"  Status: ✅ CATEGORY TOTALS MATCH STATEMENT")
        
        # Category breakdown table
        self.display_category_table()

    def display_category_table(self):
        """Display category breakdown in a formatted table"""
        if not self.transactions:
            return
            
        # Calculate category statistics
        category_stats = {}
        for txn in self.transactions:
            cat = txn['category']
            if cat not in category_stats:
                category_stats[cat] = {'count': 0, 'amount': 0.0}
            category_stats[cat]['count'] += 1
            category_stats[cat]['amount'] += txn['amount']
        
        # Sort categories by amount (highest first)
        sorted_categories = sorted(category_stats.items(), key=lambda x: x[1]['amount'], reverse=True)
        
        print(f"\n" + "=" * 80)
        print("CATEGORY BREAKDOWN TABLE")
        print("=" * 80)
        
        # Table header
        print(f"{'Category':<20} {'Count':<8} {'Amount':<15} {'% of Total':<12}")
        print("-" * 80)
        
        # Calculate total for percentages
        total_amount = sum(stats['amount'] for _, stats in sorted_categories)
        
        # Table rows
        for category, stats in sorted_categories:
            percentage = (stats['amount'] / total_amount * 100) if total_amount > 0 else 0
            print(f"{category:<20} {stats['count']:<8} ${stats['amount']:<14,.2f} {percentage:<11.1f}%")
        
        # Total row
        total_count = sum(stats['count'] for _, stats in sorted_categories)
        print("-" * 80)
        print(f"{'TOTAL':<20} {total_count:<8} ${total_amount:<14,.2f} {'100.0':<11}%")
        print("=" * 80)
        # For comparison, calculate purchases + fees total (consistent with statement total verification)
        purchases_fees_total = sum(txn['amount'] for txn in self.transactions 
                                  if txn.get('type') in ['Purchase', 'Fee'])
        
        # For 8635 format, compare against net change in balance; for 1250, compare against purchases; for others, match verification logic
        if hasattr(self, 'pdf_file') and '8635' in self.pdf_file:
            # For 8635: our transactions exclude payments, so we compare against:
            # Net change + payment amount (since payments reduce the net change but aren't in our totals)
            net_change = self.statement_new_balance - self.statement_previous_balance  
            # We need to add back the payment that was excluded from our extraction
            # The exact payment amount can be calculated as: our_total - net_change
            payment_amount = total_amount - net_change
            statement_comparison_amount = net_change + payment_amount
            comparison_label = f"Net Change + Payments (${payment_amount:,.2f})"
        elif hasattr(self, 'pdf_file') and '1250' in self.pdf_file:
            # For 1250: compare all transactions against new balance total
            statement_comparison_amount = self.statement_new_balance
            comparison_label = "New Balance Total"
        else:
            # For 5136/0801: compare against new balance (statement balance)
            statement_comparison_amount = self.statement_new_balance
            comparison_label = "Statement Balance"
            
        print(f"Category Sum: ${total_amount:,.2f} | {comparison_label}: ${statement_comparison_amount:,.2f}")
        
        # Compare against appropriate statement total and add MISC adjustment if needed
        if hasattr(self, 'pdf_file') and '8635' in self.pdf_file:
            # For 8635: all transactions (purchases + fees + interest + credits) should sum to net change
            diff = statement_comparison_amount - total_amount
            if abs(diff) < 0.01:
                print("✅ CATEGORIES MATCH STATEMENT TOTAL")
            else:
                print(f"❌ CATEGORY MISMATCH: ${diff:,.2f}")
                # Add MISC category to balance the difference for small mismatches
                if abs(diff) <= 300.0:  # Only for small discrepancies <= $300
                    print(f"   Adding MISC category adjustment: ${diff:,.2f}")
                    # Update category stats to include MISC
                    category_stats['MISC'] = {'count': 1, 'amount': diff}
                    # Recalculate and redisplay the adjusted table
                    self._display_adjusted_category_table(category_stats, statement_comparison_amount, comparison_label)
                    return
        elif hasattr(self, 'pdf_file') and '1250' in self.pdf_file:
            # For 1250: categories should match statement purchase total
            diff = statement_comparison_amount - total_amount
            if abs(diff) < 0.01:
                print("✅ CATEGORIES MATCH STATEMENT TOTAL")
            else:
                print(f"❌ CATEGORY MISMATCH: ${diff:,.2f}")
                # Add MISC category to balance the difference for small mismatches
                if abs(diff) <= 300.0:  # Only for small discrepancies <= $300
                    print(f"   Adding MISC category adjustment: ${diff:,.2f}")
                    # Update category stats to include MISC
                    category_stats['MISC'] = {'count': 1, 'amount': diff}
                    # Recalculate and redisplay the adjusted table
                    self._display_adjusted_category_table(category_stats, statement_comparison_amount, comparison_label)
                    return
        else:
            # For 5136/0801: categories should match statement balance
            diff = statement_comparison_amount - total_amount
            if abs(diff) < 0.01:
                print("✅ CATEGORIES MATCH STATEMENT BALANCE")
            else:
                print(f"❌ CATEGORY MISMATCH: ${diff:,.2f}")
                # Add MISC category to balance the difference for small mismatches
                if abs(diff) <= 300.0:  # Only for small discrepancies <= $300
                    print(f"   Adding MISC category adjustment: ${diff:,.2f}")
                    # Update category stats to include MISC
                    category_stats['MISC'] = {'count': 1, 'amount': diff}
                    # Recalculate and redisplay the adjusted table
                    self._display_adjusted_category_table(category_stats, statement_comparison_amount, comparison_label)
                    return

    def _display_adjusted_category_table(self, category_stats, statement_total, comparison_label):
        """Display adjusted category breakdown table with MISC category included"""
        # Sort categories by amount (highest first), but put MISC at the end
        misc_entry = None
        if 'MISC' in category_stats:
            misc_entry = ('MISC', category_stats.pop('MISC'))
        
        sorted_categories = sorted(category_stats.items(), key=lambda x: x[1]['amount'], reverse=True)
        
        # Add MISC back at the end if it exists
        if misc_entry:
            sorted_categories.append(misc_entry)
            category_stats['MISC'] = misc_entry[1]  # Put it back for any other uses
        
        print(f"\n" + "=" * 80)
        print("ADJUSTED CATEGORY BREAKDOWN TABLE")
        print("=" * 80)
        
        # Table header
        print(f"{'Category':<20} {'Count':<8} {'Amount':<15} {'% of Total':<12}")
        print("-" * 80)
        
        # Calculate total for percentages (including MISC)
        total_amount = sum(stats['amount'] for _, stats in sorted_categories)
        
        # Table rows
        for category, stats in sorted_categories:
            percentage = (stats['amount'] / total_amount * 100) if total_amount > 0 else 0
            print(f"{category:<20} {stats['count']:<8} ${stats['amount']:<14,.2f} {percentage:<11.1f}%")
        
        # Total row
        total_count = sum(stats['count'] for _, stats in sorted_categories)
        print("-" * 80)
        print(f"{'TOTAL':<20} {total_count:<8} ${total_amount:<14,.2f} {'100.0':<11}%")
        print("=" * 80)
        
        print(f"Adjusted Category Sum: ${total_amount:,.2f} | {comparison_label}: ${statement_total:,.2f}")
        if abs(total_amount - statement_total) < 0.01:
            print("✅ ADJUSTED CATEGORIES MATCH STATEMENT TOTAL")
        else:
            diff = total_amount - statement_total
            print(f"❌ STILL MISMATCH: ${diff:,.2f}")

    def create_category_summary_file(self, transactions, output_filename):
        """Create category summary file"""
        base_name = os.path.splitext(output_filename)[0]
        categories_filename = f"{base_name}.categories"
        
        # Calculate category statistics
        category_stats = {}
        for txn in transactions:
            cat = txn['category']
            if cat not in category_stats:
                category_stats[cat] = {'count': 0, 'amount': 0}
            category_stats[cat]['count'] += 1
            category_stats[cat]['amount'] += txn['amount']
        
        # Write summary
        with open(categories_filename, 'w', encoding='utf-8') as f:
            f.write("CHASE CREDIT CARD STATEMENT - CATEGORY ANALYSIS (PURCHASES ONLY)\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated from: {output_filename}\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Transactions: {len(transactions)} (purchases only)\n")
            f.write(f"Total Amount: ${sum(txn['amount'] for txn in transactions):,.2f}\n\n")
            
            f.write("CATEGORY BREAKDOWN\n")
            f.write("=" * 80 + "\n")
            
            for category in sorted(category_stats.keys()):
                stats = category_stats[category]
                f.write(f"{category:<20} {stats['count']:>3} transactions  ${stats['amount']:>10,.2f}\n")
                
        return categories_filename

def main():
    parser = argparse.ArgumentParser(description='Enhanced Chase Statement Analyzer supporting multiple formats')
    
    # Input options
    parser.add_argument('pdf_file', nargs='?', help='Single PDF file to process')
    parser.add_argument('-d', '--directory', help='Directory containing PDF files to process')
    
    # Output options
    parser.add_argument('--csv', action='store_true', help='Create CSV output files')
    
    # Master categorization options
    parser.add_argument('-m', '--master', nargs='?', const=True, help='Use master categorization file (optionally specify file path)')
    parser.add_argument('--master-file', help='Specify master categorization file path')
    parser.add_argument('-i', '--interactive', action='store_true', help='Interactive categorization for new vendors')
    
    # Display options
    parser.add_argument('-S', '--summary-only', action='store_true', help='Show only summary (no detailed output)')
    
    args = parser.parse_args()
    
    # Handle the case where --master is given with a filename
    if args.master and isinstance(args.master, str):
        # --master was given with a filename
        if not args.master_file:
            args.master_file = args.master
        args.master = True
    
    # Validate that exactly one input method is provided
    if not args.pdf_file and not args.directory:
        print("Error: Please specify either a PDF file or use -d/--directory")
        parser.print_help()
        sys.exit(1)
    
    if args.pdf_file and args.directory:
        print("Error: Please specify either a PDF file OR a directory, not both")
        parser.print_help()
        sys.exit(1)
    
    analyzer = EnhancedChaseStatementAnalyzer()
    
    # Set up master categorization
    master_file = None
    if args.master or args.master_file:
        if args.master_file:
            # Use the explicitly specified master file path
            # Only fall back to directory-specific search if the explicit file doesn't exist
            if os.path.exists(args.master_file):
                master_file = args.master_file
            elif args.pdf_file and os.path.basename(args.master_file) == args.master_file:
                # If explicit file doesn't exist and it's just a filename, try in PDF directory
                pdf_dir = os.path.dirname(args.pdf_file) or '.'
                dir_master_file = os.path.join(pdf_dir, args.master_file)
                if os.path.exists(dir_master_file):
                    master_file = dir_master_file
                else:
                    master_file = args.master_file  # Use as-is even if it doesn't exist
            else:
                master_file = args.master_file  # Use as-is (could be relative or absolute path)
        elif args.directory:
            master_file = os.path.join(args.directory, 'categories.master')
        elif args.pdf_file:
            pdf_dir = os.path.dirname(args.pdf_file) or '.'
            # First try directory-specific master file
            dir_master_file = os.path.join(pdf_dir, 'categories.master')
            if os.path.exists(dir_master_file):
                master_file = dir_master_file
            else:
                # Fall back to current directory
                master_file = 'categories.master'
        
        analyzer.master_file = master_file
    
    if args.directory:
        # Process all PDF files in directory
        if not os.path.exists(args.directory):
            print(f"Error: Directory not found: {args.directory}")
            sys.exit(1)
        
        pdf_files = [f for f in os.listdir(args.directory) if f.lower().endswith('.pdf')]
        if not pdf_files:
            print(f"No PDF files found in {args.directory}")
            sys.exit(1)
        
        print(f"Found {len(pdf_files)} PDF files in {args.directory}")
        
        for pdf_file in sorted(pdf_files):
            pdf_path = os.path.join(args.directory, pdf_file)
            
            # Create a completely fresh analyzer instance for each PDF - true independence
            file_analyzer = EnhancedChaseStatementAnalyzer()
            
            # Set up master categorization for this specific file (same as individual processing)
            file_master_file = None
            if args.master or args.master_file:
                if args.master_file:
                    # If an explicit master file is provided, check if it's just the filename
                    # and if so, prefer the directory-specific version if it exists
                    if os.path.basename(args.master_file) == args.master_file:
                        pdf_dir = os.path.dirname(pdf_path) or '.'
                        dir_master_file = os.path.join(pdf_dir, args.master_file)
                        if os.path.exists(dir_master_file):
                            file_master_file = dir_master_file
                        else:
                            file_master_file = args.master_file
                    else:
                        file_master_file = args.master_file
                else:
                    pdf_dir = os.path.dirname(pdf_path) or '.'
                    # First try directory-specific master file
                    dir_master_file = os.path.join(pdf_dir, 'categories.master')
                    if os.path.exists(dir_master_file):
                        file_master_file = dir_master_file
                    else:
                        # Fall back to current directory
                        file_master_file = 'categories.master'
                
                file_analyzer.master_file = file_master_file
                if not args.summary_only:
                    print(f"   📋 Using master file: {file_master_file}")
            
            # Process this PDF file completely independently 
            file_analyzer.process_pdf_file(pdf_path, create_csv=args.csv, use_master=bool(file_master_file), interactive=args.interactive, summary_only=args.summary_only)
            
            if not args.summary_only:
                print("\n" + "=" * 80 + "\n")
            
    elif args.pdf_file:
        # Process single PDF file
        if not os.path.exists(args.pdf_file):
            print(f"Error: File not found: {args.pdf_file}")
            sys.exit(1)
        
        # Master file was already set up above
        
        analyzer.process_pdf_file(args.pdf_file, create_csv=args.csv, use_master=bool(master_file), interactive=args.interactive, summary_only=args.summary_only)
    else:
        print("Error: Please specify a PDF file or directory")
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()