#!/usr/bin/env python3

"""
JUCCA GPT4All Model Downloader
===============================

This script downloads and manages GPT4All models for JUCCA.
Supports multiple models and provides progress tracking.

Usage:
    python download_model.py              # Download default model
    python download_model.py --list       # List available models
    python download_model.py --model nous-hermes-llama2.gguf  # Download specific model

Models:
    - mistral-7b-openorca.gguf    (4GB)  - Best balance of speed and quality
    - nous-hermes-llama2.gguf     (4GB)  - Strong reasoning capabilities
    - orca-mini-3b.gguf           (2GB)  - Lower RAM requirements
    - llama-2-7b-chat.gguf        (4GB)  - Good for conversations
"""

import os
import sys
import argparse
import urllib.request
import urllib.error
from pathlib import Path


# Configuration
MODEL_BASE_URL = "https://gpt4all.io/models/gguf"
MODELS_DIR = Path(os.getenv("GPT4ALL_MODEL_PATH", "./models"))

# Model information
MODELS = {
    "mistral-7b-openorca.gguf": {
        "url": f"{MODEL_BASE_URL}/mistral-7b-openorca.gguf",
        "size_gb": 4,
        "description": "Best balance of speed and quality"
    },
    "nous-hermes-llama2.gguf": {
        "url": f"{MODEL_BASE_URL}/nous-hermes-llama2.gguf",
        "size_gb": 4,
        "description": "Strong reasoning capabilities"
    },
    "orca-mini-3b.gguf": {
        "url": f"{MODEL_BASE_URL}/orca-mini-3b.gguf",
        "size_gb": 2,
        "description": "Lower RAM requirements"
    },
    "llama-2-7b-chat.gguf": {
        "url": f"{MODEL_BASE_URL}/llama-2-7b-chat.gguf",
        "size_gb": 4,
        "description": "Good for conversations"
    },
    "orca-2-7b.gguf": {
        "url": f"{MODEL_BASE_URL}/orca-2-7b.gguf",
        "size_gb": 4,
        "description": "Improved reasoning"
    }
}

# Default model
DEFAULT_MODEL = "mistral-7b-openorca.gguf"


def ensure_models_dir():
    """Create models directory if it doesn't exist."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Models directory: {MODELS_DIR}")
    return MODELS_DIR


def get_download_progress(total_size):
    """Create a progress callback for urllib."""
    def callback(count, block_size, total):
        percent = count * block_size * 100 // total
        filled = int(percent // 5)
        bar = "=" * filled + " " * (20 - filled)
        sys.stdout.write(f"\r[{bar}] {percent}% ({count * block_size / 1024 / 1024:.1f}MB / {total / 1024 / 1024:.1f}MB)")
        sys.stdout.flush()
    return callback


def check_disk_space(required_gb: int, path: Path) -> bool:
    """Check if there's enough disk space."""
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        free_gb = free / (1024**3)
        print(f"Available disk space: {free_gb:.1f}GB")
        print(f"Required: {required_gb}GB")
        return free_gb >= required_gb + 1  # Add 1GB buffer
    except Exception as e:
        print(f"Warning: Could not check disk space: {e}")
        return True


def download_model(model_name: str, force: bool = False) -> bool:
    """Download a specific model."""
    if model_name not in MODELS:
        print(f"Error: Unknown model '{model_name}'")
        print("Available models:")
        for name, info in MODELS.items():
            print(f"  - {name} ({info['size_gb']}GB) - {info['description']}")
        return False
    
    model_info = MODELS[model_name]
    output_path = MODELS_DIR / model_name
    
    # Check if model already exists
    if output_path.exists() and not force:
        size_gb = output_path.stat().st_size / (1024**3)
        print(f"Model already exists: {output_path}")
        print(f"Size: {size_gb:.2f}GB")
        response = input("Download again? (y/n): ")
        if response.lower() != 'y':
            print("Skipping download.")
            return True
    
    # Check disk space
    if not check_disk_space(model_info["size_gb"], MODELS_DIR):
        print("Error: Not enough disk space")
        return False
    
    # Create parent directory
    ensure_models_dir()
    
    # Download with progress
    print(f"\nDownloading: {model_name}")
    print(f"URL: {model_info['url']}")
    print(f"Size: ~{model_info['size_gb']}GB")
    print()
    
    try:
        urllib.request.urlretrieve(
            model_info["url"],
            output_path,
            get_download_progress(model_info["size_gb"] * 1024 * 1024 * 1024)
        )
        print(f"\n\nDownload complete!")
        print(f"Saved to: {output_path}")
        
        # Verify file
        if output_path.exists():
            actual_size = output_path.stat().st_size / (1024**3)
            print(f"File size: {actual_size:.2f}GB")
        
        return True
        
    except urllib.error.URLError as e:
        print(f"\n\nError downloading: {e}")
        print("Please check your internet connection and try again.")
        # Clean up partial download
        if output_path.exists():
            output_path.unlink()
        return False
    
    except KeyboardInterrupt:
        print("\n\nDownload cancelled.")
        if output_path.exists():
            output_path.unlink()
        return False


