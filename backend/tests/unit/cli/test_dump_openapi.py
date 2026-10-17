import json
from pathlib import Path

from app.cli.dump_openapi import dump_openapi


def test_dump_openapi_creates_file(tmp_path: Path) -> None:
    """Проверяет что файл создаётся"""
    output = tmp_path / "docs.json"
    dump_openapi(output)
    assert output.exists()


def test_dump_openapi_valid_json(tmp_path: Path) -> None:
    """Проверяет что содержимое — валидный JSON"""
    output = tmp_path / "docs.json"
    dump_openapi(output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_dump_openapi_has_openapi_key(tmp_path: Path) -> None:
    """Проверяет наличие ключа openapi"""
    output = tmp_path / "docs.json"
    dump_openapi(output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "openapi" in payload


def test_dump_openapi_has_paths(tmp_path: Path) -> None:
    """Проверяет наличие стандартных путей"""
    output = tmp_path / "docs.json"
    dump_openapi(output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    paths = payload["paths"]
    assert "/health" in paths
    assert "/ready" in paths
    assert "/search" in paths
    assert "/documents/{doc_id}" in paths


def test_dump_openapi_unicode_not_escaped(tmp_path: Path) -> None:
    """Проверяет что русские описания не экранируются"""
    output = tmp_path / "docs.json"
    dump_openapi(output)
    text = output.read_text(encoding="utf-8")
    assert "Документ" in text or "документ" in text