"""
Resource path helper for PyInstaller builds
Handles correct path resolution for bundled resources
"""

import os
import sys
from pathlib import Path


def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller
    
    Args:
        relative_path (str): Relative path to the resource file
        
    Returns:
        str: Absolute path to the resource file
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Running in development mode
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    full_path = os.path.join(base_path, relative_path)
    
    # Ensure the path exists
    if not os.path.exists(full_path):
        print(f"Warning: Resource file not found: {full_path}")
        # Try alternative paths for development
        if not hasattr(sys, '_MEIPASS'):
            # Development mode - try current directory
            alt_path = os.path.join(os.getcwd(), relative_path)
            if os.path.exists(alt_path):
                return alt_path
    
    return full_path


def get_theme_path(theme_file):
    """
    Get path to theme file
    
    Args:
        theme_file (str): Theme filename (e.g., 'dark_theme.qss')
        
    Returns:
        str: Absolute path to theme file
    """
    return resource_path(os.path.join('themes', theme_file))


def get_icon_path(icon_file):
    """
    Get path to icon file
    
    Args:
        icon_file (str): Icon filename (e.g., 'tray_icon.ico')
        
    Returns:
        str: Absolute path to icon file
    """
    return resource_path(os.path.join('icons', icon_file))


def get_version():
    """
    Get version from VERSION file
    
    Returns:
        str: Version string
    """
    try:
        version_path = resource_path('VERSION')
        with open(version_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except (FileNotFoundError, IOError):
        return "1.0.0"  # Default version


def list_resource_files(directory):
    """
    List all files in a resource directory
    
    Args:
        directory (str): Directory name relative to base path
        
    Returns:
        list: List of file paths in the directory
    """
    dir_path = resource_path(directory)
    if os.path.exists(dir_path) and os.path.isdir(dir_path):
        return [os.path.join(dir_path, f) for f in os.listdir(dir_path) 
                if os.path.isfile(os.path.join(dir_path, f))]
    return []


def verify_resources():
    """
    Verify that all critical resources exist
    
    Returns:
        dict: Dictionary with resource status
    """
    results = {
        'themes': {},
        'icons': {},
        'version': False,
    }
    
    # Check theme files
    theme_files = ['dark_theme.qss', 'light_theme.qss']
    for theme in theme_files:
        theme_path = get_theme_path(theme)
        results['themes'][theme] = os.path.exists(theme_path)
    
    # Check essential icon files
    icon_files = [
        'tray_icon.ico', 'tray_icon.svg',
        'search.svg', 'refresh.svg',
        'lock_locked.svg', 'lock_unlocked.svg',
        'checkbox_checked.svg', 'checkbox_unchecked.svg'
    ]
    
    for icon in icon_files:
        icon_path = get_icon_path(icon)
        results['icons'][icon] = os.path.exists(icon_path)
    
    # Check version file
    version_path = resource_path('VERSION')
    results['version'] = os.path.exists(version_path)
    
    return results


# Convenience functions for common resources
def get_dark_theme_path():
    """Get path to dark theme file"""
    return get_theme_path('dark_theme.qss')


def get_light_theme_path():
    """Get path to light theme file"""
    return get_theme_path('light_theme.qss')


def get_tray_icon_path():
    """Get path to tray icon file"""
    return get_icon_path('tray_icon.ico')


def get_search_icon_path():
    """Get path to search icon"""
    return get_icon_path('search.svg')


def load_theme_with_icons(theme_filename):
    """
    Load theme file and process icon paths
    
    Args:
        theme_filename (str): Theme filename (e.g., 'dark_theme.qss')
        
    Returns:
        str: Processed theme content with resolved icon paths
    """
    theme_path = get_theme_path(theme_filename)
    
    try:
        with open(theme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Process icon paths in the theme file
        # Replace relative icon paths with absolute paths
        import re
        
        # Pattern to find icon references in QSS files
        # Matches patterns like: url(icons/icon_name.svg)
        icon_pattern = r'url\(([^)]*icons/[^)]*)\)'
        
        def replace_icon_path(match):
            relative_path = match.group(1)
            # Extract just the filename from the path
            icon_filename = os.path.basename(relative_path)
            # Get the absolute path for the icon
            absolute_path = get_icon_path(icon_filename)
            # Convert to forward slashes for QSS
            absolute_path = absolute_path.replace('\\', '/')
            return f'url({absolute_path})'
        
        # Replace all icon paths
        processed_content = re.sub(icon_pattern, replace_icon_path, content)
        
        return processed_content
        
    except (FileNotFoundError, IOError) as e:
        print(f"Warning: Could not load theme file {theme_path}: {e}")
        return ""


if __name__ == "__main__":
    # Test the resource paths
    print("Testing resource paths...")
    print(f"Base path: {resource_path('')}")
    print(f"Dark theme: {get_dark_theme_path()}")
    print(f"Tray icon: {get_tray_icon_path()}")
    print(f"Version: {get_version()}")
    
    print("\nVerifying resources:")
    results = verify_resources()
    for category, items in results.items():
        if isinstance(items, dict):
            for item, exists in items.items():
                status = "OK" if exists else "MISSING"
                print(f"  {status} {category}/{item}")
        else:
            status = "OK" if items else "MISSING"
            print(f"  {status} {category}")