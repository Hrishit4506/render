#!/usr/bin/env python3
"""
Render Proxy Server for UniSync
This server runs on Render and forwards requests to your local cloudflared tunnel
"""

import os
import requests
from flask import Flask, request, Response, redirect, url_for
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
CLOUDFLARED_TUNNEL_URL = os.environ.get('CLOUDFLARED_TUNNEL_URL', 'http://localhost:5000')
RENDER_PORT = int(os.environ.get('PORT', 10000))

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    """Proxy all requests to the cloudflared tunnel"""
    try:
        # Construct the full URL for the cloudflared tunnel
        target_url = f"{CLOUDFLARED_TUNNEL_URL.rstrip('/')}/{path}"
        
        # Get query parameters
        query_string = request.query_string.decode('utf-8')
        if query_string:
            target_url += f"?{query_string}"
        
        logger.info(f"Proxying request: {request.method} {request.path} -> {target_url}")
        
        # Forward the request to the cloudflared tunnel
        if request.method == 'GET':
            response = requests.get(target_url, timeout=30)
        elif request.method == 'POST':
            response = requests.post(target_url, data=request.form, files=request.files, timeout=30)
        elif request.method == 'PUT':
            response = requests.put(target_url, data=request.form, timeout=30)
        elif request.method == 'DELETE':
            response = requests.delete(target_url, timeout=30)
        else:
            # For other methods, try to forward with data
            response = requests.request(
                method=request.method,
                url=target_url,
                data=request.get_data(),
                headers=dict(request.headers),
                timeout=30
            )
        
        # Create response with the same status code and headers
        proxy_response = Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
        
        # Remove problematic headers that might cause issues
        if 'Transfer-Encoding' in proxy_response.headers:
            del proxy_response.headers['Transfer-Encoding']
        if 'Content-Encoding' in proxy_response.headers:
            del proxy_response.headers['Content-Encoding']
            
        return proxy_response
        
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error to cloudflared tunnel: {CLOUDFLARED_TUNNEL_URL}")
        return Response(
            "Cloudflared tunnel is not accessible. Please ensure your local app is running and cloudflared tunnel is active.",
            status=503,
            content_type='text/plain'
        )
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error to cloudflared tunnel: {CLOUDFLARED_TUNNEL_URL}")
        return Response(
            "Request timeout. The cloudflared tunnel is taking too long to respond.",
            status=504,
            content_type='text/plain'
        )
    except Exception as e:
        logger.error(f"Proxy error: {str(e)}")
        return Response(
            f"Proxy error: {str(e)}",
            status=500,
            content_type='text/plain'
        )

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    try:
        # Try to connect to the cloudflared tunnel
        response = requests.get(CLOUDFLARED_TUNNEL_URL, timeout=5)
        if response.status_code == 200:
            return {"status": "healthy", "tunnel": "connected"}, 200
        else:
            return {"status": "unhealthy", "tunnel": "responding_with_error"}, 503
    except:
        return {"status": "unhealthy", "tunnel": "not_accessible"}, 503

@app.route('/status')
def status():
    """Status endpoint to check the proxy configuration"""
    return {
        "proxy_status": "running",
        "cloudflared_tunnel_url": CLOUDFLARED_TUNNEL_URL,
        "render_port": RENDER_PORT,
        "environment": os.environ.get('FLASK_ENV', 'production')
    }

if __name__ == '__main__':
    logger.info(f"Starting Render Proxy Server on port {RENDER_PORT}")
    logger.info(f"Proxying to cloudflared tunnel: {CLOUDFLARED_TUNNEL_URL}")
    app.run(host='0.0.0.0', port=RENDER_PORT, debug=False)
