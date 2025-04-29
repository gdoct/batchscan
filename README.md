# Batchscan

A tool for batch processing and analyzing images using the Gemma-3 AI model.

## Features

- Process images using advanced AI models to extract descriptions, keywords, and more
- Store image metadata and tags in a SQLite database
- Skip already processed images for efficiency
- Recursive directory scanning support
- Command-line interface for easy use

## Requirements

- Python 3.8+
- Torch
- Transformers
- GPU recommended for better performance

## Installation

### Development Installation

```bash
# Clone the repository
git clone https://github.com/gdoct/batchscan.git
cd batchscan

# Install in development mode
pip install -e .
```

### User Installation

```bash
pip install git+https://github.com/gdoct/batchscan.git
```

## Usage

### Basic Usage

```bash
# Process all images in the current directory
batchscan

# Process all images in a specific directory
batchscan /path/to/images
```

### Advanced Usage

```bash
# Process all images recursively
batchscan /path/to/images -r

# Specify a custom database file
batchscan /path/to/images -d /path/to/database.dat

# Verbose output
batchscan /path/to/images -v
```

### Command-Line Options

- `directory`: Directory containing images to scan (default: current directory)
- `-r, --recursive`: Scan directories recursively
- `-d, --database`: Database file path (default: photos.db in current directory)
- `-v, --verbose`: Print detailed processing information

## How It Works

BatchScan uses the Gemma-3 model to analyze images and extract meaningful information:

1. **Image Analysis**: Each image is processed to extract:
   - Single-sentence description of the scene
   - Keywords describing the image content
   - Mood of the image
   - Potential title for the image

2. **Database Storage**: All information is stored in an SQLite database including:
   - Image metadata (descriptions, titles, etc.)
   - Tags extracted from keywords
   - Folder information

3. **Efficiency**: The tool keeps track of processed images, so you can safely run it multiple times on the same directory without re-processing images.

## Project Structure

```
batchscan/
├── __init__.py
├── __main__.py
├── core/
│   ├── __init__.py
│   ├── batch_scanner.py
│   ├── photo_scanner.py
│   └── repository.py
```