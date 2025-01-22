#!/usr/bin/env python3

import os
import sys
import glob
import subprocess
import random
import string
import shutil
from pathlib import Path

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

def combine_markdown_files(directory):
    """Recursively combine all markdown files from directory into single file"""
    combined_content = []
    
    # Walk through directory recursively
    for root, _, files in os.walk(directory):
        for file in sorted(files):
            if file.endswith(('.md', '.markdown')):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    combined_content.append(f"\n\n{content}")
    
    return ''.join(combined_content)

def generate_random_password(length=20):
    """Generate a random password"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def main():
    if len(sys.argv) < 2:
        print("Usage: build_pdf.py <source_directory> [--ro]")
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

    # Create temporary working directory
    temp_dir = "temp_workdir"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # Combine markdown files
        combined_content = combine_markdown_files(source_dir)
        with open(os.path.join(temp_dir, "input.md"), 'w', encoding='utf-8') as f:
            f.write(combined_content)

        # Check required files and directories
        if not os.path.exists('lib'):
            print("Error: 'lib' directory not found")
            sys.exit(1)
        
        required_files = ['wordcount.lua', 'chicago.csl', 'template.tex']
        for file in required_files:
            if not os.path.exists(os.path.join('lib', file)):
                print(f"Error: Required file 'lib/{file}' not found")
                sys.exit(1)

        # Copy bibliography if exists
        bib_exists = os.path.exists(os.path.join(source_dir, "bibliography.bib"))
        if bib_exists:
            shutil.copy2(os.path.join(source_dir, "bibliography.bib"), temp_dir)

        # Copy logo if exists
        if os.path.exists("assets/logo.jpg"):
            shutil.copy2("assets/logo.jpg", temp_dir)
        else:
            print("Warning: assets/logo.jpg not found")

        # Prepare pandoc command
        pandoc_cmd = [
            "docker", "run", "--rm",
            "-v", f"{os.path.abspath(temp_dir)}:/workdir",
            "-v", f"{os.path.abspath('lib')}:/pandoc_files",
            "--entrypoint", "pandoc",
            "pandoc_pdf_local",
            "--output", "/workdir/out.tex",
            "--lua-filter=/pandoc_files/wordcount.lua",
            "-f", "markdown",
            "--csl=/pandoc_files/chicago.csl",
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
