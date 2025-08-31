#!/usr/bin/env python3
"""
Config schema validation script
Checks for required environment variables and their types
"""
import os
import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass

@dataclass
class ConfigVar:
    name: str
    required: bool
    var_type: str
    description: str
    default: Optional[str] = None
    
def get_config_schema() -> List[ConfigVar]:
    """Define the expected configuration schema"""
    return [
        # Database
        ConfigVar("DATABASE_URL", True, "str", "PostgreSQL connection string"),
        ConfigVar("PGHOST", False, "str", "Database host (alternative to DATABASE_URL)", "localhost"),
        ConfigVar("PGPORT", False, "int", "Database port", "5432"),
        ConfigVar("PGDATABASE", False, "str", "Database name", "requirement_agent"),
        ConfigVar("PGUSER", False, "str", "Database user", "username"),
        ConfigVar("PGPASSWORD", False, "str", "Database password"),
        
        # Security
        ConfigVar("JWT_SECRET", True, "str", "JWT signing secret"),
        ConfigVar("SECRET_KEY", False, "str", "General app secret key"),
        ConfigVar("API_KEYS", False, "str", "Comma-separated API keys"),
        ConfigVar("ADMIN_EMAIL_WHITELIST", False, "str", "Comma-separated admin emails"),
        
        # Services
        ConfigVar("OPENAI_API_KEY", True, "str", "OpenAI API key for content generation"),
        ConfigVar("WORDPRESS_API_URL", False, "str", "WordPress API URL (WP_API_URL)"),
        ConfigVar("WORDPRESS_USERNAME", False, "str", "WordPress username (WP_USERNAME)"),
        ConfigVar("WORDPRESS_APP_PASSWORD", False, "str", "WordPress app password (WP_APPLICATION_PASSWORD)"),
        
        # Storage
        ConfigVar("REQAGENT_STORAGE_DIR", False, "str", "Storage directory for files"),
        ConfigVar("FILE_STORAGE_ROOT", False, "str", "Legacy storage root", "/mnt/data/generated"),
        
        # App Settings
        ConfigVar("PORT", False, "int", "Server port", "8000"),
        ConfigVar("TEST_MODE", False, "bool", "Test mode flag", "false"),
        ConfigVar("DEBUG", False, "bool", "Debug mode", "false"),
        ConfigVar("LOG_LEVEL", False, "str", "Logging level", "INFO"),
        
        # Rate Limiting
        ConfigVar("RATE_LIMITS", False, "str", "Rate limit configuration"),
        
        # AWS/S3
        ConfigVar("S3_ENDPOINT", False, "str", "S3-compatible endpoint"),
        ConfigVar("S3_BUCKET", False, "str", "S3 bucket name"),
        ConfigVar("S3_ACCESS_KEY", False, "str", "S3 access key"),
        ConfigVar("S3_SECRET_KEY", False, "str", "S3 secret key"),
        
        # PDF Processing
        ConfigVar("MAX_UPLOAD_MB", False, "int", "Max upload size in MB", "20"),
        ConfigVar("MAX_PDF_PAGES", False, "int", "Max PDF pages", "150"),
        ConfigVar("PDF_ENGINE", False, "str", "PDF generation engine", "reportlab"),
        
        # OCR
        ConfigVar("OCR_BACKEND", False, "str", "OCR backend", "none"),
        ConfigVar("OCR_CONFIDENCE_THRESHOLD", False, "float", "OCR confidence threshold", "0.7"),
    ]

def load_env_file(file_path: str) -> Dict[str, str]:
    """Load environment variables from .env file"""
    env_vars = {}
    
    if not os.path.exists(file_path):
        return env_vars
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    env_vars[key] = value
                    
    except Exception as e:
        print(f"⚠️ Error reading {file_path}: {e}")
    
    return env_vars

def validate_config_value(value: str, expected_type: str) -> tuple[bool, str]:
    """Validate a config value against expected type"""
    if not value:
        return False, "empty value"
    
    try:
        if expected_type == "int":
            int(value)
        elif expected_type == "float":
            float(value)
        elif expected_type == "bool":
            if value.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                return False, f"not a valid boolean: {value}"
        elif expected_type == "str":
            # String is always valid if not empty
            pass
        else:
            return False, f"unknown type: {expected_type}"
            
        return True, "valid"
        
    except ValueError as e:
        return False, str(e)

def check_configuration() -> Dict[str, Any]:
    """Check configuration against schema"""
    schema = get_config_schema()
    
    # Load from environment and .env file
    env_from_file = load_env_file('.env')
    env_from_system = dict(os.environ)
    
    # Merge (system env takes precedence)
    all_env = {**env_from_file, **env_from_system}
    
    results = {
        'schema_vars': len(schema),
        'env_file_vars': len(env_from_file),
        'system_env_vars': len([k for k in env_from_system.keys() if not k.startswith('_')]),
        'missing_required': [],
        'missing_optional': [],
        'invalid_values': [],
        'present_vars': [],
        'env_file_exists': os.path.exists('.env')
    }
    
    for config_var in schema:
        value = all_env.get(config_var.name)
        
        if value is not None:
            # Check type
            is_valid, error_msg = validate_config_value(value, config_var.var_type)
            
            if is_valid:
                results['present_vars'].append({
                    'name': config_var.name,
                    'source': 'env_file' if config_var.name in env_from_file else 'system',
                    'type': config_var.var_type,
                    'masked_value': mask_sensitive_value(config_var.name, value)
                })
            else:
                results['invalid_values'].append({
                    'name': config_var.name,
                    'error': error_msg,
                    'type': config_var.var_type,
                    'value': mask_sensitive_value(config_var.name, value)
                })
        else:
            # Missing variable
            missing_info = {
                'name': config_var.name,
                'type': config_var.var_type,
                'description': config_var.description,
                'default': config_var.default
            }
            
            if config_var.required:
                results['missing_required'].append(missing_info)
            else:
                results['missing_optional'].append(missing_info)
    
    return results

