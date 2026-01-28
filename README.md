# Enhanced Issue Tracker System

A comprehensive web-based issue tracking and matching system with AI-powered quality analysis, multi-source enterprise integration, and accessibility-compliant design.

## 🚀 Features

### Core Functionality
- **Quick ICA Analysis**: Intelligent Context Analysis with AI-powered classification
- **AI-Powered Quality Analysis**: Intelligent input validation and completeness scoring
- **Enhanced Matching Engine**: Multi-source searching across Azure DevOps organizations
- **Real-Time Progress Tracking**: Live updates during processing operations
- **Accessibility Compliance**: WCAG-compliant UI with proper contrast ratios

### Advanced Capabilities
- **AI-Powered Search Optimization**: Azure OpenAI generates intelligent search queries for better results
- **Multi-Source Retirement Checking**: Comprehensive retirement information from multiple authoritative sources
- **Smart Service Extraction**: Automatic service name detection using pattern matching
- **Enterprise Integration**: Azure DevOps API integration for multiple organizations
- **Character Limit Validation**: 125-character limits with real-time feedback
- **Responsive Design**: Mobile-friendly interface with Bootstrap framework
- **Collapsible UI Sections**: Prevent button displacement with scrollable retirement information

## 📁 Project Structure

```
c:\Projects\Hack\
├── app.py                          # Main Flask application with routing
├── enhanced_matching.py            # AI analysis and matching engine
├── ado_integration.py             # Azure DevOps API client
├── issues_actions.json            # Local issues database
├── static/
│   └── style.css                  # Custom CSS with accessibility features
├── templates/                     # Jinja2 HTML templates
│   ├── base.html                  # Base template with navigation
│   ├── quick_ica_form.html        # Quick ICA analysis form
│   ├── context_evaluation.html    # Context analysis results
│   ├── context_summary.html       # Analysis summary page
│   ├── input_quality_review.html  # Quality analysis and improvement
│   ├── processing.html            # Real-time progress display
│   ├── enhanced_review.html       # Pre-matching review
│   ├── enhanced_results.html      # Search results display
│   ├── actions.html               # Recommended actions
│   ├── no_match.html              # No matches found
│   ├── uat_created.html           # UAT creation confirmation
│   ├── admin.html                 # Administrative interface
│   └── additional_info.html       # Additional information collection
└── documentation/
    ├── PROJECT_STATUS.md           # Current project status
    ├── QUICKSTART.md              # Quick start guide
    ├── RESTART_GUIDE.md           # System restart procedures
    └── AZURE_OPENAI_AUTH_SETUP.md # Azure OpenAI authentication configuration
```

## 🛠 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Flask web framework
- Azure DevOps API access (for enterprise features)
- Modern web browser with JavaScript enabled

### Quick Start
1. **Clone/Download the project**
   ```bash
   cd c:\Projects\Hack
   ```

2. **Install Dependencies**
   ```bash
   pip install flask requests python-dotenv
   ```

3. **Configure Azure DevOps (Optional)**
   - Update PAT tokens in `enhanced_matching.py`
   - Configure organization URLs for your environment

4. **Run the Application**
   ```bash
   python app.py
   ```

5. **Access the System**
   - Open http://127.0.0.1:5001 in your browser
   - Use the Quick ICA Analysis form to submit issues

## 🎯 Usage Workflow

### Issue Submission Process
1. **Quick ICA Form**: Enter title, description, and impact in a single form
2. **AI-Powered Analysis**: Automatic context classification and quality scoring
3. **Resource Search**: Optional search for Azure resources and retirement information
4. **Context Evaluation**: Review AI analysis with detailed reasoning
5. **ADO Integration**: Create work items or link to existing issues

### Quality Analysis Pipeline
1. **AI Analysis**: Automatic quality scoring based on completeness
2. **First Attempt**: If score < 80%, forced improvement required
3. **Second Attempt**: User choice to improve further or proceed with warning
4. **Enhanced Matching**: Multi-source search across data repositories

### Search & Matching
1. **Local Database**: Search existing evaluating retirements and solutions
2. **UAT Integration**: Query Azure DevOps UAT organization
3. **Technical Feedback**: Search technical feedback organization
4. **Result Aggregation**: Combine and rank all matches by relevance

### UAT Work Item Creation
When no matches are found, the system automatically creates a work item in Azure DevOps with:
- **Assigned To**: ACR Accelerate Blockers Help
- **Customer Scenario**: Set to the impact statement from submission
- **Corp Assignment**: Automatically set to active status
- **Opportunity ID**: Links to the submitted opportunity number
- **Milestone ID**: Links to the submitted milestone ID
- **Status Update**: Automatically tracked for monitoring

## 🔧 Configuration

### Application Settings
- **Session Management**: Automatic session cleanup and temporary data storage
- **Character Limits**: Configurable limits with real-time validation
- **Quality Thresholds**: Adjustable scoring parameters
- **Search Parameters**: Similarity thresholds and result limits

