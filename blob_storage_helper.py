"""
Azure Blob Storage Helper
Provides functions to read/write JSON data to Azure Blob Storage
Supports both connection string (dev) and managed identity (prod) authentication
"""

import json
import os
from typing import Any, Dict, List
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, InteractiveBrowserCredential
from keyvault_config import get_keyvault_config

# Global credential cache to avoid repeated authentication prompts
_cached_blob_credential = None
_cached_blob_service_client = None

class BlobStorageManager:
    """Manages JSON data in Azure Blob Storage"""
    
    def __init__(self, storage_account_name: str, container_name: str = 'gcs-data'):
        """
        Initialize Blob Storage Manager
        
        Authentication priority:
        1. Managed Identity (if AZURE_CLIENT_ID is set AND running in Azure)
        2. InteractiveBrowserCredential (local development) - CACHED to avoid repeated prompts
        """
        global _cached_blob_credential, _cached_blob_service_client
        
        self.container_name = container_name
        self.account_url = f"https://{storage_account_name}.blob.core.windows.net"
        
        # Reuse cached client if available
        if _cached_blob_service_client:
            print("  Using cached blob storage client")
            self.blob_service_client = _cached_blob_service_client
            self.container_client = self.blob_service_client.get_container_client(container_name)
            return
        
        # Check for managed identity first
        managed_identity_client_id = os.environ.get('AZURE_CLIENT_ID')
        
        if managed_identity_client_id:
            # Try managed identity for Azure deployment
            try:
                print(f"  Using Managed Identity for storage: {managed_identity_client_id[:8]}...")
                credential = ManagedIdentityCredential(client_id=managed_identity_client_id)
                self.blob_service_client = BlobServiceClient(account_url=self.account_url, credential=credential)
                _cached_blob_credential = credential
                _cached_blob_service_client = self.blob_service_client
            except Exception as e:
                print(f"  Managed Identity failed: {e}, using DefaultAzureCredential...")
                credential = DefaultAzureCredential()
                self.blob_service_client = BlobServiceClient(account_url=self.account_url, credential=credential)
                _cached_blob_credential = credential
                _cached_blob_service_client = self.blob_service_client
        else:
            # Local development: Use DefaultAzureCredential (tries Azure CLI first)
            if _cached_blob_credential:
                print("  Using cached DefaultAzureCredential for storage")
                credential = _cached_blob_credential
            else:
                print("  Using DefaultAzureCredential for storage (local development)")
                credential = DefaultAzureCredential()
                _cached_blob_credential = credential
            
            self.blob_service_client = BlobServiceClient(account_url=self.account_url, credential=credential)
            _cached_blob_service_client = self.blob_service_client
        
        self.container_client = self.blob_service_client.get_container_client(container_name)
    
    def read_json(self, filename: str) -> Any:
        """
        Read JSON file from blob storage
        
        Args:
            filename: Name of JSON file (e.g., 'context_evaluations.json')
            
        Returns:
            Parsed JSON data (dict or list)
        """
        try:
            blob_client = self.container_client.get_blob_client(filename)
            blob_data = blob_client.download_blob().readall()
            return json.loads(blob_data)
        except ResourceNotFoundError:
            print(f"⚠️  File not found in blob storage: {filename}")
            return None
        except Exception as e:
            print(f"❌ Error reading {filename}: {e}")
            return None
    
    def write_json(self, filename: str, data: Any, overwrite: bool = True) -> bool:
        """
        Write JSON data to blob storage
        
        Args:
            filename: Name of JSON file
            data: Data to write (dict or list)
            overwrite: Whether to overwrite existing file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            blob_client = self.container_client.get_blob_client(filename)
            json_data = json.dumps(data, indent=2)
            blob_client.upload_blob(json_data, overwrite=overwrite, content_type='application/json')
            return True
        except Exception as e:
            print(f"❌ Error writing {filename}: {e}")
            return False
    
    def list_files(self) -> List[str]:
        """
        List all JSON files in container
        
        Returns:
            List of filenames
        """
        try:
            return [blob.name for blob in self.container_client.list_blobs()]
        except Exception as e:
            print(f"❌ Error listing files: {e}")
            return []


# Convenience functions for backward compatibility with existing code

def _get_storage_account_name() -> str:
    """Get storage account name from AppConfig or environment"""
    try:
        from config import get_app_config
        name = getattr(get_app_config(), 'storage_account', None)
        if name:
            return name
    except Exception:
        pass
    return os.environ.get('AZURE_STORAGE_ACCOUNT_NAME', '')

def load_context_evaluations() -> List[Dict]:
    """Load context evaluations from blob storage, fallback to local file"""
    try:
        storage_account = _get_storage_account_name()
        if storage_account:
            manager = BlobStorageManager(storage_account)
            data = manager.read_json('context_evaluations.json')
            if data is not None:
                return data
    except Exception as e:
        print(f"⚠️ Blob storage unavailable, using local file: {e}")
    
    # Fallback to local file
    import os
    import json
    local_file = os.path.join(os.path.dirname(__file__), 'data', 'context_evaluations.json')
    if os.path.exists(local_file):
        try:
            with open(local_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle both old format (list) and new format (dict with evaluations key)
                if isinstance(data, dict) and 'evaluations' in data:
                    return data['evaluations']
                elif isinstance(data, list):
                    return data
        except Exception as e:
            print(f"⚠️ Could not read local file: {e}")
    
    return []

def save_context_evaluations(data: List[Dict]) -> bool:
    """Save context evaluations to blob storage"""
    manager = BlobStorageManager(_get_storage_account_name())
    return manager.write_json('context_evaluations.json', data)

def delete_context_evaluation(evaluation_id: str) -> bool:
    """
    Delete a specific evaluation by ID from blob storage
    
    Args:
        evaluation_id: The ID of the evaluation to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load all evaluations
        evaluations = load_context_evaluations()
        
        # Filter out the evaluation to delete
        initial_count = len(evaluations)
        evaluations = [e for e in evaluations if e.get('id') != evaluation_id and e.get('evaluation_id') != evaluation_id]
        
        # Check if anything was deleted
        if len(evaluations) == initial_count:
            print(f"⚠️ Evaluation {evaluation_id} not found")
            return False
        
        # Save back to blob storage
        success = save_context_evaluations(evaluations)
        if success:
            print(f"✅ Deleted evaluation {evaluation_id}")
        return success
    except Exception as e:
        print(f"❌ Error deleting evaluation: {e}")
        return False


