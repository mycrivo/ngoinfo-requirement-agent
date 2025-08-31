#!/usr/bin/env python3
"""
Filesystem policy check script
Tests storage directory resolution and write permissions
"""
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

def resolve_storage_directory() -> tuple[str, str]:
    """Resolve the active storage directory per current code logic"""
    
    # Mirror the logic from services/storage.py
    storage_dir = (
        os.getenv("REQAGENT_STORAGE_DIR") or 
        os.getenv("FILE_STORAGE_ROOT") or 
        "/tmp/reqagent_storage"
    )
    
    source = "default"
    if os.getenv("REQAGENT_STORAGE_DIR"):
        source = "REQAGENT_STORAGE_DIR"
    elif os.getenv("FILE_STORAGE_ROOT"):
        source = "FILE_STORAGE_ROOT"
    
    return storage_dir, source

def classify_storage_path(path: str) -> str:
    """Classify the storage path type"""
    path_lower = path.lower()
    
    if path_lower.startswith('/tmp') or 'temp' in path_lower:
        return "temporary"
    elif path_lower.startswith('/app') or path_lower.startswith('./app'):
        return "container_app"
    elif path_lower.startswith('/mnt'):
        return "mounted_volume"
    elif path_lower.startswith('/var') or path_lower.startswith('/opt'):
        return "system_directory"
    elif path_lower.startswith('./') or not path_lower.startswith('/'):
        return "relative_path"
    else:
        return "absolute_path"

def test_directory_operations(directory: str) -> Dict[str, Any]:
    """Test directory creation and file operations"""
    results = {
        'directory': directory,
        'exists': False,
        'is_directory': False,
        'is_writable': False,
        'can_create': False,
        'can_write_file': False,
        'can_read_file': False,
        'can_delete_file': False,
        'disk_space_mb': 0,
        'error': None
    }
    
    try:
        # Convert to Path object
        path = Path(directory)
        
        # Check if exists
        results['exists'] = path.exists()
        results['is_directory'] = path.is_dir()
        
        # Try to create directory if it doesn't exist
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                results['can_create'] = True
                results['exists'] = True
                results['is_directory'] = True
            except Exception as e:
                results['error'] = f"Cannot create directory: {e}"
                return results
        
        # Check if writable
        results['is_writable'] = os.access(path, os.W_OK)
        
        # Test file operations
        test_file = path / "audit_test_file.txt"
        test_content = "This is a test file for the audit"
        
        try:
            # Write test
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(test_content)
            results['can_write_file'] = True
            
            # Read test
            with open(test_file, 'r', encoding='utf-8') as f:
                read_content = f.read()
            results['can_read_file'] = (read_content == test_content)
            
            # Delete test
            test_file.unlink()
            results['can_delete_file'] = not test_file.exists()
            
        except Exception as e:
            results['error'] = f"File operations failed: {e}"
        
        # Check disk space
        try:
            disk_usage = shutil.disk_usage(path)
            results['disk_space_mb'] = disk_usage.free // (1024 * 1024)
        except Exception as e:
            results['error'] = f"Cannot check disk space: {e}"
    
    except Exception as e:
        results['error'] = f"Directory test failed: {e}"
    
    return results

def check_common_storage_paths() -> List[Dict[str, Any]]:
    """Check common storage paths for comparison"""
    paths_to_check = [
        "/tmp/reqagent_storage",
        "/app/data",
        "/mnt/data",
        "/var/app/data",
        "./data",
        "./storage"
    ]
    
    results = []
    for path in paths_to_check:
        # Only test if path doesn't require root permissions
        if not path.startswith('/var') and not path.startswith('/opt'):
            result = test_directory_operations(path)
            result['path_type'] = classify_storage_path(path)
            results.append(result)
    
    return results

def analyze_dockerfile_workdir() -> Optional[str]:
    """Analyze Dockerfile to determine working directory"""
    dockerfile_path = "Dockerfile"
    
    if not os.path.exists(dockerfile_path):
        return None
    
    try:
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for WORKDIR instruction
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('WORKDIR '):
                return line.split(' ', 1)[1].strip()
    
    except Exception:
        pass
    
    return None

def check_filesystem_policy() -> Dict[str, Any]:
    """Main filesystem policy check"""
    
    # Resolve storage directory
    storage_dir, source = resolve_storage_directory()
    path_type = classify_storage_path(storage_dir)
    
    # Test the resolved directory
    primary_test = test_directory_operations(storage_dir)
    primary_test['source'] = source
    primary_test['path_type'] = path_type
    
    # Test common alternatives
    alternative_tests = check_common_storage_paths()
    
    # Analyze container setup
    docker_workdir = analyze_dockerfile_workdir()
    
    return {
        'resolved_storage': storage_dir,
        'storage_source': source,
        'path_type': path_type,
        'primary_test': primary_test,
        'alternative_tests': alternative_tests,
        'docker_workdir': docker_workdir,
        'recommendations': generate_recommendations(primary_test, alternative_tests)
    }

