#!/usr/bin/env python3
"""
Generate API documentation for Fantasy Football Draft Tracker.

Run this script to update the docs/ directory with fresh OpenAPI specs and Swagger UI.
"""

import json
from pathlib import Path


def generate_docs():
    """Generate OpenAPI spec and Swagger UI files."""
    import sys

    # Add project root to Python path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    # Import after ensuring we're in the right directory
    from main import app

    # Ensure docs directory exists (relative to project root)
    docs_dir = project_root / "docs"
    docs_dir.mkdir(exist_ok=True)

    print("Generating OpenAPI specification...")

    # Generate OpenAPI spec
    openapi_spec = app.openapi()

    # Write OpenAPI JSON
    openapi_file = docs_dir / "openapi.json"
    with open(openapi_file, 'w') as f:
        json.dump(openapi_spec, f, indent=2)

    print(f"[OK] OpenAPI spec written to {openapi_file}")

    # Generate Swagger UI HTML
    swagger_html = '''<!DOCTYPE html>
<html>
<head>
    <title>Fantasy Football Draft Tracker API</title>
    <link rel="stylesheet" type="text/css"
          href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
    <style>
        html {
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }
        *, *:before, *:after {
            box-sizing: inherit;
        }
        body {
            margin:0;
            background: #fafafa;
        }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: './openapi.json',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout"
            });
        };
    </script>
</body>
</html>'''

    # Write Swagger UI HTML
    html_file = docs_dir / "index.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(swagger_html)

    print(f"[OK] Swagger UI written to {html_file}")
    print("\nDocumentation generated successfully!")
    print(f"You can now view the docs by opening: {html_file}")
    print("Or serve them locally with: python -m http.server 8080 --directory docs")

if __name__ == "__main__":
    generate_docs()
