#!/usr/bin/env python3
"""
Credit Card Statement Transaction Extractor
Extracts transactions from Chase credit card statement PDF
"""

import re
import csv
from datetime import datetime
import sys

def extract_transactions_from_text(text):
    """Extract all transactions from the PDF text content"""
    transactions = []
    
    # Define patterns for different types of transactions
    patterns = [
        # Standard transaction pattern: Date, Merchant, Amount
        r'(\d{2}/\d{2})\s+([A-Z*#\s\w\-\.\(\)\'&/,:\$@]+?)\s+(\d+\.\d{2})(?:\s|$)',
        # Payment pattern (negative amounts)
        r'(\d{2}/\d{2})\s+([A-Z*#\s\w\-\.\(\)\'&/,:\$@]+?)\s+(-\d+[,\d]*\.\d{2})(?:\s|$)',
    ]
    
    # Track current cardholder
    current_cardholder = "ASHOK RAJ"  # Default
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Check for cardholder names
        if any(name in line for name in ["ASHOK RAJ", "AAKASH RAJ", "SUMATHI RAJ", "AKSHAY RAJ"]):
            if "ASHOK RAJ" in line:
                current_cardholder = "ASHOK RAJ"
            elif "AAKASH RAJ" in line:
                current_cardholder = "AAKASH RAJ"
            elif "SUMATHI RAJ" in line:
                current_cardholder = "SUMATHI RAJ"
            elif "AKSHAY RAJ" in line:
                current_cardholder = "AKSHAY RAJ"
            continue
            
        # Skip summary lines and headers
        if any(skip_term in line.upper() for skip_term in [
            'TRANSACTIONS THIS CYCLE', 'ACCOUNT ACTIVITY', 'STATEMENT DATE',
            'MERCHANT NAME', 'DATE OF', 'TRANSACTION', '$ AMOUNT', 'PAGE',
            'ACCOUNT SUMMARY', 'NEW BALANCE', 'MINIMUM PAYMENT', 'PREVIOUS BALANCE',
            'INCLUDING PAYMENTS RECEIVED'
        ]):
            continue
            
        # Try to match transaction patterns
        for pattern in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                date_str = match.group(1)
                merchant = match.group(2).strip()
                amount_str = match.group(3).replace(',', '')
                
                # Clean up merchant name
                merchant = ' '.join(merchant.split())
                merchant = merchant.replace('TST*', '').replace('*', '').strip()
                
                # Skip if merchant is too short or looks like summary data
                if len(merchant) < 3 or merchant.upper() in ['OR', 'CA', 'TX', 'WA', 'MA']:
                    continue
                    
                try:
                    amount = float(amount_str)
                    # Add year (assume 2025 based on statement)
                    full_date = f"2025/{date_str}"
                    
                    transaction = {
                        'date': full_date,
                        'cardholder': current_cardholder,
                        'merchant': merchant,
                        'amount': amount,
                        'raw_line': line
                    }
                    transactions.append(transaction)
                    break  # Found a match, move to next line
                except ValueError:
                    continue
    
    return transactions

def save_to_csv(transactions, filename):
    """Save transactions to CSV file"""
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['date', 'cardholder', 'merchant', 'amount', 'type']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for txn in transactions:
            # Determine transaction type
            txn_type = 'Credit/Payment' if txn['amount'] < 0 else 'Purchase'
            
            writer.writerow({
                'date': txn['date'],
                'cardholder': txn['cardholder'],
                'merchant': txn['merchant'],
                'amount': txn['amount'],
                'type': txn_type
            })

def main():
    # Read actual PDF text from the document content we have
    # This includes all the transaction data from the actual PDF
    pdf_text = """
ACCOUNT ACTIVITY
Date of
Transaction Merchant Name or Transaction Description $ Amount
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
07/04 Amazon.com*N33P87HK1 Amzn.com/bill WA 71.77
07/05 THE WEBSTAURANT STORE INC 717-392-7472 PA 194.39
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
SUMATHI RAJ
TRANSACTIONS THIS CYCLE (CARD 6457) $884.92
06/08 CAFE WEEKEND ALLSTON MA 111.04
06/11 GDP*TP Produce Portland OR 205.99
06/12 CHEFSTORE 7208 BEAVERTON OR 92.41
06/12 CLR*StretchLab5036932599 503-6932599 OR 16.00
06/19 IN *NORTHWEST BIOFUEL 503-9546173 OR 135.00
06/27 CVSExtraCare 8007467287RI 800-746-7287 RI 5.00
07/01 US LINEN AND UNIFORM 509-9466125 WA 319.48
AKSHAY RAJ
TRANSACTIONS THIS CYCLE (CARD 3346) $1377.97
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
"""
    
    # Extract transactions
    transactions = extract_transactions_from_text(pdf_text)
    
    # Save to CSV
    csv_filename = 'chase_transactions.csv'
    save_to_csv(transactions, csv_filename)
    
    # Print summary
    print(f"\nExtracted {len(transactions)} transactions")
    print(f"Saved to: {csv_filename}")
    
    # Show summary by cardholder
    cardholders = {}
    total_amount = 0
    
    for txn in transactions:
        cardholder = txn['cardholder']
        amount = txn['amount']
        
        if cardholder not in cardholders:
            cardholders[cardholder] = {'count': 0, 'total': 0}
        
        cardholders[cardholder]['count'] += 1
        cardholders[cardholder]['total'] += amount
        total_amount += amount
    
    print("\nSummary by Cardholder:")
    for cardholder, stats in cardholders.items():
        print(f"{cardholder}: {stats['count']} transactions, Total: ${stats['total']:,.2f}")
    
    print(f"\nGrand Total: ${total_amount:,.2f}")

if __name__ == "__main__":
    main()