### Azure DevOps Integration
```python
# In enhanced_matching.py
UAT_ORGANIZATION = "your-uat-org"
TFT_ORGANIZATION = "your-tft-org"
PAT = "your-personal-access-token"
```

### Quality Analysis Parameters
```python
MIN_DESCRIPTION_WORDS = 5    # Minimum words in description
MIN_IMPACT_WORDS = 3         # Minimum words in impact
SIMILARITY_THRESHOLD = 0.3   # Minimum similarity for matches
```

## 🎨 Accessibility Features

### WCAG Compliance
- **Color Contrast**: Minimum 4.5:1 ratio for all text
- **Focus Indicators**: Clear focus outlines for keyboard navigation
- **Screen Reader Support**: Proper ARIA labels and semantic HTML
- **Responsive Design**: Mobile-friendly with touch-friendly controls

### Custom Accessibility Classes
```css
.text-warning-accessible   /* High contrast warning text */
.quality-progress          /* Enhanced progress bars */
.btn:focus                 /* Keyboard focus indicators */
```

## 📊 API Endpoints

### Public Routes
- `GET /` - Application entry point with Quick ICA form
- `POST /quick_ica` - Process ICA analysis submission
- `POST /perform_search` - Execute resource and retirement search
- `GET /context_summary/<session_id>` - View analysis summary
- `GET /context_evaluation/<session_id>` - Detailed evaluation page

### Processing Routes
- `GET /start_processing` - Initialize enhanced matching
- `GET /processing_status/<task_id>` - Real-time progress updates
- `GET /enhanced_review` - Pre-matching review
- `POST /confirm_enhancement` - Confirm and start matching

### Result Routes
- `GET /enhanced_results` - Display search results
- `GET /actions/<int:issue_id>` - Show recommended actions
- `GET /no_match` - No matches found page
- `POST /create_uat` - Create new UAT work item

### Administrative Routes
- `GET /admin` - Administrative dashboard
- `GET /api/search` - API testing interface

## 🔍 Troubleshooting

### Common Issues
1. **Session Errors**: Clear browser cache and restart session
2. **Azure DevOps 401**: Verify PAT token validity and permissions
3. **Quality Analysis Failures**: Check AI analyzer configuration
4. **Similarity Matching**: Adjust threshold parameters if needed

### Debug Mode
Run with debug enabled for detailed error information:
```bash
python app.py --debug
```

### Log Analysis
Check console output for:
- Azure DevOps API response codes
- Quality analysis scores
- Similarity matching results
- Session management status

## 🚧 Development Notes

### Code Architecture
- **Modular Design**: Separated concerns across multiple files
- **Session Management**: Temporary in-memory storage for analysis results
- **Error Handling**: Comprehensive try-catch blocks with user feedback
- **Type Hints**: Full type annotations for better code maintainability

### Recent Enhancements (v3.0 - January 2026)
- **AI-Powered Search Query Generation**: LLM generates intelligent 3-5 word search queries instead of blind concatenation
- **Multi-Source Retirement Checking**: Searches retirements.json + Microsoft Learn + Azure Updates for comprehensive coverage
- **Smart Service Extraction**: Regex pattern matching to extract service names from issue text when domain entities are empty
- **Retirement UI Improvements**: Collapsible sections with badges, scrollable containers (400px max-height) to prevent button displacement
- **Enhanced Filtering**: Word boundary regex matching for precise service name matching
- **Centered UI Elements**: Fixed Cancel button text alignment with flexbox classes
- **Microsoft Learn Integration**: Direct search links for retirement information when local database lacks data
- **Debug Logging**: Comprehensive retirement check tracing for troubleshooting

### Previous Enhancements (v2.0)
- Multi-attempt quality review system
- Enhanced accessibility compliance
- Character limit increase (100→125)
- Real-time progress tracking
- Multi-source Azure DevOps integration
- Improved error handling and user feedback

### Future Roadmap
- Database backend (SQLite/PostgreSQL)
- User authentication system
- Advanced ML-based matching
- Email notifications
- Mobile application
- API versioning and documentation

## 📝 License

This project is developed for internal use. Please ensure compliance with organizational policies regarding Azure DevOps API usage and data handling.

## 🤝 Contributing

For bug reports, feature requests, or contributions:
1. Document the issue or enhancement clearly
2. Provide steps to reproduce problems
3. Include screenshots for UI-related issues
4. Test changes thoroughly before submission

## 📞 Support

For technical support or questions:
- Check the troubleshooting section above
- Review console logs for error details
- Verify Azure DevOps connectivity and permissions
- Ensure all dependencies are properly installed

---

**Last Updated**: January 4, 2026  
**Version**: 3.0 (AI-Powered Resource Search & Multi-Source Retirement Checking)  
**Compatibility**: Python 3.8+, Modern Web Browsers, Azure OpenAI Service
