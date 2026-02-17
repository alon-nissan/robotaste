"""
Protocol Endpoints — CRUD operations for experiment protocols.

=== WHAT IS A ROUTER? ===
A router is a collection of related API endpoints grouped together.
Think of it like a chapter in a book — all protocol-related endpoints live here.

=== KEY CONCEPTS ===
- APIRouter: Creates a group of endpoints that get attached to the main app.
- @router.get("/path"): Decorator that says "handle GET requests to this path".
- @router.post("/path"): Handle POST requests (used for creating/uploading data).
- Path parameters: Values in the URL like /protocols/{protocol_id} — FastAPI
  automatically extracts protocol_id and passes it to your function.
- Response: FastAPI automatically converts Python dicts/lists to JSON responses.
- UploadFile: FastAPI's way of handling file uploads from the frontend.
- HTTPException: How we return error responses (like 404 Not Found).

=== WHAT THIS FILE DOES ===
Wraps the existing robotaste/data/protocol_repo.py functions as HTTP endpoints.
No business logic is duplicated — we just call the existing functions.
"""

# APIRouter: creates a group of endpoints
# HTTPException: for returning error responses (404, 400, etc.)
# UploadFile / File: for handling file uploads from the frontend
from fastapi import APIRouter, HTTPException, UploadFile, File

# json: for parsing uploaded JSON files
import json

# Import the EXISTING protocol repository functions from your codebase.
# These are the same functions that Streamlit's protocol_manager.py uses.
from robotaste.data.protocol_repo import (
    list_protocols,       # Returns list of all protocols from the database
    get_protocol_by_id,   # Returns a single protocol by its UUID
    create_protocol_in_db,  # Saves a new protocol to the database
)

# Import protocol validation (same validation Streamlit uses)
from robotaste.config.protocols import validate_protocol


# ─── CREATE ROUTER ──────────────────────────────────────────────────────────
# This router will be mounted at /api/protocols in main.py
router = APIRouter()


# ─── GET ALL PROTOCOLS ──────────────────────────────────────────────────────
@router.get("")
def get_protocols():
    """
    Return all non-archived protocols from the database.

    The React frontend calls this to populate the protocol dropdown.
    Returns a JSON array of protocol objects, each containing:
    - protocol_id: UUID string
    - name: Human-readable name
    - description: What this protocol does
    - version: Version string
    - ingredients: List of ingredient configs
    - stopping_criteria: When the experiment ends
    - etc.
    """
    # Call the existing function — it queries SQLite and returns a list of dicts
    protocols = list_protocols(include_archived=False)
    return protocols


# ─── GET SINGLE PROTOCOL ───────────────────────────────────────────────────
@router.get("/{protocol_id}")
def get_protocol(protocol_id: str):
    """
    Return a single protocol by its ID.

    Path parameter: protocol_id is extracted from the URL automatically.
    Example: GET /api/protocols/abc-123 → protocol_id = "abc-123"

    Returns 404 if the protocol doesn't exist.
    """
    protocol = get_protocol_by_id(protocol_id)

    if not protocol:
        # HTTPException sends an error response to the frontend.
        # status_code=404 means "Not Found" — the standard HTTP code.
        raise HTTPException(status_code=404, detail="Protocol not found")

    return protocol


# ─── UPLOAD PROTOCOL (JSON FILE) ───────────────────────────────────────────
@router.post("/upload")
async def upload_protocol(file: UploadFile = File(...)):
    """
    Upload a protocol JSON file and save it to the database.

    The 'async' keyword: FastAPI can handle requests asynchronously (non-blocking).
    For file uploads, async is recommended because reading files can be slow.

    UploadFile: FastAPI's wrapper for uploaded files. It provides:
    - file.filename: Original filename
    - file.read(): Read the file contents as bytes
    - file.content_type: MIME type (should be application/json)

    File(...): The ... means "this parameter is required" (no default value).

    Flow:
    1. Frontend sends a JSON file via HTTP POST
    2. We read and parse the JSON
    3. We validate it using the same validation as Streamlit
    4. We save it to the database using the same function as Streamlit
    5. We return the saved protocol data
    """
    # Step 1: Validate file type
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a .json file")

    try:
        # Step 2: Read and parse the JSON file
        # 'await' is used with async functions — it waits for the file read to complete
        # without blocking other requests from being processed.
        contents = await file.read()

        # Decode bytes to string, then parse as JSON → Python dict
        protocol_data = json.loads(contents.decode("utf-8"))

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")

    # Step 3: Validate using existing validation function
    is_valid, errors = validate_protocol(protocol_data)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Protocol validation failed: {errors}"
        )

    # Step 4: Generate metadata and save to database
    import uuid
    from datetime import datetime

    protocol_data["protocol_id"] = str(uuid.uuid4())
    protocol_data["created_at"] = datetime.utcnow().isoformat()
    protocol_data["updated_at"] = protocol_data["created_at"]
    protocol_data["is_archived"] = False

    success = create_protocol_in_db(protocol_data)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to save protocol")

    # Step 5: Return the saved protocol
    return {
        "message": "Protocol uploaded successfully",
        "protocol_id": protocol_data["protocol_id"],
        "name": protocol_data.get("name", "Unnamed"),
    }
