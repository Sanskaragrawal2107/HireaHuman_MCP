"""
HireAHuman.ai — Production-Grade MCP Server
=============================================
Exposes structured candidate data to AI agents for AI-native hiring workflows.

Tools:
  1. search_candidates       — Multi-filter search (skills, location, experience, availability)
  2. get_candidate_profile    — Full structured profile by handle
  3. list_available_candidates — Browse all available engineers
  4. get_platform_stats       — Total profiles, available, hired counts
  5. search_by_skills         — Find candidates matching specific skill requirements
  6. get_candidate_resume     — Auto-generated structured resume data
  7. check_candidate_availability — Quick availability + contact check

Transport: stdio (default) or http (--transport http)
"""

import logging
import sys
import os
from typing import Optional

from fastmcp import FastMCP
import httpx
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# LOGGING — stderr only (critical for MCP servers)
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("HireAHuman-MCP")

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
load_dotenv()

INSFORGE_URL = os.environ.get("INSFORGE_URL", "").rstrip("/")
INSFORGE_ANON_KEY = os.environ.get("INSFORGE_ANON_KEY", "")

if not INSFORGE_URL or not INSFORGE_ANON_KEY:
    logger.error("Missing INSFORGE_URL or INSFORGE_ANON_KEY environment variables")
    raise ValueError("Missing INSFORGE_URL or INSFORGE_ANON_KEY environment variables. Check your .env file.")

API_TIMEOUT = 15  # seconds
API_BASE = f"{INSFORGE_URL}/api/database/records"
HEADERS = {
    "Authorization": f"Bearer {INSFORGE_ANON_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ──────────────────────────────────────────────
# MCP SERVER
# ──────────────────────────────────────────────
mcp = FastMCP(
    name="HireAHuman",
    on_duplicate_resources="error",
)


# ──────────────────────────────────────────────
# HELPER: Query InsForge REST API
# ──────────────────────────────────────────────
async def _query_profiles(params: dict | None = None) -> list[dict]:
    """Query the profiles table via InsForge PostgREST API."""
    url = f"{API_BASE}/profiles"
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(url, headers=HEADERS, params=params or {})
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.error("Timeout querying profiles")
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP {e.response.status_code} querying profiles: {e.response.text[:200]}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error querying profiles: {e}")
        raise


async def _record_profile_view(profile_id: str, source: str = "mcp_agent") -> None:
    """Record a profile view in the profile_views table."""
    url = f"{API_BASE}/profile_views"
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                url,
                headers=HEADERS,
                json={"profile_id": profile_id, "source": source},
            )
            response.raise_for_status()
            logger.info(f"Recorded profile view for {profile_id} (source={source})")
    except Exception as e:
        # Don't fail the main request if view tracking fails
        logger.warning(f"Failed to record profile view for {profile_id}: {e}")


def _format_candidate(p: dict, brief: bool = False, for_hiring: bool = False) -> dict:
    """Format a profile record into a clean candidate object for AI consumption."""
    employment_status = p.get("employment_status", "AVAILABLE")
    
    base = {
        "handle": p.get("handle"),
        "name": p.get("display_name"),
        "role": p.get("role_title"),
        "location": p.get("location"),
        "preferred_location": p.get("preferred_location"),
        "years_of_experience": p.get("years_of_experience", 0),
        "skills": p.get("skills", []),
        "employment_status": employment_status,
        "bluetech_badge": p.get("bluetech_badge", False),
        "job_target": p.get("job_target", "full_time"),
        # For hiring workflow components
        "availability": employment_status,  # Alias for frontend component
        "experience": p.get("years_of_experience", 0),  # Alias for frontend
        "is_bluetech": p.get("bluetech_badge", False),  # Alias for frontend
        "hired_by_other": employment_status == "HIRED",  # Flag for UI
    }

    if not brief or for_hiring:
        base.update({
            "bio": p.get("bio"),
            "github_url": p.get("github_url"),
            "linkedin_url": p.get("linkedin_url"),
            "avatar_url": p.get("avatar_url"),
            "experience_history": p.get("experience_history", []),
            "projects": p.get("projects", []),
            "rating": float(p.get("rating", 5.0)),
            "total_sessions": p.get("total_sessions", 0),
            "created_at": p.get("created_at"),
            # For email drafting - use linkedin as contact if no direct email
            "email": p.get("contact_email") or f"{p.get('handle')}@hireahuman.ai",
        })

    return base