def generate_recommendations(primary_test: Dict[str, Any], alternatives: List[Dict[str, Any]]) -> List[str]:
    """Generate recommendations based on test results"""
    recommendations = []
    
    if not primary_test.get('can_write_file', False):
        recommendations.append("❌ Primary storage directory is not writable - configure REQAGENT_STORAGE_DIR")
    
    if primary_test.get('path_type') == 'mounted_volume' and not primary_test.get('exists', False):
        recommendations.append("⚠️ Using mounted volume that doesn't exist - ensure volume is mounted in production")
    
    if primary_test.get('disk_space_mb', 0) < 100:
        recommendations.append("⚠️ Less than 100MB free space available")
    
    # Find working alternatives
    working_alternatives = [alt for alt in alternatives 
                          if alt.get('can_write_file', False) and alt['directory'] != primary_test['directory']]
    
    if not primary_test.get('can_write_file', False) and working_alternatives:
        best_alt = working_alternatives[0]
        recommendations.append(f"💡 Consider using {best_alt['directory']} as alternative (writable)")
    
    if primary_test.get('path_type') == 'relative_path':
        recommendations.append("⚠️ Using relative path - may cause issues in containers")
    
    return recommendations

def generate_fs_report(results: Dict[str, Any]) -> str:
    """Generate markdown report of filesystem check"""
    report = []
    
    report.append("## Filesystem Policy Check\n")
    
    # Primary storage
    primary = results['primary_test']
    report.append(f"**Resolved Storage Directory**: `{results['resolved_storage']}`")
    report.append(f"**Source**: {results['storage_source']}")
    report.append(f"**Path Type**: {results['path_type']}")
    report.append(f"**Docker WORKDIR**: {results['docker_workdir'] or 'Not specified'}\n")
    
    # Primary test results
    report.append("### Primary Storage Test Results\n")
    report.append("| Test | Result |")
    report.append("|------|--------|")
    report.append(f"| Directory exists | {'✅' if primary['exists'] else '❌'} |")
    report.append(f"| Is directory | {'✅' if primary['is_directory'] else '❌'} |")
    report.append(f"| Is writable | {'✅' if primary['is_writable'] else '❌'} |")
    report.append(f"| Can create | {'✅' if primary['can_create'] else '❌'} |")
    report.append(f"| Can write file | {'✅' if primary['can_write_file'] else '❌'} |")
    report.append(f"| Can read file | {'✅' if primary['can_read_file'] else '❌'} |")
    report.append(f"| Can delete file | {'✅' if primary['can_delete_file'] else '❌'} |")
    report.append(f"| Free space (MB) | {primary['disk_space_mb']} |")
    
    if primary.get('error'):
        report.append(f"| Error | {primary['error']} |")
    
    report.append("")
    
    # Alternative paths
    if results['alternative_tests']:
        report.append("### Alternative Storage Paths\n")
        report.append("| Path | Type | Writable | Free Space (MB) | Status |")
        report.append("|------|------|----------|-----------------|--------|")
        
        for alt in results['alternative_tests']:
            status = "✅ Working" if alt.get('can_write_file') else "❌ Failed"
            if alt.get('error'):
                status = f"❌ {alt['error'][:30]}..."
            
            report.append(f"| `{alt['directory']}` | {alt['path_type']} | {'✅' if alt.get('is_writable') else '❌'} | {alt.get('disk_space_mb', 0)} | {status} |")
        
        report.append("")
    
    # Recommendations
    if results['recommendations']:
        report.append("### Recommendations\n")
        for rec in results['recommendations']:
            report.append(f"- {rec}")
        report.append("")
    
    return '\n'.join(report)

if __name__ == "__main__":
    print("🔍 Checking filesystem policy and storage directories...")
    
    results = check_filesystem_policy()
    
    print(f"\n📁 FILESYSTEM POLICY CHECK")
    print(f"==========================")
    print(f"Resolved storage: {results['resolved_storage']}")
    print(f"Source: {results['storage_source']}")
    print(f"Path type: {results['path_type']}")
    print(f"Docker WORKDIR: {results['docker_workdir'] or 'Not specified'}")
    
    primary = results['primary_test']
    print(f"\n📊 PRIMARY STORAGE TEST")
    print(f"=======================")
    print(f"Directory: {primary['directory']}")
    print(f"Exists: {'✅' if primary['exists'] else '❌'}")
    print(f"Writable: {'✅' if primary['is_writable'] else '❌'}")
    print(f"Can write files: {'✅' if primary['can_write_file'] else '❌'}")
    print(f"Free space: {primary['disk_space_mb']} MB")
    
    if primary.get('error'):
        print(f"Error: {primary['error']}")
    
    # Working alternatives
    working_alts = [alt for alt in results['alternative_tests'] if alt.get('can_write_file')]
    if working_alts:
        print(f"\n✅ WORKING ALTERNATIVES:")
        for alt in working_alts:
            print(f"   - {alt['directory']} ({alt['path_type']})")
    
    # Recommendations
    if results['recommendations']:
        print(f"\n💡 RECOMMENDATIONS:")
        for rec in results['recommendations']:
            print(f"   {rec}")
    
    # Generate report
    report = generate_fs_report(results)
    print(f"\n📋 DETAILED REPORT")
    print(f"==================")
    print(report)
