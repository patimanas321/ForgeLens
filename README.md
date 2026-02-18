# ForgeLens 🔮

An intelligent AI Agent that autonomously browses the web, discovers trends, generates images, evaluates them, and posts the best content to Instagram - all while mimicking human behavior.

**Built with Microsoft Agent Framework (.NET)**

---

## 🎯 Overview

ForgeLens is a multi-agent AI system designed to automate social media content creation and posting. It operates entirely on your local machine, leveraging Azure OpenAI models for intelligence and Playwright for human-like browser automation.

### Key Capabilities

- **Trend Discovery**: Autonomously browses the web to find latest trending topics
- **Topic Selection**: Intelligently picks engaging topics based on virality potential
- **Image Generation**: Creates multiple image variations using Azure OpenAI DALL-E
- **Quality Evaluation**: Assesses generated images for aesthetic appeal and engagement potential
- **Human-like Posting**: Posts to Instagram mimicking natural human behavior patterns

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FORGELENS ORCHESTRATOR                              │
│                         (Microsoft Agent Framework Workflow)                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               AGENT WORKFLOW PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │    TREND     │    │    IMAGE     │    │    IMAGE     │    │  INSTAGRAM   │  │
│  │   ANALYZER   │───▶│  GENERATOR   │───▶│  EVALUATOR   │───▶│   POSTER     │  │
│  │    AGENT     │    │    AGENT     │    │    AGENT     │    │    AGENT     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │                   │          │
│         ▼                   ▼                   ▼                   ▼          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Browser    │    │  DALL-E 3    │    │   GPT-4o     │    │   Browser    │  │
│  │  Automation  │    │    API       │    │   Vision     │    │  Automation  │  │
│  │    (MCP)     │    │              │    │              │    │    (MCP)     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INFRASTRUCTURE LAYER                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────────┐ │
│  │    Azure OpenAI       │  │   Playwright MCP      │  │   Human Behavior    │ │
│  │    (GPT-4o + DALL-E)  │  │   Browser Control     │  │   Simulator         │ │
│  └───────────────────────┘  └───────────────────────┘  └─────────────────────┘ │
│                                                                                  │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────────┐ │
│  │   Local File System   │  │   Configuration       │  │   Logging &         │ │
│  │   (Image Storage)     │  │   Management          │  │   Telemetry         │ │
│  └───────────────────────┘  └───────────────────────┘  └─────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Workflow Sequence

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXECUTION FLOW                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

     START
       │
       ▼
┌──────────────────┐
│  1. Initialize   │    • Load configuration
│     System       │    • Connect to Azure OpenAI
│                  │    • Initialize Playwright MCP
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  2. Trend        │    • Open browser (human-like)
│     Discovery    │    • Navigate to trend sources
│                  │    • Scrape trending topics
│                  │    • Random delays & scrolling
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  3. Topic        │    • Analyze trend potential
│     Selection    │    • Consider engagement metrics
│                  │    • Select optimal topic
│                  │    • Generate content brief
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  4. Image        │    • Create multiple prompts
│     Generation   │    • Generate 3-5 variations
│                  │    • Download images locally
│                  │    • Apply quality filters
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  5. Image        │    • Analyze with GPT-4o Vision
│     Evaluation   │    • Score aesthetics (1-10)
│                  │    • Score engagement potential
│                  │    • Select best image
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  6. Caption      │    • Generate engaging caption
│     Creation     │    • Add relevant hashtags
│                  │    • Match brand voice
│                  │    • Localize if needed
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  7. Instagram    │    • Open browser (human-like)
│     Posting      │    • Login with natural typing
│                  │    • Navigate to post creation
│                  │    • Upload image
│                  │    • Add caption & hashtags
│                  │    • Random engagement actions
└────────┬─────────┘
         │
         ▼
       END
```

---

## 🧩 Component Details

### 1. Trend Analyzer Agent

**Purpose**: Discovers and analyzes current trending topics across multiple platforms.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TREND ANALYZER AGENT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Data Sources:                                                  │
│  ├── Twitter/X Trending                                         │
│  ├── Google Trends                                              │
│  ├── Reddit Popular                                             │
│  ├── TikTok Discover                                            │
│  └── Instagram Explore                                          │
│                                                                 │
│  Browser Actions (via Playwright MCP):                          │
│  ├── Navigate to URL                                            │
│  ├── Wait for elements                                          │
│  ├── Extract text content                                       │
│  ├── Take screenshots                                           │
│  └── Human-like scrolling                                       │
│                                                                 │
│  Output:                                                        │
│  └── TrendAnalysisResult                                        │
│      ├── TopicName: string                                      │
│      ├── Category: string                                       │
│      ├── EngagementScore: int                                   │
│      ├── ViralityPotential: float                               │
│      └── RelatedKeywords: string[]                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Image Generator Agent

**Purpose**: Creates multiple image variations based on the selected topic using DALL-E 3.

```
┌─────────────────────────────────────────────────────────────────┐
│                   IMAGE GENERATOR AGENT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Prompt Engineering:                                            │
│  ├── Analyze topic context                                      │
│  ├── Generate creative prompts                                  │
│  ├── Apply style variations                                     │
│  └── Include Instagram-optimized parameters                     │
│                                                                 │
│  Azure OpenAI DALL-E 3:                                         │
│  ├── Model: dall-e-3                                            │
│  ├── Size: 1024x1024 (square for Instagram)                     │
│  ├── Quality: hd                                                │
│  └── Style: vivid/natural                                       │
│                                                                 │
│  Output:                                                        │
│  └── ImageGenerationResult                                      │
│      ├── Images: GeneratedImage[]                               │
│      │   ├── FilePath: string                                   │
│      │   ├── Prompt: string                                     │
│      │   └── Metadata: ImageMetadata                            │
│      └── GenerationTime: TimeSpan                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Image Evaluator Agent