def mask_sensitive_value(var_name: str, value: str) -> str:
    """Mask sensitive configuration values"""
    sensitive_keywords = ['password', 'secret', 'key', 'token', 'api_key']
    
    if any(keyword in var_name.lower() for keyword in sensitive_keywords):
        if len(value) <= 4:
            return "***"
        return value[:2] + "***" + value[-2:]
    
    return value

def find_env_vars_in_code() -> List[str]:
    """Find environment variables referenced in code"""
    env_vars = set()
    
    # Files to scan for env var usage
    directories = ['routes', 'services', 'utils', '.']
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
            
        files_to_scan = []
        if directory == '.':
            files_to_scan = [f for f in os.listdir('.') if f.endswith('.py')]
        else:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith('.py'):
                        files_to_scan.append(os.path.join(root, file))
        
        for file_path in files_to_scan:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find os.getenv() calls
                getenv_pattern = r'os\.getenv\s*\(\s*["\']([^"\']+)["\']'
                matches = re.findall(getenv_pattern, content)
                env_vars.update(matches)
                
                # Find other patterns
                env_patterns = [
                    r'os\.environ\s*\[\s*["\']([^"\']+)["\']',
                    r'os\.environ\.get\s*\(\s*["\']([^"\']+)["\']'
                ]
                
                for pattern in env_patterns:
                    matches = re.findall(pattern, content)
                    env_vars.update(matches)
                    
            except Exception as e:
                print(f"⚠️ Error scanning {file_path}: {e}")
    
    return sorted(list(env_vars))

def generate_config_report(results: Dict[str, Any]) -> str:
    """Generate markdown report of configuration status"""
    report = []
    
    # Summary
    report.append("## Configuration Schema Validation\n")
    report.append(f"- **Schema variables**: {results['schema_vars']}")
    report.append(f"- **.env file exists**: {'✅' if results['env_file_exists'] else '❌'}")
    report.append(f"- **Variables from .env file**: {results['env_file_vars']}")
    report.append(f"- **System environment variables**: {results['system_env_vars']}")
    report.append(f"- **Present variables**: {len(results['present_vars'])}")
    report.append(f"- **Missing required**: {len(results['missing_required'])}")
    report.append(f"- **Missing optional**: {len(results['missing_optional'])}")
    report.append(f"- **Invalid values**: {len(results['invalid_values'])}\n")
    
    # Present variables
    if results['present_vars']:
        report.append("### ✅ Present Variables\n")
        report.append("| Variable | Type | Source | Value |")
        report.append("|----------|------|--------|-------|")
        for var in sorted(results['present_vars'], key=lambda x: x['name']):
            report.append(f"| {var['name']} | {var['type']} | {var['source']} | {var['masked_value']} |")
        report.append("")
    
    # Missing required
    if results['missing_required']:
        report.append("### ❌ Missing Required Variables\n")
        report.append("| Variable | Type | Description |")
        report.append("|----------|------|-------------|")
        for var in results['missing_required']:
            report.append(f"| {var['name']} | {var['type']} | {var['description']} |")
        report.append("")
    
    # Invalid values
    if results['invalid_values']:
        report.append("### ⚠️ Invalid Values\n")
        report.append("| Variable | Type | Error | Value |")
        report.append("|----------|------|-------|-------|")
        for var in results['invalid_values']:
            report.append(f"| {var['name']} | {var['type']} | {var['error']} | {var['value']} |")
        report.append("")
    
    # Missing optional (subset)
    if results['missing_optional']:
        important_optional = [v for v in results['missing_optional'] 
                             if v['name'] in ['OPENAI_API_KEY', 'JWT_SECRET', 'API_KEYS']]
        if important_optional:
            report.append("### ⚠️ Missing Important Optional Variables\n")
            report.append("| Variable | Type | Description | Default |")
            report.append("|----------|------|-------------|---------|")
            for var in important_optional:
                default = var['default'] or 'None'
                report.append(f"| {var['name']} | {var['type']} | {var['description']} | {default} |")
            report.append("")
    
    return '\n'.join(report)

if __name__ == "__main__":
    print("🔍 Validating configuration schema...")
    
    results = check_configuration()
    code_env_vars = find_env_vars_in_code()
    
    print(f"\n📊 CONFIG SCHEMA VALIDATION")
    print(f"===========================")
    print(f"Schema variables: {results['schema_vars']}")
    print(f".env file exists: {'✅' if results['env_file_exists'] else '❌'}")
    print(f"Present variables: {len(results['present_vars'])}")
    print(f"Missing required: {len(results['missing_required'])}")
    print(f"Missing optional: {len(results['missing_optional'])}")
    print(f"Invalid values: {len(results['invalid_values'])}")
    print(f"Env vars found in code: {len(code_env_vars)}")
    
    if results['missing_required']:
        print(f"\n❌ MISSING REQUIRED:")
        for var in results['missing_required']:
            print(f"   - {var['name']} ({var['type']}): {var['description']}")
    
    if results['invalid_values']:
        print(f"\n⚠️ INVALID VALUES:")
        for var in results['invalid_values']:
            print(f"   - {var['name']}: {var['error']}")
    
    print(f"\n🔍 ENVIRONMENT VARIABLES IN CODE:")
    print(f"=================================")
    for var in code_env_vars:
        print(f"   - {var}")
    
    # Generate full report
    report = generate_config_report(results)
    print(f"\n📋 DETAILED REPORT")
    print(f"==================")
    print(report)

