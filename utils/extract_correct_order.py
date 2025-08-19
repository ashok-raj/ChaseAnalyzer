#!/usr/bin/env python3
"""
Extract transactions with correct cardholder assignment
Logic: Cardholder name appears one line before "TRANSACTIONS THIS CYCLE"
and owns all transactions that came before it since the last cardholder assignment
"""

import csv
import re

def extract_transactions_correct_assignment():
    """Extract transactions with correct cardholder assignment logic"""
    
    # Exact transaction data from PDF in statement order
    statement_text = """
06/08 TST* APNA BAZAAR - NEW BEAVERTON OR 64.00
06/10 COSTCO WHSE #0692 HILLSBORO OR 779.76
06/10 COSTCO GAS #0692 HILLSBORO OR 86.72
06/10 CITY OF HILLSBORO 503-615-6628 OR 91.96
06/11 CHEFSTORE 7537 PORTLAND OR 92.78
06/11 CHEFSTORE 7208 BEAVERTON OR 82.58
06/11 RESTAURANT DEPOT PORTLAND OR 3,493.67
06/13 INDIA SUPERMARKET BEAVERTON OR 13.20
06/17 COSTCO WHSE #0692 HILLSBORO OR 461.29
06/17 SAFEWAY #1230 HILLSBORO OR 2.29
06/18 COSTCO WHSE #0692 HILLSBORO OR 41.95
06/18 CHEFSTORE 7208 BEAVERTON OR 46.09
06/18 RESTAURANT DEPOT PORTLAND OR 1,921.88
06/20 SAFEWAY #1230 HILLSBORO OR 12.98
06/20 INDIA SUPERMARKET BEAVERTON OR 42.33
06/24 COSTCO WHSE #0009 ALOHA OR 403.15
06/24 COSTCO GAS #0009 ALOHA OR 79.65
06/25 TST* APNA BAZAAR - NEW BEAVERTON OR 64.00
06/25 CHEFSTORE 7537 PORTLAND OR 59.82
06/25 RESTAURANT DEPOT PORTLAND OR 1,615.60
07/01 COSTCO WHSE #0009 ALOHA OR 397.77
07/01 ABOVE ALL ACCOUNTING 503-3516455 OR 561.60
07/02 CHEFSTORE 7537 PORTLAND OR 131.87
07/02 TST* APNA BAZAAR - NEW BEAVERTON OR 5.66
07/02 RESTAURANT DEPOT PORTLAND OR 1,727.28
07/02 INDIA SUPERMARKET BEAVERTON OR 75.32
AAKASH RAJ
TRANSACTIONS THIS CYCLE (CARD 7172) $12355.20
06/17 AMZNMktplace amazon.co.uk -11.33
06/28 Payment Thank You-Mobile -19,000.00
06/28 Payment Thank You-Mobile -3,886.74
06/07 CCSI EFAX 323-817-3205 CA 169.50
06/09 PORTLAND GENERAL ELECTRIC 800-542-8818 OR 552.11
06/09 PORTLAND GENERAL ELECTRIC 800-542-8818 OR 499.59
06/09 OR SEC STATE CORPDIV 503-9862200 OR 100.00
06/12 GOOGLE *YouTube TV g.co/helppay# CA 82.99
06/12 TUALATIN VALLEY WATER 503-848-3000 OR 209.13
06/12 COMCAST / XFINITY 800-266-2278 OR 237.08
06/13 VONAGE *PRICE+TAXES 732-944-0000 NJ 16.31
06/13 PORTLAND PARKING KITTY 503-2785410 OR 5.40
06/17 eBay O*13-13208-17685 800-4563229 CA 37.99
06/18 JG *LYMPHOMA ACTION LONDON 25.00
06/18 NMI*NATIONWIDE 800-282-1446 IA 426.09
06/19 Amazon.com*NO73404K1 Amzn.com/bill WA 62.30
06/20 AMAZON MKTPL*NO2RH3151 Amzn.com/bill WA 55.95
06/22 AMAZON MKTPL*NO11F5PF0 Amzn.com/bill WA 22.95
06/22 NETFLIX.COM NETFLIX.COM CA 24.99
06/23 GOOGLE *Google One 855-836-3987 CA 2.99
06/24 PORTLAND GENERAL ELECTRIC 800-542-8818 OR 649.30
06/24 PORTLAND GENERAL ELECTRIC 800-542-8818 OR 811.91
06/24 HLU*HULUPLUS hulu.com/bill CA 26.99
06/24 PORTLAND GENERAL ELECTRIC 800-542-8818 OR 76.31
06/27 WWW.SPOTHOPPERAPP.COM WWW.SPOTHOPPE WI 448.00
06/27 APPLE.COM/BILL 866-712-7753 CA 4.99
07/02 CLCKPAY*TANASBOURNE PLACE 800-5337901 NY 308.34
07/02 AMAZON MKTPL*N35F98TV0 Amzn.com/bill WA 19.99
07/02 AMAZON MKTPL*N33010EH1 Amzn.com/bill WA 50.85
07/03 ADT SECURITY*404603211 WWW.ADT.COM FL 57.23
07/03 PITMAN RESTARAUNT EQUIP 800-2046431 OR 159.00
07/03 PY *Saela Pest Control 866-5290864 UT 80.00
07/04 AMAZON MKTPL*N35EN25T0 Amzn.com/bill WA 149.95
07/05 Amazon Tips*N36F756C1 Amzn.com/bill WA 5.00
07/06 PERFECTPOUR* PERF POUR PERFECTPOURSE OR 77.06
07/05 COMCAST / XFINITY 800-266-2278 OR 143.00
07/04 Amazon.com*N33P87HK1 Amzn.com/bill WA 71.77
07/05 THE WEBSTAURANT STORE INC 717-392-7472 PA 194.39
ASHOK RAJ
TRANSACTIONS THIS CYCLE (CARD 0801) $17033.62-
INCLUDING PAYMENTS RECEIVED
06/08 CAFE WEEKEND ALLSTON MA 111.04
06/11 GDP*TP Produce Portland OR 205.99
06/12 CHEFSTORE 7208 BEAVERTON OR 92.41
06/12 CLR*StretchLab5036932599 503-6932599 OR 16.00
06/19 IN *NORTHWEST BIOFUEL 503-9546173 OR 135.00
06/27 CVSExtraCare 8007467287RI 800-746-7287 RI 5.00
07/01 US LINEN AND UNIFORM 509-9466125 WA 319.48
SUMATHI RAJ
TRANSACTIONS THIS CYCLE (CARD 6457) $884.92
06/09 CHIPOTLE 2686 PORTLAND OR 28.90
06/12 DENNIS MARKET PORTLAND OR 4.10
06/14 MY FAVORITE MUFFIN BEAVERTON OR 23.25
06/14 NORDSTROM #0025 TIGARD OR 132.00
06/14 REDTAIL GOLF CENTER BEAVERTON OR 30.00
06/17 MARKET OF CHOICE #2 PORTLAND OR 20.88
06/17 KRISPY KREME #9000 BEAVERTON OR 19.99
06/20 TARGET 00034132 PORTLAND OR 34.97
06/21 PDX POOR YOURNWTRAVEL Portland OR 14.97
06/22 TST* JAMBA JUICE - 103299 PORTLAND OR 9.39
06/26 CULTUREMAPST2571 HOUSTON TX 6.72
06/28 053 TORCHYS WESTCHASE HOUSTON TX 22.15
06/28 CHERRY HOUSTON TX 33.78
06/28 TST*AGAS RESTAURANT & C Houston TX 96.10
06/27 OAKLEY B016 HOUSTON TX 73.08
06/28 TST* EL CENTRO HTX HOUSTON TX 31.11
06/29 TST* VELVET TACO - HOUSTO HOUSTON TX 29.29
06/28 DEAN S DOWNTOWN HOUSTON TX 50.15
06/28 TST*CICCIOS PASTA Houston TX 19.72
06/29 IAH CS FORNO MAGICO 866-5083558 TX 22.09
06/30 TST* SALT AND STRAW - CED BEAVERTON OR 6.84
06/28 OJOS LOCOS SPORTS 5004 HOUSTON TX 5.00
06/29 10207 CAVA WESTCHASE HOUSTON TX 21.70
06/29 IAH CN Q BAR 866-5083558 TX 22.09
06/29 IAH CS FORNO MAGICO 866-5083558 TX 22.09
07/01 LTF*LIFE TIME MO DUES LIFETIME.LIFE MN 255.23
07/03 COSTCO WHSE #0483 SAN DIEGO CA 157.23
07/03 10453 CAVA FRONT & BRO SAN DIEGO CA 25.64
07/04 TST*SMOKING GUN - SAN DI San Diego CA 13.01
07/05 TST* OPEN BAR SAN DIEGO CA 26.40
07/05 GAMESTOP #1403 SAN DIEGO CA 34.78
07/05 THE LOT POINT LOMA 619-566-0096 CA 46.00
07/04 GAME EMPIRE INC SAN DIEGO CA 12.92
07/05 TST* OPEN BAR SAN DIEGO CA 13.20
07/05 TST* OPEN BAR SAN DIEGO CA 13.20
AKSHAY RAJ
TRANSACTIONS THIS CYCLE (CARD 3346) $1377.97
"""
    
    lines = statement_text.strip().split('\n')
    all_transactions = []
    pending_transactions = []
    
    # Transaction pattern: MM/DD MERCHANT DESCRIPTION AMOUNT
    transaction_pattern = r'^(\d{2}/\d{2})\s+(.+?)\s+([-]?\d{1,3}(?:,\d{3})*\.?\d{2})$'
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Check if next line contains "TRANSACTIONS THIS CYCLE"
        if i + 1 < len(lines) and "TRANSACTIONS THIS CYCLE" in lines[i + 1]:
            # This line is a cardholder name
            cardholder = line
            
            # Assign all pending transactions to this cardholder
            for txn_data in pending_transactions:
                date_str, merchant, amount = txn_data
                transaction = {
                    'date': f"2025/{date_str}",
                    'cardholder': cardholder,
                    'merchant': merchant,
                    'amount': amount,
                    'type': 'Credit/Payment' if amount < 0 else 'Purchase'
                }
                all_transactions.append(transaction)
            
            # Clear pending transactions
            pending_transactions = []
            
            # Skip the "TRANSACTIONS THIS CYCLE" line and any following descriptive lines
            i += 2
            # Skip "INCLUDING PAYMENTS RECEIVED" if present
            if i < len(lines) and "INCLUDING PAYMENTS RECEIVED" in lines[i]:
                i += 1
            continue
        
        # Check if this is a transaction line
        match = re.match(transaction_pattern, line)
        if match:
            date_str = match.group(1)
            merchant = match.group(2).strip()
            amount_str = match.group(3).replace(',', '')
            
            try:
                amount = float(amount_str)
                
                # Clean up merchant name
                merchant = ' '.join(merchant.split())
                
                # Add to pending transactions
                pending_transactions.append((date_str, merchant, amount))
                
            except ValueError:
                # Skip if amount can't be parsed
                pass
        
        i += 1
    
    return all_transactions