**Purpose**: Analyzes generated images using GPT-4o Vision to select the best one.

```
┌─────────────────────────────────────────────────────────────────┐
│                   IMAGE EVALUATOR AGENT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Evaluation Criteria:                                           │
│  ├── Aesthetic Quality (composition, color, clarity)            │
│  ├── Engagement Potential (scroll-stopping power)               │
│  ├── Brand Alignment (style consistency)                        │
│  ├── Technical Quality (resolution, artifacts)                  │
│  └── Platform Fit (Instagram optimization)                      │
│                                                                 │
│  Azure OpenAI GPT-4o Vision:                                    │
│  ├── Analyze each image                                         │
│  ├── Compare against criteria                                   │
│  ├── Score each dimension                                       │
│  └── Select winner                                              │
│                                                                 │
│  Output:                                                        │
│  └── ImageEvaluationResult                                      │
│      ├── SelectedImage: GeneratedImage                          │
│      ├── Scores: EvaluationScore[]                              │
│      ├── Reasoning: string                                      │
│      └── SuggestedCaption: string                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4. Instagram Poster Agent

**Purpose**: Posts content to Instagram with human-like behavior patterns.

```
┌─────────────────────────────────────────────────────────────────┐
│                   INSTAGRAM POSTER AGENT                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Human Behavior Simulation:                                     │
│  ├── Variable typing speed (40-80 WPM)                          │
│  ├── Random delays between actions (2-8 seconds)                │
│  ├── Mouse movement with Bézier curves                          │
│  ├── Occasional typos and corrections                           │
│  ├── Random scroll patterns                                     │
│  └── Engagement actions (like, view stories)                    │
│                                                                 │
│  Posting Workflow:                                              │
│  ├── 1. Navigate to Instagram                                   │
│  ├── 2. Login (if needed) with natural typing                   │
│  ├── 3. Click create post                                       │
│  ├── 4. Select and upload image                                 │
│  ├── 5. Apply filters (optional)                                │
│  ├── 6. Write caption with pauses                               │
│  ├── 7. Add hashtags naturally                                  │
│  ├── 8. Review and post                                         │
│  └── 9. Brief engagement session                                │
│                                                                 │
│  Anti-Detection Measures:                                       │
│  ├── Randomized user agent                                      │
│  ├── Natural viewport sizes                                     │
│  ├── Realistic session duration                                 │
│  └── Cookie persistence                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Component              | Technology                | Purpose                                  |
| ---------------------- | ------------------------- | ---------------------------------------- |
| **Runtime**            | .NET 8                    | Core application framework               |
| **Agent Framework**    | Microsoft Agent Framework | Multi-agent orchestration                |
| **LLM Provider**       | Azure OpenAI              | GPT-4o for analysis, DALL-E 3 for images |
| **Browser Automation** | Playwright MCP            | Human-like web interactions              |
| **Authentication**     | Azure Identity            | Secure credential management             |
| **Configuration**      | .NET Configuration        | Environment-based settings               |
| **Logging**            | Serilog                   | Structured logging and telemetry         |

---

## 📁 Project Structure

