import requests
import json
import os

def test_ollama_connection():
    """Test Ollama API connectivity and basic functionality"""
    base_url = os.getenv('OLLAMA_HOST')
    
    try:
        # Test version endpoint
        response = requests.get(f"{base_url}/api/version")
        response.raise_for_status()
        print(f"Ollama version: {response.json()['version']}")
        
        # Test model list
        response = requests.get(f"{base_url}/api/tags")
        response.raise_for_status()
        models = response.json()['models']
        print(f"Available models: {len(models)}")
        
        return True
    except requests.exceptions.ConnectionError:
        print("Connection refused - Ollama not accessible")
        return False
    except Exception as e:
        print(f"API error: {e}")
        return False

# Run the test
if test_ollama_connection():
    print("✅ Ollama API connection successful!")
else:
    print("❌ Connection issues persist")