def list_models():
    """List all available and downloaded models."""
    print("\nAvailable GPT4All Models:")
    print("=" * 60)
    
    for name, info in MODELS.items():
        output_path = MODELS_DIR / name
        if output_path.exists():
            size = output_path.stat().st_size / (1024**3)
            status = f"Downloaded ({size:.1f}GB)"
        else:
            status = f"Not downloaded (~{info['size_gb']}GB)"
        
        print(f"\n{name}")
        print(f"  Status: {status}")
        print(f"  Description: {info['description']}")
    
    print("\n" + "=" * 60)


def list_downloaded_models():
    """List downloaded models with details."""
    print("\nDownloaded Models:")
    print("=" * 60)
    
    downloaded = []
    for model_path in MODELS_DIR.glob("*.gguf"):
        size_mb = model_path.stat().st_size / (1024 * 1024)
        downloaded.append({
            "name": model_path.name,
            "size_mb": size_mb,
            "path": model_path
        })
    
    if not downloaded:
        print("  No models downloaded yet.")
        print(f"  Run: python download_model.py --model <model_name>")
    else:
        for model in sorted(downloaded, key=lambda x: x["size_mb"], reverse=True):
            print(f"  {model['name']}")
            print(f"    Size: {model['size_mb']:.0f}MB")
            print(f"    Path: {model['path']}")
    
    print("\n" + "=" * 60)


def delete_model(model_name: str) -> bool:
    """Delete a downloaded model."""
    output_path = MODELS_DIR / model_name
    
    if not output_path.exists():
        print(f"Model not found: {output_path}")
        return False
    
    if output_path.is_file():
        size = output_path.stat().st_size / (1024**2)
        output_path.unlink()
        print(f"Deleted {model_name} ({size:.0f}MB)")
        return True
    else:
        print(f"Not a file: {output_path}")
        return False


def set_default_model(model_name: str) -> bool:
    """Set the default model in environment."""
    if model_name not in MODELS:
        print(f"Error: Unknown model '{model_name}'")
        return False
    
    # Update .env file if it exists
    env_file = Path("../.env")
    if env_file.exists():
        content = env_file.read_text()
        if "GPT4ALL_MODEL=" in content:
            content = content.replace(
                r"GPT4ALL_MODEL=.*",
                f"GPT4ALL_MODEL={model_name}"
            )
            env_file.write_text(content)
            print(f"Updated .env file with default model: {model_name}")
        else:
            with open(env_file, "a") as f:
                f.write(f"\nGPT4ALL_MODEL={model_name}\n")
            print(f"Added GPT4ALL_MODEL={model_name} to .env")
    else:
        print(f"\nTo set default model, add to your .env file:")
        print(f"  GPT4ALL_MODEL={model_name}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="JUCCA GPT4All Model Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                       # Download default model
  %(prog)s --list               # List available models
  %(prog)s --model nous-hermes-llama2.gguf  # Download specific model
  %(prog)s --delete mistral-7b-openorca.gguf  # Delete a model
  %(prog)s --set-default orca-mini-3b.gguf  # Set default model
        """
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available models"
    )
    
    parser.add_argument(
        "--downloaded",
        action="store_true",
        help="List downloaded models"
    )
    
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Model to download (default: {DEFAULT_MODEL})"
    )
    
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-download even if model exists"
    )
    
    parser.add_argument(
        "--delete", "-d",
        type=str,
        metavar="MODEL_NAME",
        help="Delete a downloaded model"
    )
    
    parser.add_argument(
        "--set-default", "-s",
        type=str,
        metavar="MODEL_NAME",
        help="Set the default model in .env"
    )
    
    parser.add_argument(
        "--check-space",
        action="store_true",
        help="Check available disk space"
    )
    
    args = parser.parse_args()
    
    # Ensure models directory exists
    ensure_models_dir()
    
    # Process commands
    if args.check_space:
        check_disk_space(1, MODELS_DIR)
    
    elif args.list:
        list_models()
    
    elif args.downloaded:
        list_downloaded_models()
    
    elif args.delete:
        delete_model(args.delete)
    
    elif args.set_default:
        set_default_model(args.set_default)
    
    else:
        print("JUCCA GPT4All Model Downloader")
        print("=" * 40)
        print(f"Target model: {args.model}")
        print(f"Models directory: {MODELS_DIR}")
        print()
        
        success = download_model(args.model, force=args.force)
        
        if success:
            print("\nModel downloaded successfully!")
            print("\nNext steps:")
            print(f"  1. Set as default: python download_model.py --set-default {args.model}")
            print("  2. Start JUCCA: ./scripts/deploy.sh start")
        else:
            print("\nDownload failed. Please try again.")
            sys.exit(1)


if __name__ == "__main__":
    main()
