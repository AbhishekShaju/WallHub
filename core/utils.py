from datetime import datetime
import random
import string

def generate_invoice_number():
    """
    Generate a unique invoice number in the format: INV-YYYYMMDD-XXXXX
    where:
    - YYYYMMDD is the current date
    - XXXXX is a random 5-digit number
    """
    # Get current date in YYYYMMDD format
    date_str = datetime.now().strftime('%Y%m%d')
    
    # Generate a random 5-digit number
    random_num = ''.join(random.choices(string.digits, k=5))
    
    # Combine to create invoice number
    invoice_number = f'INV-{date_str}-{random_num}'
    
    return invoice_number 