#!/bin/bash
# npm-security-audit.sh — checks for malicious/vulnerable packages
# Run: ./scripts/npm-security-audit.sh /path/to/project
# Exits non-zero if critical issues found

set -euo pipefail

PROJECT_DIR="${1:-.}"
ISSUES=0

echo "🔒 NPM Security Audit: $PROJECT_DIR"
echo "=================================="

# 1. Check for known vulnerable packages
echo ""
echo "▶ Running npm audit..."
cd "$PROJECT_DIR"
if [ -f "package-lock.json" ]; then
    AUDIT=$(npm audit --json 2>/dev/null || true)
    CRITICAL=$(echo "$AUDIT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('metadata',{}).get('vulnerabilities',{}).get('critical',0))" 2>/dev/null || echo "0")
    HIGH=$(echo "$AUDIT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('metadata',{}).get('vulnerabilities',{}).get('high',0))" 2>/dev/null || echo "0")
    echo "   Critical: $CRITICAL | High: $HIGH"
    if [ "$CRITICAL" -gt 0 ]; then
        echo "   ❌ CRITICAL vulnerabilities found!"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo "   ⚠️ No package-lock.json — run npm install first"
fi

# 2. Check for known malicious packages (typosquatting, wormware)
echo ""
echo "▶ Checking for known malicious packages..."
MALICIOUS_PATTERNS=(
    "event-stream"       # known compromised
    "flatmap-stream"     # malware payload
    "ua-parser-js"       # hijacked versions
    "coa"                # hijacked
    "rc"                 # hijacked
    "colors"            # sabotaged (>1.4.0)
    "faker"             # sabotaged (>5.5.3)
    "node-ipc"          # protestware/wormware
    "peacenotwar"       # embedded in node-ipc
    "es5-ext"           # protestware
    "styled-components" # typosquat target
    "loadsh"            # typosquat of lodash
    "crossenv"          # typosquat of cross-env
    "babelcli"          # typosquat of babel-cli
    "d3.js"             # typosquat of d3
    "gruntcli"          # typosquat of grunt-cli
    "mongose"           # typosquat of mongoose
    "mariadb"           # typosquat of mysql
)

if [ -f "package.json" ]; then
    for pkg in "${MALICIOUS_PATTERNS[@]}"; do
        if grep -q "\"$pkg\"" package.json package-lock.json 2>/dev/null; then
            echo "   ❌ MALICIOUS PACKAGE DETECTED: $pkg"
            ISSUES=$((ISSUES + 1))
        fi
    done
    if [ $ISSUES -eq 0 ]; then
        echo "   ✅ No known malicious packages found"
    fi
fi

# 3. Check for suspicious install scripts
echo ""
echo "▶ Checking for suspicious install scripts..."
if [ -f "package-lock.json" ]; then
    SCRIPTS=$(grep -c '"preinstall"\|"postinstall"\|"install"' node_modules/*/package.json 2>/dev/null | grep -v ":0$" | wc -l || echo "0")
    echo "   Packages with install scripts: $SCRIPTS"
    if [ "$SCRIPTS" -gt 20 ]; then
        echo "   ⚠️ High number of install scripts — review manually"
    fi
fi

# 4. Check for packages pulling from non-registry sources
echo ""
echo "▶ Checking for non-registry dependencies..."
if [ -f "package.json" ]; then
    SUSPICIOUS=$(grep -E '"(http|git|github|file):' package.json 2>/dev/null | wc -l || echo "0")
    if [ "$SUSPICIOUS" -gt 0 ]; then
        echo "   ⚠️ $SUSPICIOUS dependencies from non-registry sources:"
        grep -E '"(http|git|github|file):' package.json 2>/dev/null || true
    else
        echo "   ✅ All dependencies from npm registry"
    fi
fi

# 5. Check .npmrc for registry overrides
echo ""
echo "▶ Checking .npmrc..."
if [ -f ".npmrc" ]; then
    if grep -q "registry=" .npmrc; then
        echo "   ⚠️ Custom registry configured: $(grep 'registry=' .npmrc)"
    fi
else
    echo "   ✅ Using default npm registry"
fi

echo ""
echo "=================================="
if [ $ISSUES -gt 0 ]; then
    echo "❌ FAILED: $ISSUES critical issue(s) found"
    exit 1
else
    echo "✅ PASSED: No critical security issues"
    exit 0
fi
