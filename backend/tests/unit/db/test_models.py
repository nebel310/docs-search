from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Text
from sqlalchemy.dialects.postgresql import ARRAY

from app.db.base import Base
from app.db.models import Document


def test_document_tablename() -> None:
    """Проверяет имя таблицы документа"""
    assert Document.__tablename__ == "documents"


def test_document_registered_in_metadata() -> None:
    """Проверяет что модель зарегистрирована в metadata"""
    assert "documents" in Base.metadata.tables


def test_document_has_all_columns() -> None:
    """Проверяет наличие всех обязательных колонок"""
    columns = Document.__table__.columns
    assert "id" in columns
    assert "rubrics" in columns
    assert "text" in columns
    assert "created_date" in columns


def test_document_id_is_biginteger_primary_key() -> None:
    """Проверяет тип и роль колонки id"""
    column = Document.__table__.columns["id"]
    assert isinstance(column.type, BigInteger)
    assert column.primary_key is True
    assert column.autoincrement is True


def test_document_rubrics_is_array_of_text() -> None:
    """Проверяет тип колонки rubrics"""
    column = Document.__table__.columns["rubrics"]
    assert isinstance(column.type, ARRAY)
    assert isinstance(column.type.item_type, Text)


def test_document_text_is_text() -> None:
    """Проверяет тип колонки text"""
    column = Document.__table__.columns["text"]
    assert isinstance(column.type, Text)


def test_document_created_date_is_timestamptz() -> None:
    """Проверяет тип и timezone колонки created_date"""
    column = Document.__table__.columns["created_date"]
    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True


def test_document_non_pk_columns_not_nullable() -> None:
    """Проверяет что rubrics, text и created_date обязательны"""
    columns = Document.__table__.columns
    assert columns["rubrics"].nullable is False
    assert columns["text"].nullable is False
    assert columns["created_date"].nullable is False


def test_document_instantiation() -> None:
    """Проверяет что экземпляр модели создаётся с валидными полями"""
    now = datetime.now(timezone.utc)
    doc = Document(rubrics=["python", "backend"], text="hello world", created_date=now)
    assert doc.rubrics == ["python", "backend"]
    assert doc.text == "hello world"
    assert doc.created_date == now


def test_document_empty_rubrics_allowed() -> None:
    """Проверяет что пустой список рубрик допустим"""
    doc = Document(rubrics=[], text="empty", created_date=datetime.now(timezone.utc))
    assert doc.rubrics == []


def test_document_empty_text_allowed() -> None:
    """Проверяет что пустой текст допустим"""
    doc = Document(rubrics=["a"], text="", created_date=datetime.now(timezone.utc))
    assert doc.text == ""


def test_document_unicode_text() -> None:
    """Проверяет что текст с юникодом корректно сохраняется в атрибут"""
    doc = Document(rubrics=["ru"], text="привет мир", created_date=datetime.now(timezone.utc))
    assert doc.text == "привет мир"