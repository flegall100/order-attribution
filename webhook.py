import os
import json
import requests
from requests_oauthlib import OAuth1
from datetime import datetime

try:
    import pytz
    CST = pytz.timezone('US/Central')
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False
    CST = None

class BigCommerceService:
    def __init__(self, store_hash, access_token, store_name=None):
        self.store_hash = store_hash
        self.access_token = access_token
        self.store_name = store_name or store_hash
        self.base_url = "https://api.bigcommerce.com/stores/{}/v2".format(store_hash)
        
    def get_order_details(self, order_id):
        """Get detailed order information"""
        try:
            url = "{}/orders/{}".format(self.base_url, order_id)
            headers = {
                'X-Auth-Token': self.access_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            billing_address = data.get('billing_address', {})
            
            return {
                'id': data.get('id'),
                'email': billing_address.get('email', ''),
                'customer_name': "{} {}".format(billing_address.get('first_name', ''), billing_address.get('last_name', '')).strip(),
                'phone': billing_address.get('phone', ''),
                'order_date': data.get('date_created'),
                'order_total': data.get('subtotal_ex_tax', data.get('total_ex_tax', '0.00')),
                'store': self.store_name
            }
            
        except Exception as error:
            print("Error fetching order {} from {}: {}".format(order_id, self.store_name, error))
            raise error

class NetSuiteService:
    def __init__(self):
        self.account_id = os.getenv('NETSUITE_ACCOUNT_ID')
        self.consumer_key = os.getenv('NETSUITE_CONSUMER_KEY')
        self.consumer_secret = os.getenv('NETSUITE_CONSUMER_SECRET')
        self.token_id = os.getenv('NETSUITE_TOKEN_ID')
        self.token_secret = os.getenv('NETSUITE_TOKEN_SECRET')
        
        self.auth = OAuth1(
            self.consumer_key,
            self.consumer_secret,
            self.token_id,
            self.token_secret,
            signature_method='HMAC-SHA256',
            realm=self.account_id
        )
        
        self.query_base_url = "https://{}.suitetalk.api.netsuite.com/services/rest/query/v1".format(self.account_id.lower())
        
    def search_contact_by_email_and_phone(self, email, phone=None):
        """Search for contact by email and phone with discrepancy handling"""
        try:
            clean_phone = self._clean_phone(phone) if phone else None
            
            if clean_phone:
                perfect_match = self._search_customer_perfect_match(email, clean_phone)
                if perfect_match:
                    return perfect_match
            
            email_match = self._search_customer_email_only(email)
            if email_match:
                if clean_phone and email_match.get('phone'):
                    netsuite_phone = self._clean_phone(email_match.get('phone'))
                    if netsuite_phone != clean_phone:
                        email_match['manual_verification'] = True
                        email_match['review_reason'] = 'Phone number mismatch'
                    else:
                        email_match['manual_verification'] = False
                        email_match['review_reason'] = 'Perfect match'
                else:
                    email_match['manual_verification'] = True if clean_phone else False
                    email_match['review_reason'] = 'Missing phone in NetSuite' if clean_phone else 'No phone provided'
                
                return email_match
            
            return {
                'found': False,
                'manual_verification': True,
                'review_reason': 'No NetSuite record found'
            }
                
        except Exception as error:
            print("Error searching NetSuite contact: {}".format(error))
            return {
                'found': False,
                'manual_verification': True,
                'review_reason': 'Search error: {}'.format(str(error))
            }
    
    def _clean_phone(self, phone):
        """Clean phone number for comparison"""
        if not phone:
            return None
        import re
        return re.sub(r'\\D', '', phone)
    
    def _search_customer_perfect_match(self, email, clean_phone):
        """Search customer table for perfect email + phone match with sales rep"""
        query = """
        SELECT 
            id,
            email,
            phone,
            entityid,
            custentity_lead_caselastmoddate as last_contact_date,
            lastmodifieddate,
            datecreated,
            firstname,
            lastname,
            salesrep,
            'customer' as record_type
        FROM customer 
        WHERE UPPER(email) = UPPER('{}') 
        AND REGEXP_REPLACE(NVL(phone, ''), '[^0-9]', '') = '{}'
        AND salesrep IS NOT NULL
        
        ORDER BY 
            CASE WHEN last_contact_date IS NOT NULL THEN last_contact_date ELSE lastmodifieddate END DESC
        """.format(email, clean_phone)
        
        return self._execute_search_query(query, 'Perfect match')
    
    def _search_customer_email_only(self, email):
        """Search customer table for email-only match with sales rep"""
        query = """
        SELECT 
            id,
            email,
            phone,
            entityid,
            custentity_lead_caselastmoddate as last_contact_date,
            lastmodifieddate,
            datecreated,
            firstname,
            lastname,
            salesrep,
            'customer' as record_type
        FROM customer 
        WHERE UPPER(email) = UPPER('{}') 
        AND salesrep IS NOT NULL
        
        ORDER BY 
            CASE WHEN last_contact_date IS NOT NULL THEN last_contact_date ELSE lastmodifieddate END DESC
        """.format(email)
        
        return self._execute_search_query(query, 'Email match')
    
    def _execute_search_query(self, query, match_type):
        """Execute search query and process results"""
        try:
            url = "{}/suiteql".format(self.query_base_url)
            headers = {
                "Content-Type": "application/json",
                "Prefer": "transient"
            }
            
            response = requests.post(
                url, 
                auth=self.auth, 
                headers=headers, 
                json={"q": query},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                
                if items:
                    record = items[0]
                    sales_rep_id = record.get('salesrep')
                    
                    if sales_rep_id and str(sales_rep_id).isdigit():
                        sales_rep = self.get_employee_name(sales_rep_id)
                    else:
                        sales_rep = sales_rep_id or 'Not Assigned'
                    
                    return {
                        'contact_id': record.get('id'),
                        'email': record.get('email'),
                        'phone': record.get('phone'),
                        'sales_rep': sales_rep,
                        'contact_date': record.get('last_contact_date') or record.get('lastmodifieddate'),
                        'created_date': record.get('datecreated'),
                        'name': "{} {}".format(record.get('firstname', ''), record.get('lastname', '')).strip() or record.get('entityid', ''),
                        'record_type': record.get('record_type'),
                        'found': True,
                        'manual_verification': False,
                        'review_reason': match_type
                    }
                else:
                    return None
            else:
                print("NetSuite API Error: {}".format(response.status_code))
                return None
                
        except Exception as error:
            print("Error executing search query: {}".format(error))
            return None

    def get_employee_name(self, employee_id):
        """Get employee name from employee ID"""
        try:
            query = """
            SELECT 
                id,
                entityid,
                firstname,
                lastname,
                email
            FROM employee 
            WHERE id = '{}'
            """.format(employee_id)
            
            url = "{}/suiteql".format(self.query_base_url)
            headers = {
                "Content-Type": "application/json",
                "Prefer": "transient"
            }
            
            response = requests.post(url, auth=self.auth, headers=headers, json={"q": query}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                
                if items:
                    employee = items[0]
                    name = "{} {}".format(employee.get('firstname', ''), employee.get('lastname', '')).strip()
                    if not name:
                        name = employee.get('entityid', 'Employee ID: {}'.format(employee_id))
                    return name
            
            return 'Employee ID: {}'.format(employee_id)
            
        except Exception as error:
            print("Error fetching employee {}: {}".format(employee_id, error))
            return 'Employee ID: {}'.format(employee_id)

def format_bigcommerce_date(date_string):
    """Convert BigCommerce date to 12-hour AM/PM Central Time"""
    if not date_string:
        return ''
    
    try:
        for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ']:
            try:
                dt = datetime.strptime(date_string, fmt)
                if PYTZ_AVAILABLE and CST:
                    if dt.tzinfo is None:
                        dt = pytz.utc.localize(dt)
                    dt_cst = dt.astimezone(CST)
                    return dt_cst.strftime('%m/%d/%Y %I:%M:%S %p CST')
                else:
                    return dt.strftime('%m/%d/%Y %I:%M:%S %p UTC')
            except ValueError:
                continue
        
        return date_string
        
    except Exception as error:
        print("Error formatting date {}: {}".format(date_string, error))
        return date_string

def send_to_sheets(data):
    """Send data to Google Sheets via webhook"""
    try:
        webapp_url = os.getenv('GOOGLE_WEBAPP_URL')
        if not webapp_url:
            manual_flag = " [MANUAL VERIFICATION]" if data.get('manual_verification') else ""
            print("[SIMULATION] Would send to sheets: {} - {} - {}{}".format(data['order_id'], data['email'], data.get('sales_rep', 'No Rep'), manual_flag))
            return True
            
        response = requests.post(webapp_url, json=data, timeout=10)
        if response.status_code == 200:
            manual_flag = " [MANUAL VERIFICATION]" if data.get('manual_verification') else ""
            print("Sent to sheets: Order {} - {}{}".format(data['order_id'], data.get('sales_rep', 'No Rep'), manual_flag))
            return True
        else:
            print("Failed to send to sheets: {}".format(response.status_code))
            return False
    except Exception as e:
        print("Error sending to sheets: {}".format(e))
        return False

def get_bigcommerce_service_by_store_name(store_name):
    """Get BigCommerce service instance by store name"""
    store_configs = {
        'Wilson US': ('BIGCOMMERCE_STORE1_HASH', 'BIGCOMMERCE_STORE1_ACCESS_TOKEN', 'BIGCOMMERCE_STORE1_NAME'),
        'Signal US': ('BIGCOMMERCE_STORE2_HASH', 'BIGCOMMERCE_STORE2_ACCESS_TOKEN', 'BIGCOMMERCE_STORE2_NAME'),
        'Wilson CA': ('BIGCOMMERCE_STORE3_HASH', 'BIGCOMMERCE_STORE3_ACCESS_TOKEN', 'BIGCOMMERCE_STORE3_NAME'),
        'Signal CA': ('BIGCOMMERCE_STORE4_HASH', 'BIGCOMMERCE_STORE4_ACCESS_TOKEN', 'BIGCOMMERCE_STORE4_NAME')
    }
    
    config = store_configs.get(store_name)
    if not config:
        raise ValueError("Unknown store name: {}".format(store_name))
    
    hash_key, token_key, name_key = config
    store_hash = os.getenv(hash_key)
    access_token = os.getenv(token_key)
    store_display_name = os.getenv(name_key)
    
    if not store_hash or not access_token:
        raise ValueError("Missing configuration for store: {}".format(store_name))
    
    return BigCommerceService(store_hash, access_token, store_display_name)

def process_klaviyo_order(klaviyo_data):
    """Process a single order from Klaviyo trigger data"""
    try:
        order_info = klaviyo_data.get('data', {})
        order_id = order_info.get('order_id')
        store_name = order_info.get('store')
        
        if not order_id:
            return {"error": "No order ID found in Klaviyo data"}, 400
        
        if not store_name:
            return {"error": "No store name found in Klaviyo data"}, 400
        
        print("Processing order {} from {}".format(order_id, store_name))
        
        bigcommerce = get_bigcommerce_service_by_store_name(store_name)
        order_details = bigcommerce.get_order_details(order_id)
        
        netsuite = NetSuiteService()
        contact_result = netsuite.search_contact_by_email_and_phone(order_details['email'], order_details['phone'])
        
        if contact_result.get('found') and contact_result.get('sales_rep') not in ['Not Assigned', 'NO OWNER', None, '']:
            sales_rep = contact_result.get('sales_rep')
            manual_verification = contact_result.get('manual_verification', False)
            review_reason = contact_result.get('review_reason', 'Unknown')
            
            print("Found customer with sales rep: {} - {}".format(sales_rep, review_reason))
            
            sheet_data = {
                'store': store_name,
                'order_id': str(order_details['id']),
                'email': order_details['email'],
                'customer_name': order_details['customer_name'],
                'phone': order_details['phone'],
                'order_date': format_bigcommerce_date(order_details['order_date']),
                'order_total': order_details.get('order_total', '0.00'),
                'sales_rep': sales_rep,
                'contact_date': contact_result.get('contact_date', ''),
                'manual_verification': manual_verification,
                'review_reason': review_reason,
                'record_type': contact_result.get('record_type', 'unknown'),
                'netsuite_phone': contact_result.get('phone', '')
            }
            
            if send_to_sheets(sheet_data):
                return {
                    "status": "success",
                    "message": "Order attributed to sales rep",
                    "order_id": order_id,
                    "sales_rep": sales_rep,
                    "manual_verification": manual_verification
                }
            else:
                return {"error": "Failed to send to Google Sheets"}, 500
        else:
            reason = contact_result.get('review_reason', 'No sales rep found')
            print("No sales rep attribution - ignoring order ({})".format(reason))
            
            return {
                "status": "ignored",
                "message": "Order has no sales rep attribution",
                "order_id": order_id,
                "reason": reason
            }
            
    except Exception as error:
        print("Error processing Klaviyo order: {}".format(error))
        return {"error": str(error)}, 500

# Vercel handler function  
def handler(request, response):
    """Vercel serverless function handler"""
    # Set CORS headers
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    
    if request.method == 'OPTIONS':
        response.status_code = 200
        return ''
        
    if request.method != 'POST':
        response.status_code = 405
        return json.dumps({"error": "Method not allowed"})
    
    try:
        # Handle both application/json and application/x-www-form-urlencoded
        if hasattr(request, 'get_json'):
            klaviyo_data = request.get_json()
        else:
            # For Vercel Python runtime
            import json
            klaviyo_data = json.loads(request.body)
            
        result = process_klaviyo_order(klaviyo_data)
        response.status_code = 200
        return json.dumps(result)
    except Exception as error:
        print("Handler error: {}".format(error))
        response.status_code = 500
        return json.dumps({"error": "Handler error: {}".format(str(error))})
