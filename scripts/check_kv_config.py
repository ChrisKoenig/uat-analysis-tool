"""Check Key Vault OpenAI configuration"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps'))
from shared.keyvault_config import get_keyvault_config

kv = get_keyvault_config()
cfg = kv.get_config()

print(f'Endpoint: {cfg.get("AZURE_OPENAI_ENDPOINT")}')
print(f'Deployment: {cfg.get("AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT")}')
print(f'Embedding Deployment: {cfg.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")}')
print(f'Use AAD: {cfg.get("AZURE_OPENAI_USE_AAD")}')
print(f'API Key: {cfg.get("AZURE_OPENAI_API_KEY", "")[:20]}...')
