import json
import os

def load_json_config(filepath):
    """
    Safely loads a JSON configuration or parameter file.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"[ERROR] Configuration file not found: {filepath}")
        
    with open(filepath, 'r') as f:
        config = json.load(f)
    return config