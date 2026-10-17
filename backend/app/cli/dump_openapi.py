import argparse
import json
from pathlib import Path

from app.main import create_app


def dump_openapi(output: Path) -> None:
    """Сохраняет OpenAPI-схему приложения в файл"""
    application = create_app()
    schema = application.openapi()
    output.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(description="Dump FastAPI OpenAPI schema")
    parser.add_argument("--output", type=Path, default=Path("docs.json"), help="Output path")
    return parser.parse_args()


def main() -> None:
    """CLI-точка входа для дампа OpenAPI"""
    args = parse_args()
    dump_openapi(args.output)


if __name__ == "__main__":
    main()