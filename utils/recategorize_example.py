#!/usr/bin/env python3
"""
Example: How to recategorize transactions in CSV file
This shows how to edit categories programmatically or manually
"""

import csv
import sys

def show_recategorization_example(csv_file):
    """Show how to recategorize transactions"""
    
    print("📝 MANUAL RECATEGORIZATION EXAMPLE")
    print("=" * 50)
    print()
    print("1. Open your CSV file in any text editor or Excel")
    print("2. Find transactions you want to recategorize")
    print("3. Edit the 'category' column")
    print("4. Save the file")
    print("5. Run category_totals.py again")
    print()
    
    # Read a few transactions to show examples
    try:
        with open(csv_file, 'r') as file:
            reader = csv.DictReader(file)
            transactions = list(reader)[:10]
    except:
        print("Could not read CSV file for examples")
        return
    
    print("EXAMPLES FROM YOUR FILE:")
    print("-" * 30)
    
    for i, txn in enumerate(transactions[:5], 1):
        merchant = txn['merchant'][:30] + "..." if len(txn['merchant']) > 30 else txn['merchant']
        print(f"{i}. ${float(txn['amount']):,.2f} | {merchant}")
        print(f"   Current: {txn['category']}")
        
        # Suggest alternative categories for some transactions
        if 'COSTCO' in txn['merchant'].upper():
            if txn['category'] == 'GROCERY':
                print(f"   Could change to: WAREHOUSE_SHOPPING")
        elif 'RESTAURANT' in txn['merchant'].upper():
            if txn['category'] == 'RESTAURANT':
                print(f"   Could change to: BUSINESS_MEALS")
        elif 'AMAZON' in txn['merchant'].upper():
            if txn['category'] == 'SHOPPING':
                print(f"   Could change to: ONLINE_SHOPPING")
        
        print()
    
    print("📋 COMMON RECATEGORIZATION PATTERNS:")
    print("-" * 40)
    print("• COSTCO purchases → WAREHOUSE_SHOPPING")
    print("• Restaurant Depot → BUSINESS_SUPPLIES") 
    print("• Amazon purchases → ONLINE_SHOPPING")
    print("• Large restaurant bills → BUSINESS_MEALS")
    print("• Equipment purchases → BUSINESS_EQUIPMENT")
    print()
    
    print("💡 WORKFLOW:")
    print("1. python category_totals.py your_file.csv  # See current totals")
    print("2. Edit CSV file categories as needed")
    print("3. python category_totals.py your_file.csv  # See updated totals")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python recategorize_example.py your_file.csv")
        sys.exit(1)
    
    show_recategorization_example(sys.argv[1])