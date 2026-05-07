import os
import sys
import serverless_wsgi

# Add the parent directory to sys.path so we can import app
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from app import app

def handler(event, context):
    return serverless_wsgi.handle_request(app, event, context)
