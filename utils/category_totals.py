#!/usr/bin/env python3
"""
Category Totals Calculator with Master Categorization
Reads a Chase statement CSV file and produces category totals.
Uses master_cat.csv to override default categories based on vendor patterns.

Usage:
    python category_totals.py [csv_file] [options]
    python category_totals.py -d [directory] [options]
    
Examples:
    python category_totals.py statement.csv
    python category_totals.py -d 0801/
    python category_totals.py 0801/20250306-statements-0801-.csv --show-comparison
"""

import csv
import sys
import os
import argparse
import re
import glob
from datetime import datetime

def load_master_categories(master_file):
    """Load master categorization rules from CSV file, create if doesn't exist"""
    master_categories = {}
    
    if not os.path.exists(master_file):
        print(f"📋 Creating new master categorization file: {master_file}")
        # Create empty master file with headers
        try:
            with open(master_file, 'w', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['vendor_pattern', 'category'])
        except Exception as e:
            print(f"⚠️  Warning: Could not create master file: {e}")
        return {}
    
    try:
        with open(master_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                pattern = row['vendor_pattern'].strip()
                category = row['category'].strip()
                master_categories[pattern] = category
        
        print(f"📋 Loaded {len(master_categories)} categorization rules from {master_file}")
        return master_categories
        
    except Exception as e:
        print(f"⚠️  Warning: Could not load master categories: {e}")
        return {}

def save_master_categories(master_categories, master_file):
    """Save master categorization rules to CSV file, sorted by vendor pattern"""
    try:
        # Sort by vendor pattern for easy maintenance
        sorted_items = sorted(master_categories.items())
        
        with open(master_file, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['vendor_pattern', 'category'])
            for pattern, category in sorted_items:
                writer.writerow([pattern, category])
                
    except Exception as e:
        print(f"⚠️  Warning: Could not save master categories: {e}")

def extract_vendor_key(merchant):
    """Extract a key vendor name from the full merchant string"""
    # Remove common suffixes and clean up
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
        # For long names, take first 2-3 meaningful words
        key_parts = []
        for part in parts[:3]:
            if len(part) > 2 and not part.isdigit():  # Skip short words and numbers
                key_parts.append(part)
            if len(key_parts) >= 2:
                break
        merchant = ' '.join(key_parts) if key_parts else parts[0]
    
    return merchant.strip()

def recategorize_transaction(merchant, original_category, master_categories, new_vendors=None):
    """Apply master categorization rules to override original category"""
    if new_vendors is None:
        new_vendors = set()
        
    # Extract vendor key for matching
    vendor_key = extract_vendor_key(merchant)
    merchant_upper = merchant.upper()
    
    # Special handling for Amazon - always categorize as MAINTENANCE
    if 'AMAZON' in merchant_upper or 'AMZN' in merchant_upper:
        # Check if AMAZON rule exists, if not add it
        if 'AMAZON' not in master_categories:
            new_vendors.add(('AMAZON', 'MAINTENANCE'))
            return 'MAINTENANCE', True
        else:
            return master_categories['AMAZON'], False
    
    # Check each pattern in master categories
    for pattern, new_category in master_categories.items():
        if pattern.upper() in merchant_upper:
            return new_category, False  # Found existing rule, not new vendor
    
    # No pattern matched - this is a new vendor
    new_vendors.add((vendor_key, original_category))
    return original_category, True  # Keep original, mark as new vendor

def calculate_category_totals(csv_file, master_file, auto_balance=True):
    """Read CSV file and calculate category totals with automatic master file maintenance"""
    if not os.path.exists(csv_file):
        print(f"❌ Error: File not found: {csv_file}")
        return None
    
    print(f"📊 Reading CSV file: {os.path.basename(csv_file)}")
    
    # Load master categorization rules (creates file if doesn't exist)
    master_categories = load_master_categories(master_file)
    new_vendors = set()  # Track new vendors to add to master
    
    # Read CSV data
    transactions = []
    recategorized_count = 0
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                original_category = row['category']
                merchant = row['merchant']
                
                # Apply master categorization rules
                final_category, is_new_vendor = recategorize_transaction(
                    merchant, original_category, master_categories, new_vendors
                )
                
                if final_category != original_category:
                    recategorized_count += 1
                
                transactions.append({
                    'date': row['date'],
                    'cardholder': row['cardholder'],
                    'merchant': merchant,
                    'amount': float(row['amount']),
                    'type': row['type'],
                    'original_category': original_category,
                    'category': final_category
                })
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return None
    
    print(f"✅ Loaded {len(transactions)} transactions")
    if master_categories and recategorized_count > 0:
        print(f"🔄 Recategorized {recategorized_count} transactions using master rules")
    
    # Add new vendors to master file
    if new_vendors:
        print(f"🆕 Found {len(new_vendors)} new vendors, adding to master file...")
        
        # Add new vendors to master categories dict
        for vendor_key, category in new_vendors:
            master_categories[vendor_key] = category
        
        # Save updated master file (sorted)
        save_master_categories(master_categories, master_file)
        print(f"💾 Updated {master_file} with new vendors")
    
    # Calculate category totals
    category_totals = {}
    original_category_totals = {}
    total_amount = 0
    
    for txn in transactions:
        final_category = txn['category']
        original_category = txn['original_category']
        amount = txn['amount']
        
        # Track final categories
        if final_category not in category_totals:
            category_totals[final_category] = {'count': 0, 'total': 0.0}
        category_totals[final_category]['count'] += 1
        category_totals[final_category]['total'] += amount
        
        # Track original categories for comparison
        if original_category not in original_category_totals:
            original_category_totals[original_category] = {'count': 0, 'total': 0.0}
        original_category_totals[original_category]['count'] += 1
        original_category_totals[original_category]['total'] += amount
        
        total_amount += amount
    
    # Check if we should auto-balance small differences
    csv_was_modified = False
    if auto_balance:
        csv_was_modified = check_and_balance_csv(csv_file, total_amount)
        
        # If CSV was modified, recalculate totals
        if csv_was_modified:
            print(f"🔄 Recalculating totals after balance adjustment...")
            
            # Re-read the updated CSV
            updated_transactions = []
            updated_recategorized_count = 0
            
            try:
                with open(csv_file, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        original_category = row['category']
                        merchant = row['merchant']
                        
                        # Apply master categorization rules
                        final_category, is_new_vendor = recategorize_transaction(
                            merchant, original_category, master_categories, set()  # Don't add new vendors on recalc
                        )
                        
                        if final_category != original_category:
                            updated_recategorized_count += 1
                        
                        updated_transactions.append({
                            'date': row['date'],
                            'cardholder': row['cardholder'],
                            'merchant': merchant,
                            'amount': float(row['amount']),
                            'type': row['type'],
                            'original_category': original_category,
                            'category': final_category
                        })
                        
                # Recalculate totals
                updated_category_totals = {}
                updated_original_totals = {}
                updated_total_amount = 0
                
                for txn in updated_transactions:
                    final_category = txn['category']
                    original_category = txn['original_category']
                    amount = txn['amount']
                    
                    if final_category not in updated_category_totals:
                        updated_category_totals[final_category] = {'count': 0, 'total': 0.0}
                    updated_category_totals[final_category]['count'] += 1
                    updated_category_totals[final_category]['total'] += amount
                    
                    if original_category not in updated_original_totals:
                        updated_original_totals[original_category] = {'count': 0, 'total': 0.0}
                    updated_original_totals[original_category]['count'] += 1
                    updated_original_totals[original_category]['total'] += amount
                    
                    updated_total_amount += amount
                
                return updated_category_totals, updated_original_totals, updated_total_amount, len(updated_transactions), updated_recategorized_count, len(new_vendors)
                
            except Exception as e:
                print(f"⚠️  Warning: Could not recalculate after balance adjustment: {e}")
                # Fall through to return original totals
    
    return category_totals, original_category_totals, total_amount, len(transactions), recategorized_count, len(new_vendors)

def process_directory(directory_path):
    """Process all CSV files in a directory and combine results"""
    if not os.path.exists(directory_path):
        print(f"❌ Error: Directory not found: {directory_path}")
        return None
    
    # Find all CSV files in directory
    csv_pattern = os.path.join(directory_path, "*.csv")
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        print(f"❌ Error: No CSV files found in directory: {directory_path}")
        return None
    
    print(f"📁 Found {len(csv_files)} CSV files in directory")
    
    # Use master file in the same directory
    master_file = os.path.join(directory_path, "categories.master")
    
    # Combined results
    combined_category_totals = {}
    combined_original_totals = {}
    total_amount = 0
    total_transactions = 0
    total_recategorized = 0
    total_new_vendors = 0
    
    # Process each CSV file
    for csv_file in sorted(csv_files):
        print(f"\n📊 Processing: {os.path.basename(csv_file)}")
        
        result = calculate_category_totals(csv_file, master_file, auto_balance=False)  # Don't auto-balance individual files in directory scan
        if result is None:
            continue
            
        category_totals, original_totals, amount, count, recategorized, new_vendors = result
        
        # Display individual file summary
        print(f"\n" + "=" * 50)
        print(f"SUMMARY: {os.path.basename(csv_file)}")
        print("=" * 50)
        display_category_totals(category_totals, original_totals, amount, count, recategorized, new_vendors, show_comparison=False)
        
        # Combine results
        for category, stats in category_totals.items():
            if category not in combined_category_totals:
                combined_category_totals[category] = {'count': 0, 'total': 0.0}
            combined_category_totals[category]['count'] += stats['count']
            combined_category_totals[category]['total'] += stats['total']
        
        for category, stats in original_totals.items():
            if category not in combined_original_totals:
                combined_original_totals[category] = {'count': 0, 'total': 0.0}
            combined_original_totals[category]['count'] += stats['count']
            combined_original_totals[category]['total'] += stats['total']
        
        total_amount += amount
        total_transactions += count
        total_recategorized += recategorized
        total_new_vendors += new_vendors
    
    print(f"\n" + "=" * 70)
    print(f"COMBINED RESULTS FROM {len(csv_files)} FILES")
    print(f"Directory: {directory_path}")
    print("=" * 70)
    
    return combined_category_totals, combined_original_totals, total_amount, total_transactions, total_recategorized, total_new_vendors

def add_misc_balancing_entry(csv_file, difference_amount):
    """Add a MISC vendor entry to balance small differences in the CSV file"""
    try:
        # Read existing CSV data
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        # Get the last transaction date for reference
        last_date = rows[-1]['date'] if rows else datetime.now().strftime('%Y/%m/%d')
        
        # Create MISC balancing entry
        misc_entry = {
            'date': last_date,
            'cardholder': 'SYSTEM',
            'merchant': 'MISC BALANCE ADJUSTMENT',
            'amount': f"{difference_amount:.2f}",
            'type': 'Adjustment',
            'category': 'MISCELLANEOUS'
        }
        
        # Add the balancing entry
        rows.append(misc_entry)
        
        # Write back to CSV
        with open(csv_file, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            
        print(f"💰 Added MISC balance adjustment: ${difference_amount:.2f}")
        return True
        
    except Exception as e:
        print(f"⚠️  Warning: Could not add balance adjustment: {e}")
        return False

def check_and_balance_csv(csv_file, total_amount, tolerance=1.00):
    """Check if total is close to zero and add balancing entry if needed"""
    # Check if the total is a small positive or negative amount
    if 0 < abs(total_amount) < tolerance:
        print(f"\n🔍 Detected small imbalance: ${total_amount:.2f}")
        print(f"📝 Adding MISC balancing entry to achieve zero balance...")
        
        # Add opposite amount to balance to zero
        balance_amount = -total_amount
        success = add_misc_balancing_entry(csv_file, balance_amount)
        
        if success:
            print(f"✅ CSV file balanced with MISC adjustment")
            return True
        else:
            print(f"❌ Failed to balance CSV file")
            return False
    
    return False

def display_category_totals(category_totals, original_category_totals, total_amount, total_count, recategorized_count, new_vendors_count=0, show_comparison=False):
    """Display category totals in a formatted table"""
    if not category_totals:
        print("❌ No categories found")
        return
    
    # Sort categories by total (highest first)
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1]['total'], reverse=True)
    
    print(f"\n" + "=" * 70)
    print("CATEGORY TOTALS")
    print("=" * 70)
    
    # Table header
    print(f"{'Category':<25} {'Count':<8} {'Total':<15} {'% of Total':<12}")
    print("-" * 70)
    
    # Category rows
    for category, stats in sorted_categories:
        percentage = (stats['total'] / total_amount * 100) if total_amount > 0 else 0
        print(f"{category:<25} {stats['count']:<8} ${stats['total']:<14,.2f} {percentage:<11.1f}%")
    
    # Summary row
    print("-" * 70)
    print(f"{'TOTAL':<25} {total_count:<8} ${total_amount:<14,.2f} {'100.0':<11}%")
    print("=" * 70)
    
    if recategorized_count > 0 or new_vendors_count > 0:
        print(f"\n📊 MASTER FILE MAINTENANCE:")
        if recategorized_count > 0:
            print(f"   • {recategorized_count} transactions recategorized using existing rules")
        if new_vendors_count > 0:
            print(f"   • {new_vendors_count} new vendors added to categories.master")
        remaining = total_count - recategorized_count - new_vendors_count
        if remaining > 0:
            print(f"   • {remaining} transactions used existing master rules")
    
    # Show comparison if requested and there were changes
    if show_comparison and recategorized_count > 0 and original_category_totals:
        print(f"\n" + "=" * 70)
        print("COMPARISON: ORIGINAL vs FINAL CATEGORIES")
        print("=" * 70)
        
        # Show categories that changed
        all_categories = set(category_totals.keys()) | set(original_category_totals.keys())
        
        for category in sorted(all_categories):
            orig_total = original_category_totals.get(category, {'total': 0, 'count': 0})['total']
            final_total = category_totals.get(category, {'total': 0, 'count': 0})['total']
            
            if abs(orig_total - final_total) > 0.01:  # Only show changed categories
                change = final_total - orig_total
                if change > 0:
                    print(f"{category:<25} ${orig_total:>8,.2f} → ${final_total:>8,.2f} (+${change:,.2f})")
                else:
                    print(f"{category:<25} ${orig_total:>8,.2f} → ${final_total:>8,.2f} (${change:,.2f})")

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description='Calculate category totals with automatic master file maintenance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python category_totals.py statement.csv
  python category_totals.py -d 0801/                    # Process all CSV files in directory
  python category_totals.py statement.csv --show-comparison
  
Notes:
  - Automatically creates and maintains categories.master file in same directory
  - New vendors are added to the master file automatically 
  - Master file is kept sorted by vendor name for easy editing
  - Edit categories.master to customize vendor categorizations
  - Use -d to process all CSV files in a directory
        """
    )
    
    parser.add_argument('csv_file', nargs='?', help='CSV file containing categorized transactions')
    parser.add_argument('-d', '--directory', help='Directory containing CSV files to process')
    parser.add_argument('--show-comparison', action='store_true',
                       help='Show comparison between original and recategorized totals')
    parser.add_argument('--no-balance', action='store_true',
                       help='Disable automatic balancing of small differences')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.directory and not args.csv_file:
        parser.error('Must specify either csv_file or -d/--directory')
    
    if args.directory and args.csv_file:
        parser.error('Cannot specify both csv_file and -d/--directory')
    
    # Process directory or single file
    if args.directory:
        result = process_directory(args.directory)
    else:
        # Single file - master file goes in same directory as CSV
        csv_dir = os.path.dirname(os.path.abspath(args.csv_file))
        master_file = os.path.join(csv_dir, "categories.master")
        result = calculate_category_totals(args.csv_file, master_file, auto_balance=not args.no_balance)  # Auto-balance unless disabled
    
    if result is None:
        sys.exit(1)
    
    category_totals, original_category_totals, total_amount, total_count, recategorized_count, new_vendors_count = result
    
    # Display results
    display_category_totals(category_totals, original_category_totals, total_amount, total_count, 
                          recategorized_count, new_vendors_count, args.show_comparison)
    
    print(f"\n💡 Tips:")
    print(f"   • Edit categories.master to customize vendor categorizations")
    print(f"   • Master file is automatically maintained and sorted")
    print(f"   • Use --show-comparison to see before/after changes")
    print(f"   • Use -d to process all CSV files in a directory")

if __name__ == "__main__":
    main()