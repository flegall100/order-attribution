import json
import os

def handler(request):
    """Simplified webhook handler for testing"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': ''
        }
    
    # Only allow POST requests
    if request.method != 'POST':
        return {
            'statusCode': 405,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({"error": "Method not allowed"})
        }
    
    try:
        # Parse the request body
        if hasattr(request, 'body'):
            if isinstance(request.body, bytes):
                body = request.body.decode('utf-8')
            else:
                body = request.body
            data = json.loads(body) if body else {}
        else:
            data = getattr(request, 'json', {})
        
        # Simple response
        response_data = {
            'status': 'success',
            'message': 'Webhook received successfully',
            'data_received': bool(data),
            'method': request.method
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps(response_data)
        }
        
    except Exception as error:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({"error": str(error)})
        } 
