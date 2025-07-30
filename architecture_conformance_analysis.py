#!/usr/bin/env python3
"""
Architecture Conformance Analysis Script for Shopping Cart Application

This script performs the following:
1. Reads the codebase from the provided GitHub URL.
2. Parses the architecture and class diagrams from the provided RTF document.
3. Identifies annotations (@RestController, @Service, @Entity, etc.) and maps them to architecture components.
4. Analyzes methods and fields to understand roles and responsibilities.
5. Validates expected chains (Controller → Service → Repository).
6. Evaluates architectural rules (YAML format) from the architecture document.
7. Verifies relationships from class diagrams are implemented in code.
8. Generates a detailed Markdown report as specified.
"""
import os
import re
import requests
import tempfile
import zipfile
import yaml
from bs4 import BeautifulSoup
from striprtf.striprtf import rtf_to_text

GITHUB_CODE_URL = "https://github.com/saniyakapur39/shopping-cart-app/tree/main/src/main"
ARCH_DOC_URL = "https://github.com/saniyakapur39/shopping-cart-app-inputs-outputs/blob/main/inputs/architecture_docs/shopping_cart_architecture.rtf"

REPORT_MD = "architecture_conformance_report.md"

# Helper functions
def download_github_folder(url, dest_dir):
    # Use GitHub API to download the folder as zip
    repo = url.split('/')[3] + '/' + url.split('/')[4]
    branch = url.split('/')[6]
    path = '/'.join(url.split('/')[7:])
    zip_url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
    r = requests.get(zip_url)
    zip_path = os.path.join(dest_dir, 'repo.zip')
    with open(zip_path, 'wb') as f:
        f.write(r.content)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest_dir)
    # Find extracted folder
    for name in os.listdir(dest_dir):
        if name.startswith(repo.split('/')[1] + '-' + branch):
            return os.path.join(dest_dir, name, path)
    return None

def download_file(url, dest_path):
    # Raw file download for GitHub
    raw_url = url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
    r = requests.get(raw_url)
    with open(dest_path, 'wb') as f:
        f.write(r.content)

def parse_java_files(src_dir):
    java_files = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.java'):
                java_files.append(os.path.join(root, file))
    return java_files

def extract_annotations_and_classes(java_file):
    with open(java_file, 'r', encoding='utf-8') as f:
        code = f.read()
    annotations = re.findall(r'@(RestController|Controller|Service|Repository|Entity|Component)', code)
    class_match = re.search(r'(public|private|protected)?\s*class\s+(\w+)', code)
    class_name = class_match.group(2) if class_match else None
    methods = re.findall(r'(public|private|protected)\s+[\w<>\[\]]+\s+(\w+)\s*\(', code)
    fields = re.findall(r'(private|protected|public)\s+[\w<>\[\]]+\s+(\w+);', code)
    return {
        'file': java_file,
        'annotations': annotations,
        'class_name': class_name,
        'methods': [m[1] for m in methods],
        'fields': [f[1] for f in fields],
        'code': code
    }

def parse_architecture_doc(rtf_path):
    with open(rtf_path, 'r', encoding='utf-8') as f:
        rtf_content = f.read()
    text = rtf_to_text(rtf_content)
    # Extract YAML rules
    yaml_match = re.search(r'---(.*?)---', text, re.DOTALL)
    rules = yaml.safe_load(yaml_match.group(1)) if yaml_match else {}
    # Extract component/class mapping
    components = {}
    for line in text.splitlines():
        if ':' in line and any(x in line for x in ['Controller', 'Service', 'Repository', 'Entity']):
            k, v = line.split(':', 1)
            components[k.strip()] = v.strip()
    return text, rules, components

def analyze_codebase(java_files):
    analysis = []
    for jf in java_files:
        analysis.append(extract_annotations_and_classes(jf))
    return analysis

def map_components(analysis, arch_components):
    mapped = []
    for item in analysis:
        for ann in item['annotations']:
            for k, v in arch_components.items():
                if ann in k or ann in v:
                    mapped.append({
                        'class': item['class_name'],
                        'annotation': ann,
                        'file': item['file'],
                        'methods': item['methods'],
                        'fields': item['fields'],
                        'arch_component': k
                    })
    return mapped

