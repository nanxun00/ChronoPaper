"""DOCX/PDF Document Generation MCP Server.

Provides tools for generating DOCX and PDF documents from LLM output
with formatting, templates, and export capabilities.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Dict, List, Optional

from mcp.server import FastMCP

# Initialize MCP server
mcp = FastMCP("docxpdf-mcp-agent")
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "default_format": "docx",
    "default_template": "academic",
    "supported_formats": ["docx", "pdf", "md", "html"],
    "supported_templates": [
        "academic", 
        "report", 
        "memo", 
        "letter", 
        "thesis",
        "presentation"
    ],
    "max_content_length": 50000,
    "font_family": "Times New Roman",
    "font_size": 12,
    "line_spacing": 1.5,
    "margins": {
        "top": 1.0,
        "bottom": 1.0,
        "left": 1.0,
        "right": 1.0
    }
}


def _json_ok(data: Any) -> str:
    """Serialize successful result to JSON."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def _json_error(message: str, details: str = None) -> str:
    """Serialize error result to JSON."""
    payload = {"error": message}
    if details:
        payload["details"] = details
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _validate_content(content: str, max_length: int = 50000) -> bool:
    """Validate content length and format."""
    if not content or not content.strip():
        return False
    if len(content) > max_length:
        return False
    return True


def _validate_format(fmt: str) -> bool:
    """Validate output format."""
    return fmt.lower() in DEFAULT_CONFIG["supported_formats"]


def _validate_template(template: str) -> bool:
    """Validate template name."""
    return template.lower() in DEFAULT_CONFIG["supported_templates"]


@mcp.tool()
async def create_docx_document(
    content: str,
    title: str = "Untitled Document",
    template: str = "academic",
    font_family: str = "Times New Roman",
    font_size: int = 12,
    line_spacing: float = 1.5,
    include_toc: bool = False,
    include_page_numbers: bool = True,
) -> str:
    """Create a DOCX document from text content.
    
    Args:
        content: Document content (supports markdown-like formatting).
        title: Document title.
        template: Document template style.
        font_family: Font family name.
        font_size: Font size in points.
        line_spacing: Line spacing multiplier.
        include_toc: Whether to include table of contents.
        include_page_numbers: Whether to include page numbers.
        
    Returns:
        JSON string with document metadata and download info.
    """
    if not _validate_content(content):
        return _json_error("Invalid content: empty or too long")
        
    if not _validate_template(template):
        return _json_error(f"Invalid template: {template}")
        
    # Process content and generate document
    try:
        # Mock document generation
        doc_id = f"doc_{hash(content) % 10000:04d}"
        word_count = len(content.split())
        
        result = {
            "doc_id": doc_id,
            "title": title,
            "format": "docx",
            "template": template,
            "word_count": word_count,
            "status": "generated",
            "metadata": {
                "font_family": font_family,
                "font_size": font_size,
                "line_spacing": line_spacing,
                "include_toc": include_toc,
                "include_page_numbers": include_page_numbers
            },
            "download_url": f"/api/documents/{doc_id}/download",
            "created_at": "2026-06-24T14:12:23Z"
        }
        return _json_ok(result)
    except Exception as e:
        logger.exception("create_docx_document failed")
        return _json_error(f"Document generation failed: {str(e)}")


@mcp.tool()
async def create_pdf_document(
    content: str,
    title: str = "Untitled Document",
    template: str = "academic",
    font_family: str = "Times New Roman",
    font_size: int = 12,
    line_spacing: float = 1.5,
    include_toc: bool = False,
    include_page_numbers: bool = True,
    page_size: str = "A4",
) -> str:
    """Create a PDF document from text content.
    
    Args:
        content: Document content (supports markdown-like formatting).
        title: Document title.
        template: Document template style.
        font_family: Font family name.
        font_size: Font size in points.
        line_spacing: Line spacing multiplier.
        include_toc: Whether to include table of contents.
        include_page_numbers: Whether to include page numbers.
        page_size: Page size (A4, Letter, Legal).
        
    Returns:
        JSON string with document metadata and download info.
    """
    if not _validate_content(content):
        return _json_error("Invalid content: empty or too long")
        
    if not _validate_template(template):
        return _json_error(f"Invalid template: {template}")
        
    try:
        # Mock document generation
        doc_id = f"pdf_{hash(content) % 10000:04d}"
        word_count = len(content.split())
        
        result = {
            "doc_id": doc_id,
            "title": title,
            "format": "pdf",
            "template": template,
            "word_count": word_count,
            "status": "generated",
            "metadata": {
                "font_family": font_family,
                "font_size": font_size,
                "line_spacing": line_spacing,
                "include_toc": include_toc,
                "include_page_numbers": include_page_numbers,
                "page_size": page_size
            },
            "download_url": f"/api/documents/{doc_id}/download",
            "created_at": "2026-06-24T14:12:23Z"
        }
        return _json_ok(result)
    except Exception as e:
        logger.exception("create_pdf_document failed")
        return _json_error(f"Document generation failed: {str(e)}")


