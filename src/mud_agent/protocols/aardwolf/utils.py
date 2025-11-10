"""
Utility functions for Aardwolf GMCP.

This module provides utility functions for working with GMCP data.
"""

from typing import Any


def deep_copy_dict(d: Any) -> Any:
    """Create a deep copy of a dictionary.

    Args:
        d: The dictionary to copy

    Returns:
        Any: A deep copy of the dictionary
    """
    if not isinstance(d, dict):
        return d

    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = deep_copy_dict(v)
        elif isinstance(v, list):
            result[k] = [
                deep_copy_dict(item) if isinstance(item, dict) else item for item in v
            ]
        else:
            result[k] = v

    return result


def deep_update_dict(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Deep update a target dictionary with a source dictionary.

    Args:
        target: The target dictionary to update
        source: The source dictionary with new values
    """
    for k, v in source.items():
        if k in target and isinstance(target[k], dict) and isinstance(v, dict):
            deep_update_dict(target[k], v)
        else:
            target[k] = v


def extract_coordinates(data: dict[str, Any]) -> dict[str, int]:
    """Extract coordinates from GMCP data.

    Args:
        data: The GMCP data to extract coordinates from

    Returns:
        dict: The extracted coordinates
    """
    coords = {}

    # Check for coordinates in different formats
    if "coord" in data and isinstance(data["coord"], dict):
        coords = data["coord"]
    elif "coords" in data and isinstance(data["coords"], dict):
        coords = data["coords"]
    elif "coordinates" in data and isinstance(data["coordinates"], dict):
        coords = data["coordinates"]

    # Ensure x, y, z are present
    if "x" not in coords:
        coords["x"] = 0
    if "y" not in coords:
        coords["y"] = 0
    if "z" not in coords:
        coords["z"] = 0

    return coords


def extract_exits(data: dict[str, Any]) -> list[str]:
    """Extract exits from GMCP data.

    Args:
        data: The GMCP data to extract exits from

    Returns:
        list: The extracted exits
    """
    exits = []

    # Check for exits in different formats
    if "exits" in data:
        if isinstance(data["exits"], dict):
            exits = list(data["exits"].keys())
        elif isinstance(data["exits"], list):
            exits = data["exits"]

    return exits