# ══════════════════════════════════════════════
# TOOL 1: search_candidates
# ══════════════════════════════════════════════
@mcp.tool()
async def search_candidates(
    skills: Optional[str] = None,
    location: Optional[str] = None,
    min_experience: Optional[int] = None,
    max_experience: Optional[int] = None,
    available_only: bool = False,
    bluetech_only: bool = False,
    job_target: Optional[str] = None,
    limit: int = 10,
    include_hired: bool = True,
) -> str:
    """
    Search for engineering candidates with multiple filters.
    This is the primary discovery tool for AI-assisted hiring.
    
    Returns candidates separated into two groups:
    - Available candidates (not hired yet)
    - Already hired candidates (hired by other companies)
    
    Results are ordered with BlueTech verified badge holders first (up to 3), 
    then regular candidates (up to 7), for a total of 10 max per request.

    Args:
        skills: Comma-separated skill keywords to match (e.g. "Python,React,AWS"). Case-insensitive partial match.
        location: Location keyword to match against current OR preferred location (e.g. "Remote", "San Francisco").
        min_experience: Minimum years of experience (inclusive).
        max_experience: Maximum years of experience (inclusive).
        available_only: If True, only return candidates with AVAILABLE status. Default False (show both).
        bluetech_only: If True, only return BlueTech badge holders (premium candidates). Default False.
        job_target: Filter by what candidates are looking for. Use "internship" to find intern candidates or "full_time" for full-time candidates. Default None (no filter).
        limit: Maximum number of results to return (1-20). Default 10.
        include_hired: If True, include already-hired candidates in a separate section. Default True.

    Returns:
        JSON with candidates array containing both available and hired candidates, 
        with hired_by_other flag for each. Includes has_more flag for pagination.
    """
    # Input validation - limit to 20 max for this tool
    limit = max(1, min(20, limit))

    logger.info(f"search_candidates: skills={skills}, location={location}, exp={min_experience}-{max_experience}, available={available_only}, limit={limit}")

    try:
        # Build query params for InsForge PostgREST
        # Fetch more than limit to allow for filtering
        params: dict = {
            "limit": str(limit * 4),  # Fetch extra to filter
            "order": "bluetech_badge.desc,years_of_experience.desc",
        }

        if available_only:
            params["employment_status"] = "eq.AVAILABLE"

        if bluetech_only:
            params["bluetech_badge"] = "eq.true"

        if job_target and job_target in ("internship", "full_time"):
            params["job_target"] = f"eq.{job_target}"

        if min_experience is not None:
            params["years_of_experience"] = f"gte.{max(0, min_experience)}"

        if max_experience is not None:
            if min_experience is None:
                params["years_of_experience"] = f"lte.{max_experience}"

        profiles = await _query_profiles(params)

        # In-memory filters for skills, location, max_experience (when min is also set)
        if skills:
            skill_keywords = [s.strip().lower() for s in skills.split(",") if s.strip()]
            profiles = [
                p for p in profiles
                if any(
                    kw in skill.lower()
                    for kw in skill_keywords
                    for skill in (p.get("skills") or [])
                )
            ]

        if location:
            location_lower = location.strip().lower()
            profiles = [
                p for p in profiles
                if location_lower in (p.get("location") or "").lower()
                or location_lower in (p.get("preferred_location") or "").lower()
            ]

        if max_experience is not None and min_experience is not None:
            profiles = [
                p for p in profiles
                if (p.get("years_of_experience") or 0) <= max_experience
            ]

        # Format and separate into available vs hired
        all_candidates = [_format_candidate(p, brief=True, for_hiring=True) for p in profiles]
        
        # Separate available and hired
        available = [c for c in all_candidates if not c.get("hired_by_other")]
        hired = [c for c in all_candidates if c.get("hired_by_other")]
        
        # Sort each group: bluetech first, then by experience
        def sort_candidates(candidates):
            return sorted(candidates, key=lambda x: (
                not x.get("is_bluetech", False),  # Bluetech first (False < True, so negate)
                -(x.get("experience", 0) or 0)    # Then by experience desc
            ))
        
        available = sort_candidates(available)
        hired = sort_candidates(hired)
        
        # Limit to 3 verified + 7 unverified per group
        def limit_by_badge(candidates, max_verified=3, max_unverified=7):
            verified = [c for c in candidates if c.get("is_bluetech")][:max_verified]
            unverified = [c for c in candidates if not c.get("is_bluetech")][:max_unverified]
            return verified + unverified
        
        limited_available = limit_by_badge(available)
        limited_hired = limit_by_badge(hired) if include_hired else []
        
        # Combine for response
        all_limited = limited_available + limited_hired
        
        # Check if there are more candidates
        total_available = len(available)
        total_hired = len(hired)
        has_more = (total_available > len(limited_available)) or (total_hired > len(limited_hired))

        logger.info(f"search_candidates: returning {len(all_limited)} results ({len(limited_available)} available, {len(limited_hired)} hired)")
        return str({
            "total_results": len(all_limited),
            "available_count": len(limited_available),
            "hired_count": len(limited_hired),
            "has_more": has_more,
            "filters_applied": {
                "skills": skills,
                "location": location,
                "min_experience": min_experience,
                "max_experience": max_experience,
                "available_only": available_only,
                "bluetech_only": bluetech_only,
                "job_target": job_target,
            },
            "candidates": all_limited,
        })

    except httpx.TimeoutException:
        return f"Error: Request timed out after {API_TIMEOUT}s. Please try again."
    except httpx.HTTPStatusError as e:
        return f"Error: API returned status {e.response.status_code}"
    except Exception as e:
        logger.error(f"search_candidates error: {e}")
        return f"Error searching candidates: {str(e)}"


