#!/usr/bin/env python3
"""
Verify transaction totals against statement
Removes payments and compares purchase totals with statement
"""

import csv
import pandas as pd

def process_transactions():
    """Remove payments and calculate purchase totals"""
    
    # Read the complete CSV file
    df = pd.read_csv('chase_complete_transactions.csv')
    
    print(f"Total transactions loaded: {len(df)}")
    
    # Show breakdown by type
    type_counts = df['type'].value_counts()
    print(f"Transaction types: {type_counts.to_dict()}")
    
    # Filter out payments/credits
    purchases_only = df[df['type'] == 'Purchase'].copy()
    payments_only = df[df['type'] == 'Credit/Payment'].copy()
    
    print(f"\nPurchases: {len(purchases_only)}")
    print(f"Payments/Credits: {len(payments_only)}")
    
    # Show payments being removed
    print("\nPayments/Credits being removed:")
    for _, payment in payments_only.iterrows():
        print(f"  {payment['date']} - {payment['cardholder']} - {payment['merchant']} - ${payment['amount']:,.2f}")
    
    # Calculate totals by cardholder (purchases only)
    cardholder_totals = purchases_only.groupby('cardholder')['amount'].sum()
    
    print(f"\nPurchase totals by cardholder (excluding payments):")
    total_purchases = 0
    for cardholder, total in cardholder_totals.items():
        print(f"  {cardholder}: ${total:,.2f}")
        total_purchases += total
    
    print(f"\nTotal purchases (all cardholders): ${total_purchases:,.2f}")
    
    # Save purchases-only CSV
    purchases_only.to_csv('chase_purchases_only.csv', index=False)
    print(f"Saved purchases-only data to: chase_purchases_only.csv")
    
    return total_purchases, cardholder_totals

def find_statement_totals():
    """Extract totals from the statement data"""
    
    # From the PDF analysis, key totals are:
    statement_data = {
        'new_balance': 20482.54,
        'previous_balance': 22898.07,
        'payments_credits': -22898.07,
        'purchases': 20482.54,  # This should match our calculation
        'cash_advances': 0.00,
        'balance_transfers': 0.00,
        'fees_charged': 0.00,
        'interest_charged': 0.00
    }
    
    print("\nStatement Summary from PDF:")
    print(f"  New Balance: ${statement_data['new_balance']:,.2f}")
    print(f"  Previous Balance: ${statement_data['previous_balance']:,.2f}")
    print(f"  Payments/Credits: ${statement_data['payments_credits']:,.2f}")
    print(f"  Purchases: ${statement_data['purchases']:,.2f}")
    print(f"  Cash Advances: ${statement_data['cash_advances']:,.2f}")
    print(f"  Balance Transfers: ${statement_data['balance_transfers']:,.2f}")
    print(f"  Fees Charged: ${statement_data['fees_charged']:,.2f}")
    print(f"  Interest Charged: ${statement_data['interest_charged']:,.2f}")
    
    return statement_data

def main():
    print("="*60)
    print("TRANSACTION VERIFICATION ANALYSIS")
    print("="*60)
    
    # Process transactions
    calculated_total, cardholder_totals = process_transactions()
    
    print("\n" + "="*60)
    
    # Get statement totals
    statement_data = find_statement_totals()
    
    print("\n" + "="*60)
    print("COMPARISON")
    print("="*60)
    
    statement_purchases = statement_data['purchases']
    difference = calculated_total - statement_purchases
    
    print(f"Statement Purchases Total: ${statement_purchases:,.2f}")
    print(f"Calculated Purchases Total: ${calculated_total:,.2f}")
    print(f"Difference: ${difference:,.2f}")
    
    if abs(difference) < 0.01:
        print("✅ MATCH: Totals match!")
    else:
        print(f"❌ MISMATCH: Difference of ${abs(difference):,.2f}")
        
    # Show percentage difference
    if statement_purchases > 0:
        pct_diff = (difference / statement_purchases) * 100
        print(f"Percentage difference: {pct_diff:.2f}%")

if __name__ == "__main__":
    main()