def load_corrections() -> Dict:
    """Load corrections from blob storage"""
    manager = BlobStorageManager(_get_storage_account_name())
    data = manager.read_json('corrections.json')
    return data if data is not None else {}

def save_corrections(data: Dict) -> bool:
    """Save corrections to blob storage"""
    manager = BlobStorageManager(_get_storage_account_name())
    return manager.write_json('corrections.json', data)

def load_retirements() -> Dict:
    """Load retirements from blob storage"""
    manager = BlobStorageManager(_get_storage_account_name())
    data = manager.read_json('retirements.json')
    return data if data is not None else {}

def save_retirements(data: Dict) -> bool:
    """Save retirements to blob storage"""
    manager = BlobStorageManager(_get_storage_account_name())
    return manager.write_json('retirements.json', data)

def load_issues_actions() -> Dict:
    """Load issues/actions from blob storage"""
    manager = BlobStorageManager(_get_storage_account_name())
    data = manager.read_json('issues_actions.json')
    return data if data is not None else {}

def save_issues_actions(data: Dict) -> bool:
    """Save issues/actions to blob storage"""
    manager = BlobStorageManager(_get_storage_account_name())
    return manager.write_json('issues_actions.json', data)


if __name__ == '__main__':
    """Test the blob storage manager"""
    from dotenv import load_dotenv
    load_dotenv('.env.azure')
    
    print("Testing Blob Storage Manager...")
    print()
    
    # Test reading
    print("📖 Testing read operations:")
    evals = load_context_evaluations()
    print(f"  ✅ Context evaluations: {len(evals) if evals else 0} records")
    
    corrections = load_corrections()
    print(f"  ✅ Corrections: {len(corrections) if corrections else 0} records")
    
    retirements = load_retirements()
    print(f"  ✅ Retirements: {len(retirements) if retirements else 0} records")
    
    issues = load_issues_actions()
    print(f"  ✅ Issues/Actions: {len(issues) if issues else 0} records")
    
    print()
    print("🎉 Blob Storage Manager is ready to use!")
