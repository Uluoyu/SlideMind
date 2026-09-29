import { useEffect, useState } from 'react';
import { Download, FileOutput, Plus, Save, Trash2 } from 'lucide-react';
import { api, apiResponse, post, type PageRecord, type Pages, type PageSpec } from './api';

export default function PageEditor({ documentId, projectId, onStatus, onBusy, onDirty }: {
  documentId: number; projectId: number;
  onStatus: (status: string) => void; onBusy: (busy: boolean) => void; onDirty: (dirty: boolean) => void;
}) {
  const [data, setData] = useState<Pages | null>(null);
  const [selected, setSelected] = useState(1);
  const [draft, setDraft] = useState<PageSpec | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const base = `/documents/${documentId}`;
  const scope = `?projectId=${projectId}`;
  const current = data?.pages.find(page => page.pageNo === selected);
  const dirty = !!draft && JSON.stringify(draft) !== JSON.stringify(current?.pageJson);
  const complete = !!data?.pages.length && data.pages.every(page => page.pageJson);
  const valid = draft && draft.title.trim() && draft.content.every(block => block.title.trim() && block.text.trim());

  useEffect(() => {
    let active = true;
    api<Pages>(`${base}/pages${scope}`).then(result => {
      if (active) { setData(result); setDraft(result.pages[0]?.pageJson ?? null); }
    }).catch(e => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [base, scope]);

  useEffect(() => { onBusy(busy || loading); return () => onBusy(false); }, [busy, loading, onBusy]);
  useEffect(() => { onDirty(dirty); return () => onDirty(false); }, [dirty, onDirty]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setBusy(false); }
  }

  function selectPage(page: PageRecord) {
    setSelected(page.pageNo); setDraft(page.pageJson); setNotice(''); setError('');
  }

  function generate() {
    void run(async () => {
      const result = await api<Pages>(`${base}/pages/generate${scope}`, post());
      setData(result); onStatus(result.status);
      setDraft(result.pages.find(page => page.pageNo === selected)?.pageJson ?? null);
    });
  }

  function save() {
    if (!current || !draft || !data) return;
    void run(async () => {
      const result = await api<PageRecord>(`${base}/pages/${selected}${scope}`,
        post({ version: current.version, page: draft }));
      const pages = data.pages.map(page => page.pageNo === selected ? result : page);
      const status = pages.every(page => page.pageJson) ? 'DESIGN_GENERATED' : 'OUTLINE_CONFIRMED';
      setData({ ...data, pages, status }); setDraft(result.pageJson); onStatus(status);
      setNotice('页面已保存。可继续编辑其他页面，或生成新的 PPTX。');
    });
  }

  function render() {
    if (!data) return;
    void run(async () => {
      try {
        const result = await api<{ status: string }>(`${base}/render${scope}`, post());
        setData({ ...data, status: result.status }); onStatus(result.status);
        setNotice('PPTX 已生成，可以下载。');
      } catch (error) {
        // A transport error alone cannot tell us whether the server finished rendering.
        const latest = await api<{ status: string }>(`${base}${scope}`).catch(() => null);
        if (latest) { setData({ ...data, status: latest.status }); onStatus(latest.status); }
        throw error;
      }
    });
  }

  function download() {
    void run(async () => {
      const response = await apiResponse(`${base}/download${scope}`);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url; link.download = `slidemind-${documentId}.pptx`;
      document.body.append(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  if (loading) return <p role="status" className="hint">正在读取页面…</p>;
  return <section className="page-editor" aria-label="页面编辑器">
    <div className="section-heading"><div><span className="eyebrow">SHAPE YOUR STORY</span><h2>把思路，写成每一页。</h2></div>
      <span className="badge">{data?.pages.length ?? 0} 页</span></div>
    <p className="hint">草稿来自已确认的大纲，请补充并核实项目内容。当前使用默认主题；上传的公司模板尚未应用。</p>
    {error && <div role="alert" className="message error">{error}</div>}
    {notice && <div role="status" className="message success">{notice}</div>}
    {!complete && <button className="primary" disabled={busy || dirty} onClick={generate}><Plus size={16} />生成页面草稿</button>}
    <div className="page-tabs" aria-label="选择页面">{data?.pages.map(page => <button key={page.pageNo}
      aria-label={`编辑第 ${page.pageNo} 页`} aria-pressed={selected === page.pageNo}
      className={selected === page.pageNo ? 'selected' : ''} disabled={busy || dirty}
      onClick={() => selectPage(page)}><span>{String(page.pageNo).padStart(2, '0')}</span>
      {page.pageJson?.title ?? '待生成'}</button>)}</div>
    {draft && <>
      <div className="slide-preview" aria-label="页面结构示意">
        <small>结构示意 · 导出效果以 PPTX 为准</small><h3>{draft.title}</h3><p>{draft.subtitle}</p>
        <div className={draft.layout === 'two_column' ? 'preview-content columns' : 'preview-content'}>
          {draft.content.map((block, index) => <div key={index}><strong>{block.title}</strong><p>{block.text}</p></div>)}
        </div><span className="preview-footer">SlideMind / {String(selected).padStart(2, '0')}</span>
      </div>
      <fieldset className="page-fields" disabled={busy}>
        <div className="form-grid"><label>页面标题<input maxLength={80} value={draft.title}
          onChange={e => setDraft({ ...draft, title: e.target.value })} /></label>
          <label>页面布局<select value={draft.layout} onChange={e => setDraft({ ...draft, layout: e.target.value as PageSpec['layout'] })}>
            <option value="title">封面</option><option value="two_column">双栏内容</option><option value="summary">总结</option>
          </select></label></div>
        <label>副标题<input maxLength={160} value={draft.subtitle} onChange={e => setDraft({ ...draft, subtitle: e.target.value })} /></label>
        {draft.content.map((block, index) => <div className="content-block" key={index}>
          <label>内容标题 {index + 1}<input maxLength={60} value={block.title} onChange={e => setDraft({ ...draft,
            content: draft.content.map((item, i) => i === index ? { ...item, title: e.target.value } : item) })} /></label>
          <label>正文 {index + 1}<textarea rows={3} maxLength={500} value={block.text} onChange={e => setDraft({ ...draft,
            content: draft.content.map((item, i) => i === index ? { ...item, text: e.target.value } : item) })} /></label>
          {block.sources.length > 0 && <p className="source-note">引用：{block.sources.map(source =>
            `${source.file_name}${source.page_no ? ` 第 ${source.page_no} 页` : ''}`).join('、')}</p>}
          <button className="text-button" onClick={() => setDraft({ ...draft, content: draft.content.filter((_, i) => i !== index) })}>
            <Trash2 size={14} />删除内容块 {index + 1}</button>
        </div>)}
        <button className="secondary" disabled={draft.content.length >= 4} onClick={() => setDraft({ ...draft,
          content: [...draft.content, { type: 'text', title: '核心观点', text: '', sources: [] }] })}><Plus size={15} />添加内容块</button>
      </fieldset>
      <div className="editor-footer page-actions"><div className="save-actions">
        <button className="primary" disabled={busy || !dirty || !valid} onClick={save}><Save size={15} />保存当前页</button>
        {dirty && <button className="text-button" disabled={busy} onClick={() => setDraft(current?.pageJson ?? null)}>放弃本次修改</button>}
      </div><div className="export-actions">
        <button className="secondary" disabled={busy || dirty || !complete} onClick={render}><FileOutput size={15} />生成 PPTX</button>
        {data?.status === 'COMPLETED' && <button className="secondary" disabled={busy || dirty} onClick={download}><Download size={15} />下载 PPTX</button>}
      </div></div>
      <p className="save-hint" role="status">{busy ? '正在处理…' : dirty ? '有未保存的修改，请保存或放弃后切换页面。' : '当前页面已保存'}</p>
    </>}
  </section>;
}
