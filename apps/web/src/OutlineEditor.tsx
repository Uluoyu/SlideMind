import { ArrowDown, ArrowUp, Check, Plus, Trash2 } from 'lucide-react';
import type { Outline, OutlinePage } from './api';

export default function OutlineEditor({ outline, busy, onChange, onConfirm }: {
  outline: Outline; busy: boolean; onChange: (outline: Outline) => void; onConfirm: () => void;
}) {
  const confirmed = outline.status !== 'OUTLINE_GENERATED';
  function update(pages: OutlinePage[]) {
    onChange({ ...outline, pages: pages.map((page, index) => ({ ...page, pageNo: index + 1 })) });
  }
  function move(index: number, direction: number) {
    const pages = [...outline.pages];
    [pages[index], pages[index + direction]] = [pages[index + direction], pages[index]];
    update(pages);
  }
  return <div className="outline-panel">
    <div className="section-heading compact"><div><span className="eyebrow">STORY FIRST</span><h2>先理清思路，再开始设计。</h2></div>
      <span className={`badge ${confirmed ? 'green' : ''}`}>{confirmed ? '已确认' : `${outline.pages.length} 页大纲`}</span></div>
    <p className="hint">本地规则生成的初始大纲，可修改标题、用途和顺序。尚未使用 AI 或检索项目资料。</p>
    {outline.pages.map((page, index) => <div className="outline-row" key={page.pageNo}>
      <span className="page-number">{String(page.pageNo).padStart(2, '0')}</span>
      <div className="outline-fields"><input aria-label={`第 ${page.pageNo} 页标题`} maxLength={80} value={page.title}
        disabled={confirmed || busy} onChange={e => update(outline.pages.map((p, i) => i === index ? { ...p, title: e.target.value } : p))} />
        <textarea aria-label={`第 ${page.pageNo} 页用途`} rows={2} maxLength={500} value={page.purpose}
          disabled={confirmed || busy} onChange={e => update(outline.pages.map((p, i) => i === index ? { ...p, purpose: e.target.value } : p))} /></div>
      {!confirmed && <div className="row-actions"><button aria-label={`上移第 ${page.pageNo} 页`} disabled={busy || index === 0} onClick={() => move(index, -1)}><ArrowUp size={15} /></button>
        <button aria-label={`下移第 ${page.pageNo} 页`} disabled={busy || index === outline.pages.length - 1} onClick={() => move(index, 1)}><ArrowDown size={15} /></button>
        <button aria-label={`删除第 ${page.pageNo} 页`} disabled={busy || outline.pages.length === 1} onClick={() => update(outline.pages.filter((_, i) => i !== index))}><Trash2 size={15} /></button></div>}
    </div>)}
    {confirmed ? <div role="status" className="message success"><Check size={18} />大纲已确认，可在下方生成和编辑页面草稿。</div> :
      <div className="editor-footer"><button className="secondary" disabled={busy || outline.pages.length >= 50} onClick={() => update([...outline.pages, { pageNo: 0, title: '新页面', purpose: '说明本页要传达的核心观点' }])}><Plus size={16} />添加页面</button>
        <button className="primary" onClick={onConfirm} disabled={busy || outline.pages.some(p => !p.title.trim() || !p.purpose.trim())}><Check size={16} />确认并保存大纲</button></div>}
  </div>;
}
