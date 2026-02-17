"""
Documentation Endpoints — Serve protocol documentation files.

=== WHAT THIS FILE DOES ===
Provides endpoints to download documentation files that already exist
in the docs/ folder. The React frontend uses these for the
"Download User Guide" and "Download Schema" buttons.

=== KEY CONCEPT: FileResponse ===
Instead of returning JSON, FileResponse sends a file download.
The browser will prompt the user to save the file (or display it,
depending on the media_type).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

# ─── CREATE ROUTER ──────────────────────────────────────────────────────────
router = APIRouter()

# Base path for documentation files (relative to project root)
# Path(__file__) gives us this file's location, then we go up to the project root
DOCS_DIR = Path(__file__).parent.parent.parent / "docs"


# ─── GET USER GUIDE ─────────────────────────────────────────────────────────
@router.get("/user-guide")
def get_user_guide():
    """
    Download the protocol user guide markdown file.

    FileResponse sends the file as a download to the browser.
    - path: The file on disk to send
    - filename: What the browser should name the downloaded file
    - media_type: The MIME type (text/markdown for .md files)
    """
    file_path = DOCS_DIR / "protocol_user_guide.md"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="User guide not found")

    return FileResponse(
        path=str(file_path),
        filename="protocol_user_guide.md",
        media_type="text/markdown",
    )


# ─── GET SCHEMA REFERENCE ──────────────────────────────────────────────────
@router.get("/schema")
def get_schema_reference():
    """
    Download the protocol schema reference markdown file.
    """
    file_path = DOCS_DIR / "protocol_schema.md"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Schema reference not found")

    return FileResponse(
        path=str(file_path),
        filename="protocol_schema.md",
        media_type="text/markdown",
    )
