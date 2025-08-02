# CarbonCast Repository Integration Guide

> **Complete step-by-step guide for integrating the RDA Automation System into the existing CarbonCast repository**

## 🎯 Overview

This guide provides specific instructions for pushing the cleaned-up RDA Automation codebase to the existing CarbonCast repository (https://github.com/carbonfirst/CarbonCast.git) in a new branch, ensuring proper integration without overwriting existing code.

## 📋 Prerequisites

- Git installed and configured
- Access to the CarbonCast repository
- Current RDA Automation System codebase ready for integration
- Sufficient disk space (minimum 2GB recommended)

## 🔒 Phase 1: Security Preparation

### Step 1.1: Clean Sensitive Files

Execute these commands from your RDA automation directory:

```bash
# Remove authentication tokens
find . -name "rdams_token.txt" -type f -delete
find . -name "*token*.txt" -type f -delete
find . -name "*_token" -type f -delete

# Remove credential files
find . -name "credentials.txt" -type f -delete
find . -name "api_keys.txt" -type f -delete
find . -name "*credential*" -type f -delete

# Remove local configuration files
find . -name "*_local.*" -type f -delete
find . -name "local_config.*" -type f -delete
find . -name "config_local.*" -type f -delete
find . -name "settings_local.*" -type f -delete

# Clean log files
find ./logs -name "*.log" -type f -delete 2>/dev/null || true
find . -name "*.log" -type f -delete 2>/dev/null || true
find . -name "*_debug.log" -type f -delete 2>/dev/null || true

# Remove database backups and temporary files
find . -name "*.db.backup*" -type f -delete
find . -name "*_backup.db" -type f -delete
find . -name "*.sqlite.backup" -type f -delete
find . -name "dev.db" -type f -delete
find . -name "test.db" -type f -delete
find . -name "local.db" -type f -delete

# Remove temporary and cache files
find . -name "temp_*" -type f -delete
find . -name "*.tmp" -type f -delete
find . -name "*.temp" -type f -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -type f -delete
find . -name "*.pyo" -type f -delete

# Remove system files
find . -name ".DS_Store" -type f -delete 2>/dev/null || true
find . -name "Thumbs.db" -type f -delete 2>/dev/null || true

# Remove IDE files (optional - keep if you want to share IDE settings)
find . -name ".vscode/settings.json" -type f -delete 2>/dev/null || true
find . -name ".idea" -type d -exec rm -rf {} + 2>/dev/null || true
```

### Step 1.2: Verify .gitignore Coverage

```bash
# Check that .gitignore covers sensitive patterns
echo "🔍 Verifying .gitignore coverage..."
grep -E "(token|credential|secret|password|api_key)" .gitignore || echo "⚠️  Consider adding more sensitive file patterns"
grep -E "(\.log|\.db|\.tmp)" .gitignore || echo "⚠️  Consider adding temporary file patterns"
```

### Step 1.3: Security Verification

```bash
# Scan for any remaining sensitive content
echo "🔍 Scanning for potential sensitive content..."
grep -r -i "password\|secret\|token\|credential" --exclude-dir=.git --exclude-dir=venv --exclude="*.md" . || echo "✅ No sensitive content found"

# Check for large files that shouldn't be committed
find . -type f -size +50M -not -path "./.git/*" -not -path "./venv/*" || echo "✅ No large files found"
```

## 🌿 Phase 2: Repository Cloning and Branch Setup

### Step 2.1: Clone CarbonCast Repository

```bash
# Navigate to a temporary directory for cloning
cd /tmp
mkdir carboncast-integration
cd carboncast-integration

# Clone the CarbonCast repository
echo "📥 Cloning CarbonCast repository..."
git clone https://github.com/carbonfirst/CarbonCast.git
cd CarbonCast

# Verify the clone
echo "✅ Repository cloned successfully"
git remote -v
git branch -a
```

### Step 2.2: Create Integration Branch

```bash
# Create and switch to a new branch for RDA integration
BRANCH_NAME="feature/rda-automation-integration"
echo "🌿 Creating integration branch: $BRANCH_NAME"

git checkout -b $BRANCH_NAME
git push -u origin $BRANCH_NAME

echo "✅ Integration branch created and pushed"
```

## 📁 Phase 3: Directory Structure Integration

### Step 3.1: Plan Integration Structure

The RDA Automation System will be integrated into CarbonCast using this structure:

```
CarbonCast/
├── rda-automation/                    # Main RDA system directory
│   ├── src/                          # Source code
│   │   └── python/                   # Python automation code
│   │       └── automation/           # Core automation modules
│   ├── config/                       # Configuration files
│   ├── control_files/                # RDA control files
│   ├── docs/                         # RDA documentation
│   ├── test/                         # Test files
│   ├── templates/                    # Template files
│   ├── requirements.txt              # Python dependencies
│   ├── README.md                     # RDA system documentation
│   └── start_automation.py           # Main entry point
├── data/                             # Data directories (gitignored)
│   └── rda-automation/
│       ├── downloaded_files/
│       ├── logs/
│       └── results/
└── [existing CarbonCast files...]    # Existing CarbonCast structure
```

### Step 3.2: Create Integration Directory Structure

```bash
# Create the main RDA automation directory
mkdir -p rda-automation
mkdir -p data/rda-automation/downloaded_files
mkdir -p data/rda-automation/logs
mkdir -p data/rda-automation/results

echo "✅ Integration directory structure created"
```

## 📦 Phase 4: Copy RDA Codebase

### Step 4.1: Copy Core Files

```bash
# Set the path to your RDA automation source (adjust as needed)
RDA_SOURCE_PATH="/Users/tanushsavadi/Documents/Research Lab Work/rda-apps-clients"

echo "📦 Copying RDA Automation System files..."

# Copy main source code
cp -r "$RDA_SOURCE_PATH/src" rda-automation/
cp -r "$RDA_SOURCE_PATH/config" rda-automation/
cp -r "$RDA_SOURCE_PATH/control_files" rda-automation/
cp -r "$RDA_SOURCE_PATH/docs" rda-automation/
cp -r "$RDA_SOURCE_PATH/test" rda-automation/
cp -r "$RDA_SOURCE_PATH/templates" rda-automation/

# Copy root files
cp "$RDA_SOURCE_PATH/README.md" rda-automation/
cp "$RDA_SOURCE_PATH/requirements.txt" rda-automation/
cp "$RDA_SOURCE_PATH/pytest.ini" rda-automation/
cp "$RDA_SOURCE_PATH/start_automation.py" rda-automation/
cp "$RDA_SOURCE_PATH/.gitignore" rda-automation/.gitignore-rda

# Copy license and contributing files if they exist
cp "$RDA_SOURCE_PATH/LICENSE" rda-automation/ 2>/dev/null || true
cp "$RDA_SOURCE_PATH/CONTRIBUTING.md" rda-automation/ 2>/dev/null || true

echo "✅ Core files copied successfully"
```

### Step 4.2: Update Configuration Paths

```bash
# Update configuration files to reflect new directory structure
echo "🔧 Updating configuration paths..."

# Update automation_config.json paths
sed -i.bak 's|"base_download_dir": "src/python/downloaded_files"|"base_download_dir": "../data/rda-automation/downloaded_files"|g' rda-automation/config/automation_config.json
sed -i.bak 's|"logs_dir": "./logs"|"logs_dir": "../data/rda-automation/logs"|g' rda-automation/config/automation_config.json
sed -i.bak 's|"control_files_dir": "./control_files"|"control_files_dir": "./control_files"|g' rda-automation/config/automation_config.json

# Remove backup files
rm -f rda-automation/config/*.bak

echo "✅ Configuration paths updated"
```

## 📝 Phase 5: Create Integration Documentation

### Step 5.1: Create CarbonCast Integration README

```bash
cat > rda-automation/CARBONCAST_INTEGRATION.md << 'EOF'
# RDA Automation System - CarbonCast Integration

## Overview

This directory contains the RDA Automation System integrated into the CarbonCast project. The RDA system provides automated meteorological data collection from NCAR's Research Data Archive.

## Quick Start

```bash
# Navigate to RDA automation directory
cd rda-automation

# Setup Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup RDA authentication (create this file with your token)
echo "your_rda_token_here" > rdams_token.txt

# Initialize system
cd src/python
python start_automation.py
```

## Integration Notes

- **Data Directory**: All data files are stored in `../data/rda-automation/`
- **Logs**: System logs are written to `../data/rda-automation/logs/`
- **Configuration**: Main config in `config/automation_config.json`
- **Documentation**: Complete docs in `docs/` directory

## Key Features

- 🔄 Sequential file processing with resume capability
- 🧠 Smart retry mechanisms with exponential backoff
- 📊 Real-time dashboard monitoring
- ⚡ Automated capacity management
- 🔍 Comprehensive error tracking
- 🗺️ Support for 200+ CTL files across 85+ regions

## Support

See the main [README.md](README.md) for complete documentation and troubleshooting guides.
EOF

echo "✅ Integration documentation created"
```

### Step 5.2: Update Main CarbonCast README

```bash
# Add RDA integration section to main README if it exists
if [ -f README.md ]; then
    echo "" >> README.md
    echo "## RDA Automation System Integration" >> README.md
    echo "" >> README.md
    echo "This repository includes an integrated RDA (Research Data Archive) Automation System for meteorological data collection." >> README.md
    echo "" >> README.md
    echo "**Location**: \`rda-automation/\`" >> README.md
    echo "" >> README.md
    echo "**Quick Start**:" >> README.md
    echo "\`\`\`bash" >> README.md
    echo "cd rda-automation" >> README.md
    echo "python -m venv venv && source venv/bin/activate" >> README.md
    echo "pip install -r requirements.txt" >> README.md
    echo "cd src/python && python start_automation.py" >> README.md
    echo "\`\`\`" >> README.md
    echo "" >> README.md
    echo "**Documentation**: See [rda-automation/README.md](rda-automation/README.md) for complete setup and usage instructions." >> README.md
    echo "" >> README.md
    
    echo "✅ Main README updated with RDA integration info"
fi
```

## 🔄 Phase 6: Git Integration and Commit

### Step 6.1: Stage and Review Changes

```bash
# Add all RDA automation files
git add rda-automation/

# Add updated main README if modified
git add README.md 2>/dev/null || true

# Review what will be committed
echo "📋 Reviewing changes to be committed..."
git status
echo ""
echo "📊 File count and size summary:"
git ls-files rda-automation/ | wc -l
du -sh rda-automation/
```

### Step 6.2: Create Comprehensive Commit

```bash
# Create detailed commit message
git commit -m "feat: Integrate RDA Automation System for meteorological data collection

🚀 Features Added:
- Complete RDA Automation System with 200+ CTL file support
- Sequential file processing with resume capability
- Smart retry mechanisms with exponential backoff
- Real-time dashboard monitoring with WebSocket updates
- Automated capacity management for RDA's 10-request limit
- Comprehensive error tracking and recovery
- Support for 85+ regions (US grid operators + European countries)
- Weather variables: solar radiation, wind, temperature, precipitation

📁 Integration Structure:
- Main system: rda-automation/
- Data storage: data/rda-automation/
- Configuration: rda-automation/config/
- Documentation: rda-automation/docs/

🔧 Technical Details:
- Python 3.7+ automation system
- Flask-based web dashboard
- SQLite database for state management
- Comprehensive test suite included
- Production-ready with enterprise-grade reliability

📖 Documentation:
- Complete setup guide in rda-automation/README.md
- Integration notes in rda-automation/CARBONCAST_INTEGRATION.md
- API reference and troubleshooting guides included

This integration maintains full compatibility with existing CarbonCast
functionality while adding powerful meteorological data automation
capabilities."

echo "✅ Changes committed successfully"
```

## 🚀 Phase 7: Push and Verification

### Step 7.1: Push Integration Branch

```bash
# Push the integration branch
echo "🚀 Pushing integration branch to CarbonCast repository..."
git push origin $BRANCH_NAME

echo "✅ Integration branch pushed successfully"
echo ""
echo "🔗 Branch URL: https://github.com/carbonfirst/CarbonCast/tree/$BRANCH_NAME"
```

### Step 7.2: Create Pull Request Information

```bash
# Generate pull request information
cat > PR_INFORMATION.md << 'EOF'
# Pull Request: RDA Automation System Integration

## Summary
This PR integrates a comprehensive RDA (Research Data Archive) Automation System into CarbonCast, providing automated meteorological data collection capabilities.

## Key Features
- 🔄 **Sequential Processing**: Ordered file processing with resume capability
- 🧠 **Smart Retry System**: Intelligent failure recovery with exponential backoff
- 📊 **Real-time Dashboard**: Live monitoring with WebSocket updates
- ⚡ **Capacity Management**: Automated handling of RDA's 10-request limit
- 🔍 **Error Tracking**: Comprehensive error detection and recovery
- 🗺️ **Extensive Coverage**: 200+ CTL files across 85+ regions

## Integration Details
- **Location**: `rda-automation/` directory
- **Data Storage**: `data/rda-automation/` (gitignored)
- **No Conflicts**: Completely isolated from existing CarbonCast code
- **Documentation**: Complete setup and usage guides included

## Testing
- ✅ All sensitive files removed
- ✅ Configuration paths updated for integration
- ✅ Documentation updated
- ✅ No conflicts with existing code structure

## Next Steps
1. Review integration structure
2. Test RDA system setup (requires RDA token)
3. Merge when approved
4. Update team documentation

## Files Changed
- Added: `rda-automation/` directory with complete RDA system
- Modified: `README.md` (added integration section)
- Added: Integration documentation and setup guides
EOF

echo "✅ Pull request information generated in PR_INFORMATION.md"
```

## ✅ Phase 8: Verification and Testing

### Step 8.1: Verify Integration Structure

```bash
echo "🔍 Verifying integration structure..."

# Check directory structure
echo "📁 Directory structure:"
find rda-automation -type d -maxdepth 3 | head -20

echo ""
echo "📊 File counts by directory:"
echo "Source code: $(find rda-automation/src -name "*.py" | wc -l) Python files"
echo "Documentation: $(find rda-automation/docs -name "*.md" | wc -l) documentation files"
echo "Control files: $(find rda-automation/control_files -name "*.ctl" | wc -l) control files"
echo "Tests: $(find rda-automation/test -name "*.py" | wc -l) test files"

echo ""
echo "✅ Integration structure verified"
```

### Step 8.2: Test Installation Process

```bash
# Test the installation process
echo "🧪 Testing installation process..."

# Create test environment
cd /tmp
mkdir rda-integration-test
cd rda-integration-test

# Clone the integration branch
git clone -b $BRANCH_NAME https://github.com/carbonfirst/CarbonCast.git test-install
cd test-install/rda-automation

# Test Python environment setup
python3 -m venv test_env
source test_env/bin/activate

# Test dependency installation
pip install -r requirements.txt

# Test basic import
cd src/python
python -c "
try:
    from automation.sequential_file_processor import create_sequential_file_processor
    print('✅ Core modules import successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
except Exception as e:
    print(f'⚠️  Other error (may be normal without RDA token): {e}')
"

# Cleanup test environment
deactivate
cd /tmp
rm -rf rda-integration-test

echo "✅ Installation test completed"
```

## 🔧 Phase 9: Post-Integration Setup

### Step 9.1: Team Setup Instructions

```bash
cat > rda-automation/TEAM_SETUP.md << 'EOF'
# Team Setup Instructions

## For Team Members

### Initial Setup
```bash
# Clone the repository
git clone https://github.com/carbonfirst/CarbonCast.git
cd CarbonCast

# Switch to RDA integration branch (until merged)
git checkout feature/rda-automation-integration

# Setup RDA automation
cd rda-automation
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### RDA Authentication Setup
1. Create an account at [RDA](https://rda.ucar.edu/)
2. Generate an authentication token
3. Create `rdams_token.txt` in the `rda-automation/` directory:
   ```bash
   echo "your_rda_token_here" > rdams_token.txt
   ```

### Quick Test
```bash
cd src/python
python start_automation.py --test
```

### Dashboard Access
```bash
cd src/python
python automation/dashboard.py --port 8080
# Visit: http://localhost:8080
```

## Security Notes
- Never commit `rdams_token.txt` to git
- Keep RDA tokens secure and rotate regularly
- Use environment variables in production

## Support
- Main documentation: `README.md`
- Integration guide: `CARBONCAST_INTEGRATION.md`
- Troubleshooting: `docs/Troubleshooting_Guide.md`
EOF

echo "✅ Team setup instructions created"
```

### Step 9.2: Update .gitignore for Data Directory

```bash
# Add data directory to main .gitignore if it exists
if [ -f .gitignore ]; then
    echo "" >> .gitignore
    echo "# RDA Automation System data (added by integration)" >> .gitignore
    echo "data/rda-automation/" >> .gitignore
    echo "rda-automation/rdams_token.txt" >> .gitignore
    echo "rda-automation/src/python/data/" >> .gitignore
    echo "rda-automation/logs/" >> .gitignore
    
    git add .gitignore
    git commit -m "chore: Update .gitignore for RDA automation data directories"
    git push origin $BRANCH_NAME
    
    echo "✅ Main .gitignore updated and committed"
else
    # Create .gitignore if it doesn't exist
    cat > .gitignore << 'EOF'
# RDA Automation System data
data/rda-automation/
rda-automation/rdams_token.txt
rda-automation/src/python/data/
rda-automation/logs/
EOF
    
    git add .gitignore
    git commit -m "chore: Add .gitignore for RDA automation system"
    git push origin $BRANCH_NAME
    
    echo "✅ New .gitignore created and committed"
fi
```

## 📋 Phase 10: Final Verification Checklist

### Step 10.1: Complete Integration Checklist

```bash
echo "📋 Final Integration Verification Checklist:"
echo ""

# Check 1: Branch exists and is pushed
if git ls-remote --heads origin $BRANCH_NAME | grep -q $BRANCH_NAME; then
    echo "✅ Integration branch exists on remote"
else
    echo "❌ Integration branch not found on remote"
fi

# Check 2: RDA directory structure
if [ -d "rda-automation/src/python/automation" ]; then
    echo "✅ RDA automation source code present"
else
    echo "❌ RDA automation source code missing"
fi

# Check 3: Documentation
if [ -f "rda-automation/README.md" ] && [ -f "rda-automation/CARBONCAST_INTEGRATION.md" ]; then
    echo "✅ Integration documentation present"
else
    echo "❌ Integration documentation missing"
fi

# Check 4: Configuration files
if [ -f "rda-automation/config/automation_config.json" ]; then
    echo "✅ Configuration files present"
else
    echo "❌ Configuration files missing"
fi

# Check 5: No sensitive files
if ! find rda-automation -name "*token*" -o -name "*credential*" -o -name "*.log" | grep -q .; then
    echo "✅ No sensitive files found"
else
    echo "⚠️  Potential sensitive files found - review needed"
fi

# Check 6: Git status clean
if git status --porcelain | grep -q .; then
    echo "⚠️  Uncommitted changes present"
    git status --short
else
    echo "✅ Git working directory clean"
fi

echo ""
echo "🎉 Integration verification completed!"
```

## 🚨 Troubleshooting

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| **Large file errors** | Check for accidentally included data files: `find rda-automation -size +50M` |
| **Permission denied** | Ensure you have push access to CarbonCast repository |
| **Merge conflicts** | The integration is isolated, conflicts should be rare |
| **Import errors during testing** | Normal without RDA token - verify Python path setup |
| **Missing dependencies** | Ensure `requirements.txt` was copied correctly |

### Emergency Rollback

```bash
# If you need to rollback the integration
git checkout main
git branch -D $BRANCH_NAME
git push origin --delete $BRANCH_NAME
```

### Clean Restart

```bash
# To start the integration process over
cd /tmp/carboncast-integration/CarbonCast
git checkout main
git branch -D $BRANCH_NAME 2>/dev/null || true
git push origin --delete $BRANCH_NAME 2>/dev/null || true

# Then restart from Phase 2
```

## 📞 Support and Next Steps

### Immediate Next Steps
1. **Review the integration** in the GitHub web interface
2. **Create a Pull Request** using the information in `PR_INFORMATION.md`
3. **Test the setup** following `TEAM_SETUP.md` instructions
4. **Schedule team review** of the integration

### Long-term Considerations
- **Production deployment** planning
- **Team training** on RDA system usage
- **Monitoring setup** for production environment
- **Backup strategy** for RDA data and configurations

### Support Resources
- **Integration Issues**: Check this guide's troubleshooting section
- **RDA System Issues**: See `rda-automation/docs/Troubleshooting_Guide.md`
- **CarbonCast Issues**: Follow existing CarbonCast support procedures

---

## 🎉 Integration Complete!

The RDA Automation System has been successfully integrated into the CarbonCast repository. The system is now available in the `feature/rda-automation-integration` branch and ready for team review and testing.

**Key Integration Points:**
- ✅ **Isolated Integration**: No conflicts with existing CarbonCast code
- ✅ **Complete System**: All RDA automation features preserved
- ✅ **Proper Documentation**: Setup and usage guides included
- ✅ **Security Verified**: All sensitive files removed
- ✅ **Team Ready**: Setup instructions provided

**Branch URL**: https://github.com/carbonfirst/CarbonCast/tree/feature/rda-automation-integration

The integration maintains the full power and functionality of the RDA Automation System while seamlessly fitting into the CarbonCast project structure.