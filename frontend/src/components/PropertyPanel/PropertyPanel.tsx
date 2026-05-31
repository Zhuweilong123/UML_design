/**
 * Property Panel – edit properties of selected class or relation.
 */

import React, { useEffect } from 'react';
import {
  Form, Input, Select, Switch, Button, Collapse, Space,
  Popconfirm, Empty, Divider, InputNumber,
} from 'antd';
import {
  DeleteOutlined, PlusOutlined, MinusCircleOutlined,
} from '@ant-design/icons';
import { useDiagramStore } from '../../stores/diagramStore';
import {
  Visibility, Stereotype, RelationType,
  type UmlAttribute, type UmlMethod,
} from '../../types/uml';
import './PropertyPanel.css';

const { TextArea } = Input;

const PropertyPanel: React.FC = () => {
  const {
    diagram, selectedClassId, selectedRelationId,
    updateClass, removeClass, updateRelation, removeRelation,
  } = useDiagramStore();

  const selectedClass = diagram.classes.find((c) => c.id === selectedClassId);
  const selectedRelation = diagram.relations.find((r) => r.id === selectedRelationId);

  // ── Class Property Editor ──────────────────────────
  if (selectedClass) {
    const handleClassChange = (field: string, value: unknown) => {
      updateClass(selectedClass.id, { [field]: value });
    };

    return (
      <div className="property-panel">
        <div className="property-panel-header">
          <h3>类属性</h3>
          <Popconfirm
            title="确认删除此类？"
            onConfirm={() => removeClass(selectedClass.id)}
            okText="删除" cancelText="取消"
          >
            <Button danger size="small" icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </div>

        <Form layout="vertical" size="small">
          <Form.Item label="类名">
            <Input
              value={selectedClass.name}
              onChange={(e) => handleClassChange('name', e.target.value)}
            />
          </Form.Item>
          <Form.Item label="构造型">
            <Select
              value={selectedClass.stereotype}
              onChange={(v) => handleClassChange('stereotype', v)}
              options={Object.values(Stereotype).map((s) => ({ value: s, label: s }))}
            />
          </Form.Item>
          <Form.Item label="备注">
            <TextArea
              value={selectedClass.note}
              onChange={(e) => handleClassChange('note', e.target.value)}
              rows={2}
              placeholder="添加备注..."
            />
          </Form.Item>
        </Form>

        {/* Attributes */}
        <Collapse
          ghost
          defaultActiveKey={['attrs']}
          items={[{
            key: 'attrs',
            label: `属性 (${selectedClass.attributes.length})`,
            children: (
              <div>
                {selectedClass.attributes.map((attr, idx) => (
                  <div key={idx} className="property-row">
                    <Select
                      value={attr.visibility}
                      size="small"
                      style={{ width: 50 }}
                      onChange={(v) => {
                        const attrs = [...selectedClass.attributes];
                        attrs[idx] = { ...attrs[idx], visibility: v };
                        handleClassChange('attributes', attrs);
                      }}
                      options={Object.values(Visibility).map((v) => ({ value: v, label: v }))}
                    />
                    <Input
                      size="small"
                      style={{ width: 80 }}
                      value={attr.name}
                      placeholder="名称"
                      onChange={(e) => {
                        const attrs = [...selectedClass.attributes];
                        attrs[idx] = { ...attrs[idx], name: e.target.value };
                        handleClassChange('attributes', attrs);
                      }}
                    />
                    <span className="attr-colon">:</span>
                    <Input
                      size="small"
                      style={{ width: 80 }}
                      value={attr.type}
                      placeholder="类型"
                      onChange={(e) => {
                        const attrs = [...selectedClass.attributes];
                        attrs[idx] = { ...attrs[idx], type: e.target.value };
                        handleClassChange('attributes', attrs);
                      }}
                    />
                    <Switch
                      size="small"
                      checked={attr.is_static}
                      onChange={(v) => {
                        const attrs = [...selectedClass.attributes];
                        attrs[idx] = { ...attrs[idx], is_static: v };
                        handleClassChange('attributes', attrs);
                      }}
                      title="static"
                    />
                    <Button
                      type="text" size="small" danger
                      icon={<MinusCircleOutlined />}
                      onClick={() => {
                        const attrs = selectedClass.attributes.filter((_, i) => i !== idx);
                        handleClassChange('attributes', attrs);
                      }}
                    />
                  </div>
                ))}
                <Button
                  type="dashed" size="small" block
                  icon={<PlusOutlined />}
                  onClick={() => {
                    const attrs = [...selectedClass.attributes, {
                      name: '', type: '', visibility: Visibility.PUBLIC, is_static: false,
                    }];
                    handleClassChange('attributes', attrs);
                  }}
                >
                  添加属性
                </Button>
              </div>
            ),
          }]}
        />

        {/* Methods */}
        <Collapse
          ghost
          defaultActiveKey={['methods']}
          items={[{
            key: 'methods',
            label: `方法 (${selectedClass.methods.length})`,
            children: (
              <div>
                {selectedClass.methods.map((method, idx) => (
                  <div key={idx} className="property-row method-row">
                    <Select
                      value={method.visibility}
                      size="small"
                      style={{ width: 50 }}
                      onChange={(v) => {
                        const methods = [...selectedClass.methods];
                        methods[idx] = { ...methods[idx], visibility: v };
                        handleClassChange('methods', methods);
                      }}
                      options={Object.values(Visibility).map((v) => ({ value: v, label: v }))}
                    />
                    <Input
                      size="small"
                      style={{ width: 80 }}
                      value={method.name}
                      placeholder="方法名"
                      onChange={(e) => {
                        const methods = [...selectedClass.methods];
                        methods[idx] = { ...methods[idx], name: e.target.value };
                        handleClassChange('methods', methods);
                      }}
                    />
                    <span className="attr-colon">(</span>
                    <Input
                      size="small"
                      style={{ width: 70 }}
                      value={method.params}
                      placeholder="参数"
                      onChange={(e) => {
                        const methods = [...selectedClass.methods];
                        methods[idx] = { ...methods[idx], params: e.target.value };
                        handleClassChange('methods', methods);
                      }}
                    />
                    <span className="attr-colon">):</span>
                    <Input
                      size="small"
                      style={{ width: 70 }}
                      value={method.return_type}
                      placeholder="返回"
                      onChange={(e) => {
                        const methods = [...selectedClass.methods];
                        methods[idx] = { ...methods[idx], return_type: e.target.value };
                        handleClassChange('methods', methods);
                      }}
                    />
                    <Button
                      type="text" size="small" danger
                      icon={<MinusCircleOutlined />}
                      onClick={() => {
                        const methods = selectedClass.methods.filter((_, i) => i !== idx);
                        handleClassChange('methods', methods);
                      }}
                    />
                  </div>
                ))}
                <Button
                  type="dashed" size="small" block
                  icon={<PlusOutlined />}
                  onClick={() => {
                    const methods = [...selectedClass.methods, {
                      name: '', return_type: 'void', params: '',
                      visibility: Visibility.PUBLIC, is_static: false, is_abstract: false,
                    }];
                    handleClassChange('methods', methods);
                  }}
                >
                  添加方法
                </Button>
              </div>
            ),
          }]}
        />
      </div>
    );
  }

  // ── Relation Property Editor ───────────────────────
  if (selectedRelation) {
    const srcClass = diagram.classes.find((c) => c.id === selectedRelation.source);
    const tgtClass = diagram.classes.find((c) => c.id === selectedRelation.target);

    const handleRelChange = (field: string, value: unknown) => {
      updateRelation(selectedRelation.id, { [field]: value });
    };

    return (
      <div className="property-panel">
        <div className="property-panel-header">
          <h3>连接属性</h3>
          <Popconfirm
            title="确认删除此连接？"
            onConfirm={() => removeRelation(selectedRelation.id)}
            okText="删除" cancelText="取消"
          >
            <Button danger size="small" icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </div>

        <div className="relation-summary">
          {srcClass?.name || selectedRelation.source}
          {' → '}
          {tgtClass?.name || selectedRelation.target}
        </div>

        <Form layout="vertical" size="small">
          <Form.Item label="关系类型">
            <Select
              value={selectedRelation.type}
              onChange={(v) => handleRelChange('type', v)}
              options={Object.values(RelationType).map((t) => ({
                value: t, label: t,
              }))}
            />
          </Form.Item>
          <Form.Item label="源多重性">
            <Input
              value={selectedRelation.multiplicity_source}
              onChange={(e) => handleRelChange('multiplicity_source', e.target.value)}
              placeholder="如: 0..1, 1..*, *"
            />
          </Form.Item>
          <Form.Item label="目标多重性">
            <Input
              value={selectedRelation.multiplicity_target}
              onChange={(e) => handleRelChange('multiplicity_target', e.target.value)}
              placeholder="如: 0..1, 1..*, *"
            />
          </Form.Item>
          <Form.Item label="角色名">
            <Input
              value={selectedRelation.role_name}
              onChange={(e) => handleRelChange('role_name', e.target.value)}
              placeholder="角色名称"
            />
          </Form.Item>
          <Form.Item label="连接备注">
            <TextArea
              value={selectedRelation.note}
              onChange={(e) => handleRelChange('note', e.target.value)}
              rows={2}
              placeholder="添加备注..."
            />
          </Form.Item>
        </Form>
      </div>
    );
  }

  // ── Nothing selected ───────────────────────────────
  return (
    <div className="property-panel">
      <Empty
        description="选择类或连接以编辑属性"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
      <div className="property-hints">
        <p><strong>提示:</strong></p>
        <ul>
          <li>双击画布空白区域添加类</li>
          <li>从节点端口拖拽创建连接</li>
          <li>Ctrl+滚轮缩放画布</li>
          <li>空格/中键拖拽平移</li>
          <li>Ctrl+Z 撤销 | Ctrl+Y 重做</li>
        </ul>
      </div>
    </div>
  );
};

export default PropertyPanel;