```
ForgeLens/
├── src/
│   ├── ForgeLens.Core/                    # Core domain models and interfaces
│   │   ├── Models/
│   │   │   ├── TrendAnalysisResult.cs
│   │   │   ├── GeneratedImage.cs
│   │   │   ├── ImageEvaluationResult.cs
│   │   │   └── PostingResult.cs
│   │   ├── Interfaces/
│   │   │   ├── ITrendAnalyzer.cs
│   │   │   ├── IImageGenerator.cs
│   │   │   ├── IImageEvaluator.cs
│   │   │   └── IInstagramPoster.cs
│   │   └── ForgeLens.Core.csproj
│   │
│   ├── ForgeLens.Agents/                  # Agent implementations
│   │   ├── Executors/
│   │   │   ├── TrendAnalyzerExecutor.cs
│   │   │   ├── ImageGeneratorExecutor.cs
│   │   │   ├── ImageEvaluatorExecutor.cs
│   │   │   └── InstagramPosterExecutor.cs
│   │   ├── Tools/
│   │   │   ├── BrowserTool.cs
│   │   │   ├── ImageGenerationTool.cs
│   │   │   └── HumanBehaviorSimulator.cs
│   │   └── ForgeLens.Agents.csproj
│   │
│   ├── ForgeLens.Infrastructure/          # External service integrations
│   │   ├── AzureOpenAI/
│   │   │   ├── AzureOpenAIService.cs
│   │   │   └── DalleImageService.cs
│   │   ├── Browser/
│   │   │   ├── PlaywrightMcpClient.cs
│   │   │   └── BrowserSessionManager.cs
│   │   └── ForgeLens.Infrastructure.csproj
│   │
│   └── ForgeLens.App/                     # Main application
│       ├── Program.cs
│       ├── WorkflowOrchestrator.cs
│       ├── appsettings.json
│       └── ForgeLens.App.csproj
│
├── tests/
│   ├── ForgeLens.Tests.Unit/
│   └── ForgeLens.Tests.Integration/
│
├── artifacts/                             # Generated images storage
│   └── images/
│
├── .env.example                           # Environment template
├── ForgeLens.sln                          # Solution file
└── README.md
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_GPT4O=gpt-4o
AZURE_OPENAI_DEPLOYMENT_DALLE=dall-e-3

# Or use Azure AI Foundry Project (Recommended)
FOUNDRY_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/
FOUNDRY_MODEL_DEPLOYMENT_NAME=gpt-4o

# Instagram Credentials (stored securely)
INSTAGRAM_USERNAME=your-username
INSTAGRAM_PASSWORD=your-password

# Application Settings
IMAGE_OUTPUT_PATH=./artifacts/images
MAX_IMAGES_PER_RUN=5
POSTING_DELAY_MINUTES=30
HUMAN_BEHAVIOR_RANDOMNESS=0.3
```

### appsettings.json

```json
{
  "AzureOpenAI": {
    "Endpoint": "",
    "DeploymentGPT4o": "gpt-4o",
    "DeploymentDallE": "dall-e-3"
  },
  "TrendSources": [
    "https://twitter.com/explore/tabs/trending",
    "https://trends.google.com/trending",
    "https://www.reddit.com/r/popular/"
  ],
  "ImageGeneration": {
    "Variations": 4,
    "Size": "1024x1024",
    "Quality": "hd",
    "Style": "vivid"
  },
  "HumanBehavior": {
    "MinTypingDelayMs": 50,
    "MaxTypingDelayMs": 150,
    "MinActionDelayMs": 2000,
    "MaxActionDelayMs": 8000,
    "TypoChance": 0.02,
    "ScrollVariation": 0.3
  },
  "Posting": {
    "EnableFilters": false,
    "DefaultHashtags": ["#ai", "#aiart", "#trending"],
    "MaxHashtags": 30
  }
}
```

---

## 🚀 Getting Started

### Prerequisites

- .NET 8 SDK
- Node.js (for Playwright MCP)
- Azure subscription with OpenAI service enabled
- Instagram account

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/ForgeLens.git
   cd ForgeLens
   ```

2. **Install .NET dependencies**

   ```bash
   dotnet restore
   ```

3. **Install Playwright MCP**

   ```bash
   npm install -g @playwright/mcp@latest
   npx playwright install chromium
   ```

4. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Build the solution**

   ```bash
   dotnet build
   ```

6. **Run ForgeLens**
   ```bash
   dotnet run --project src/ForgeLens.App
   ```

---

## 🔒 Security Considerations

- **Credentials**: Never commit `.env` files. Use Azure Key Vault for production.
- **Rate Limiting**: Built-in delays prevent API throttling and detection.
- **Session Management**: Browser sessions are isolated and cookies are managed securely.
- **Audit Logging**: All actions are logged for compliance and debugging.

---

## 📊 Monitoring & Debugging

### Logging Output

```
[2024-02-18 10:30:00] INFO  Workflow started
[2024-02-18 10:30:05] INFO  TrendAnalyzer: Opening browser...
[2024-02-18 10:30:15] INFO  TrendAnalyzer: Found 12 trending topics
[2024-02-18 10:30:20] INFO  TrendAnalyzer: Selected topic "AI Art Revolution"
[2024-02-18 10:30:25] INFO  ImageGenerator: Generating 4 variations...
[2024-02-18 10:31:45] INFO  ImageGenerator: Generated 4 images
[2024-02-18 10:31:50] INFO  ImageEvaluator: Analyzing images with GPT-4o Vision...
[2024-02-18 10:32:10] INFO  ImageEvaluator: Selected image_003.png (Score: 9.2/10)
[2024-02-18 10:32:15] INFO  InstagramPoster: Starting human-like posting sequence...
[2024-02-18 10:35:00] INFO  InstagramPoster: Post published successfully!
[2024-02-18 10:35:05] INFO  Workflow completed
```

### Debug Mode

Enable verbose logging in `appsettings.json`:

```json
{
  "Serilog": {
    "MinimumLevel": "Debug"
  }
}
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

This tool is for educational and personal use. Automated posting to social media platforms may violate their Terms of Service. Use responsibly and at your own risk. The authors are not responsible for any account restrictions or bans resulting from the use of this software.

---

## 🙏 Acknowledgments

- Microsoft Agent Framework Team
- Azure OpenAI Service
- Playwright MCP Contributors
