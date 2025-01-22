#!/usr/bin/env python3

import os
import sys
import glob
import subprocess
import random
import string
import shutil
import requests
import tempfile
from pathlib import Path
from tempfile import NamedTemporaryFile

def get_script_path():
    """Get the real path of the script, following symlinks"""
    return os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))

class DockerError(Exception):
    """Custom exception for Docker-related errors"""
    pass

def check_docker():
    """Check if Docker is available and running"""
    try:
        subprocess.run(["docker", "info"], 
                      check=True, 
                      capture_output=True)
    except subprocess.CalledProcessError:
        raise DockerError("Docker is not running or not accessible")
    except FileNotFoundError:
        raise DockerError("Docker is not installed")

def ensure_docker_image():
    """Ensure the required Docker image exists, build if not"""
    try:
        result = subprocess.run(
            ["docker", "images", "-q", "pandoc_pdf_local"],
            check=True,
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():
            print("Docker image not found. Building...")
            subprocess.run(
                ["docker", "build", "-t", "pandoc_pdf_local", "."],
                check=True
            )
            print("Docker image built successfully")
    except subprocess.CalledProcessError as e:
        raise DockerError(f"Failed to check/build Docker image: {str(e)}")

def extract_zotero_id(content):
    """Extract Zotero ID from markdown frontmatter"""
    import re
    match = re.search(r'^---\n(.*?\n)?.*?zotero:\s*["\']?([^"\'\n]+)["\']?.*?\n---', content, re.DOTALL)
    if match:
        return match.group(2)
    return None

def combine_markdown_files(directory):
    """Recursively combine all markdown files from directory into single file"""
    combined_content = []
    zotero_id = None

    # Walk through directory recursively
    for root, _, files in os.walk(directory):
        for file in sorted(files):
            if file.endswith(('.md', '.markdown')):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Check for Zotero ID in each file
                    file_zotero_id = extract_zotero_id(content)
                    if file_zotero_id:
                        zotero_id = file_zotero_id
                    combined_content.append(f"\n\n{content}")

    return ''.join(combined_content), zotero_id

def download_zotero_bibliography(zotero_id):
    """Download bibliography from Zotero"""
    url = f"http://localhost:23119/better-bibtex/export/collection?/1/{zotero_id}.bibtex"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to download Zotero bibliography: HTTP {response.status_code}")
    return response.text

def merge_bibliographies(existing_bib, zotero_bib):
    """Merge two bibliography contents"""
    # Simple concatenation for now - could be made smarter to detect duplicates
    return existing_bib + "\n\n" + zotero_bib

def generate_random_password(length=20):
    """Generate a random password"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def main():
    if len(sys.argv) < 2:
        print("Usage: build_pdf.py <source_directory> [--ro] [--zotero ZOTERO_ID]")
        sys.exit(1)

    try:
        check_docker()
        ensure_docker_image()
    except DockerError as e:
        print(f"Docker error: {str(e)}")
        sys.exit(1)

    source_dir = sys.argv[1]
    readonly_mode = False
    owner_password = ""

    # Check for --ro argument and its value
    if "--ro" in sys.argv:
        readonly_mode = True
        ro_index = sys.argv.index("--ro")
        if ro_index + 1 < len(sys.argv) and not sys.argv[ro_index + 1].startswith("--"):
            owner_password = sys.argv[ro_index + 1]

    # Check if source directory exists
    if not os.path.isdir(source_dir):
        print(f"Error: Directory {source_dir} does not exist")
        sys.exit(1)

    # Create temporary working directory under /tmp
    temp_dir = tempfile.mkdtemp(prefix='pandoc_build_')

    try:
        # Combine markdown files and get Zotero ID if present
        combined_content, markdown_zotero_id = combine_markdown_files(source_dir)
        with open(os.path.join(temp_dir, "input.md"), 'w', encoding='utf-8') as f:
            f.write(combined_content)

        # Get the real script path and check required files
        script_dir = get_script_path()
        lib_path = os.path.join(script_dir, 'lib')
        
        if not os.path.exists(lib_path):
            print(f"Error: 'lib' directory not found in {script_dir}")
            sys.exit(1)

        required_files = ['wordcount.lua', 'template.tex']
        for file in required_files:
            file_path = os.path.join(lib_path, file)
            if not os.path.exists(file_path):
                print(f"Error: Required file not found: {file_path}")
                sys.exit(1)

        # Copy bibliography if exists
        bib_exists = os.path.exists(os.path.join(source_dir, "bibliography.bib"))

        # Get Zotero ID from command line or markdown
        zotero_id = None
        if "--zotero" in sys.argv:
            zotero_index = sys.argv.index("--zotero")
            if zotero_index + 1 < len(sys.argv):
                zotero_id = sys.argv[zotero_index + 1]
        if not zotero_id and markdown_zotero_id:
            zotero_id = markdown_zotero_id

        if zotero_id:
            try:
                zotero_bib = download_zotero_bibliography(zotero_id)
                if bib_exists:
                    # Merge bibliographies
                    with open(os.path.join(source_dir, "bibliography.bib"), 'r', encoding='utf-8') as f:
                        existing_bib = f.read()
                    merged_bib = merge_bibliographies(existing_bib, zotero_bib)
                    with open(os.path.join(temp_dir, "bibliography.bib"), 'w', encoding='utf-8') as f:
                        f.write(merged_bib)
                else:
                    # Just write Zotero bibliography
                    with open(os.path.join(temp_dir, "bibliography.bib"), 'w', encoding='utf-8') as f:
                        f.write(zotero_bib)
                bib_exists = True
            except Exception as e:
                print(f"Warning: Failed to process Zotero bibliography: {str(e)}")
                if bib_exists:
                    shutil.copy2(os.path.join(source_dir, "bibliography.bib"), temp_dir)
        elif bib_exists:
            shutil.copy2(os.path.join(source_dir, "bibliography.bib"), temp_dir)

        # Look for logo.jpg in various locations
        logo_found = False
        logo_locations = [
            "logo.jpg",  # Current working directory
            "assets/logo.jpg",  # Current working directory assets
            os.path.join(source_dir, "logo.jpg"),  # Target directory
            os.path.join(source_dir, "assets/logo.jpg"),  # Target directory assets
            os.path.join(script_dir, "assets/logo.jpg"),  # Script directory assets
        ]
        
        for logo_path in logo_locations:
            if os.path.exists(logo_path):
                shutil.copy2(logo_path, os.path.join(temp_dir, "logo.jpg"))
                logo_found = True
                break
                
        if not logo_found:
            print("Warning: logo.jpg not found in any of the expected locations")

        # Prepare pandoc command
        pandoc_cmd = [
            "docker", "run", "--rm",
            "-v", f"{os.path.abspath(temp_dir)}:/workdir",
            "-v", f"{os.path.abspath(lib_path)}:/pandoc_files",
            "--entrypoint", "pandoc",
            "pandoc_pdf_local",
            "--output", "/workdir/out.tex",
            "--lua-filter=/pandoc_files/wordcount.lua",
            "-f", "markdown",
            "--template=/pandoc_files/template.tex",
            "--standalone",
            "--biblatex"
        ]

        if bib_exists:
            pandoc_cmd.append("--bibliography=/workdir/bibliography.bib")

        pandoc_cmd.append("/workdir/input.md")

        # Verify input file exists
        input_file = os.path.join(temp_dir, "input.md")
        if not os.path.exists(input_file):
            print(f"Error: Input file {input_file} not found")
            sys.exit(1)

        # Execute commands in container
        try:
            # Run pandoc
            subprocess.run(pandoc_cmd, check=True)

            # Verify out.tex was created
            if not os.path.exists(os.path.join(temp_dir, "out.tex")):
                print("Error: Pandoc failed to create out.tex")
                sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error running pandoc command: {str(e)}")
            sys.exit(1)

        for _ in range(2):
            try:
                subprocess.run([
                    "docker", "run", "--rm",
                    "-v", f"{os.path.abspath(temp_dir)}:/workdir",
                    "--entrypoint", "xelatex",
                    "pandoc_pdf_local",
                    "/workdir/out"
                ], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error running xelatex: {str(e)}")
                sys.exit(1)

        try:
            subprocess.run([
                "docker", "run", "--rm",
                "-v", f"{os.path.abspath(temp_dir)}:/workdir",
                "--entrypoint", "biber",
                "pandoc_pdf_local",
                "/workdir/out"
            ], check=True)

            # Verify biber output files exist
            if not os.path.exists(os.path.join(temp_dir, "out.bbl")):
                print("Error: Biber failed to create out.bbl")
                sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error running biber: {str(e)}")
            sys.exit(1)

        for _ in range(2):
            subprocess.run([
                "docker", "run", "--rm",
                "-v", f"{os.path.abspath(temp_dir)}:/workdir",
                "--entrypoint", "xelatex",
                "pandoc_pdf_local",
                "/workdir/out"
            ], check=True)

            # Verify final PDF was created
            if not os.path.exists(os.path.join(temp_dir, "out.pdf")):
                print("Error: XeLaTeX failed to create out.pdf")
                sys.exit(1)

        if readonly_mode:
            password = generate_random_password()
            try:
                subprocess.run([
                    "docker", "run", "--rm",
                    "-v", f"{os.path.abspath(temp_dir)}:/workdir",
                    "--entrypoint", "qpdf",
                    "pandoc_pdf_local",
                    "--encrypt", owner_password, password, "256",
                    "--print=none",
                    "--modify=none",
                    "--extract=n",
                    "--annotate=n",
                    "--",
                    "/workdir/out.pdf", "/workdir/protected.pdf"
                ], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error encrypting PDF: {str(e)}")
                sys.exit(1)
            print(f"\nPDF owner password: {password}")
            shutil.copy2(os.path.join(temp_dir, "protected.pdf"), "out.pdf")
        else:
            shutil.copy2(os.path.join(temp_dir, "out.pdf"), "out.pdf")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        pass

if __name__ == "__main__":
    main()
