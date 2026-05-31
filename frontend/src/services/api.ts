/** API service – communicates with the FastAPI backend. */

import axios from 'axios';
import type { UmlDiagram } from '../types/uml';
import type { PipelineState } from '../types/pipeline';

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
});

// ─── Files ──────────────────────────────────────────────

export async function listDiagrams(): Promise<Array<{
  name: string; path: string; size: number; modified: string;
}>> {
  const { data } = await api.get('/files/list');
  return data.files;
}

export async function saveDiagram(diagram: UmlDiagram, filename?: string): Promise<{
  success: boolean; filepath: string; filename: string;
}> {
  const params = filename ? `?filename=${encodeURIComponent(filename)}` : '';
  const { data } = await api.post(`/files/save${params}`, diagram);
  return data;
}

export async function openDiagram(filepath: string): Promise<UmlDiagram> {
  const { data } = await api.get('/files/open', { params: { filepath } });
  return data.diagram;
}

export async function newDiagram(name = 'Untitled'): Promise<UmlDiagram> {
  const { data } = await api.post('/files/new', null, { params: { name } });
  return data.diagram;
}

export async function exportMarkdown(diagram: UmlDiagram): Promise<string> {
  const { data } = await api.post('/files/export/markdown', { diagram });
  return data;
}

export async function uploadExcel(file: File): Promise<{
  filename: string; sheets: Record<string, unknown[]>; sheet_names: string[];
}> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/files/upload/excel', form);
  return data;
}

// ─── LLM ────────────────────────────────────────────────

export async function getSupportedLanguages(): Promise<string[]> {
  const { data } = await api.get('/llm/languages');
  return data.languages;
}

export async function llmChat(prompt: string, systemPrompt?: string): Promise<string> {
  const { data } = await api.post('/llm/chat', {
    prompt,
    system_prompt: systemPrompt,
  });
  return data.content;
}

export async function generateCode(
  diagram: UmlDiagram, language: string
): Promise<{ language: string; files: Record<string, string> }> {
  const { data } = await api.post('/llm/generate-code', { diagram, language });
  return data;
}

export async function optimizeUml(
  diagram: UmlDiagram, instructions = ''
): Promise<{
  original: UmlDiagram;
  optimized: UmlDiagram;
  changes_summary: string;
  diff: string;
}> {
  const { data } = await api.post('/llm/optimize-uml', { diagram, instructions });
  return data;
}

// ─── Pipeline ───────────────────────────────────────────

export async function createPipeline(diagramId: string, diagram: UmlDiagram): Promise<PipelineState> {
  const { data } = await api.post('/pipeline/create', {
    diagram_id: diagramId,
    diagram: diagram,
  });
  return data.pipeline;
}

export async function getPipeline(pipelineId: string): Promise<PipelineState> {
  const { data } = await api.get(`/pipeline/${pipelineId}`);
  return data.pipeline;
}

export async function confirmStage(
  pipelineId: string, stage: string, accepted: boolean, comment = ''
): Promise<PipelineState> {
  const { data } = await api.post(`/pipeline/${pipelineId}/confirm`, {
    stage, accepted, comment,
  });
  return data.pipeline;
}

export async function resumePipeline(
  pipelineId: string, diagram: UmlDiagram, language = 'python'
): Promise<{ events: unknown[]; pipeline: PipelineState }> {
  const { data } = await api.post(
    `/pipeline/${pipelineId}/resume`, diagram, { params: { language } }
  );
  return data;
}

export function createPipelineWs(
  pipelineId: string,
  diagram: UmlDiagram,
  language = 'python',
  autoConfirm = false,
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/pipeline/ws/${pipelineId}`;
  const ws = new WebSocket(wsUrl);
  ws.onopen = () => {
    ws.send(JSON.stringify({ diagram, language, auto_confirm: autoConfirm }));
  };
  return ws;
}

// ─── Browse directories ────────────────────────────────

export interface BrowseResult {
  current: string;
  parent: string;
  dirs: Array<{ name: string; path: string }>;
  files: Array<{
    name: string; path: string; size: number; modified: string;
  }>;
}

export async function browseDirectory(path?: string): Promise<BrowseResult> {
  const params = path ? `?path=${encodeURIComponent(path)}` : '';
  const { data } = await api.get(`/files/browse${params}`);
  return data;
}

// ─── Review ────────────────────────────────────────────

// ─── TestHub ──────────────────────────────────────────

export async function listTestFiles(): Promise<{
  files: Array<{ name: string; path: string; size: number; modified: string }>;
  testhub_dir: string;
}> {
  const { data } = await api.get('/testhub/list');
  return data;
}

export async function loadTestFile(filename: string): Promise<{
  filename: string;
  sheets: Record<string, { headers: string[]; rows: Record<string, string>[] }>;
  sheet_names: string[];
  filepath: string;
}> {
  const { data } = await api.get('/testhub/load', { params: { filename } });
  return data;
}

export async function saveTestFile(req: {
  filename: string;
  sheets: Record<string, { headers: string[]; rows: Record<string, string>[] }>;
}): Promise<{ success: boolean; filename: string }> {
  const { data } = await api.post('/testhub/save', req);
  return data;
}

export async function generateTestCode(req: {
  filename: string;
  sheets: Record<string, unknown>;
  language: string;
  mode: 'full' | 'incremental';
  changed_cases?: Array<Record<string, unknown>>;
}): Promise<{ files: Record<string, string>; language: string; mode: string }> {
  const { data } = await api.post('/testhub/generate-tests', req);
  return data;
}

export async function saveTestReview(req: {
  action: string;
  comment: string;
  filename: string;
  sheet: string;
  case_id: string;
  details: string;
}): Promise<{ success: boolean; file: string }> {
  const { data } = await api.post('/testhub/save-review', req);
  return data;
}

// ─── Review ────────────────────────────────────────────

export async function saveReview(review: {
  action: string;
  comment: string;
  requirements: string;
  original_name: string;
  optimized_name: string;
  timestamp: string;
}): Promise<{ success: boolean; file: string }> {
  const { data } = await api.post('/files/save-review', review);
  return data;
}
