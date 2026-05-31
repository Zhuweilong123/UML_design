/** Diagram store – manages the UML diagram state and operations. */

import { create } from 'zustand';
import type { UmlDiagram, UmlClass, UmlRelation, Position, Size } from '../types/uml';
import { createDefaultDiagram, createDefaultClass, createDefaultRelation } from '../types/uml';

// Undo/Redo snapshot
interface Snapshot {
  diagram: UmlDiagram;
  timestamp: number;
}

interface DiagramState {
  // Core state
  diagram: UmlDiagram;
  selectedClassId: string | null;
  selectedRelationId: string | null;
  isModified: boolean;
  currentFilepath: string | null;

  // History
  undoStack: Snapshot[];
  redoStack: Snapshot[];
  lastOperationTime: number;
  maxHistorySteps: number;
  mergeWindowMs: number;

  // Actions
  setDiagram: (diagram: UmlDiagram) => void;
  newDiagram: (name?: string) => void;
  markModified: () => void;

  // Class operations
  addClass: (position?: Position) => void;
  removeClass: (id: string) => void;
  updateClass: (id: string, updates: Partial<UmlClass>) => void;
  moveClass: (id: string, position: Position) => void;
  resizeClass: (id: string, size: Size) => void;
  selectClass: (id: string | null) => void;

  // Relation operations
  addRelation: (source: string, target: string) => void;
  removeRelation: (id: string) => void;
  updateRelation: (id: string, updates: Partial<UmlRelation>) => void;
  selectRelation: (id: string | null) => void;

  // Grid
  toggleGrid: () => void;
  setGridSize: (size: number) => void;
  setGridColor: (color: string) => void;
  setGridThickness: (thickness: number) => void;
  toggleSnapToGrid: () => void;

  // View
  setZoom: (zoom: number) => void;
  setPan: (x: number, y: number) => void;

  // Undo/Redo
  undo: () => void;
  redo: () => void;
  pushSnapshot: (operation: string) => void;
  clearHistory: () => void;

  // File
  setCurrentFilepath: (path: string | null) => void;
}

