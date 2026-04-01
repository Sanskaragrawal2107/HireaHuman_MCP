# HireAHuman MCP Server

> **AI-native hiring, powered by the Model Context Protocol.**

An MCP (Model Context Protocol) server that connects AI agents — such as Claude and Cursor — directly to the [HireAHuman.ai](https://hireahuman.ai) talent platform. Let your AI assistant search candidates, view profiles, generate resumes, and check availability, all without leaving your chat interface.

---

## ✨ Features

- 🔍 **Multi-criteria candidate search** — filter by skills, location, experience, availability, and BlueTech verification
- 👤 **Full candidate profiles** — bio, experience history, skills, and social links
- 📄 **Auto-generated resumes** — structured resume data built on-the-fly from profile data
- 📊 **Platform analytics** — aggregate stats on talent pool, top skills, and experience distribution
- ⚡ **Skill-match scoring** — rank candidates by required and preferred skill overlap
- ✅ **Quick availability checks** — confirm status and get contact info before outreach
- 🏅 **BlueTech badge support** — prioritize verified premium candidates

---

## 🛠️ MCP Tools

| # | Tool | Description |
|---|------|-------------|
| 1 | `search_candidates` | Search by skills, location, experience range, availability, and BlueTech badge |
| 2 | `get_candidate_profile` | Retrieve a full structured profile by handle; records the view |
| 3 | `list_available_candidates` | Paginated list of available engineers (sort by experience, recency, or rating) |
| 4 | `get_platform_stats` | Platform-wide stats: totals, top skills, location distribution, experience buckets |
| 5 | `search_by_skills` | Score and rank candidates by required vs. preferred skill overlap |
| 6 | `get_candidate_resume` | Auto-generate a structured resume from a candidate's profile |
| 7 | `check_candidate_availability` | Quick pre-outreach check: availability status, location, and contact info |

---

## 🏗️ Architecture

```
AI Agent (Claude / Cursor)
        │
        │  MCP Protocol (stdio or HTTP)
        ▼
  HireAHuman MCP Server  (FastMCP · Python 3.12)
        │
        │  REST (httpx · async)
        ▼
  InsForge PostgREST API  (candidate & profile-view tables)
```

- **Framework:** [FastMCP](https://github.com/jlowin/fastmcp) ≥ 2.0.0
- **HTTP client:** httpx (async, 15 s timeout)
- **Transport:** `stdio` (default) or `http`
- **No heavy SDK** — pure REST calls, minimal dependencies

---

## 📦 Requirements

- Python **3.10+** (3.12 recommended)
- pip

```
fastmcp>=2.0.0
httpx>=0.27.0
python-dotenv>=1.0.0
```

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Sanskaragrawal2107/HireaHuman_MCP.git
cd HireaHuman_MCP
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
INSFORGE_URL=https://r6xn2b5d.us-west.insforge.app
INSFORGE_ANON_KEY=your_anon_key_here
```

### 4. Run the server

**stdio mode** *(for Claude Desktop, Cursor, and most local AI agents)*

```bash
python server.py
```

**HTTP mode** *(for remote access or manual testing)*

```bash
python server.py --transport http --port 8000
```

**Custom host / port**

```bash
python server.py --transport http --host 0.0.0.0 --port 8080
```

---

## 🐳 Docker

```bash
# Build
docker build -t hireahuman-mcp .

# Run
docker run -p 8000:8000 \
  -e INSFORGE_URL=https://r6xn2b5d.us-west.insforge.app \
  -e INSFORGE_ANON_KEY=your_anon_key_here \
  hireahuman-mcp
```

The container exposes port **8000** and includes a built-in health check.

---

## 🔌 Connecting to Claude Desktop

Add the following to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hireahuman": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/absolute/path/to/HireaHuman_MCP",
      "env": {
        "INSFORGE_URL": "https://r6xn2b5d.us-west.insforge.app",
        "INSFORGE_ANON_KEY": "your_anon_key_here"
      }
    }
  }
}
```

> **Windows path example:**
> `"cwd": "C:/Users/YourName/Desktop/HireaHuman_MCP"`

After saving, restart Claude Desktop — the HireAHuman tools will appear automatically.

---

## 💡 Example Agent Workflows

### Find React developers in San Francisco

```
User: Find me React developers in San Francisco with 3+ years of experience.

Agent → search_candidates(
  skills="React",
  location="San Francisco",
  min_experience=3,
  available_only=True,
  limit=10
)
→ Returns up to 10 candidates, BlueTech-verified first.
```

### Score candidates by skill match

```
User: Which available engineers know both Node.js and PostgreSQL? AWS is a bonus.

Agent → search_by_skills(
  required_skills="Node.js,PostgreSQL",
  preferred_skills="AWS",
  min_match_count=2
)
→ Returns ranked list with match scores.
```

### Generate a resume and check availability

```
Agent → get_candidate_profile(handle="alice_dev")
     → get_candidate_resume(handle="alice_dev")
     → check_candidate_availability(handle="alice_dev")
→ Full profile, formatted resume, and live availability status.
```

### Get platform overview

```
User: Give me a snapshot of your talent pool.

Agent → get_platform_stats()
→ Total profiles, available vs. hired counts, top 10 skills,
  location distribution, experience breakdown.
```

---

## 📁 Project Structure

```
HireaHuman_MCP/
├── server.py          # MCP server — all 7 tools
├── requirements.txt   # Python dependencies
├── Dockerfile         # Container deployment
├── start_mcp.bat      # Windows helper script (SSE transport, port 8000)
├── INSTRUCTIONS.md    # Original setup notes
├── .env               # Environment variables (git-ignored)
└── .gitignore
```

---

## 🔐 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `INSFORGE_URL` | ✅ | Base URL for the InsForge PostgREST API |
| `INSFORGE_ANON_KEY` | ✅ | Anonymous API key for database access |

> ⚠️ Never commit your `.env` file. It is already listed in `.gitignore`.

---

## 🤝 Contributing

Contributions, bug reports, and feature requests are welcome! Please open an issue or pull request on [GitHub](https://github.com/Sanskaragrawal2107/HireaHuman_MCP).

---

## 📄 License

This project is provided as-is. See the repository for license details.
