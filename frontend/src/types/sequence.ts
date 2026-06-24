/** Sequence diagram types — lifelines, messages, combined fragments. */

export interface SeqLifeline {
  id: string;
  name: string;
  class_ref: string;   // optional: UmlClass.id
  x: number;
  activations: number[];  // y-offsets of activation bars (from top of lifeline body)
}

export type MessageType = 'sync' | 'async' | 'return' | 'simple' | 'self';

export const MESSAGE_TYPE_LABELS: Record<MessageType, string> = {
  sync:   '同步消息',
  async:  '异步消息',
  return: '返回消息',
  simple: '简单消息',
  self:   '自反消息',
};

export interface SeqMessage {
  id: string;
  from_lifeline: string;
  to_lifeline: string;
  label: string;
  type: MessageType;
  order: number;
  y: number;            // persisted Y position — survives diagram switches
  note: string;         // functional comment / 功能备注
}

export function createDefaultLifeline(x?: number): SeqLifeline {
  return {
    id: `life_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name: 'Participant',
    class_ref: '',
    x: x || 150 + Math.random() * 400,
    activations: [],
  };
}

export function createDefaultMessage(from: string, to: string, order: number, y?: number): SeqMessage {
  return {
    id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    from_lifeline: from,
    to_lifeline: to,
    label: 'message()',
    type: 'sync',
    order,
    y: y || (order * 40 + 100),  // default: LIFELINE_Y(60) + 40 + order*40
    note: '',
  };
}
