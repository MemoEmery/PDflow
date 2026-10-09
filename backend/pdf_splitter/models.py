"""Parâmetros estruturados da separação. A instrução do usuário NUNCA é executada diretamente:
ela é convertida (por IA ou heurística) neste modelo, validada e mostrada ao usuário antes de qualquer uso."""
from typing import Literal
import regex
from pydantic import BaseModel, Field, field_validator, model_validator

IdType = Literal["none", "cpf", "cnpj", "process", "invoice_number", "contract_number", "customer_name", "custom_regex"]

class Identifier(BaseModel):
    type: IdType = "none"
    regex: str | None = Field(None, max_length=200)
    label: str | None = Field(None, max_length=40)
    location: Literal["page_start", "anywhere"] = "anywhere"

    @field_validator("regex")
    @classmethod
    def _ok(cls, v):
        if v:
            try: regex.compile(v)
            except regex.error: raise ValueError("expressão regular inválida")
        return v

class SplitParams(BaseModel):
    strategy: Literal["keyword", "pattern", "identifier", "semantic", "combined"] = "keyword"
    start_keywords: list[str] = Field(default_factory=list, max_length=20)
    start_regexes: list[str] = Field(default_factory=list, max_length=10)
    keyword_location: Literal["header", "anywhere"] = "anywhere"
    identifier: Identifier = Field(default_factory=Identifier)
    combine: Literal["any", "all"] = "any"
    document_type: str | None = Field(None, max_length=40)
    min_document_pages: int = Field(1, ge=1, le=500)
    allow_single_page_documents: bool = True
    confidence_threshold: float = Field(0.85, ge=0.5, le=1.0)
    name_template: str = Field("{identifier}", max_length=60)

    @field_validator("start_keywords")
    @classmethod
    def _kw(cls, v):
        v = [k.strip() for k in v if k and k.strip()]
        if any(len(k) > 80 for k in v): raise ValueError("palavra-chave muito longa")
        return v

    @field_validator("start_regexes")
    @classmethod
    def _rx(cls, v):
        v = [r.strip() for r in v if r and r.strip()]
        for r in v:
            if len(r) > 200: raise ValueError("expressão regular muito longa")
            try: regex.compile(r)
            except regex.error: raise ValueError(f"expressão regular inválida: {r[:40]}")
        return v

    @model_validator(mode="after")
    def _needs(self):
        has = {"keyword": bool(self.start_keywords), "pattern": bool(self.start_regexes),
               "identifier": self.identifier.type != "none"}
        if self.identifier.type == "custom_regex" and not self.identifier.regex:
            raise ValueError("informe a expressão do identificador personalizado")
        if self.strategy in has and not has[self.strategy]:
            raise ValueError({"keyword": "informe ao menos uma palavra-chave", "pattern": "informe ao menos uma expressão regular",
                              "identifier": "escolha o tipo de identificador"}[self.strategy])
        if self.strategy == "combined" and not any(has.values()):
            raise ValueError("a estratégia combinada precisa de ao menos um critério")
        return self
