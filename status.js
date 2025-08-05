module.exports = (req, res) => {
  // Set CORS headers for cross-origin requests
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }
  
  if (req.method !== 'GET') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  
  // System status information
  const status = {
    status: 'online',
    timestamp: new Date().toISOString(),
    system: 'Sales Attribution System',
    version: '1.0.0',
    components: {
      bigcommerce: 'operational',
      netsuite: 'operational',
      googleSheets: 'operational',
      webhookProcessor: 'operational'
    },
    endpoints: {
      webhook: '/api/webhook',
      status: '/api/status'
    },
    environment: process.env.NODE_ENV || 'production'
  };
  
  res.status(200).json(status);
}; 