# ══════════════════════════════════════════════
# TOOL 2: get_candidate_profile
# ══════════════════════════════════════════════
@mcp.tool()
async def get_candidate_profile(handle: str) -> str:
    """
    Get the full detailed profile of a specific candidate by their handle.
    Use this after search_candidates to view complete details.

    Args:
        handle: The candidate's unique handle (e.g. "johndoe", "alice_dev").

    Returns:
        Full structured profile including bio, experience history, links, and skills.
    """
    if not handle or not handle.strip():
        return "Error: handle cannot be empty"

    handle_clean = handle.strip().lower()
    logger.info(f"get_candidate_profile: {handle_clean}")

    try:
        params = {"handle": f"eq.{handle_clean}", "limit": "1"}
        profiles = await _query_profiles(params)

        if not profiles:
            return f"Error: No candidate found with handle '{handle_clean}'"

        profile = _format_candidate(profiles[0], brief=False)

        # Record a profile view (non-blocking, won't fail the request)
        profile_id = profiles[0].get("id")
        if profile_id:
            await _record_profile_view(profile_id, source="mcp_agent")

        logger.info(f"get_candidate_profile: found {handle_clean}")
        return str(profile)

    except httpx.TimeoutException:
        return f"Error: Request timed out after {API_TIMEOUT}s."
    except Exception as e:
        logger.error(f"get_candidate_profile error: {e}")
        return f"Error fetching profile: {str(e)}"


# ══════════════════════════════════════════════
# TOOL 3: list_available_candidates
# ══════════════════════════════════════════════
@mcp.tool()
async def list_available_candidates(
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "experience",
) -> str:
    """
    Browse all available (unhired) candidates with pagination.
    Good for getting an overview of the talent pool.

    Args:
        page: Page number (1-indexed). Default 1.
        page_size: Results per page (1-50). Default 20.
        sort_by: Sort order — "experience" (desc), "recent" (newest first), or "rating". Default "experience".

    Returns:
        Paginated list of available candidates.
    """
    page = max(1, page)
    page_size = max(1, min(50, page_size))
    offset = (page - 1) * page_size

    order_map = {
        "experience": "years_of_experience.desc",
        "recent": "created_at.desc",
        "rating": "rating.desc",
    }
    order = order_map.get(sort_by, "years_of_experience.desc")

    logger.info(f"list_available_candidates: page={page}, size={page_size}, sort={sort_by}")

    try:
        params = {
            "employment_status": "eq.AVAILABLE",
            "limit": str(page_size),
            "offset": str(offset),
            "order": order,
        }

        profiles = await _query_profiles(params)
        candidates = [_format_candidate(p, brief=True) for p in profiles]

        return str({
            "page": page,
            "page_size": page_size,
            "results_on_page": len(candidates),
            "sort_by": sort_by,
            "candidates": candidates,
        })

    except Exception as e:
        logger.error(f"list_available_candidates error: {e}")
        return f"Error listing candidates: {str(e)}"


