#!/usr/bin/env python3
"""
Script to validate the encoding of the .env file.
Checks if it's UTF-8 or UTF-16 and provides warnings if needed.
"""
import os

def detect_encoding(file_path):
    """Detect the encoding of a file by reading its byte order mark (BOM) and content."""
    if not os.path.exists(file_path):
        return None, f"File '{file_path}' does not exist."
    
    try:
        # Read first few bytes to check for BOM
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        # Check for UTF-16 BOM
        if raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
            return 'UTF-16', "File contains UTF-16 BOM"
        
        # Check for UTF-8 BOM
        if raw_data.startswith(b'\xef\xbb\xbf'):
            return 'UTF-8-BOM', "File contains UTF-8 BOM (not recommended)"
        
        # Try to decode as UTF-8
        try:
            raw_data.decode('utf-8')
            return 'UTF-8', "File appears to be UTF-8 encoded (no BOM)"
        except UnicodeDecodeError:
            return 'UNKNOWN', "File encoding could not be determined"
            
    except Exception as e:
        return None, f"Error reading file: {str(e)}"

def validate_env_file():
    """Validate the .env file encoding."""
    env_file = '.env'
    
    print("🔍 Validating .env file encoding...")
    print(f"📁 Checking file: {os.path.abspath(env_file)}")
    
    encoding, message = detect_encoding(env_file)
    
    if encoding is None:
        print(f"❌ ERROR: {message}")
        return False
    
    print(f"📄 Detected encoding: {encoding}")
    print(f"ℹ️  Details: {message}")
    
    if encoding == 'UTF-16':
        print("⚠️  WARNING: .env file is UTF-16 encoded!")
        print("💡 RECOMMENDATION: Please resave the .env file using UTF-8 encoding without BOM.")
        print("   Most text editors have an option to 'Save As' with encoding selection.")
        print("   Choose 'UTF-8' or 'UTF-8 without BOM' when saving.")
        return False
    elif encoding == 'UTF-8-BOM':
        print("⚠️  WARNING: .env file has UTF-8 BOM (Byte Order Mark)!")
        print("💡 RECOMMENDATION: Consider resaving without BOM for better compatibility.")
        return True
    elif encoding == 'UTF-8':
        print("✅ GOOD: .env file is properly UTF-8 encoded without BOM.")
        return True
    else:
        print("❓ UNKNOWN: Could not determine encoding or file may be corrupted.")
        return False

def main():
    """Main function."""
    print("=" * 60)
    print("🔧 .env File Encoding Validator")
    print("=" * 60)
    
    is_valid = validate_env_file()
    
    print("=" * 60)
    if is_valid:
        print("✅ Validation completed successfully!")
    else:
        print("❌ Validation found issues that should be addressed.")
    
    return 0 if is_valid else 1

if __name__ == "__main__":
    exit(main()) 