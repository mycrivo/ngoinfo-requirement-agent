#!/usr/bin/env python3
"""
AST parameter order audit script
Scans Python files for functions with parameter order issues
"""
import ast
import os
from typing import List, Dict, Any

def audit_parameter_order(file_path: str) -> List[Dict[str, Any]]:
    """Audit parameter order in a Python file using AST"""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                issue = check_function_parameters(node, file_path)
                if issue:
                    issues.append(issue)
                    
    except Exception as e:
        print(f"⚠️ Error parsing {file_path}: {e}")
    
    return issues

def check_function_parameters(func_node, file_path: str) -> Dict[str, Any]:
    """Check if function has parameter order issues"""
    args = func_node.args
    
    # Check for non-default after default arguments
    seen_default = False
    
    # Regular arguments
    for i, arg in enumerate(args.args):
        # Skip 'self' and 'cls'
        if arg.arg in ('self', 'cls'):
            continue
            
        has_default = i >= len(args.args) - len(args.defaults)
        
        if seen_default and not has_default:
            return {
                'file': file_path,
                'line': func_node.lineno,
                'function': func_node.name,
                'issue': 'non-default argument follows default argument',
                'signature': get_function_signature(func_node)
            }
        
        if has_default:
            seen_default = True
    
    # Check keyword-only arguments with defaults
    kw_defaults = args.kw_defaults or []
    for i, (arg, default) in enumerate(zip(args.kwonlyargs, kw_defaults)):
        if arg.arg == 'request':
            # Special check: request parameter should come early
            if i > 2:  # Allow some flexibility but request shouldn't be too late
                return {
                    'file': file_path,
                    'line': func_node.lineno,
                    'function': func_node.name,
                    'issue': 'request parameter appears late in signature',
                    'signature': get_function_signature(func_node)
                }
    
    return None

def get_function_signature(func_node) -> str:
    """Extract function signature for display"""
    try:
        args_list = []
        
        # Regular arguments
        for i, arg in enumerate(func_node.args.args):
            if i >= len(func_node.args.args) - len(func_node.args.defaults):
                # Has default
                default_idx = i - (len(func_node.args.args) - len(func_node.args.defaults))
                args_list.append(f"{arg.arg}=...")
            else:
                # No default
                args_list.append(arg.arg)
        
        # Keyword-only arguments
        for kwarg in func_node.args.kwonlyargs:
            args_list.append(f"{kwarg.arg}=...")
        
        return f"def {func_node.name}({', '.join(args_list)})"
        
    except Exception:
        return f"def {func_node.name}(...)"

def scan_codebase() -> List[Dict[str, Any]]:
    """Scan entire codebase for parameter order issues"""
    all_issues = []
    
    # Directories to scan
    directories = [
        'routes',
        'services', 
        'utils',
        '.'  # Root directory for main.py etc
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
            
        if directory == '.':
            # Only scan Python files in root
            for file in os.listdir('.'):
                if file.endswith('.py') and not file.startswith('test_'):
                    issues = audit_parameter_order(file)
                    all_issues.extend(issues)
        else:
            # Scan all Python files in directory
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        issues = audit_parameter_order(file_path)
                        all_issues.extend(issues)
    
    return all_issues

def generate_issues_table(issues: List[Dict[str, Any]]) -> str:
    """Generate markdown table of parameter order issues"""
    if not issues:
        return "✅ No parameter order issues found.\n"
    
    table = "| File:Line | Function | Issue | Signature |\n"
    table += "|-----------|----------|-------|----------|\n"
    
    for issue in sorted(issues, key=lambda x: (x['file'], x['line'])):
        file_line = f"{issue['file']}:{issue['line']}"
        table += f"| {file_line} | {issue['function']} | {issue['issue']} | `{issue['signature']}` |\n"
    
    return table

if __name__ == "__main__":
    print("🔍 Scanning codebase for parameter order issues...")
    
    issues = scan_codebase()
    
    print(f"\n📊 AST PARAMETER ORDER AUDIT")
    print(f"============================")
    print(f"Files scanned: {len([f for d in ['routes', 'services', 'utils', '.'] for f in (os.listdir(d) if os.path.exists(d) else []) if f.endswith('.py')])}")
    print(f"Issues found: {len(issues)}")
    
    if issues:
        print(f"\n❌ PARAMETER ORDER ISSUES")
        print(f"=========================")
        print(generate_issues_table(issues))
    else:
        print(f"\n✅ No parameter order issues found!")
    
    # Summary
    print(f"\n📋 SUMMARY")
    print(f"==========")
    if issues:
        print(f"❌ Found {len(issues)} parameter order issues that need fixing")
        for issue in issues:
            print(f"   - {issue['file']}:{issue['line']} {issue['function']}(): {issue['issue']}")
    else:
        print(f"✅ All function parameter orders are correct")

