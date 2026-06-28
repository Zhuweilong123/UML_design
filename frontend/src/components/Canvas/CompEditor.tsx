/**
 * Component Diagram Editor — powered by AntV X6.
 * Reuses the same X6 patterns as UMLEditor.
 */

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { Button, Tooltip } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { Graph, Node, Edge } from '@antv/x6';
import { History } from '@antv/x6-plugin-history';
import { Transform } from '@antv/x6-plugin-transform';
import { Selection } from '@antv/x6-plugin-selection';
import { Snapline } from '@antv/x6-plugin-snapline';
import { useDiagramStore } from '../../stores/diagramStore';
import { useUiStore } from '../../stores/uiStore';
import type { CompNode, CompRelation } from '../../types/component';
import './CompEditor.css';

// ── Register X6 shapes (once) ────────────────────────

let shapesRegistered = false;
function ensureShapesRegistered() {
  if (shapesRegistered) return;
  shapesRegistered = true;

  Graph.registerNode('comp-component', {
    inherit: 'rect',
    markup: [
      { tagName: 'rect', selector: 'body' },
      {
        tagName: 'foreignObject', selector: 'fo',
        children: [{
          tagName: 'div', ns: 'http://www.w3.org/1999/xhtml', selector: 'content',
          style: {
            width: '100%', height: '100%',
            fontFamily: 'Consolas, Monaco, monospace',
            fontSize: '12px', lineHeight: '1.5', overflow: 'hidden',
          },
        }],
      },
    ],
    attrs: {
      body: { stroke: '#d48806', strokeWidth: 2, fill: '#fffbe6', rx: 6, ry: 6 },
      fo: { refWidth: '100%', refHeight: '100%' },
      content: { html: '' },
    },
    ports: {
      groups: {
        top: {
          position: { name: 'top' },
          markup: [{ tagName: 'circle', selector: 'circle' }],
          attrs: { circle: { r: 5, magnet: true, stroke: '#d48806', strokeWidth: 2, fill: '#fff' } },
        },
        right: {
          position: { name: 'right' },
          markup: [{ tagName: 'circle', selector: 'circle' }],
          attrs: { circle: { r: 5, magnet: true, stroke: '#d48806', strokeWidth: 2, fill: '#fff' } },
        },
        bottom: {
          position: { name: 'bottom' },
          markup: [{ tagName: 'circle', selector: 'circle' }],
          attrs: { circle: { r: 5, magnet: true, stroke: '#d48806', strokeWidth: 2, fill: '#fff' } },
        },
        left: {
          position: { name: 'left' },
          markup: [{ tagName: 'circle', selector: 'circle' }],
          attrs: { circle: { r: 5, magnet: true, stroke: '#d48806', strokeWidth: 2, fill: '#fff' } },
        },
      },
      items: [{ id: 'pt', group: 'top' }, { id: 'pr', group: 'right' }, { id: 'pb', group: 'bottom' }, { id: 'pl', group: 'left' }],
    },
  });

  console.log('[CompEditor] X6 component shapes registered');
}

// ── HTML builder ─────────────────────────────────────

function buildCompHTML(comp: CompNode, selected: boolean): string {
  const isChild = !!comp.parent_id;
  const selClass = selected ? 'selected' : '';
  const childClass = isChild ? 'child' : '';

  // UML 2.5.1 lollipop (provided) and socket (required) notation
  const provided = (comp.provided_interfaces || []).map((i) =>
    `<div class="comp-iface provided"><span class="comp-lollipop">⊃</span> ${i}</div>`
  ).join('');
  const required = (comp.required_interfaces || []).map((i) =>
    `<div class="comp-iface required"><span class="comp-socket">⊂</span> ${i}</div>`
  ).join('');

  return `<div class="comp-node ${childClass} ${selClass}">
    <div class="comp-stereotype">${isChild ? '' : '«component»'}</div>
    <div class="comp-name">${comp.name}</div>
    ${provided ? `<div class="comp-block"><div class="comp-block-label">provided interfaces</div>${provided}</div>` : ''}
    ${required ? `<div class="comp-block"><div class="comp-block-label">required interfaces</div>${required}</div>` : ''}
  </div>`;
}

// ── Component ────────────────────────────────────────

const COMP_WIDTH = 200;
const COMP_HEIGHT = 160;
const CHILD_WIDTH = 150;
const CHILD_HEIGHT = 100;