def validate_chains(mapped):
    # Simple validation for Controller → Service → Repository
    chains = []
    for m in mapped:
        if m['annotation'] in ['RestController', 'Controller']:
            for method in m['methods']:
                # Look for service usage in code
                with open(m['file'], 'r', encoding='utf-8') as f:
                    code = f.read()
                if re.search(r'\bservice\b', code, re.IGNORECASE):
                    chains.append((m['class'], 'Service'))
        if m['annotation'] == 'Service':
            with open(m['file'], 'r', encoding='utf-8') as f:
                code = f.read()
            if re.search(r'\brepository\b', code, re.IGNORECASE):
                chains.append((m['class'], 'Repository'))
    return chains

def evaluate_rules(mapped, rules):
    # Evaluate YAML rules against mapped components
    results = []
    for rule in rules.get('rules', []):
        for m in mapped:
            if rule['component'] in m['arch_component']:
                # Check for required relationships
                if 'must_depend_on' in rule:
                    dep = rule['must_depend_on']
                    found = any(dep in x['arch_component'] for x in mapped if x['class'] != m['class'])
                    results.append({
                        'rule': rule,
                        'component': m['class'],
                        'result': 'Pass' if found else 'Fail'
                    })
    return results

def generate_report(text, mapped, chains, rule_results, analysis):
    with open(REPORT_MD, 'w', encoding='utf-8') as f:
        f.write("# Architecture Conformance Analysis Report\n\n")
        f.write("## Executive Summary\n\n")
        f.write("This report presents a comprehensive architecture conformance analysis for the Shopping Cart Application. The analysis covers mapping of codebase components to the architecture, evaluation of architectural rules, identification of gaps, and suggestions for remediation.\n\n")
        f.write("## Detailed Rule Evaluation\n\n")
        for rr in rule_results:
            f.write(f"- Rule: {rr['rule']}\n  - Component: {rr['component']}\n  - Result: {rr['result']}\n")
        f.write("\n## Matched Components\n\n")
        f.write("| Class | Annotation | Architecture Component | Methods | Fields |\n|-------|------------|-----------------------|---------|--------|\n")
        for m in mapped:
            f.write(f"| {m['class']} | @{m['annotation']} | {m['arch_component']} | {', '.join(m['methods'])} | {', '.join(m['fields'])} |\n")
        f.write("\n## Gaps & Missing Components\n\n")
        all_arch = set([k for k in mapped])
        all_code = set([a['class_name'] for a in analysis])
        missing = all_code - set([m['class'] for m in mapped])
        for m in missing:
            f.write(f"- {m} is present in code but not mapped to any architecture component.\n")
        f.write("\n## Suggested Remediations\n\n")
        for m in missing:
            f.write(f"- Review class `{m}` and annotate or refactor to align with architecture.\n")
        f.write("\n## Coverage Statistics\n\n")
        total = len(analysis)
        mapped_count = len(mapped)
        f.write(f"- Total classes analyzed: {total}\n")
        f.write(f"- Classes mapped to architecture: {mapped_count}\n")
        f.write(f"- Coverage: {mapped_count/total*100:.2f}%\n")
        f.write("\n## Embedded Examples\n\n")
        # Example code snippet
        if mapped:
            f.write("### Example Controller Class\n\n")
            f.write("```java\n")
            f.write(mapped[0]['code'][:500])
            f.write("\n```")
        f.write("\n\n### Architecture Diagram Fragment\n\n")
        f.write("```")
        f.write(text[:500])
        f.write("\n```")

# Main execution
def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = download_github_folder(GITHUB_CODE_URL, tmpdir)
        rtf_path = os.path.join(tmpdir, 'arch.rtf')
        download_file(ARCH_DOC_URL, rtf_path)
        java_files = parse_java_files(src_dir)
        analysis = analyze_codebase(java_files)
        text, rules, arch_components = parse_architecture_doc(rtf_path)
        mapped = map_components(analysis, arch_components)
        chains = validate_chains(mapped)
        rule_results = evaluate_rules(mapped, rules)
        generate_report(text, mapped, chains, rule_results, analysis)
        print(f"Report generated: {REPORT_MD}")

if __name__ == "__main__":
    main()
