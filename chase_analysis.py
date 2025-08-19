#!/usr/bin/env python3
"""
Real Chase Credit Card Statement Analysis - NO HARDCODED DATA
Extracts ALL data directly from PDF files

Usage:
    python real_chase_analysis.py [options] [pdf_file]
    
Options:
    -c, --csv       Create CSV file with same name as input PDF
    -d, --directory Directory of PDF files to process
    -h, --help      Show this help message
"""

import csv
import re
import os
import sys
import argparse
import glob
from datetime import datetime
import pdfplumber

class RealChaseStatementAnalyzer:
    def __init__(self, pdf_file=None, master_file=None):
        self.pdf_file = pdf_file
        self.master_file = master_file
        self.statement_purchase_total = 0.0
        self.statement_payment_total = 0.0
        self.statement_previous_balance = 0.0
        self.statement_new_balance = 0.0
        self.transactions = []
        self.pdf_text = ""
        self.statement_period = ""
        self.master_categories = {}
        self.new_vendors = set()
        
        # Category mapping for automatic categorization
        self.category_mapping = {
            'RESTAURANT': ['RESTAURANT', 'DEPOT', 'CHEFSTORE', 'TORCHYS', 'CHIPOTLE', 'VELVET TACO', 
                          'CHERRY', 'AGAS', 'EL CENTRO', 'DEAN', 'CICCIOS', 'FORNO MAGICO', 'Q BAR',
                          'SMOKING GUN', 'OPEN BAR', 'CAVA', 'JAMBA JUICE'],
            'GROCERY': ['COSTCO', 'SAFEWAY', 'INDIA SUPERMARKET', 'APNA BAZAAR', 'DENNIS MARKET',
                       'MARKET OF CHOICE', 'TARGET', 'GDP*TP', 'CAFE WEEKEND'],
            'GAS/FUEL': ['COSTCO GAS', 'NORTHWEST BIOFUEL', 'CHEVRON', 'SHELL', 'MOBIL', 'BP'],
            'UTILITIES': ['PORTLAND GENERAL ELECTRIC', 'TUALATIN VALLEY WATER', 'COMCAST', 'XFINITY'],
            'SUBSCRIPTIONS': ['NETFLIX', 'HULU', 'GOOGLE', 'YOUTUBE TV', 'APPLE.COM/BILL', 'VONAGE'],
            'SHOPPING': ['AMAZON', 'EBAY', 'NORDSTROM', 'GAMESTOP', 'OAKLEY'],
            'TRAVEL/DINING': ['IAH', 'PDX', 'SALT AND STRAW', 'KRISPY KREME', 'MY FAVORITE MUFFIN',
                             'OJOS LOCOS', 'THE LOT POINT LOMA', 'GAME EMPIRE'],
            'SERVICES': ['ABOVE ALL ACCOUNTING', 'CLR*StretchLab', 'REDTAIL GOLF', 'LTF*LIFE TIME',
                        'ADT SECURITY', 'PITMAN', 'Saela Pest Control', 'US LINEN', 'PERFECTPOUR',
                        'WEBSTAURANT STORE', 'SPOTHOPPERAPP', 'TANASBOURNE PLACE'],
            'GOVERNMENT': ['CITY OF HILLSBORO', 'OR SEC STATE', 'PORTLAND PARKING'],
            'MEDICAL/HEALTH': ['LYMPHOMA ACTION', 'NATIONWIDE'],
            'TELECOM': ['CCSI EFAX'],
            'MISCELLANEOUS': ['CULTUREMAP', 'CVSExtraCare'],
            'PAYMENT': ['Payment Thank You', 'PAYMENT']
        }

    def extract_pdf_content(self, pdf_path):
        """Extract actual text content from PDF file using pdfplumber"""
        try:
            print(f"   📄 Reading PDF file: {os.path.basename(pdf_path)}")
            
            with pdfplumber.open(pdf_path) as pdf:
                all_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        all_text += page_text + "\n"
                
                if all_text.strip():
                    print(f"   ✅ Successfully extracted {len(all_text)} characters from PDF")
                    return all_text
                else:
                    raise ValueError("No text could be extracted from PDF")
                    
        except Exception as e:
            print(f"   ❌ Error reading PDF: {e}")
            print(f"   💡 Make sure the PDF file exists and is readable")
            return ""

    def parse_statement_summary(self, pdf_text):
        """Parse statement summary from actual PDF text"""
        print(f"   🔍 Parsing statement summary...")
        
        # Debug: Show relevant lines from PDF
        lines = pdf_text.split('\n')
        print(f"   📋 Looking for statement summary in {len(lines)} lines...")
        
        try:
            # Look for Previous Balance
            prev_patterns = [
                r'Previous Balance\s*\$?([\d,]+\.?\d*)',
                r'PREVIOUS BALANCE\s*\$?([\d,]+\.?\d*)',
                r'Previous\s+Balance\s*\$?([\d,]+\.?\d*)'
            ]
            
            for pattern in prev_patterns:
                match = re.search(pattern, pdf_text, re.IGNORECASE)
                if match:
                    self.statement_previous_balance = float(match.group(1).replace(',', ''))
                    print(f"     Previous Balance: ${self.statement_previous_balance:,.2f}")
                    break
            
            # Look for Payment/Credits
            payment_patterns = [
                r'Payment(?:s)?,?\s*Credits?\s*-?\$?([\d,]+\.?\d*)',
                r'PAYMENTS?\s*,?\s*CREDITS?\s*-?\$?([\d,]+\.?\d*)',
                r'Payments?\s+Credits?\s*-?\$?([\d,]+\.?\d*)'
            ]
            
            for pattern in payment_patterns:
                match = re.search(pattern, pdf_text, re.IGNORECASE)
                if match:
                    amount = float(match.group(1).replace(',', ''))
                    self.statement_payment_total = -abs(amount)  # Ensure negative
                    print(f"     Payments/Credits: ${self.statement_payment_total:,.2f}")
                    break
            
            # Look specifically for the purchase line in statement summary
            purchase_line_pattern = r'Purchases?\s*\+\$?([\d,]+\.?\d{2})'
            purchase_match = re.search(purchase_line_pattern, pdf_text, re.IGNORECASE)
            
            if purchase_match:
                self.statement_purchase_total = float(purchase_match.group(1).replace(',', ''))
                print(f"     Purchases: ${self.statement_purchase_total:,.2f}")
            else:
                # Fallback patterns
                fallback_patterns = [
                    r'Purchases?\s*\$?([\d,]+\.?\d{2})',
                    r'Purchase\s+Total\s*\$?([\d,]+\.?\d{2})'
                ]
                
                for pattern in fallback_patterns:
                    match = re.search(pattern, pdf_text, re.IGNORECASE)
                    if match:
                        self.statement_purchase_total = float(match.group(1).replace(',', ''))
                        print(f"     Purchases (fallback): ${self.statement_purchase_total:,.2f}")
                        break
                else:
                    print(f"     ⚠️  No purchase totals found")
            
            # Look specifically for the new balance line in statement summary  
            new_balance_pattern = r'New Balance\s*\$?([\d,]+\.?\d{2})'
            new_balance_match = re.search(new_balance_pattern, pdf_text, re.IGNORECASE)
            
            if new_balance_match:
                self.statement_new_balance = float(new_balance_match.group(1).replace(',', ''))
                print(f"     New Balance: ${self.statement_new_balance:,.2f}")
            else:
                print(f"     ⚠️  No new balance found")
            
            # Look for Statement Period
            period_patterns = [
                r'(\d{2}/\d{2}/\d{2})\s*-\s*(\d{2}/\d{2}/\d{2})',
                r'Opening/Closing Date\s+(\d{2}/\d{2}/\d{2})\s*-\s*(\d{2}/\d{2}/\d{2})'
            ]
            
            for pattern in period_patterns:
                match = re.search(pattern, pdf_text)
                if match:
                    self.statement_period = f"{match.group(1)} - {match.group(2)}"
                    print(f"     Statement Period: {self.statement_period}")
                    break
                    
            if self.statement_purchase_total == 0 and self.statement_new_balance == 0:
                print(f"   ⚠️  Warning: Could not parse statement totals from PDF")
                print(f"   💡 The PDF format might be different than expected")
                
        except Exception as e:
            print(f"   ⚠️  Warning: Error parsing statement summary: {e}")

    def debug_pdf_content(self, pdf_text):
        """Debug function to show relevant PDF content"""
        lines = pdf_text.split('\n')
        print(f"\n   🔍 DEBUG: Showing relevant PDF content...")
        
        # Look for lines containing balance/purchase keywords
        relevant_lines = []
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ['balance', 'purchase', 'payment', 'credit']):
                relevant_lines.append((i, line.strip()))
        
        print(f"   📋 Found {len(relevant_lines)} relevant lines:")
        for line_num, line in relevant_lines[:15]:  # Show first 15
            print(f"     Line {line_num}: {line}")
            
        # Look for transaction-like patterns
        print(f"\n   🔍 Looking for transaction patterns...")
        transaction_pattern = r'(\d{2}/\d{2})\s+(.{10,}?)\s+(\$?\d{1,3}(?:,\d{3})*\.?\d{0,2})'
        matches = re.findall(transaction_pattern, pdf_text)
        print(f"   📋 Found {len(matches)} potential transaction patterns")
        
        if matches:
            print(f"   💰 Sample transaction patterns:")
            for i, (date, merchant, amount) in enumerate(matches[:10]):
                print(f"     {i+1}. {date} | {merchant[:30]}... | {amount}")

    def extract_transactions_from_pdf(self, pdf_text):
        """Extract all transactions from actual PDF text (excluding payments)"""
        print(f"   🔍 Extracting transactions from PDF (excluding payments)...")
        
        lines = pdf_text.split('\n')
        all_transactions = []
        pending_transactions = []
        current_cardholder = None
        
        # Transaction patterns to try
        transaction_patterns = [
            r'^(\d{2}/\d{2})\s+(.+?)\s+([-]?\$?\d{1,3}(?:,\d{3})*\.?\d{0,2})$',
            r'^(\d{2}/\d{2})\s+(.+?)\s+([-]?\d{1,3}(?:,\d{3})*\.?\d{0,2})\s*$',
            r'(\d{2}/\d{2})\s+(.+?)\s+([-]?\$?\d{1,3}(?:,\d{3})*\.?\d{0,2})(?:\s|$)'
        ]
        
        cardholder_patterns = [
            r'([A-Z]+\s+RAJ)',
            r'([A-Z]+\s+[A-Z]+)',
            r'^([A-Z\s]+)$'
        ]
        
        transactions_cycle_patterns = [
            r'TRANSACTIONS?\s+THIS\s+CYCLE',
            r'TRANSACTION.*CYCLE'
        ]
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check if next line contains "TRANSACTIONS THIS CYCLE" or similar
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            
            is_transactions_cycle = False
            for pattern in transactions_cycle_patterns:
                if re.search(pattern, next_line, re.IGNORECASE):
                    is_transactions_cycle = True
                    break
            
            if is_transactions_cycle:
                # This line is a cardholder name
                for pattern in cardholder_patterns:
                    match = re.search(pattern, line)
                    if match:
                        current_cardholder = match.group(1).strip()
                        print(f"     Found cardholder: {current_cardholder}")
                        
                        # Assign all pending transactions to this cardholder
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
                        
                        # Clear pending transactions
                        pending_transactions = []
                        break
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
        
        print(f"   ✅ Extracted {len(all_transactions)} transactions")
        
        # Show transaction summary by cardholder
        if all_transactions:
            cardholder_totals = {}
            for txn in all_transactions:
                ch = txn['cardholder']
                if ch not in cardholder_totals:
                    cardholder_totals[ch] = {'count': 0, 'total': 0}
                cardholder_totals[ch]['count'] += 1
                cardholder_totals[ch]['total'] += txn['amount']
            
            print(f"   📋 Transaction summary by cardholder:")
            grand_total = 0
            for ch, stats in cardholder_totals.items():
                print(f"     {ch}: {stats['count']} txns, ${stats['total']:,.2f}")
                grand_total += stats['total']
            print(f"     TOTAL: {len(all_transactions)} txns, ${grand_total:,.2f}")
            
            # Show largest transactions for verification
            sorted_txns = sorted(all_transactions, key=lambda x: x['amount'], reverse=True)
            print(f"   💰 Largest transactions:")
            for i, txn in enumerate(sorted_txns[:5]):
                print(f"     {i+1}. ${txn['amount']:,.2f} | {txn['cardholder']} | {txn['merchant'][:40]}")
        
        # Debug: Look for any missed high-value transactions in the PDF
        print(f"   🔍 Checking for high-value transactions that might be missed...")
        high_value_pattern = r'(\d{2}/\d{2}).*?\$?(\d{1,3}(?:,\d{3})+\.?\d{0,2})'
        high_value_matches = re.findall(high_value_pattern, pdf_text)
        if high_value_matches:
            print(f"     Found {len(high_value_matches)} potential high-value patterns:")
            for date, amount in high_value_matches[:10]:  # Show first 10
                try:
                    amt_val = float(amount.replace(',', ''))
                    if amt_val > 500:  # Only show amounts > $500
                        print(f"       {date}: ${amt_val:,.2f}")
                except:
                    pass
        
        self.transactions = all_transactions
        return all_transactions

    def categorize_transaction(self, merchant, amount):
        """Automatically categorize transaction based on merchant name (purchases only)"""
        merchant_upper = merchant.upper()
        
        # Since we're only processing purchases, no need to check for payments
        # Check each category
        for category, keywords in self.category_mapping.items():
            # Skip payment categories since we're not including payments
            if category in ['PAYMENT', 'REFUND/CREDIT']:
                continue
                
            for keyword in keywords:
                if keyword.upper() in merchant_upper:
                    return category
        
        # Default category for unmatched transactions
        return 'OTHER'

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
        
        # Special handling for Amazon - consolidate all Amazon transactions
        if 'AMAZON' in merchant or 'AMZN' in merchant:
            return 'AMAZON'
        
        # Remove common location indicators
        merchant = re.sub(r'\s+\d{3}-\d{3}-\d{4}.*$', '', merchant)  # Phone numbers
        merchant = re.sub(r'\s+[A-Z]{2}$', '', merchant)  # State codes
        merchant = re.sub(r'\s+#\d+.*$', '', merchant)  # Store numbers
        merchant = re.sub(r'\s+\d+.*$', '', merchant)  # Trailing numbers
        
        # Get first part for compound names
        parts = merchant.split()
        if len(parts) > 3:
            key_parts = []
            for part in parts[:3]:
                if len(part) > 2 and not part.isdigit():
                    key_parts.append(part)
                if len(key_parts) >= 2:
                    break
            merchant = ' '.join(key_parts) if key_parts else parts[0]
        
        return merchant.strip()

    def recategorize_transaction(self, merchant, original_category, master_categories, new_vendors=None):
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
        
        # Check each pattern in master categories
        for pattern, new_category in master_categories.items():
            if pattern.upper() in merchant_upper:
                return new_category, False
        
        # No pattern matched - this is a new vendor
        new_vendors.add((vendor_key, original_category))
        return original_category, True

    def apply_master_categorization(self, transactions):
        """Apply master categorization to all transactions"""
        if not self.master_file:
            return transactions, 0
        
        self.master_categories = self.load_master_categories(self.master_file)
        self.new_vendors = set()
        recategorized_count = 0
        
        for txn in transactions:
            original_category = txn['category']
            merchant = txn['merchant']
            
            final_category, is_new_vendor = self.recategorize_transaction(
                merchant, original_category, self.master_categories, self.new_vendors
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
        
        if recategorized_count > 0:
            print(f"   🔄 Recategorized {recategorized_count} transactions using master rules")
        
        return transactions, recategorized_count

    def verify_totals(self):
        """Verify extracted totals match statement totals (purchases only)"""
        # All transactions are purchases now (payments excluded)
        purchases = self.transactions
        
        calculated_purchase_total = sum(txn['amount'] for txn in purchases)
        
        purchase_match = abs(calculated_purchase_total - self.statement_purchase_total) < 0.01
        
        return {
            'purchase_total_calculated': calculated_purchase_total,
            'purchase_total_statement': self.statement_purchase_total,
            'purchase_match': purchase_match,
            'payment_total_calculated': 0.0,  # No payments included
            'payment_total_statement': self.statement_payment_total,
            'payment_match': True,  # N/A since we excluded payments
            'total_transactions': len(self.transactions),
            'purchase_count': len(purchases),
            'payment_count': 0  # No payments included
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

    def process_pdf_file(self, pdf_path, create_csv=False, use_master=False):
        """Process a single PDF file by actually reading it"""
        self.pdf_file = pdf_path
        
        print(f"🔍 Processing PDF file: {os.path.basename(pdf_path)}")
        print("=" * 80)
        
        # Step 1: Extract PDF content
        self.pdf_text = self.extract_pdf_content(pdf_path)
        if not self.pdf_text:
            print("❌ Failed to extract PDF content")
            return None
            
        # Step 2: Parse statement summary
        self.parse_statement_summary(self.pdf_text)
        
        # Step 2.5: Debug PDF content if there are discrepancies (commented out for cleaner output)
        # self.debug_pdf_content(self.pdf_text)
        
        # Step 3: Extract transactions
        transactions = self.extract_transactions_from_pdf(self.pdf_text)
        if not transactions:
            print("❌ No transactions found in PDF")
            return None
        
        # Step 3.5: Apply master categorization if enabled
        recategorized_count = 0
        if use_master and self.master_file:
            print(f"   📋 Applying master categorization...")
            transactions, recategorized_count = self.apply_master_categorization(transactions)
            self.transactions = transactions
            
        # Step 4: Verify totals
        verification = self.verify_totals()
        verification['recategorized_count'] = recategorized_count
        verification['new_vendors_count'] = len(self.new_vendors) if hasattr(self, 'new_vendors') else 0
        
        # Step 5: Display results
        self.display_results(verification)
        
        # Step 6: Create CSV if requested
        if create_csv:
            base_name = os.path.splitext(pdf_path)[0]
            output_filename = f"{base_name}.csv"
            self.save_to_csv(transactions, output_filename)
            print(f"\n📁 CSV file created: {output_filename}")
            print(f"   - {len(transactions)} total transactions with categories")
            
            # Create category summary
            categories_filename = self.create_category_summary_file(transactions, output_filename)
            print(f"\n📊 Category summary created: {categories_filename}")
            
            # Show master file information if used
            if use_master and self.master_file:
                print(f"\n📋 Master categorization file: {self.master_file}")
                if hasattr(self, 'new_vendors') and self.new_vendors:
                    print(f"   • Added {len(self.new_vendors)} new vendors to master file")
                if recategorized_count > 0:
                    print(f"   • Recategorized {recategorized_count} transactions using master rules")
        
        return verification

    def display_results(self, verification):
        """Display analysis results"""
        print("\n" + "=" * 80)
        print("CHASE CREDIT CARD STATEMENT ANALYSIS - REAL PDF DATA")
        print("=" * 80)
        print(f"File: {self.pdf_file}")
        print(f"Statement Period: {self.statement_period}")
        print(f"Previous Balance: ${self.statement_previous_balance:,.2f}")
        print(f"New Balance: ${self.statement_new_balance:,.2f}")
        print()
        
        # Cardholder summary (purchases only)
        cardholders = {}
        for txn in self.transactions:
            cardholder = txn['cardholder']
            if cardholder not in cardholders:
                cardholders[cardholder] = {'purchases': 0, 'count': 0}
            
            cardholders[cardholder]['count'] += 1
            cardholders[cardholder]['purchases'] += txn['amount']
        
        print("SUMMARY BY CARDHOLDER (PURCHASES ONLY)")
        print("=" * 80)
        for cardholder, stats in cardholders.items():
            print(f"\n{cardholder}:")
            print(f"  Total Transactions: {stats['count']}")
            print(f"  Purchases: ${stats['purchases']:,.2f}")
        
        # Verification summary
        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)
        
        print(f"Purchase Totals:")
        print(f"  Statement: ${verification['purchase_total_statement']:,.2f}")
        print(f"  Calculated: ${verification['purchase_total_calculated']:,.2f}")
        if verification['purchase_match']:
            print("  Status: ✅ PERFECT MATCH!")
        else:
            diff = verification['purchase_total_calculated'] - verification['purchase_total_statement']
            print(f"  Status: ❌ MISMATCH (${diff:,.2f} difference)")
        
        print(f"\nPayments: EXCLUDED from analysis")
        
        overall_match = verification['purchase_match']
        print(f"\nOverall: {'✅ PURCHASE TOTALS MATCH STATEMENT' if overall_match else '❌ PURCHASE TOTALS DO NOT MATCH'}")
        
        # Show master file usage summary if applicable
        if 'recategorized_count' in verification and verification['recategorized_count'] > 0:
            print(f"\nMaster Categorization Summary:")
            print(f"  Recategorized Transactions: {verification['recategorized_count']}")
            if 'new_vendors_count' in verification and verification['new_vendors_count'] > 0:
                print(f"  New Vendors Added: {verification['new_vendors_count']}")
        
        # Category verification (purchases only)
        if self.transactions:
            total_amount = sum(txn['amount'] for txn in self.transactions)
            
            print(f"\nCategory Summary Verification (Purchases Only):")
            print(f"  Statement Purchase Total: ${self.statement_purchase_total:,.2f}")
            print(f"  Extracted Purchase Total: ${total_amount:,.2f}")
            if abs(self.statement_purchase_total - total_amount) < 0.01:
                print(f"  Status: ✅ CATEGORY TOTALS MATCH STATEMENT")
            else:
                diff = total_amount - self.statement_purchase_total
                print(f"  Status: ❌ MISMATCH (${diff:,.2f} difference)")
            
            # Category breakdown table
            self.display_category_table()
            
            # Show master categorization tips if master file was used
            if hasattr(self, 'master_file') and self.master_file and os.path.exists(self.master_file):
                print(f"\n💡 Master Categorization Tips:")
                print(f"   • Edit {os.path.basename(self.master_file)} to customize vendor categorizations")
                print(f"   • Master file is automatically maintained and sorted")
                print(f"   • New vendors are automatically added for future processing")

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
        
        # Table footer
        print("-" * 80)
        total_count = sum(stats['count'] for _, stats in sorted_categories)
        print(f"{'TOTAL':<20} {total_count:<8} ${total_amount:<14,.2f} {'100.0':<11}%")
        print("=" * 80)
        
        # Verification line
        print(f"Category Sum: ${total_amount:,.2f} | Statement Total: ${self.statement_purchase_total:,.2f}")
        if abs(total_amount - self.statement_purchase_total) < 0.01:
            print("✅ CATEGORIES MATCH STATEMENT TOTAL")
        else:
            diff = total_amount - self.statement_purchase_total
            print(f"❌ MISMATCH: ${diff:,.2f} difference")

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
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description='Real Chase Credit Card Statement Analysis Tool - NO HARDCODED DATA',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python real_chase_analysis.py statement.pdf              # Analyze specific PDF
  python real_chase_analysis.py -c statement.pdf           # Analyze and create CSV
  python real_chase_analysis.py -c -m statement.pdf        # Analyze with master categorization
  python real_chase_analysis.py -d /path/to/pdfs/          # Process directory
  python real_chase_analysis.py -d -m /path/to/pdfs/       # Process directory with master categorization
  python real_chase_analysis.py --master-file custom.csv statement.pdf  # Use custom master file
        """
    )
    
    parser.add_argument('pdf_file', nargs='?', help='PDF file to analyze')
    parser.add_argument('-c', '--csv', action='store_true', 
                       help='Create CSV file with same name as input PDF')
    parser.add_argument('-d', '--directory', 
                       help='Directory containing PDF files to process')
    parser.add_argument('-m', '--master', action='store_true',
                       help='Use master categorization file for advanced categorization')
    parser.add_argument('--master-file', 
                       help='Specify custom master categorization file path')
    
    args = parser.parse_args()
    
    if args.directory:
        # Process directory of PDFs
        pdf_files = glob.glob(os.path.join(args.directory, "*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in directory: {args.directory}")
            return
        
        # Set up master file for directory processing
        master_file = None
        if args.master or args.master_file:
            if args.master_file:
                master_file = args.master_file
            else:
                master_file = os.path.join(args.directory, "categories.master")
        
        for pdf_file in pdf_files:
            analyzer = RealChaseStatementAnalyzer(master_file=master_file)
            analyzer.process_pdf_file(pdf_file, create_csv=args.csv, use_master=bool(master_file))
            print("\n" + "=" * 80 + "\n")
            
    elif args.pdf_file:
        # Process single PDF file
        if not os.path.exists(args.pdf_file):
            print(f"Error: File not found: {args.pdf_file}")
            sys.exit(1)
        
        # Set up master file for single file processing
        master_file = None
        if args.master or args.master_file:
            if args.master_file:
                master_file = args.master_file
            else:
                # Put master file in same directory as PDF
                pdf_dir = os.path.dirname(os.path.abspath(args.pdf_file))
                master_file = os.path.join(pdf_dir, "categories.master")
        
        analyzer = RealChaseStatementAnalyzer(master_file=master_file)
        analyzer.process_pdf_file(args.pdf_file, create_csv=args.csv, use_master=bool(master_file))
    else:
        print("Error: Please specify a PDF file or directory")
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()