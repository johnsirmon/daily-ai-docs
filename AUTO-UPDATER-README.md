# AI Documentation Auto-Updater

An automated system that monitors your AI documentation files (ChatGPT and Claude guides) and checks for updates daily using AI APIs to detect changes in capabilities, models, and best practices.

## 🚀 Quick Start

### Option 1: Simple Setup (Recommended)
1. **Run Setup**: Double-click `setup.bat` 
2. **Add API Keys**: The setup will open `config.json` - add your API keys
3. **Start Using**: Double-click `run_updater.bat` to check for updates

### Option 2: Manual Setup
1. **Install Python 3.8+** from [python.org](https://python.org)
2. **Create virtual environment**: `python -m venv venv`
3. **Activate**: `venv\Scripts\activate`
4. **Install packages**: `pip install -r requirements.txt`
5. **Configure**: Edit `config.json` with your API keys
6. **Run**: `python doc_updater.py`

## 📋 What You Need

### API Keys (Required)
- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/api-keys)
- **Anthropic API Key**: Get from [Anthropic Console](https://console.anthropic.com/)

### Files in This System
```
📁 Your Documentation Folder/
├── 🔧 Core System Files
│   ├── doc_updater.py          # Main updater application
│   ├── config.json             # Configuration (add your API keys here)
│   ├── requirements.txt        # Python dependencies
│   ├── run_updater.bat         # Easy Windows launcher
│   ├── setup.bat              # One-click setup script
│   └── run_updater.ps1        # PowerShell automation script
│
├── 📚 Documentation Files
│   ├── ChatGPT-Complete-Reference-Guide.md
│   ├── ChatGPT-Models-Prompting-Guide.md
│   ├── Anthropic-Claude-Models-Guide.md
│   ├── AI-Platform-Comparison-Guide.md
│   └── AI-Terminal-CLI-Guide.md
│
└── 📊 Generated Files (auto-created)
    ├── logs/                   # Update logs and history
    ├── versions/               # Backup versions with timestamps
    └── changes/                # Change reports and summaries
```

## 🎯 How to Use

### Daily Updates
- **Quick Check**: Double-click `run_updater.bat` → Choose option 1
- **Full Update**: Double-click `run_updater.bat` → Choose option 2
- **View Summary**: Double-click `run_updater.bat` → Choose option 3

### Command Line Options
```powershell
# Check for updates (creates versions, doesn't modify originals)
python doc_updater.py

# Update original files if changes found
python doc_updater.py --update-originals

# Show summary of last check only
python doc_updater.py --summary-only

# Check specific document
python doc_updater.py --file "ChatGPT-Complete-Reference-Guide.md"
```

## ⚙️ Configuration

Edit `config.json` to customize:

```json
{
  "api_keys": {
    "openai": "YOUR_OPENAI_API_KEY_HERE",
    "anthropic": "YOUR_ANTHROPIC_API_KEY_HERE"
  },
  "documents": [
    "ChatGPT-Complete-Reference-Guide.md",
    "Anthropic-Claude-Models-Guide.md"
  ],
  "update_frequency_hours": 24,
  "create_backups": true,
  "notify_on_changes": true
}
```

## 👤 Human-in-the-Loop Review & Self-Tuning

The system learns from your feedback. After each update run a review request file is
generated automatically. Rate the output and your corrections are injected into the
next AI run — making documentation progressively more accurate and useful.

### Quick Review (< 2 minutes)

```powershell
# See what needs review
python feedback_collector.py list

# Start interactive review session
python feedback_collector.py review
# or use the shortcut:
python doc_updater.py --review
```

### Feedback via GitHub Issue

Open a **📝 Document Feedback** issue using the template in
`.github/ISSUE_TEMPLATE/doc-feedback.yml` to leave async feedback without a local setup.

### Non-interactive feedback

```powershell
python feedback_collector.py add `
  --doc "ChatGPT-Models-Prompting-Guide.md" `
  --run-id "20250222_090012" `
  --accuracy 4 --usefulness 5 `
  --comments "Good depth" `
  --corrections "GPT-4o mini price is $0.15/1M tokens"
```

See **[HUMAN-REVIEW-GUIDE.md](HUMAN-REVIEW-GUIDE.md)** for the complete workflow.

---

## 🔄 Automation Options

### Windows Task Scheduler (Daily Auto-Run)

1. Open **Task Scheduler** (`taskschd.msc`)
2. Create **Basic Task**
3. **Name**: "AI Doc Updates"
4. **Trigger**: Daily at your preferred time
5. **Action**: Start a program
6. **Program**: `powershell.exe`
7. **Arguments**: `-ExecutionPolicy Bypass -File "C:\full\path\to\run_updater.ps1"`
8. **Start in**: `C:\full\path\to\your\docs\folder`

### Manual Scheduling
- Add `run_updater.bat` to your Windows Startup folder
- Create a desktop shortcut for quick daily checks
- Set a calendar reminder to run weekly

## 📊 What It Checks

### For ChatGPT Documents
- New model releases and capabilities
- Updated API endpoints and parameters
- Changed rate limits or pricing
- New features and tools
- Best practice updates

### For Claude Documents
- Model updates and new versions
- API changes and improvements
- New capabilities and features
- Usage guideline changes
- Performance improvements

### For All Documents
- Outdated information detection
- Broken links or references
- New techniques and strategies
- Community best practices
- Security and compliance updates

## 🛠️ Troubleshooting

### Common Issues

**"Python not found"**
- Install Python 3.8+ from [python.org](https://python.org)
- Make sure "Add to PATH" is checked during installation

**"API key invalid"**
- Check your API keys in `config.json`
- Ensure keys have proper permissions
- Verify account has available credits

**"No changes detected"**
- This is normal - it means your docs are up to date
- Check `logs/` folder for detailed analysis

**"Permission denied"**
- Run as Administrator if needed
- Check file permissions in your folder

### Getting Help
1. Check the `logs/` folder for detailed error messages
2. Run `python doc_updater.py --summary-only` to see last status
3. Verify your `config.json` format is valid JSON
4. Test API keys with simple calls first

## 📈 Advanced Features

### Version Control Integration
The system automatically:
- Creates timestamped backups in `versions/` folder
- Generates change reports in `changes/` folder
- Logs all operations in `logs/` folder
- Preserves original files unless you specify otherwise

### Customization
- Modify `doc_updater.py` to add new document types
- Adjust checking frequency in `config.json`
- Add custom validation rules for your specific needs
- Integrate with your existing workflow tools

## 🎯 Best Practices

### Daily Workflow
1. **Morning**: Run quick check to see if updates are available
2. **Review**: Check generated summaries for important changes
3. **Update**: Apply updates to original files if needed
4. **Backup**: System automatically maintains version history

### Maintenance
- Review logs weekly to ensure system is working
- Update API keys if they expire
- Check for new document types to add to monitoring
- Keep the Python environment updated

---

## 🚀 Ready to Start?

1. **First Time**: Run `setup.bat`
2. **Add Your Keys**: Edit the `config.json` file that opens
3. **Test It**: Run `run_updater.bat` and choose option 1
4. **Go Daily**: Set up automation or run manually each day

Your AI documentation will now stay current automatically! 🎉
