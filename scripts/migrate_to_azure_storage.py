"""
GCS Data Migration Script
Migrates JSON files from local storage to Azure Blob Storage
Phase 2 of GCS Architecture Implementation
"""

import os
import json
from datetime import datetime
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.azure')

# Configuration
STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
CONTAINER_NAME = 'gcs-data'

# JSON files to migrate
JSON_FILES = [
    'context_evaluations.json',
    'corrections.json',
    'retirements.json',
    'issues_actions.json'
]

def create_backup():
    """Create backup of existing JSON files"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f'backup_{timestamp}'
    
    print(f"\n📦 Creating backup in: {backup_dir}")
    os.makedirs(backup_dir, exist_ok=True)
    
    for filename in JSON_FILES:
        if os.path.exists(filename):
            backup_path = os.path.join(backup_dir, filename)
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"  ✅ Backed up: {filename}")
    
    print(f"✅ Backup complete: {backup_dir}\n")
    return backup_dir

def connect_to_blob_storage():
    """Connect to Azure Blob Storage using Azure AD authentication"""
    print("🔌 Connecting to Azure Blob Storage...")
    
    try:
        storage_account_name = os.getenv('AZURE_STORAGE_ACCOUNT_NAME')
        account_url = f"https://{storage_account_name}.blob.core.windows.net"
        
        print(f"  Using Azure AD authentication (subscription owner permissions)")
        credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(account_url, credential=credential)
        
        print("✅ Connected to Blob Storage (using Azure AD)\n")
        return blob_service_client
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        print("  Note: Make sure you're signed in via VS Code Azure extension")
        return None

def ensure_container_exists(blob_service_client):
    """Create container if it doesn't exist"""
    print(f"📁 Checking container: {CONTAINER_NAME}")
    
    try:
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        # Try to get container properties (will fail if doesn't exist)
        try:
            container_client.get_container_properties()
            print(f"✅ Container '{CONTAINER_NAME}' exists\n")
        except:
            print(f"⚠️  Container '{CONTAINER_NAME}' not found, creating...")
            container_client.create_container()
            print(f"✅ Container '{CONTAINER_NAME}' created\n")
        
        return container_client
    except Exception as e:
        print(f"❌ Container error: {e}")
        return None

def upload_json_file(container_client, filename):
    """Upload a JSON file to blob storage"""
    print(f"📤 Uploading: {filename}")
    
    try:
        # Read local file
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to JSON string
        json_data = json.dumps(data, indent=2)
        
        # Upload to blob
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(json_data, overwrite=True, content_type='application/json')
        
        # Get file size
        file_size = len(json_data.encode('utf-8'))
        record_count = len(data) if isinstance(data, list) else len(data.keys())
        
        print(f"  ✅ Uploaded: {filename} ({file_size:,} bytes, {record_count} records)")
        return True
        
    except FileNotFoundError:
        print(f"  ⚠️  File not found: {filename} (skipping)")
        return False
    except Exception as e:
        print(f"  ❌ Upload failed: {e}")
        return False

def verify_upload(container_client, filename):
    """Verify file was uploaded correctly"""
    print(f"🔍 Verifying: {filename}")
    
    try:
        # Download from blob
        blob_client = container_client.get_blob_client(filename)
        blob_data = blob_client.download_blob().readall()
        cloud_data = json.loads(blob_data)
        
        # Read local file
        with open(filename, 'r', encoding='utf-8') as f:
            local_data = json.load(f)
        
        # Compare
        if cloud_data == local_data:
            print(f"  ✅ Verified: {filename} matches local file")
            return True
        else:
            print(f"  ⚠️  Warning: {filename} data mismatch")
            return False
            
    except FileNotFoundError:
        print(f"  ⚠️  Local file not found: {filename} (skipped)")
        return True  # Not an error if file doesn't exist locally
    except Exception as e:
        print(f"  ❌ Verification failed: {e}")
        return False

def list_blobs(container_client):
    """List all blobs in container"""
    print("\n📋 Files in Blob Storage:")
    
    try:
        blob_list = container_client.list_blobs()
        for blob in blob_list:
            print(f"  - {blob.name} ({blob.size:,} bytes)")
        print()
    except Exception as e:
        print(f"❌ Failed to list blobs: {e}\n")

def main():
    """Main migration function"""
    print("=" * 60)
    print("  GCS Data Migration - Phase 2")
    print("  Migrating JSON files to Azure Blob Storage")
    print("=" * 60)
    print()
    
    # Step 1: Create backup
    backup_dir = create_backup()
    
    # Step 2: Connect to Blob Storage
    blob_service_client = connect_to_blob_storage()
    if not blob_service_client:
        print("❌ Migration aborted: Could not connect to Blob Storage")
        return False
    
    # Step 3: Ensure container exists
    container_client = ensure_container_exists(blob_service_client)
    if not container_client:
        print("❌ Migration aborted: Could not access container")
        return False
    
    # Step 4: Upload files
    print("📤 Uploading JSON files...")
    print("-" * 60)
    upload_results = []
    for filename in JSON_FILES:
        result = upload_json_file(container_client, filename)
        upload_results.append((filename, result))
    print()
    
    # Step 5: Verify uploads
    print("🔍 Verifying uploads...")
    print("-" * 60)
    verify_results = []
    for filename, uploaded in upload_results:
        if uploaded:
            result = verify_upload(container_client, filename)
            verify_results.append((filename, result))
    print()
    
    # Step 6: List all blobs
    list_blobs(container_client)
    
    # Summary
    print("=" * 60)
    print("  Migration Summary")
    print("=" * 60)
    
    uploaded_count = sum(1 for _, result in upload_results if result)
    verified_count = sum(1 for _, result in verify_results if result)
    
    print(f"✅ Files uploaded: {uploaded_count}/{len(JSON_FILES)}")
    print(f"✅ Files verified: {verified_count}/{len(verify_results)}")
    print(f"📦 Backup location: {backup_dir}")
    print(f"☁️  Blob container: {CONTAINER_NAME}")
    print()
    
    if uploaded_count == len([f for f in JSON_FILES if os.path.exists(f)]):
        print("🎉 Migration completed successfully!")
        print()
        print("Next steps:")
        print("  1. Test reading data from Blob Storage")
        print("  2. Update application code to use Azure Storage")
        print("  3. Keep local backups until migration is confirmed stable")
        return True
    else:
        print("⚠️  Migration completed with warnings")
        print("    Some files may not have been migrated")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
