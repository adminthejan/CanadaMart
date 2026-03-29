#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  CanadaMart POS – Linux/macOS Build Script
# ═══════════════════════════════════════════════════════════════
set -e

echo ""
echo "  ============================================="
echo "   CanadaMart POS – Building with PyInstaller"
echo "  ============================================="
echo ""

pip install -r requirements.txt --upgrade

rm -rf dist/CanadaMartPOS build/CanadaMartPOS

pyinstaller build.spec --clean --noconfirm

echo ""
echo "  BUILD COMPLETE → dist/CanadaMartPOS/"
echo ""
