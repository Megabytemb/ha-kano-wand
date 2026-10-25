"""Tests for Home Assistant & HACS metadata files, translations, and brand assets."""
from __future__ import annotations

import json
from pathlib import Path
import struct

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
COMPONENT_DIR = ROOT_DIR / "custom_components" / "kano_wand"


def test_manifest_json_and_hassfest_key_order() -> None:
    """Verify manifest.json is valid and follows Hassfest key ordering (domain, name, alphabetical)."""
    manifest = json.loads((COMPONENT_DIR / "manifest.json").read_text(encoding="utf-8"))
    keys = list(manifest.keys())
    assert keys[0] == "domain"
    assert keys[1] == "name"
    assert keys[2:] == sorted(keys[2:]), "manifest.json keys after 'name' must be alphabetical for Hassfest"
    assert manifest["domain"] == "kano_wand"
    assert manifest["config_flow"] is True


def test_hacs_json_configuration() -> None:
    """Verify hacs.json configures zipped release installation."""
    hacs_cfg = json.loads((ROOT_DIR / "hacs.json").read_text(encoding="utf-8"))
    assert hacs_cfg["zip_release"] is True
    assert hacs_cfg["filename"] == "kano_wand.zip"


def test_strings_and_en_translations_match() -> None:
    """Verify strings.json and translations/en.json are in sync."""
    strings_cfg = json.loads((COMPONENT_DIR / "strings.json").read_text(encoding="utf-8"))
    en_cfg = json.loads((COMPONENT_DIR / "translations" / "en.json").read_text(encoding="utf-8"))
    assert strings_cfg == en_cfg


@pytest.mark.parametrize(
    "filename,expected_size",
    [
        ("icon.png", (256, 256)),
        ("icon@2x.png", (512, 512)),
        ("logo.png", (512, 256)),
        ("logo@2x.png", (1024, 512)),
        ("dark_logo.png", (512, 256)),
        ("dark_logo@2x.png", (1024, 512)),
    ],
)
def test_brand_rgba_png_assets(filename: str, expected_size: tuple[int, int]) -> None:
    """Verify all 6 local brand images exist and are valid RGBA PNGs with expected dimensions."""
    path = COMPONENT_DIR / "brand" / filename
    assert path.is_file(), f"Missing brand image: {filename}"
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
    assert (width, height) == expected_size
    assert bit_depth == 8
    assert color_type == 6  # RGBA with transparent background
