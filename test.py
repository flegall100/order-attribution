import json

def handler(request):
    """Simple test handler for Vercel Python runtime"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': ''
        }
    
    # Return test response
    response_data = {
        'status': 'success',
        'message': 'Test endpoint is working!',
        'method': request.method,
        'timestamp': '2024-01-15T10:00:00Z'
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(response_data)
    } 
