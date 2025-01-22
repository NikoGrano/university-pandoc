# PDF Document Generator

A tool to combine multiple markdown files into a single PDF document with proper formatting and bibliography support.

## Prerequisites

- Docker
- Python 3.x

## Project Structure

```
.
├── assets/
│   └── logo.jpg         # Your logo file for cover page
├── lib/
│   ├── chicago.csl      # Citation style file
│   ├── template.tex     # LaTeX template
│   └── wordcount.lua    # Lua filter for word counting
├── Dockerfile
├── run.py
└── README.md
```

## Setup

1. Install Docker if not already installed
2. Place your logo in `assets/logo.jpg`
3. Ensure required files are in the `lib` directory
4. Build the Docker image:
   ```bash
   docker build -t pandoc_pdf_local .
   ```

## Usage

### Basic Usage
```bash
./run.py <source_directory>
```

### Read-only PDF
To generate a password-protected PDF that can only be viewed:
```bash
./run.py <source_directory> --ro                  # Random password for owner actions
./run.py <source_directory> --ro superpass123     # Additional password required to open the file
```

### Source Directory Structure
Your source directory should contain:
- Markdown files (`.md`)
- Bibliography file (optional) named `bibliography.bib`

The script will:
1. Combine all markdown files recursively
2. Process citations if bibliography exists
3. Generate a PDF with proper formatting
4. Output `out.pdf` in the current directory

## Template Variables

The template supports the following variables in your markdown frontmatter:
- title
- subtitle
- author
- date
- place
- school
- studies
- direction
- tyon_tyyppi
- opiskelijanumero
- opintojakson_nimi
- opintojakso
- opintokokonaisuus_nimi
- opintokokonaisuus
- lisatiedot

Example frontmatter:
```yaml
---
title: "Document Title"
author: "Author Name"
date: "2024-01-22"
---
```