export const useDiagramStore = create<DiagramState>((set, get) => ({
  diagram: createDefaultDiagram(),
  selectedClassId: null,
  selectedRelationId: null,
  isModified: false,
  currentFilepath: null,
  undoStack: [],
  redoStack: [],
  lastOperationTime: 0,
  maxHistorySteps: 50,
  mergeWindowMs: 500,

  setDiagram: (diagram) => set({ diagram, isModified: false, currentFilepath: null }),

  newDiagram: (name) => set({
    diagram: createDefaultDiagram(name),
    selectedClassId: null,
    selectedRelationId: null,
    isModified: false,
    currentFilepath: null,
    undoStack: [],
    redoStack: [],
  }),

  markModified: () => set({ isModified: true }),

  addClass: (position) => {
    const state = get();
    const newClass = createDefaultClass(position);
    get().pushSnapshot('add_class');
    set({
      diagram: {
        ...state.diagram,
        classes: [...state.diagram.classes, newClass],
      },
      selectedClassId: newClass.id,
      selectedRelationId: null,
      isModified: true,
    });
  },

  removeClass: (id) => {
    const state = get();
    get().pushSnapshot('remove_class');
    set({
      diagram: {
        ...state.diagram,
        classes: state.diagram.classes.filter((c) => c.id !== id),
        relations: state.diagram.relations.filter(
          (r) => r.source !== id && r.target !== id
        ),
      },
      selectedClassId: state.selectedClassId === id ? null : state.selectedClassId,
      isModified: true,
    });
  },

  updateClass: (id, updates) => {
    const state = get();
    get().pushSnapshot('update_class');
    set({
      diagram: {
        ...state.diagram,
        classes: state.diagram.classes.map((c) =>
          c.id === id ? { ...c, ...updates } : c
        ),
      },
      isModified: true,
    });
  },

  moveClass: (id, position) => {
    const state = get();
    const now = Date.now();
    // Merge with previous move if within window
    if (state.lastOperationTime && (now - state.lastOperationTime) < state.mergeWindowMs) {
      get().redoStack.pop(); // Remove last redo entry
    } else {
      get().pushSnapshot('move_class');
    }
    set({
      diagram: {
        ...state.diagram,
        classes: state.diagram.classes.map((c) =>
          c.id === id ? { ...c, position } : c
        ),
      },
      lastOperationTime: now,
      isModified: true,
    });
  },

  resizeClass: (id, size) => {
    const state = get();
    get().pushSnapshot('resize_class');
    set({
      diagram: {
        ...state.diagram,
        classes: state.diagram.classes.map((c) =>
          c.id === id ? { ...c, size } : c
        ),
      },
      isModified: true,
    });
  },

  selectClass: (id) => set({ selectedClassId: id, selectedRelationId: null }),

  addRelation: (source, target) => {
    const state = get();
    const newRel = createDefaultRelation(source, target);
    get().pushSnapshot('add_relation');
    set({
      diagram: {
        ...state.diagram,
        relations: [...state.diagram.relations, newRel],
      },
      selectedRelationId: newRel.id,
      selectedClassId: null,
      isModified: true,
    });
  },

  removeRelation: (id) => {
    const state = get();
    get().pushSnapshot('remove_relation');
    set({
      diagram: {
        ...state.diagram,
        relations: state.diagram.relations.filter((r) => r.id !== id),
      },
      selectedRelationId: state.selectedRelationId === id ? null : state.selectedRelationId,
      isModified: true,
    });
  },

  updateRelation: (id, updates) => {
    const state = get();
    get().pushSnapshot('update_relation');
    set({
      diagram: {
        ...state.diagram,
        relations: state.diagram.relations.map((r) =>
          r.id === id ? { ...r, ...updates } : r
        ),
      },
      isModified: true,
    });
  },

  selectRelation: (id) => set({ selectedRelationId: id, selectedClassId: null }),

  toggleGrid: () => {
    const state = get();
    set({ diagram: { ...state.diagram, grid_visible: !state.diagram.grid_visible } });
  },

  setGridSize: (size) => {
    const state = get();
    set({ diagram: { ...state.diagram, grid_size: size } });
  },

  setGridColor: (color) => {
    const state = get();
    set({ diagram: { ...state.diagram, grid_color: color } });
  },

  setGridThickness: (thickness) => {
    const state = get();
    set({ diagram: { ...state.diagram, grid_thickness: thickness } });
  },

  toggleSnapToGrid: () => {
    const state = get();
    set({ diagram: { ...state.diagram, snap_to_grid: !state.diagram.snap_to_grid } });
  },

  setZoom: (zoom) => {
    const state = get();
    set({ diagram: { ...state.diagram, zoom: Math.max(0.1, Math.min(5, zoom)) } });
  },

  setPan: (x, y) => {
    const state = get();
    set({ diagram: { ...state.diagram, pan_x: x, pan_y: y } });
  },

  pushSnapshot: (_operation) => {
    const state = get();
    const snapshot: Snapshot = {
      diagram: JSON.parse(JSON.stringify(state.diagram)),
      timestamp: Date.now(),
    };
    const newUndo = [...state.undoStack, snapshot].slice(-state.maxHistorySteps);
    set({ undoStack: newUndo, redoStack: [] });
  },

  undo: () => {
    const state = get();
    if (state.undoStack.length === 0) return;
    const currentSnapshot: Snapshot = {
      diagram: JSON.parse(JSON.stringify(state.diagram)),
      timestamp: Date.now(),
    };
    const newUndo = [...state.undoStack];
    const target = newUndo.pop()!;
    const newRedo = [...state.redoStack, currentSnapshot];
    set({
      diagram: target.diagram,
      undoStack: newUndo,
      redoStack: newRedo,
      isModified: true,
    });
  },

  redo: () => {
    const state = get();
    if (state.redoStack.length === 0) return;
    const currentSnapshot: Snapshot = {
      diagram: JSON.parse(JSON.stringify(state.diagram)),
      timestamp: Date.now(),
    };
    const newRedo = [...state.redoStack];
    const target = newRedo.pop()!;
    const newUndo = [...state.undoStack, currentSnapshot];
    set({
      diagram: target.diagram,
      undoStack: newUndo,
      redoStack: newRedo,
      isModified: true,
    });
  },

  clearHistory: () => set({ undoStack: [], redoStack: [], lastOperationTime: 0 }),

  setCurrentFilepath: (path) => set({ currentFilepath: path }),
}));