@mcp.tool()
async def convert_document(
    doc_id: str,
    target_format: str,
    template: str = None,
) -> str:
    """Convert an existing document to a different format.
    
    Args:
        doc_id: Source document ID.
        target_format: Target format (docx, pdf, md, html).
        template: Optional template for conversion.
        
    Returns:
        JSON string with converted document info.
    """
    if not doc_id or not doc_id.strip():
        return _json_error("Invalid document ID")
        
    if not _validate_format(target_format):
        return _json_error(f"Invalid target format: {target_format}")
        
    try:
        # Mock conversion
        new_doc_id = f"conv_{hash(doc_id) % 10000:04d}_{target_format}"
        
        result = {
            "doc_id": new_doc_id,
            "original_doc_id": doc_id,
            "format": target_format,
            "template": template or "default",
            "status": "converted",
            "download_url": f"/api/documents/{new_doc_id}/download",
            "created_at": "2026-06-24T14:12:23Z"
        }
        return _json_ok(result)
    except Exception as e:
        logger.exception("convert_document failed")
        return _json_error(f"Document conversion failed: {str(e)}")


@mcp.tool()
async def get_document_info(doc_id: str) -> str:
    """Get information about a generated document.
    
    Args:
        doc_id: Document ID to query.
        
    Returns:
        JSON string with document metadata.
    """
    if not doc_id or not doc_id.strip():
        return _json_error("Invalid document ID")
        
    try:
        # Mock document info
        result = {
            "doc_id": doc_id,
            "title": "Sample Document",
            "format": "docx",
            "template": "academic",
            "word_count": 1250,
            "page_count": 5,
            "status": "ready",
            "created_at": "2026-06-24T14:12:23Z",
            "download_url": f"/api/documents/{doc_id}/download"
        }
        return _json_ok(result)
    except Exception as e:
        logger.exception("get_document_info failed")
        return _json_error(f"Failed to get document info: {str(e)}")


@mcp.tool()
async def list_documents() -> str:
    """List all generated documents.
    
    Returns:
        JSON string with document list.
    """
    try:
        # Mock document list
        result = {
            "documents": [
                {
                    "doc_id": "doc_0001",
                    "title": "Research Paper",
                    "format": "docx",
                    "created_at": "2026-06-24T10:30:00Z"
                },
                {
                    "doc_id": "pdf_0002",
                    "title": "Technical Report",
                    "format": "pdf",
                    "created_at": "2026-06-24T12:45:00Z"
                }
            ],
            "total": 2
        }
        return _json_ok(result)
    except Exception as e:
        logger.exception("list_documents failed")
        return _json_error(f"Failed to list documents: {str(e)}")


@mcp.tool()
async def delete_document(doc_id: str) -> str:
    """Delete a generated document.
    
    Args:
        doc_id: Document ID to delete.
        
    Returns:
        JSON string with deletion status.
    """
    if not doc_id or not doc_id.strip():
        return _json_error("Invalid document ID")
        
    try:
        result = {
            "doc_id": doc_id,
            "status": "deleted",
            "deleted_at": "2026-06-24T14:12:23Z"
        }
        return _json_ok(result)
    except Exception as e:
        logger.exception("delete_document failed")
        return _json_error(f"Failed to delete document: {str(e)}")


@mcp.tool()
async def get_template_list() -> str:
    """Get available document templates.
    
    Returns:
        JSON string with template list.
    """
    try:
        templates = [
            {
                "name": "academic",
                "description": "Academic paper template with abstract, introduction, etc.",
                "features": ["title", "abstract", "sections", "references"]
            },
            {
                "name": "report",
                "description": "Business report template",
                "features": ["title", "executive_summary", "sections", "conclusions"]
            },
            {
                "name": "memo",
                "description": "Internal memo template",
                "features": ["header", "body", "signature"]
            },
            {
                "name": "letter",
                "description": "Formal letter template",
                "features": ["sender_info", "recipient_info", "body", "closing"]
            },
            {
                "name": "thesis",
                "description": "Thesis/dissertation template",
                "features": ["title_page", "abstract", "chapters", "references", "appendices"]
            },
            {
                "name": "presentation",
                "description": "Presentation slides template",
                "features": ["title_slide", "content_slides", "summary_slide"]
            }
        ]
        result = {
            "templates": templates,
            "total": len(templates)
        }
        return _json_ok(result)
    except Exception as e:
        logger.exception("get_template_list failed")
        return _json_error(f"Failed to get templates: {str(e)}")


# Entry point
if __name__ == "__main__":
    mcp.run(transport="stdio")
