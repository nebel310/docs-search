from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.db.models import Document
from app.schemas.document import DocumentOut


def _payload() -> dict:
    """Возвращает валидный payload документа"""
    return {
        "id": 1,
        "rubrics": ["python"],
        "text": "hello",
        "created_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }


def test_document_out_from_valid_payload() -> None:
    """Проверяет создание схемы из валидного payload"""
    document = DocumentOut(**_payload())
    assert document.id == 1
    assert document.rubrics == ["python"]
    assert document.text == "hello"
    assert document.created_date == datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_document_out_from_orm_model() -> None:
    """Проверяет маппинг из ORM-модели через from_attributes"""
    model = Document(
        id=7,
        rubrics=["a", "b"],
        text="orm",
        created_date=datetime(2024, 5, 5, tzinfo=timezone.utc),
    )
    document = DocumentOut.model_validate(model)
    assert document.id == 7
    assert document.rubrics == ["a", "b"]
    assert document.text == "orm"


def test_document_out_missing_id_raises() -> None:
    """Проверяет ошибку при отсутствии id"""
    payload = _payload()
    payload.pop("id")
    with pytest.raises(ValidationError):
        DocumentOut(**payload)


def test_document_out_missing_text_raises() -> None:
    """Проверяет ошибку при отсутствии text"""
    payload = _payload()
    payload.pop("text")
    with pytest.raises(ValidationError):
        DocumentOut(**payload)


def test_document_out_invalid_rubrics_type_raises() -> None:
    """Проверяет ошибку при невалидном типе rubrics"""
    payload = _payload()
    payload["rubrics"] = "not-a-list"
    with pytest.raises(ValidationError):
        DocumentOut(**payload)


def test_document_out_invalid_created_date_raises() -> None:
    """Проверяет ошибку при невалидном created_date"""
    payload = _payload()
    payload["created_date"] = "not-a-date"
    with pytest.raises(ValidationError):
        DocumentOut(**payload)


def test_document_out_empty_rubrics_allowed() -> None:
    """Проверяет что пустой список рубрик допустим"""
    payload = _payload()
    payload["rubrics"] = []
    document = DocumentOut(**payload)
    assert document.rubrics == []


def test_document_out_empty_text_allowed() -> None:
    """Проверяет что пустой текст допустим"""
    payload = _payload()
    payload["text"] = ""
    document = DocumentOut(**payload)
    assert document.text == ""


def test_document_out_serialization_roundtrip() -> None:
    """Проверяет сериализацию и обратную десериализацию"""
    document = DocumentOut(**_payload())
    dumped = document.model_dump()
    again = DocumentOut(**dumped)
    assert again == document


def test_document_out_json_schema_has_descriptions() -> None:
    """Проверяет наличие описаний в JSON-схеме"""
    schema = DocumentOut.model_json_schema()
    assert schema["properties"]["id"]["description"]
    assert schema["properties"]["text"]["description"]
    assert schema["properties"]["rubrics"]["description"]
    assert schema["properties"]["created_date"]["description"]