/** UML data types – mirrors backend Pydantic models */

export enum Visibility {
  PUBLIC = '+',
  PRIVATE = '-',
  PROTECTED = '#',
}

export enum Stereotype {
  CLASS = 'class',
  INTERFACE = 'interface',
  ABSTRACT = 'abstract',
  ENUM = 'enum',
}

export enum RelationType {
  INHERITANCE = 'inheritance',
  COMPOSITION = 'composition',
  AGGREGATION = 'aggregation',
  ASSOCIATION = 'association',
  REALIZATION = 'realization',
  DEPENDENCY = 'dependency',
}

export interface UmlAttribute {
  name: string;
  type: string;
  visibility: Visibility;
  default_value?: string;
  is_static: boolean;
}

export interface UmlMethod {
  name: string;
  return_type: string;
  params: string;
  visibility: Visibility;
  is_static: boolean;
  is_abstract: boolean;
}

export interface Position {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

export interface UmlClass {
  id: string;
  name: string;
  stereotype: Stereotype;
  attributes: UmlAttribute[];
  methods: UmlMethod[];
  position: Position;
  size: Size;
  note: string;
}

export interface UmlRelation {
  id: string;
  source: string;
  target: string;
  type: RelationType;
  multiplicity_source: string;
  multiplicity_target: string;
  role_name: string;
  note: string;
}

import type { SeqLifeline, SeqMessage } from './sequence';
import type { CompNode, CompRelation } from './component';

export interface UmlDiagram {
  version: string;
  name: string;
  diagram_type?: string;  // "class" | "sequence" | "component"
  // Class diagram
  classes: UmlClass[];
  relations: UmlRelation[];
  // Sequence diagram
  lifelines?: SeqLifeline[];
  messages?: SeqMessage[];
  // Component diagram
  components?: CompNode[];
  comp_relations?: CompRelation[];
  // View
  grid_visible: boolean;
  grid_size: number;
  grid_color: string;
  grid_thickness: number;
  snap_to_grid: boolean;
  zoom: number;
  pan_x: number;
  pan_y: number;
}

export function createDefaultDiagram(name = 'Untitled'): UmlDiagram {
  return {
    version: '1.0',
    name,
    diagram_type: 'class',
    classes: [],
    relations: [],
    lifelines: [],
    messages: [],
    components: [],
    comp_relations: [],
    grid_visible: true,
    grid_size: 20,
    grid_color: '#e0e0e0',
    grid_thickness: 1,
    snap_to_grid: true,
    zoom: 1.0,
    pan_x: 0,
    pan_y: 0,
  };
}

export function createDefaultClass(position?: Position): UmlClass {
  return {
    id: `class_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name: 'NewClass',
    stereotype: Stereotype.CLASS,
    attributes: [],
    methods: [],
    position: position || { x: 100, y: 100 },
    size: { width: 200, height: 150 },
    note: '',
  };
}

export function createDefaultRelation(source: string, target: string): UmlRelation {
  return {
    id: `rel_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    source,
    target,
    type: RelationType.ASSOCIATION,
    multiplicity_source: '',
    multiplicity_target: '',
    role_name: '',
    note: '',
  };
}

// ── Project (multi-diagram container) ─────────────────

export interface Project {
  version: string;
  name: string;
  diagrams: UmlDiagram[];
  active_diagram_index: number;
}

export function createDefaultProject(name = 'Untitled'): Project {
  return {
    version: '1.0',
    name,
    diagrams: [createDefaultDiagram(name)],
    active_diagram_index: 0,
  };
}