def save_to_csv(transactions, filename):
    """Save transactions to CSV file"""
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['date', 'cardholder', 'merchant', 'amount', 'type']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for txn in transactions:
            writer.writerow(txn)

def main():
    print("="*60)
    print("EXTRACTING WITH CORRECT CARDHOLDER ASSIGNMENT")
    print("="*60)
    
    # Extract transactions with correct assignment
    transactions = extract_transactions_correct_assignment()
    
    # Save to CSV
    filename = 'chase_correct_assignment.csv'
    save_to_csv(transactions, filename)
    
    # Calculate totals
    purchase_total = sum(txn['amount'] for txn in transactions if txn['type'] == 'Purchase')
    payment_total = sum(txn['amount'] for txn in transactions if txn['type'] == 'Credit/Payment')
    
    # Summary by cardholder in order of appearance
    cardholders_order = []
    cardholders = {}
    
    for txn in transactions:
        cardholder = txn['cardholder']
        if cardholder not in cardholders:
            cardholders_order.append(cardholder)
            cardholders[cardholder] = {'purchases': 0, 'payments': 0, 'count': 0}
        
        cardholders[cardholder]['count'] += 1
        if txn['type'] == 'Purchase':
            cardholders[cardholder]['purchases'] += txn['amount']
        else:
            cardholders[cardholder]['payments'] += txn['amount']
    
    print(f"Total transactions extracted: {len(transactions)}")
    print(f"Saved to: {filename}")
    
    print(f"\nGrand Totals:")
    print(f"  Total Purchases: ${purchase_total:,.2f}")
    print(f"  Total Payments/Credits: ${payment_total:,.2f}")
    print(f"  Net Amount: ${purchase_total + payment_total:,.2f}")
    
    print(f"\nBy Cardholder (in statement order):")
    for cardholder in cardholders_order:
        stats = cardholders[cardholder]
        print(f"\n{cardholder}: {stats['count']} transactions")
        print(f"  Purchases: ${stats['purchases']:,.2f}")
        print(f"  Payments/Credits: ${stats['payments']:,.2f}")
        print(f"  Net: ${stats['purchases'] + stats['payments']:,.2f}")
    
    # Show first few transactions to verify assignment
    print(f"\nFirst 10 transactions:")
    for i, txn in enumerate(transactions[:10]):
        print(f"{i+1:2d}. {txn['date']} - {txn['cardholder'][:12]:12} - {txn['merchant'][:35]:35} - ${txn['amount']:>8.2f}")
        
    print(f"\nStatement total should be $20,482.54")
    print(f"Our purchase total: ${purchase_total:,.2f}")
    if abs(purchase_total - 20482.54) < 0.01:
        print("✅ MATCH!")
    else:
        print(f"❌ Difference: ${purchase_total - 20482.54:,.2f}")

if __name__ == "__main__":
    main()