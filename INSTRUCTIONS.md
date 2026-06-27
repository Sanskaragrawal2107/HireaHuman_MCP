# HireAHuman.ai — MCP Server

Production-grade MCP server that exposes HireAHuman.ai candidate data to AI agents for AI-native hiring workflows.

## Architecture

- **Framework:** FastMCP (Python)
- **Transport:** stdio (default) or HTTP
- **API Backend:** InsForge PostgREST (via httpx REST calls)
- **No Supabase SDK** — zero heavy dependencies, pure REST

## Tools Available

| # | Tool | Description |
|---|------|-------------|
| 1 | `search_candidates` | Multi-filter search by skills, location, experience, availability, BlueTech |
| 2 | `get_candidate_profile` | Full structured profile by handle |
| 3 | `list_available_candidates` | Paginated browse of available engineers |
| 4 | `get_platform_stats` | Platform-wide stats (total, skill distribution, experience breakdown) |
| 5 | `search_by_skills` | Advanced skill matching with required/preferred scoring |
| 6 | `get_candidate_resume` | Auto-generated structured resume data |
| 7 | `check_candidate_availability` | Quick availability + contact check before outreach |

## Setup

### 1. Install Dependencies

```bash
cd mcp_server
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file (already provided):

```env
INSFORGE_URL=https://r6xn2b5d.us-west.insforge.app
INSFORGE_ANON_KEY=your_anon_key_here
```

### 3. Run

**stdio mode** (for Claude Desktop, Cursor, etc):
```bash
python server.py
```

**HTTP mode** (for remote access / testing):
```bash
python server.py --transport http --port 8000
```

## Claude Desktop / Cursor Config

Add to your `mcp_config.json` or Claude Desktop config:

```json
{
  "mcpServers": {
    "hireahuman": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "C:/Users/sanskar agrawal/Desktop/HireaHuman/mcp_server",
      "env": {
        "INSFORGE_URL": "https://r6xn2b5d.us-west.insforge.app",
        "INSFORGE_ANON_KEY": "your_anon_key_here"
      }
    }
  }
}
```

## Example Usage (AI Agent)

```
User: Find me React developers with 3+ years experience who are available and preferably know AWS
Agent: [calls search_candidates(skills="React", min_experience=3, available_only=True)]
Agent: [calls search_by_skills(required_skills="React", preferred_skills="AWS", min_match_count=1)]
Agent: Found 5 candidates. Let me get the details of the top match...
Agent: [calls get_candidate_profile(handle="johndoe")]
Agent: [calls get_candidate_resume(handle="johndoe")]
```

## File Structure

```
mcp_server/
├── server.py          # Main MCP server (all 7 tools)
├── requirements.txt   # Python dependencies
├── .env               # Environment variables
├── Dockerfile         # Container deployment (optional)
└── INSTRUCTIONS.md    # This file
```
