"""UML data models based on the design document specifications."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class Visibility(str, Enum):
    PUBLIC = "+"
    PRIVATE = "-"
    PROTECTED = "#"


class Stereotype(str, Enum):
    CLASS = "class"
    INTERFACE = "interface"
    ABSTRACT = "abstract"
    ENUM = "enum"


class RelationType(str, Enum):
    INHERITANCE = "inheritance"
    COMPOSITION = "composition"
    AGGREGATION = "aggregation"
    ASSOCIATION = "association"
    REALIZATION = "realization"
    DEPENDENCY = "dependency"


# ---------- UML Attribute / Method ----------

class UmlAttribute(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = ""
    type: str = ""
    visibility: Visibility = Visibility.PUBLIC
    default_value: Optional[str] = None
    is_static: bool = False


class UmlMethod(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = ""
    return_type: str = ""
    params: str = ""
    visibility: Visibility = Visibility.PUBLIC
    is_static: bool = False
    is_abstract: bool = False


# ---------- UML Class ----------

class Position(BaseModel):
    x: float = 0
    y: float = 0


class Size(BaseModel):
    width: float = 200
    height: float = 150


class UmlClass(BaseModel):
    model_config = {"extra": "ignore"}
    id: str
    name: str = "NewClass"
    stereotype: Stereotype = Stereotype.CLASS
    attributes: list[UmlAttribute] = Field(default_factory=list)
    methods: list[UmlMethod] = Field(default_factory=list)
    position: Position = Field(default_factory=Position)
    size: Size = Field(default_factory=Size)
    note: str = ""


# ---------- UML Relation ----------

class UmlRelation(BaseModel):
    model_config = {"extra": "ignore"}
    id: str
    source: str
    target: str
    type: RelationType = RelationType.ASSOCIATION
    multiplicity_source: str = ""
    multiplicity_target: str = ""
    role_name: str = ""
    note: str = ""


# ---------- UML Diagram (file format) ----------

class UmlDiagram(BaseModel):
    model_config = {"extra": "ignore"}
    version: str = "1.0"
    name: str = "Untitled"
    classes: list[UmlClass] = Field(default_factory=list)
    relations: list[UmlRelation] = Field(default_factory=list)
    grid_visible: bool = True
    grid_size: int = 20
    grid_color: str = "#e0e0e0"
    grid_thickness: int = 1
    snap_to_grid: bool = True
    zoom: float = 1.0
    pan_x: float = 0
    pan_y: float = 0


# ---------- LLM ----------

class LlmRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096


class LlmResponse(BaseModel):
    content: str
    usage: dict = Field(default_factory=dict)


class CodeGenRequest(BaseModel):
    diagram: UmlDiagram
    language: str  # one of 12 supported languages
    include_tests: bool = False


class CodeGenResponse(BaseModel):
    language: str
    files: dict[str, str]  # filename -> content


class UmlOptimizeRequest(BaseModel):
    diagram: UmlDiagram
    instructions: str = ""


class UmlOptimizeResponse(BaseModel):
    original: UmlDiagram
    optimized: UmlDiagram
    changes_summary: str
    diff: str


# ---------- Markdown Export ----------

class ExportRequest(BaseModel):
    diagram: UmlDiagram
