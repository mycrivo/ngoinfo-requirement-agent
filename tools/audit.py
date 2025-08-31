#!/usr/bin/env python3
"""
DevOps + Code Quality Audit Tool for Railway Deployment
Performs comprehensive checks on FastAPI codebase.
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple, Any
import subprocess
import json

class CodeAuditor:
    def __init__(self):
        self.root_path = Path(".")
        self.results = {}
        
    def run_all_audits(self):
        """Run all audit checks and return consolidated report"""
        print("🔍 Running comprehensive codebase audit...\n")
        
        # Run all audits
        self.audit_fastapi_param_order()
        self.audit_env_vars()
        self.audit_health_endpoint()
        self.audit_port_usage()
        self.audit_migrations()
        self.audit_requirements()
        self.audit_playwright_deps()
        self.audit_import_at_start()
        
        # Print consolidated report
        self.print_report()
        return self.results
    
    def audit_fastapi_param_order(self):
        """(A) FastAPI param-order auditor"""
        print("🔧 (A) FastAPI Parameter Order Audit")
        violations = []
        
        routes_path = self.root_path / "routes"
        if not routes_path.exists():
            self.results['param_order'] = {'status': 'SKIP', 'message': 'No routes directory found'}
            return
            
        for py_file in routes_path.glob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        violation = self._check_param_order(node, py_file)
                        if violation:
                            violations.append(violation)
                            
            except Exception as e:
                print(f"   ⚠️ Error parsing {py_file}: {e}")
                
        if violations:
            self.results['param_order'] = {
                'status': 'FAIL', 
                'violations': violations,
                'message': f'Found {len(violations)} parameter order violations'
            }
            for v in violations:
                print(f"   ❌ {v['file']}:{v['line']}:{v['function']} - {v['issue']}")
        else:
            self.results['param_order'] = {'status': 'PASS', 'message': 'All parameter orders correct'}
            print("   ✅ All parameter orders correct")
        print()
    
    def _check_param_order(self, func_node: ast.FunctionDef, file_path: Path) -> Dict:
        """Check if non-default params come after default params"""
        args = func_node.args
        found_default = False
        
        # Check regular args
        for i, arg in enumerate(args.args):
            has_default = i >= (len(args.args) - len(args.defaults))
            
            if has_default:
                found_default = True
            elif found_default:
                # Non-default after default found
                return {
                    'file': str(file_path),
                    'line': func_node.lineno,
                    'function': func_node.name,
                    'issue': f'Non-default parameter "{arg.arg}" after default parameter'
                }
        
        return None
    
    def audit_env_vars(self):
        """(B) Environment variable auditor"""
        print("🔧 (B) Environment Variables Audit")
        
        env_vars_found = set()
        
        # Search for os.getenv usage
        for py_file in self.root_path.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Find os.getenv("VAR_NAME") patterns
                getenv_matches = re.findall(r'os\.getenv\(["\']([^"\']+)["\']', content)
                env_vars_found.update(getenv_matches)
                
            except Exception as e:
                continue
        
        env_vars_found = sorted(list(env_vars_found))
        
        # Check .env.example
        env_example_path = self.root_path / "env.example"
        env_example_vars = set()
        missing_in_example = []
        
        if env_example_path.exists():
            try:
                with open(env_example_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            var_name = line.split('=')[0].strip()
                            env_example_vars.add(var_name)
                            
                missing_in_example = [var for var in env_vars_found if var not in env_example_vars]
            except Exception as e:
                print(f"   ⚠️ Error reading env.example: {e}")
        
        self.results['env_vars'] = {
            'status': 'PASS' if not missing_in_example else 'WARN',
            'found_vars': env_vars_found,
            'missing_in_example': missing_in_example,
            'message': f'Found {len(env_vars_found)} env vars, {len(missing_in_example)} missing from .env.example'
        }
        
        print(f"   📋 Found {len(env_vars_found)} environment variables in code")
        if missing_in_example:
            print(f"   ⚠️ Missing from .env.example: {', '.join(missing_in_example)}")
        else:
            print("   ✅ All env vars documented in .env.example")
        print()
    
    def audit_health_endpoint(self):
        """(C) Health endpoint auditor"""
        print("🔧 (C) Health Endpoint Audit")
        
        health_found = False
        main_py = self.root_path / "main.py"
        
        if main_py.exists():
            try:
                with open(main_py, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if re.search(r'@app\.get\(["\']\/health["\']', content):
                    health_found = True
                    
            except Exception as e:
                print(f"   ⚠️ Error reading main.py: {e}")
        
        # Also check routes files
        routes_path = self.root_path / "routes"
        if routes_path.exists():
            for py_file in routes_path.glob("*.py"):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if re.search(r'@[^.]+\.get\(["\']\/health["\']', content):
                            health_found = True
                            break
                except Exception:
                    continue
        
        self.results['health_endpoint'] = {
            'status': 'PASS' if health_found else 'FAIL',
            'found': health_found,
            'message': 'Health endpoint found' if health_found else 'No health endpoint detected'
        }
        
        if health_found:
            print("   ✅ Health endpoint found")
        else:
            print("   ❌ No health endpoint detected")
        print()
    
    def audit_port_usage(self):
        """(D) PORT usage auditor"""
        print("🔧 (D) PORT Usage Audit")
        
        dockerfile_path = self.root_path / "Dockerfile"
        port_usage_correct = False
        uvicorn_config_correct = False
        
        if dockerfile_path.exists():
            try:
                with open(dockerfile_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check for PORT variable usage
                if re.search(r'\$\{?PORT', content):
                    port_usage_correct = True
                    
                # Check for proper uvicorn command
                if re.search(r'uvicorn.*--host.*0\.0\.0\.0.*--port.*\$\{?PORT', content):
                    uvicorn_config_correct = True
                    
            except Exception as e:
                print(f"   ⚠️ Error reading Dockerfile: {e}")
        
        status = 'PASS' if (port_usage_correct and uvicorn_config_correct) else 'FAIL'
        self.results['port_usage'] = {
            'status': status,
            'port_usage': port_usage_correct,
            'uvicorn_config': uvicorn_config_correct,
            'message': f'PORT usage: {port_usage_correct}, Uvicorn config: {uvicorn_config_correct}'
        }
        
        print(f"   📊 PORT variable usage: {'✅' if port_usage_correct else '❌'}")
        print(f"   📊 Uvicorn config: {'✅' if uvicorn_config_correct else '❌'}")
        print()
    
    def audit_migrations(self):
        """(E) Migrations auditor"""
        print("🔧 (E) Database Migrations Audit")
        
        alembic_ini = self.root_path / "alembic.ini"
        migrations_dir = self.root_path / "migrations" / "versions"
        
        migrations_found = False
        migration_files = []
        
        if alembic_ini.exists() and migrations_dir.exists():
            migrations_found = True
            migration_files = list(migrations_dir.glob("*.py"))
            migration_files = [f.name for f in migration_files if not f.name.startswith("__")]
        
        # Try to get alembic heads if alembic is available
        heads_info = "N/A"
        try:
            result = subprocess.run(['alembic', 'heads'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                heads_info = result.stdout.strip()
        except Exception:
            pass
        
        self.results['migrations'] = {
            'status': 'PASS' if migrations_found else 'WARN',
            'found': migrations_found,
            'migration_files': migration_files,
            'heads': heads_info,
            'message': f'Alembic setup: {migrations_found}, {len(migration_files)} migration files'
        }
        
        if migrations_found:
            print(f"   ✅ Alembic detected with {len(migration_files)} migration files")
            print(f"   📋 Migration files: {', '.join(migration_files)}")
        else:
            print("   ⚠️ No Alembic migration system detected")
        print()
    
    def audit_requirements(self):
        """(F) Requirements auditor"""
        print("🔧 (F) Requirements Audit")
        
        requirements_file = self.root_path / "requirements.txt"
        required_packages = [
            'fastapi', 'uvicorn', 'psycopg2-binary', 'psycopg', 
            'sqlalchemy', 'alembic', 'python-multipart'
        ]
        
        installed_packages = set()
        missing_packages = []
        playwright_imported = False
        
        if requirements_file.exists():
            try:
                with open(requirements_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Extract package name (before == or >= etc)
                            pkg_name = re.split(r'[>=<!=]', line)[0].strip()
                            installed_packages.add(pkg_name.lower())
            except Exception as e:
                print(f"   ⚠️ Error reading requirements.txt: {e}")
        
        # Check for missing packages
        for pkg in required_packages:
            if pkg not in installed_packages:
                missing_packages.append(pkg)
        
        # Check if playwright is imported in code
        for py_file in self.root_path.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'playwright' in content or 'async_playwright' in content:
                        playwright_imported = True
                        break
            except Exception:
                continue
        
        # Check if playwright is in requirements when imported
        if playwright_imported and 'playwright' not in installed_packages:
            missing_packages.append('playwright')
        
        status = 'PASS' if not missing_packages else 'FAIL'
        self.results['requirements'] = {
            'status': status,
            'missing_packages': missing_packages,
            'playwright_needed': playwright_imported,
            'message': f'Missing packages: {missing_packages}' if missing_packages else 'All required packages present'
        }
        
        if missing_packages:
            print(f"   ❌ Missing packages: {', '.join(missing_packages)}")
        else:
            print("   ✅ All required packages present")
        
        if playwright_imported:
            print(f"   📱 Playwright usage detected: {'✅' if 'playwright' in installed_packages else '❌'}")
        print()
    
    def audit_playwright_deps(self):
        """(G) Playwright/system deps auditor"""
        print("🔧 (G) Playwright Dependencies Audit")
        
        playwright_needed = self.results.get('requirements', {}).get('playwright_needed', False)
        
        if not playwright_needed:
            self.results['playwright_deps'] = {'status': 'SKIP', 'message': 'Playwright not detected in code'}
            print("   ⏭️ Playwright not detected in code")
            print()
            return
        
        dockerfile_path = self.root_path / "Dockerfile"
        chromium_deps_found = False
        playwright_install_found = False
        
        if dockerfile_path.exists():
            try:
                with open(dockerfile_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check for chromium dependencies
                chromium_libs = ['libnss3', 'libxss1', 'libasound2', 'libatk-bridge2.0-0', 'libgtk-3-0']
                if any(lib in content for lib in chromium_libs):
                    chromium_deps_found = True
                    
                # Check for playwright install
                if 'playwright install' in content:
                    playwright_install_found = True
                    
            except Exception as e:
                print(f"   ⚠️ Error reading Dockerfile: {e}")
        
        status = 'PASS' if (chromium_deps_found and playwright_install_found) else 'FAIL'
        self.results['playwright_deps'] = {
            'status': status,
            'chromium_deps': chromium_deps_found,
            'playwright_install': playwright_install_found,
            'message': f'Chromium deps: {chromium_deps_found}, Playwright install: {playwright_install_found}'
        }
        
        print(f"   🌐 Chromium dependencies: {'✅' if chromium_deps_found else '❌'}")
        print(f"   🌐 Playwright install: {'✅' if playwright_install_found else '❌'}")
        print()
    
    def audit_import_at_start(self):
        """(H) Import-at-start auditor"""
        print("🔧 (H) Import-at-Start Heavy Operations Audit")
        
        heavy_operations = []
        check_files = ['main.py'] + [str(f) for f in (self.root_path / "routes").glob("*.py") if f.is_file()]
        
        heavy_patterns = [
            r'\.connect\(',
            r'Session\(',
            r'create_engine\(',
            r'requests\.(get|post)',
            r'open\([^)]*["\'][rwab]',
            r'\.read\(\)',
            r'\.write\(',
        ]
        
        for file_path in check_files:
            try:
                full_path = self.root_path / file_path
                if not full_path.exists():
                    continue
                    
                with open(full_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                in_function = False
                for i, line in enumerate(lines, 1):
                    # Skip if we're inside a function or class
                    if re.match(r'^\s*(def|class|async def)', line):
                        in_function = True
                    elif line.strip() == '' or line.startswith(' ') or line.startswith('\t'):
                        continue
                    else:
                        in_function = False
                    
                    if not in_function:
                        for pattern in heavy_patterns:
                            if re.search(pattern, line):
                                heavy_operations.append({
                                    'file': file_path,
                                    'line': i,
                                    'content': line.strip()
                                })
                                
            except Exception as e:
                continue
        
        status = 'PASS' if not heavy_operations else 'WARN'
        self.results['import_heavy_ops'] = {
            'status': status,
            'violations': heavy_operations,
            'message': f'Found {len(heavy_operations)} potential heavy operations at import time'
        }
        
        if heavy_operations:
            print(f"   ⚠️ Found {len(heavy_operations)} potential heavy operations at import time:")
            for op in heavy_operations[:5]:  # Show first 5
                print(f"      {op['file']}:{op['line']} - {op['content'][:60]}...")
        else:
            print("   ✅ No heavy operations detected at import time")
        print()
    
    def print_report(self):
        """Print consolidated audit report"""
        print("=" * 60)
        print("🎯 COMPREHENSIVE AUDIT REPORT")
        print("=" * 60)
        
        for audit_name, result in self.results.items():
            status = result.get('status', 'UNKNOWN')
            message = result.get('message', 'No details')
            
            status_icon = {
                'PASS': '✅',
                'FAIL': '❌', 
                'WARN': '⚠️',
                'SKIP': '⏭️'
            }.get(status, '❓')
            
            print(f"{status_icon} {audit_name.upper().replace('_', ' ')}: {status}")
            print(f"   {message}")
            print()

if __name__ == "__main__":
    auditor = CodeAuditor()
    auditor.run_all_audits()