const CompEditor: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const isInternalUpdate = useRef(false);
  const clipboard = useRef<any>(null);

  const {
    diagram, selectedComponentId,
    addComponent, removeComponent, moveComponent,
    addCompRelation, removeCompRelation,
    selectComponent, selectCompRelation,
    undo, redo,
  } = useDiagramStore();

  const { setRightPanelTab } = useUiStore();

  // ── Init graph ──────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || graphRef.current) return;
    ensureShapesRegistered();

    const d = useDiagramStore.getState().diagram;
    const graph = new Graph({
      container: containerRef.current,
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      background: { color: '#fafafa' },
      grid: {
        size: d.grid_size || 20, visible: d.grid_visible !== false,
        args: { color: d.grid_color || '#e0e0e0', thickness: d.grid_thickness || 1 },
      },
      connecting: {
        connector: { name: 'smooth' },
        connectionPoint: 'boundary',
        router: { name: 'normal' },
        allowBlank: false,
        allowMulti: true,
        highlight: true,
        snap: { radius: 20 },
        createEdge() {
          return new Edge({
            attrs: {
              line: {
                stroke: '#d48806', strokeWidth: 2, strokeDasharray: '6,4',
                targetMarker: { name: 'block', width: 10, height: 6 },
              },
            },
          });
        },
        validateConnection({ sourceCell, targetCell }) {
          return !!(sourceCell && targetCell && sourceCell.id !== targetCell.id);
        },
      },
      mousewheel: { enabled: true, modifiers: ['ctrl', 'meta'], minScale: 0.1, maxScale: 5 },
      panning: { enabled: true },
    });

    graph.use(new History({ enabled: true }));
    graph.use(new Transform({ resizing: true, rotating: false }));
    graph.use(new Selection({ enabled: true, rubberband: true, showNodeSelectionBox: true }));
    graph.use(new Snapline({ enabled: true, sharp: true }));

    graph.on('node:click', ({ node }) => {
      selectComponent(node.id);
      setRightPanelTab('properties');
    });
    graph.on('blank:click', () => {
      selectComponent(null);
      selectCompRelation(null);
    });
    graph.on('node:moved', ({ node }) => {
      moveComponent(node.id, node.position().x, node.position().y);
    });
    graph.on('node:resized', ({ node }) => {
      const store = useDiagramStore.getState();
      store.updateComponent(node.id, {
        width: node.size().width,
        height: node.size().height,
      });
    });
    graph.on('edge:click', ({ edge }) => {
      selectCompRelation(edge.id);
      setRightPanelTab('properties');
    });
    graph.on('edge:connected', ({ edge, isNew }) => {
      if (isNew) {
        const src = edge.getSourceCellId();
        const tgt = edge.getTargetCellId();
        if (src && tgt) {
          isInternalUpdate.current = true;
          edge.remove();
          isInternalUpdate.current = false;
          addCompRelation(src, tgt);
        }
      }
    });
    graph.on('edge:mouseenter', ({ edge }) => {
      try { edge.addTools([
        { name: 'source-arrowhead' }, { name: 'target-arrowhead' },
        { name: 'button-remove', args: { distance: -30 } },
      ]); } catch { /* ignore */ }
    });
    graph.on('edge:mouseleave', ({ edge }) => {
      try { edge.removeTools(); } catch { /* ignore */ }
    });
    graph.on('edge:removed', ({ edge }) => {
      if (!isInternalUpdate.current) removeCompRelation(edge.id);
    });

    // Keyboard
    const handleKeyDown = (e: KeyboardEvent) => {
      const store = useDiagramStore.getState();
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.ctrlKey && e.key === 'c') {
        if (store.selectedComponentId) {
          const c = (store.diagram.components || []).find((x) => x.id === store.selectedComponentId);
          if (c) clipboard.current = JSON.parse(JSON.stringify(c));
        }
      } else if (e.ctrlKey && e.key === 'v') {
        if (clipboard.current) {
          const c = clipboard.current;
          store.addComponent({
            x: c.x + 30, y: c.y + 30
          }, c.parent_id || '');
          // Apply copied size and interfaces
          const store2 = useDiagramStore.getState();
          const comps = store2.diagram.components || [];
          const pasted = comps[comps.length - 1];
          if (pasted) {
            store2.updateComponent(pasted.id, {
              width: c.width, height: c.height,
              provided_interfaces: [...(c.provided_interfaces || [])],
              required_interfaces: [...(c.required_interfaces || [])],
            });
          }
        }
      } else if (e.ctrlKey && e.key === 'z' && !e.shiftKey) { e.preventDefault(); store.undo(); }
      else if (e.ctrlKey && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) { e.preventDefault(); store.redo(); }
      else if (e.key === 'Delete' || e.key === 'Backspace') {
        const cells = graph.getSelectedCells();
        if (cells.length > 0) {
          e.preventDefault();
          isInternalUpdate.current = true;
          cells.forEach((cell) => {
            if (cell.isNode()) store.removeComponent(cell.id);
            else if (cell.isEdge()) store.removeCompRelation(cell.id);
            cell.remove();
          });
          isInternalUpdate.current = false;
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);

    graph.centerContent();
    graphRef.current = graph;
    console.log('[CompEditor] Graph initialized');

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      try { graph.dispose(); } catch { /* ignore */ }
      graphRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Sync diagram → graph ───────────────────────────
  const prevCompIds = useRef<Set<string>>(new Set());
  const htmlCache = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    try {
      isInternalUpdate.current = true;
      const comps = diagram.components || [];
      const rels = diagram.comp_relations || [];
      const currentIds = new Set(comps.map((c) => c.id));

      // Remove deleted
      prevCompIds.current.forEach((id) => {
        if (!currentIds.has(id)) { try { graph.removeCell(id); } catch { /* ignore */ } htmlCache.current.delete(id); }
      });

      // Add/update components + handle embedding
      comps.forEach((c) => {
        const isChild = !!c.parent_id;
        const w = c.width || (isChild ? CHILD_WIDTH : COMP_WIDTH);
        const h = c.height || (isChild ? CHILD_HEIGHT : COMP_HEIGHT);
        const htmlContent = buildCompHTML(c, c.id === selectedComponentId);
        const cached = htmlCache.current.get(c.id);
        try {
          const existing = graph.getCellById(c.id);
          if (existing && existing.isNode()) {
            const node = existing as Node;
            node.setPosition(c.x, c.y);
            node.setSize({ width: w, height: h });
            if (cached !== htmlContent) {
              node.setAttrByPath('content/html', htmlContent);
              htmlCache.current.set(c.id, htmlContent);
            }
            // Re-embed child in parent
            if (isChild) {
              const parent = graph.getCellById(c.parent_id);
              if (parent) parent.addChild(node);
            }
          } else {
            const node = graph.addNode({
              id: c.id, shape: 'comp-component',
              x: c.x, y: c.y,
              width: w, height: h,
              attrs: { content: { html: htmlContent } },
            });
            htmlCache.current.set(c.id, htmlContent);
            if (isChild && node) {
              const parent = graph.getCellById(c.parent_id) as Node;
              if (parent) parent.addChild(node as Node);
            }
          }
        } catch (e) { console.warn('[CompEditor] Sync error:', c.name, e); }
      });

      // Sync edges
      const existingEdges = new Set(graph.getEdges().map((e) => e.id));
      const dataEdgeIds = new Set(rels.map((r) => r.id));
      existingEdges.forEach((id) => { if (!dataEdgeIds.has(id)) try { graph.removeCell(id); } catch { /* ignore */ } });

      rels.forEach((r) => {
        try {
          if (!existingEdges.has(r.id)) {
            graph.addEdge({
              id: r.id,
              source: { cell: r.source },
              target: { cell: r.target },
              attrs: {
                line: {
                  stroke: '#d48806', strokeWidth: 2, strokeDasharray: '6,4',
                  targetMarker: { name: 'block', width: 10, height: 6 },
                },
              },
            });
          }
        } catch (e) { console.warn('[CompEditor] Edge error:', r.id, e); }
      });

      prevCompIds.current = currentIds;
      isInternalUpdate.current = false;
    } catch (err) {
      console.error('[CompEditor] Sync error:', err);
      isInternalUpdate.current = false;
    }
  }, [diagram, selectedComponentId]);

  // ── Sync grid settings ─────────────────────────────
  useEffect(() => {
    const graph = graphRef.current as any;
    if (!graph) return;
    try {
      if (diagram.grid_visible !== false) {
        graph.showGrid();
        graph.setGridSize(diagram.grid_size || 20);
        graph.drawGrid({ size: diagram.grid_size || 20,
          args: { color: diagram.grid_color || '#e0e0e0', thickness: diagram.grid_thickness || 1 } });
      } else {
        graph.hideGrid();
      }
    } catch (e) { /* ignore */ }
  }, [diagram.grid_visible, diagram.grid_size, diagram.grid_color, diagram.grid_thickness]);

  // ── Auto-center on recenter trigger ───────────────
  const recenterCounter = useDiagramStore((s) => s.recenterCounter);
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || recenterCounter <= 0) return;
    setTimeout(() => {
      graph.centerContent({ padding: { top: 20, right: 60, bottom: 20, left: 60 } });
    }, 100);
  }, [recenterCounter]);

  const [showToolbar, setShowToolbar] = useState(true);

  const handleAddComponent = useCallback(() => {
    const store = useDiagramStore.getState();
    const parent = store.selectedComponentId;
    if (parent) {
      // Create child inside selected parent
      const parentComp = store.diagram.components?.find((c) => c.id === parent);
      const relX = 20 + Math.random() * 80;
      const relY = 40 + Math.random() * 60;
      store.addComponent({ x: relX, y: relY }, parent);
    } else {
      const x = 150 + Math.random() * 400;
      const y = 100 + Math.random() * 200;
      store.addComponent({ x, y });
    }
  }, []);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {showToolbar && (
        <div style={{
          position: 'absolute', top: 8, left: 8, zIndex: 100,
          background: '#fff', border: '1px solid #d9d9d9', borderRadius: 6,
          padding: '4px 6px', boxShadow: '0 2px 6px rgba(0,0,0,0.1)',
        }}>
          <Tooltip title="选中组件时创建子组件，未选中时创建顶层组件">
            <Button size="small" icon={<PlusOutlined />} onClick={handleAddComponent}>组件</Button>
          </Tooltip>
          <Button size="small" type="text" onClick={() => setShowToolbar(false)}
            style={{ fontSize: 10, marginLeft: 4 }}>✕</Button>
        </div>
      )}
      {!showToolbar && (
        <div style={{ position: 'absolute', top: 8, left: 8, zIndex: 100 }}>
          <Button size="small" type="dashed" onClick={() => setShowToolbar(true)}>🔧</Button>
        </div>
      )}
      <div ref={containerRef} className="comp-canvas-container" />
    </div>
  );
};

export default CompEditor;
