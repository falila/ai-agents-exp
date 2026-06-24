import os

# XRPL Connectivity Settings
XRPL_NETWORK_URL = os.getenv("XRPL_NETWORK_URL", "https://rippletest.net")

# AI & LLM Engine Settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "llama3")

# Cryptographic Gateway Security Keys
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "default_dev_fallback_secret_key_999123")

# Corporate Spending Limits
MAX_ALLOWANCE_XRP = float(os.getenv("MAX_ALLOWANCE_XRP", "50.0"))

# Merchant settlement configuration
MERCHANT_RECEIVING_ADDRESS = os.getenv("MERCHANT_RECEIVING_ADDRESS", "")
