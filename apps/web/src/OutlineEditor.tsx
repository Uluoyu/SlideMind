import { useState } from 'react';
import { ArrowDown, ArrowUp, Check, Combine, Plus, RefreshCw, Split, Trash2, Wand2 } from 'lucide-react';
import type { Outline, OutlinePage, OutlineSource } from './api';

const MAX_PAGES = 50;
const MAX_SOURCES = 16;

function joinSources(a: OutlineSource[], b: OutlineSource[]): OutlineSource[] {
  const seen = new Set<number>();
  return [...a, ...b].filter(s => !seen.has(s.chunkId) && seen.add(s.chunkId)).slice(0, MAX_SOURCES);
}

function withSources(page: OutlinePage, sources: OutlineSource[]): OutlinePage {
  return { ...page, sources, sourceChunkIds: sources.map(s => s.chunkId) };
}

export default function OutlineEditor({ outline, busy, onChange, onConfirm, onRegenerate, onRevise }: {
  outline: Outline; busy: boolean; onChange: (outline: Outline) => void; onConfirm: () => void;
  onRegenerate?: () => void; onRevise?: (feedback: string) => void;
}) {
  const [feedback, setFeedback] = useState('');
  const confirmed = outline.status !== 'OUTLINE_GENERATED';
  const model = outline.planner === 'model';
  function update(pages: OutlinePage[]) {
    onChange({ ...outline, pages: pages.map((page, index) => ({ ...page, pageNo: index + 1 })) });
  }
  function move(index: number, direction: number) {
    const pages = [...outline.pages];
    [pages[index], pages[index + direction]] = [pages[index + direction], pages[index]];
    update(pages);
  }
  function merge(index: number) {
    const [a, b] = [outline.pages[index], outline.pages[index + 1]];
    const merged = withSources({ ...a, title: `${a.title}与${b.title}`.slice(0, 80),
      purpose: `${a.purpose}\n${b.purpose}`.slice(0, 500) }, joinSources(a.sources, b.sources));
    update([...outline.pages.slice(0, index), merged, ...outline.pages.slice(index + 2)]);
  }
  function split(index: number) {
    const page = outline.pages[index];
    const next = { ...page, title: `${page.title.slice(0, 76)}（续）` };
    update([...outline.pages.slice(0, index + 1), next, ...outline.pages.slice(index + 1)]);
  }
  const hint = model
    ? '由模型结合项目资料生成，可修改标题、用途和顺序，合并或拆分页面，也可以写下修改意见让模型重新调整。事实以引用资料为准，请确认后再进入页面阶段。'
    : '本地规则生成的初始大纲，可修改标题、用途和顺序，合并或拆分页面。未配置模型服务，尚未使用 AI 或检索项目资料。';
  return <div className="outline-panel">
    <div className="section-heading compact"><div><span className="eyebrow">STORY FIRST</span><h2>先理清思路，再开始设计。</h2></div>
      <span className={`badge ${confirmed ? 'green' : ''}`}>{confirmed ? '已确认' : `${outline.pages.length} 页大纲`}</span></div>
    {!confirmed && <p className="hint">{hint}</p>}
    {outline.warning && <div role="status" className="message notice">{outline.warning}</div>}
    {outline.pages.map((page, index) => <div className="outline-row" key={page.pageNo}>
      <span className="page-number">{String(page.pageNo).padStart(2, '0')}</span>
      <div className="outline-fields"><input aria-label={`第 ${page.pageNo} 页标题`} maxLength={80} value={page.title}
        disabled={confirmed || busy} onChange={e => update(outline.pages.map((p, i) => i === index ? { ...p, title: e.target.value } : p))} />
        <textarea aria-label={`第 ${page.pageNo} 页用途`} rows={2} maxLength={500} value={page.purpose}
          disabled={confirmed || busy} onChange={e => update(outline.pages.map((p, i) => i === index ? { ...p, purpose: e.target.value } : p))} />
        {page.sources.length > 0 && <details className="outline-sources"><summary>依据 {page.sources.length} 条项目资料</summary>
          <ul>{page.sources.map(source => <li key={source.chunkId}>
            <div className="outline-source-head"><strong>{source.fileName}</strong><small>{source.location}</small>
              {!confirmed && <button aria-label={`移除第 ${page.pageNo} 页引用 ${source.fileName} ${source.location}`} disabled={busy}
                onClick={() => update(outline.pages.map((p, i) => i === index ? withSources(p, p.sources.filter(s => s.chunkId !== source.chunkId)) : p))}>移除</button>}</div>
            <p>{source.excerpt}</p></li>)}</ul></details>}</div>
      {!confirmed && <div className="row-actions"><button aria-label={`上移第 ${page.pageNo} 页`} disabled={busy || index === 0} onClick={() => move(index, -1)}><ArrowUp size={15} /></button>
        <button aria-label={`下移第 ${page.pageNo} 页`} disabled={busy || index === outline.pages.length - 1} onClick={() => move(index, 1)}><ArrowDown size={15} /></button>
        <button aria-label={`合并第 ${page.pageNo} 页与下一页`} title="与下一页合并" disabled={busy || index === outline.pages.length - 1} onClick={() => merge(index)}><Combine size={15} /></button>
        <button aria-label={`拆分第 ${page.pageNo} 页`} title="拆分为两页" disabled={busy || outline.pages.length >= MAX_PAGES} onClick={() => split(index)}><Split size={15} /></button>
        <button aria-label={`删除第 ${page.pageNo} 页`} disabled={busy || outline.pages.length === 1} onClick={() => update(outline.pages.filter((_, i) => i !== index))}><Trash2 size={15} /></button></div>}
    </div>)}
    {confirmed ? <div role="status" className="message success"><Check size={18} />大纲已确认，可在下方生成和编辑页面草稿。</div> : <>
      {model && onRevise && <form className="outline-feedback" onSubmit={e => { e.preventDefault(); onRevise(feedback.trim()); }}>
        <label htmlFor="outline-feedback">修改意见</label>
        <textarea id="outline-feedback" rows={2} maxLength={1000} value={feedback} disabled={busy}
          placeholder="例如：P3 和 P4 合并，增加一页“AI 违规检测”，P8 改成“项目价值”" onChange={e => setFeedback(e.target.value)} />
        <button className="secondary" disabled={busy || !feedback.trim()}><Wand2 size={16} />按意见调整大纲</button>
      </form>}
      <div className="editor-footer"><div className="footer-group">
        <button className="secondary" disabled={busy || outline.pages.length >= MAX_PAGES} onClick={() => update([...outline.pages, { pageNo: 0, title: '新页面', purpose: '说明本页要传达的核心观点', sourceChunkIds: [], sources: [] }])}><Plus size={16} />添加页面</button>
        {onRegenerate && <button className="secondary" disabled={busy} onClick={() => { if (window.confirm('重新生成会替换当前大纲及未保存的修改，确定继续吗？')) onRegenerate(); }}><RefreshCw size={16} />重新生成</button>}</div>
        <button className="primary" onClick={onConfirm} disabled={busy || outline.pages.some(p => !p.title.trim() || !p.purpose.trim())}><Check size={16} />确认并保存大纲</button></div>
    </>}
  </div>;
}