# ══════════════════════════════════════════════
# TOOL 4: get_platform_stats
# ══════════════════════════════════════════════
@mcp.tool()
async def get_platform_stats() -> str:
    """
    Get overall platform statistics.
    Useful for understanding the talent pool size and health.

    Returns:
        Total profiles, available count, hired count, and skill distribution.
    """
    logger.info("get_platform_stats")

    try:
        all_profiles = await _query_profiles({"limit": "1000"})

        total = len(all_profiles)
        available = sum(1 for p in all_profiles if p.get("employment_status") == "AVAILABLE")
        hired = sum(1 for p in all_profiles if p.get("employment_status") == "HIRED")
        bluetech = sum(1 for p in all_profiles if p.get("bluetech_badge"))

        # Skill frequency
        skill_freq: dict[str, int] = {}
        for p in all_profiles:
            for skill in (p.get("skills") or []):
                skill_freq[skill] = skill_freq.get(skill, 0) + 1

        top_skills = sorted(skill_freq.items(), key=lambda x: x[1], reverse=True)[:20]

        # Location distribution
        loc_freq: dict[str, int] = {}
        for p in all_profiles:
            loc = p.get("location") or "Unknown"
            loc_freq[loc] = loc_freq.get(loc, 0) + 1

        top_locations = sorted(loc_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        # Experience distribution
        exp_buckets = {"0-2 yrs": 0, "3-5 yrs": 0, "6-10 yrs": 0, "10+ yrs": 0}
        for p in all_profiles:
            yoe = p.get("years_of_experience") or 0
            if yoe <= 2:
                exp_buckets["0-2 yrs"] += 1
            elif yoe <= 5:
                exp_buckets["3-5 yrs"] += 1
            elif yoe <= 10:
                exp_buckets["6-10 yrs"] += 1
            else:
                exp_buckets["10+ yrs"] += 1

        return str({
            "total_profiles": total,
            "available": available,
            "hired": hired,
            "bluetech_members": bluetech,
            "top_skills": dict(top_skills),
            "top_locations": dict(top_locations),
            "experience_distribution": exp_buckets,
        })

    except Exception as e:
        logger.error(f"get_platform_stats error: {e}")
        return f"Error fetching stats: {str(e)}"


# ══════════════════════════════════════════════
# TOOL 5: search_by_skills
# ══════════════════════════════════════════════
@mcp.tool()
async def search_by_skills(
    required_skills: str,
    preferred_skills: Optional[str] = None,
    min_match_count: int = 1,
    available_only: bool = True,
    limit: int = 20,
) -> str:
    """
    Advanced skill-based candidate search with required and preferred skill matching.
    Returns candidates ranked by how many skills they match.

    Args:
        required_skills: Comma-separated skills that candidates MUST have (e.g. "Python,Django").
        preferred_skills: Comma-separated nice-to-have skills for bonus ranking (e.g. "Docker,AWS").
        min_match_count: Minimum number of required skills a candidate must match. Default 1.
        available_only: Only return available candidates. Default True.
        limit: Max results (1-50). Default 20.

    Returns:
        Candidates ranked by skill match score with match details.
    """
    if not required_skills or not required_skills.strip():
        return "Error: required_skills cannot be empty"

    required = [s.strip().lower() for s in required_skills.split(",") if s.strip()]
    preferred = [s.strip().lower() for s in (preferred_skills or "").split(",") if s.strip()]
    limit = max(1, min(50, limit))

    logger.info(f"search_by_skills: required={required}, preferred={preferred}")

    try:
        params: dict = {"limit": "200"}
        if available_only:
            params["employment_status"] = "eq.AVAILABLE"

        profiles = await _query_profiles(params)

        # Score each candidate
        scored_candidates = []
        for p in profiles:
            candidate_skills = [s.lower() for s in (p.get("skills") or [])]

            required_matches = [
                rskill for rskill in required
                if any(rskill in cskill for cskill in candidate_skills)
            ]

            if len(required_matches) < min_match_count:
                continue

            preferred_matches = [
                pskill for pskill in preferred
                if any(pskill in cskill for cskill in candidate_skills)
            ]

            # Score: required matches * 10 + preferred matches * 3 + bluetech * 5
            score = (len(required_matches) * 10
                     + len(preferred_matches) * 3
                     + (5 if p.get("bluetech_badge") else 0))

            candidate = _format_candidate(p, brief=True)
            candidate["match_score"] = score
            candidate["required_skills_matched"] = required_matches
            candidate["preferred_skills_matched"] = preferred_matches
            scored_candidates.append(candidate)

        # Sort by score desc
        scored_candidates.sort(key=lambda x: x["match_score"], reverse=True)

        result = scored_candidates[:limit]
        logger.info(f"search_by_skills: returning {len(result)} matched candidates")

        return str({
            "total_matches": len(result),
            "required_skills_searched": required,
            "preferred_skills_searched": preferred,
            "candidates": result,
        })

    except Exception as e:
        logger.error(f"search_by_skills error: {e}")
        return f"Error searching by skills: {str(e)}"


# ══════════════════════════════════════════════
# TOOL 6: get_candidate_resume
# ══════════════════════════════════════════════
@mcp.tool()
async def get_candidate_resume(handle: str) -> str:
    """
    Get a structured auto-generated resume for a candidate.
    The resume is built from the candidate's profile data (not uploaded).

    Args:
        handle: The candidate's unique handle.

    Returns:
        Structured resume data with sections: header, summary, skills, experience, links.
    """
    if not handle or not handle.strip():
        return "Error: handle cannot be empty"

    handle_clean = handle.strip().lower()
    logger.info(f"get_candidate_resume: {handle_clean}")

    try:
        params = {"handle": f"eq.{handle_clean}", "limit": "1"}
        profiles = await _query_profiles(params)

        if not profiles:
            return f"Error: No candidate found with handle '{handle_clean}'"

        p = profiles[0]

        resume = {
            "header": {
                "name": p.get("display_name"),
                "role": p.get("role_title"),
                "location": p.get("location"),
                "preferred_location": p.get("preferred_location"),
                "years_of_experience": p.get("years_of_experience", 0),
                "employment_status": p.get("employment_status"),
            },
            "summary": p.get("bio"),
            "technical_skills": p.get("skills", []),
            "experience_history": [
                {
                    "role": exp.get("role"),
                    "company": exp.get("company"),
                    "from": exp.get("from"),
                    "to": exp.get("to", "Present"),
                }
                for exp in (p.get("experience_history") or [])
            ],
            "links": {
                "github": p.get("github_url"),
                "linkedin": p.get("linkedin_url"),
                "profile_url": f"https://hireahuman.ai/engineer/{handle_clean}",
            },
            "badges": {
                "bluetech": p.get("bluetech_badge", False),
                "verified": bool(p.get("avatar_url")),
            },
        }

        logger.info(f"get_candidate_resume: generated for {handle_clean}")
        return str(resume)

    except Exception as e:
        logger.error(f"get_candidate_resume error: {e}")
        return f"Error generating resume: {str(e)}"


# ══════════════════════════════════════════════
# TOOL 7: check_candidate_availability
# ══════════════════════════════════════════════
@mcp.tool()
async def check_candidate_availability(handle: str) -> str:
    """
    Quick check on a candidate's availability and key contact info.
    Use this before reaching out to a candidate.

    Args:
        handle: The candidate's unique handle.

    Returns:
        Availability status, preferred location, and contact links.
    """
    if not handle or not handle.strip():
        return "Error: handle cannot be empty"

    handle_clean = handle.strip().lower()
    logger.info(f"check_candidate_availability: {handle_clean}")

    try:
        params = {
            "handle": f"eq.{handle_clean}",
            "select": "handle,display_name,employment_status,location,preferred_location,linkedin_url,github_url,bluetech_badge,role_title",
            "limit": "1",
        }
        profiles = await _query_profiles(params)

        if not profiles:
            return f"Error: No candidate found with handle '{handle_clean}'"

        p = profiles[0]

        return str({
            "handle": p.get("handle"),
            "name": p.get("display_name"),
            "role": p.get("role_title"),
            "is_available": p.get("employment_status") == "AVAILABLE",
            "employment_status": p.get("employment_status"),
            "location": p.get("location"),
            "preferred_location": p.get("preferred_location"),
            "linkedin": p.get("linkedin_url"),
            "github": p.get("github_url"),
            "bluetech_badge": p.get("bluetech_badge", False),
        })

    except Exception as e:
        logger.error(f"check_candidate_availability error: {e}")
        return f"Error checking availability: {str(e)}"


# ──────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────
def main():
    """Main entry point for the HireAHuman MCP server."""
    logger.info("=" * 50)
    logger.info("Starting HireAHuman.ai MCP Server")
    logger.info(f"InsForge URL: {INSFORGE_URL}")
    logger.info("Available tools:")
    logger.info("  1. search_candidates         — Multi-filter candidate search")
    logger.info("  2. get_candidate_profile      — Full profile by handle")
    logger.info("  3. list_available_candidates   — Paginated browse")
    logger.info("  4. get_platform_stats          — Platform-wide statistics")
    logger.info("  5. search_by_skills            — Advanced skill matching with scoring")
    logger.info("  6. get_candidate_resume        — Auto-generated structured resume")
    logger.info("  7. check_candidate_availability — Quick availability check")
    logger.info("=" * 50)

    # Default: stdio transport for Claude Desktop / Cursor / etc.
    # Use: python server.py  (stdio)
    # Or:  python server.py --transport http  (HTTP on port 8000)
    import argparse
    parser = argparse.ArgumentParser(description="HireAHuman.ai MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio",
                        help="Transport protocol (default: stdio)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="HTTP host (default: 0.0.0.0)")
    args = parser.parse_args()

    if args.transport == "http":
        logger.info(f"Running HTTP transport on {args.host}:{args.port}")
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        logger.info("Running stdio transport")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
