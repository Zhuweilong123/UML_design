/** UI store – manages UI panel state and global UI preferences. */

import { create } from 'zustand';
import type { UmlDiagram } from '../types/uml';

export type RightPanelTab = 'properties' | 'code' | 'pipeline' | 'diff' | 'testcase';
export type Language = 'python' | 'java' | 'typescript' | 'javascript' | 'csharp' | 'cpp' |
  'go' | 'rust' | 'ruby' | 'swift' | 'kotlin' | 'php';

interface UiState {
  // Panel visibility
  rightPanelVisible: boolean;
  rightPanelTab: RightPanelTab;
  rightPanelWidth: number;

  // Language
  selectedLanguage: Language;

  // Code viewer
  generatedCode: Record<string, string> | null;
  activeCodeFile: string | null;

  // Diff / optimization
  diffContent: string | null;
  originalCode: Record<string, string> | null;
  optimizedCode: Record<string, string> | null;
  originalDiagram: UmlDiagram | null;
  optimizedDiagram: UmlDiagram | null;
  showingOptimized: boolean;
  optimizeInstructions: string; // last optimization request content

  // Pipeline
  activePipelineId: string | null;

  // Modal
  fileDialogVisible: boolean;
  exportDialogVisible: boolean;
  codeGenLoading: boolean;
  currentBrowsePath: string;

  // Actions
  toggleRightPanel: () => void;
  setRightPanelVisible: (visible: boolean) => void;
  setRightPanelTab: (tab: RightPanelTab) => void;
  setRightPanelWidth: (width: number) => void;

  setSelectedLanguage: (lang: Language) => void;

  setGeneratedCode: (code: Record<string, string> | null) => void;
  setActiveCodeFile: (file: string | null) => void;
  setDiffContent: (diff: string | null) => void;
  setOriginalCode: (code: Record<string, string> | null) => void;
  setOptimizedCode: (code: Record<string, string> | null) => void;
  setOptimizationResult: (original: UmlDiagram, optimized: UmlDiagram, diff: string, instructions: string) => void;
  toggleShowingVersion: () => void;
  setShowingOptimized: (v: boolean) => void;

  setActivePipelineId: (id: string | null) => void;

  setFileDialogVisible: (visible: boolean) => void;
  setExportDialogVisible: (visible: boolean) => void;
  setCodeGenLoading: (loading: boolean) => void;
  setCurrentBrowsePath: (path: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  rightPanelVisible: true,
  rightPanelTab: 'properties',
  rightPanelWidth: 420,
  selectedLanguage: 'python',
  generatedCode: null,
  activeCodeFile: null,
  diffContent: null,
  originalCode: null,
  optimizedCode: null,
  originalDiagram: null,
  optimizedDiagram: null,
  showingOptimized: false,
  optimizeInstructions: '',
  activePipelineId: null,
  fileDialogVisible: false,
  exportDialogVisible: false,
  codeGenLoading: false,
  currentBrowsePath: '',

  toggleRightPanel: () => set((s) => ({ rightPanelVisible: !s.rightPanelVisible })),
  setRightPanelVisible: (visible: boolean) => set({ rightPanelVisible: visible }),
  setRightPanelTab: (tab) => set((s) => ({
    rightPanelTab: tab,
    rightPanelVisible: s.rightPanelVisible && s.rightPanelTab !== tab ? true : s.rightPanelVisible,
  })),
  setRightPanelWidth: (width) => set({ rightPanelWidth: width }),

  setSelectedLanguage: (lang) => set({ selectedLanguage: lang }),

  setGeneratedCode: (code) => set({ generatedCode: code, activeCodeFile: code ? Object.keys(code)[0] || null : null }),
  setActiveCodeFile: (file) => set({ activeCodeFile: file }),
  setDiffContent: (diff) => set({ diffContent: diff }),
  setOriginalCode: (code) => set({ originalCode: code }),
  setOptimizedCode: (code) => set({ optimizedCode: code }),

  setOptimizationResult: (original, optimized, diff, instructions) => set({
    originalDiagram: original,
    optimizedDiagram: optimized,
    originalCode: { 'original.uml': JSON.stringify(original, null, 2) },
    optimizedCode: { 'optimized.uml': JSON.stringify(optimized, null, 2) },
    diffContent: diff,
    optimizeInstructions: instructions || '',
    showingOptimized: false,
  }),

  toggleShowingVersion: () => set((s) => ({ showingOptimized: !s.showingOptimized })),
  setShowingOptimized: (v) => set({ showingOptimized: v }),

  setActivePipelineId: (id) => set({ activePipelineId: id }),

  setFileDialogVisible: (visible) => set({ fileDialogVisible: visible }),
  setExportDialogVisible: (visible) => set({ exportDialogVisible: visible }),
  setCodeGenLoading: (loading) => set({ codeGenLoading: loading }),
  setCurrentBrowsePath: (path) => set({ currentBrowsePath: path }),
}));
