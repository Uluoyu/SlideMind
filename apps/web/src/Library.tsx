import { useEffect, useRef, useState, type FormEvent } from 'react';
import { FileText, Image, Layers3, RefreshCw, Search, Upload, X } from 'lucide-react';
import { api, post, type DocumentChunk, type ProjectDocument, type SearchHit, type SearchResult, type StoredFile, type TemplateFile } from './api';

type Kind = 'documents' | 'assets' | 'templates';
const kinds: { key: Kind; label: string; accept: string }[] = [
  { key: 'documents', label: '项目资料', accept: '.pdf,.docx,.pptx,.txt,.md' },
  { key: 'assets', label: '图片素材', accept: '.png,.jpg,.jpeg,.webp' },
  { key: 'templates', label: '公司模板', accept: '.pptx' },
];
const pendingStatuses = new Set(['UPLOADED', 'QUEUED', 'PARSING', 'INDEXING']);
const documentStatusText: Record<string, string> = {
  UPLOADED: '待处理', QUEUED: '等待处理', PARSING: '正在解析', INDEXING: '正在建立索引', READY: '可检索', FAILED: '处理失败',
};
const templateStatusText: Record<string, string> = {
  UPLOADED: '待解析', READY: '可应用', FAILED: '解析失败',
};
const securityText: Record<string, string> = { PUBLIC: '公开', INTERNAL: '内部', CONFIDENTIAL: '机密', TOP_SECRET: '绝密' };
function errorMessage(error: unknown, fallback: string) { return error instanceof Error ? error.message : fallback; }
function sourceLocation(hit: SearchHit) {
  return hit.location || (hit.source.page_no !== null ? `第 ${hit.source.page_no} 页` : '文档正文');
}

export default function Library({ projectId }: { projectId: number | null }) {
  const [kind, setKind] = useState<Kind>('documents');
  // Each project/tab owns its requests and state; leaving it unmounts and cancels them.
  return <LibraryPanel key={`${projectId}:${kind}`} projectId={projectId} kind={kind} onKindChange={setKind} />;
}

function LibraryPanel({ projectId, kind, onKindChange }: {
  projectId: number | null; kind: Kind; onKindChange: (kind: Kind) => void;
}) {
  const [files, setFiles] = useState<(StoredFile | ProjectDocument | TemplateFile)[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState<number[]>([]);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [notice, setNotice] = useState('');
  const [level, setLevel] = useState('INTERNAL');
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [result, setResult] = useState<SearchResult | null>(null);
  const [selectedSource, setSelectedSource] = useState<SearchHit | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const scope = useRef<AbortController | null>(null);
  const listRevision = useRef(0);
  const mutations = useRef(0);
  const searchRevision = useRef(0);
  const sourceTrigger = useRef<HTMLButtonElement | null>(null);
  const path = kind === 'templates' ? '/templates' : projectId ? `/projects/${projectId}/${kind}` : null;
  const current = kinds.find(item => item.key === kind)!;
  const hasPending = kind === 'documents' && files.some(file => pendingStatuses.has(file.status));

  useEffect(() => {
    const controller = new AbortController();
    scope.current = controller;
    if (!path) setLoading(false);
    else api<(StoredFile | ProjectDocument | TemplateFile)[]>(path, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setFiles(data); })
      .catch(e => { if (!controller.signal.aborted) setError(errorMessage(e, '读取文件失败')); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path]);

  useEffect(() => {
    if (!path || !hasPending) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      const revision = listRevision.current;
      try {
        if (mutations.current === 0) {
          const data = await api<ProjectDocument[]>(path!, { signal: controller.signal });
          if (!controller.signal.aborted && revision === listRevision.current) {
            setFiles(data); setPollError('');
          }
        }
      } catch (e) {
        if (!controller.signal.aborted) setPollError(`状态更新失败：${errorMessage(e, '连接失败')}，将自动重试。`);
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 2000);
      }
    }
    timer = setTimeout(refresh, 1500);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [path, hasPending]);

  async function upload(file: File) {
    const signal = scope.current?.signal;
    if (!path || !signal || signal.aborted) return;
    setUploading(true); setError(''); setNotice('');
    mutations.current++; listRevision.current++;
    const form = new FormData(); form.append('file', file); form.append('securityLevel', level);
    try {
      const saved = await api<StoredFile | ProjectDocument>(path, { method: 'POST', body: form, signal });
      if (signal.aborted) return;
      setFiles(previous => [saved, ...previous.filter(item => item.id !== saved.id)]);
      setNotice(kind === 'documents' ? '文件已上传，处理进度会自动更新；完成后即可搜索内容。' :
        kind === 'assets' ? '图片素材已保存到当前项目。' :
          saved.status === 'READY' ? '公司模板已保存并完成解析，可在项目中关联使用。' :
            '公司模板已保存，但解析未完成；请查看原因并重试。');
    } catch (e) { if (!signal.aborted) setError(errorMessage(e, '上传失败')); }
    finally {
      mutations.current--; listRevision.current++;
      if (!signal.aborted) { setUploading(false); if (input.current) input.current.value = ''; }
    }
  }

  async function processDocument(document: ProjectDocument) {
    const signal = scope.current?.signal;
    if (!path || !signal || signal.aborted || processing.includes(document.id)) return;
    setProcessing(previous => [...previous, document.id]); setError(''); setNotice('');
    setResult(null); setSelectedSource(null); searchRevision.current++; setSearching(false);
    mutations.current++; listRevision.current++;
    try {
      const updated = await api<ProjectDocument>(`${path}/${document.id}/process`, { ...post(), signal });
      if (!signal.aborted) {
        setFiles(previous => previous.map(item => item.id === updated.id ? updated : item));
        setNotice('已提交处理，进度会自动更新。');
      }
    } catch (e) { if (!signal.aborted) setError(errorMessage(e, '提交处理失败')); }
    finally {
      mutations.current--; listRevision.current++;
      if (!signal.aborted) setProcessing(previous => previous.filter(id => id !== document.id));
    }
  }

  async function processTemplate(template: TemplateFile) {
    const signal = scope.current?.signal;
    if (!signal || signal.aborted || processing.includes(template.id)) return;
    setProcessing(previous => [...previous, template.id]); setError(''); setNotice('');
    try {
      // Synchronous parse; the response already carries the final status.
      const updated = await api<TemplateFile>(`/templates/${template.id}/process`, { ...post(), signal });
      if (!signal.aborted) {
        setFiles(previous => previous.map(item => item.id === updated.id ? updated : item));
        setNotice(updated.status === 'READY' ? '模板解析完成，可在项目中关联并在导出时应用。' : '模板解析失败，请查看原因或更换文件后重试。');
      }
    } catch (e) { if (!signal.aborted) setError(errorMessage(e, '解析模板失败')); }
    finally {
      if (!signal.aborted) setProcessing(previous => previous.filter(id => id !== template.id));
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    const signal = scope.current?.signal;
    const text = query.trim();
    if (!projectId || !text || !signal || signal.aborted) return;
    const revision = ++searchRevision.current;
    setSearching(true); setSearchError(''); setResult(null); setSelectedSource(null);
    try {
      const data = await api<SearchResult>(`/projects/${projectId}/search`, { ...post({ query: text, topK: 5 }), signal });
      if (!signal.aborted && revision === searchRevision.current) setResult(data);
    } catch (e) {
      if (!signal.aborted && revision === searchRevision.current) setSearchError(errorMessage(e, '搜索失败，请重试'));
    } finally { if (!signal.aborted && revision === searchRevision.current) setSearching(false); }
  }

  return <section className="library">
    <div className="section-heading"><div><span className="eyebrow">YOUR KNOWLEDGE, ORGANIZED</span>
      <h1>每一份资料，都是表达的底气。</h1><p>按项目归档资料与素材，搜索内容并回看原文来源。</p></div></div>
    <div className="tabs" role="group" aria-label="资料类别">{kinds.map(item =>
      <button key={item.key} aria-pressed={kind === item.key} className={kind === item.key ? 'active' : ''}
        onClick={() => onKindChange(item.key)}>{item.key === 'documents' ? <FileText size={16} /> :
          item.key === 'assets' ? <Image size={16} /> : <Layers3 size={16} />}{item.label}</button>)}</div>
    {error && <div role="alert" className="message error">{error}</div>}
    {notice && <div role="status" className="message success">{notice}</div>}
    <div className="upload-zone">
      <span className="icon-tile"><Upload size={24} /></span><h2>添加{current.label}</h2>
      <p>{path ? `支持 ${current.accept.replaceAll('.', '').toUpperCase().replaceAll(',', ' / ')}` : '请先创建或选择一个项目'}</p>
      <div className="upload-actions"><label>安全等级<select value={level} onChange={e => setLevel(e.target.value)} disabled={uploading}>
        <option value="PUBLIC">公开</option><option value="INTERNAL">内部</option>
        <option value="CONFIDENTIAL">机密</option><option value="TOP_SECRET">绝密</option>
      </select></label><button className="primary" disabled={!path || loading || uploading} onClick={() => input.current?.click()}>
        <Upload size={16} />{uploading ? '正在上传…' : '选择文件'}</button></div>
      <input ref={input} type="file" accept={current.accept} aria-label={`上传${current.label}`} hidden onChange={e => {
        const file = e.target.files?.[0]; if (file) void upload(file);
      }} />
      <small>{kind === 'documents' ? '上传后自动解析与建立索引；“可检索”的资料可用于搜索。' :
        kind === 'assets' ? '图片按项目保存，供演示文稿使用。' : '公司模板保存在共享模板库中，上传后自动解析主题（颜色、字体与页面尺寸）。'}</small>
    </div>
    <div className="section-heading compact"><h2>{current.label}</h2><span className="muted">{files.length} 个文件</span></div>
    {pollError && <div role="alert" className="message error">{pollError}</div>}
    {loading ? <p role="status">正在读取文件…</p> : files.length === 0 ?
      <div className="empty-small">这里还没有文件。上传{kind === 'documents' ? '第一份资料，开始积累项目知识。' : `文件，建立${current.label}库。`}</div> :
      <ul className="file-list" aria-label={current.label}>{files.map(file => {
        const document = kind === 'documents' ? file as ProjectDocument : null;
        const template = kind === 'templates' ? file as TemplateFile : null;
        const tracked = document ?? template;
        const failed = tracked?.status === 'FAILED';
        const ready = tracked?.status === 'READY';
        return <li className="file-row" key={file.id}>
          <span className="file-type">{file.fileType.toUpperCase()}</span><div className="file-name"><strong>{file.fileName}</strong>
            <small>{(file.sizeBytes / 1024).toFixed(1)} KB · {new Date(file.createdAt).toLocaleDateString('zh-CN')}
              {document && ` · ${document.chunkCount ?? 0} 个片段`}</small>
            {document?.processedAt && <small>处理完成于 {new Date(document.processedAt).toLocaleString('zh-CN')}</small>}
            {failed && <p className="file-error" role="alert">{tracked?.processingError ||
              (document ? '处理未完成，请重试或上传新的文件。' : '模板解析未完成，请重试或上传新的文件。')}</p>}
          </div>
          <span className="file-security">{securityText[file.securityLevel] ?? file.securityLevel}</span>
          <div className="file-status-actions"><span role="status" className={`badge ${ready ? 'green' : failed ? 'failed' : ''}`}>
            {document ? documentStatusText[document.status] ?? '待处理' :
              template ? templateStatusText[template.status] ?? '待解析' : '已保存'}</span>
            {document && ['FAILED', 'READY', 'UPLOADED'].includes(document.status) &&
              <button className="file-process" disabled={processing.includes(file.id)} onClick={() => void processDocument(document)}>
                <RefreshCw size={13} />{processing.includes(file.id) ? '正在提交…' : document.status === 'FAILED' ? '重试处理' : document.status === 'READY' ? '重新索引' : '开始处理'}
              </button>}
            {template && ['FAILED', 'READY', 'UPLOADED'].includes(template.status) &&
              <button className="file-process" disabled={processing.includes(file.id)} onClick={() => void processTemplate(template)}>
                <RefreshCw size={13} />{processing.includes(file.id) ? '正在解析…' : template.status === 'FAILED' ? '重试解析' : template.status === 'READY' ? '重新解析' : '开始解析'}
              </button>}
          </div>
        </li>;
      })}</ul>}
    {kind === 'documents' && <section className="library-search" aria-labelledby="library-search-title">
      <div className="section-heading compact"><div><h2 id="library-search-title">从资料中找答案</h2><p>搜索当前项目的内容，查看对应原文。</p></div><Search size={20} /></div>
      <form onSubmit={search}><label htmlFor="library-query">搜索项目资料</label><div className="search-actions">
        <input id="library-query" value={query} onChange={e => setQuery(e.target.value)} required maxLength={500}
          placeholder="输入关键词或问题，例如：项目的交付计划" disabled={!projectId} />
        <button className="primary" disabled={!projectId || !query.trim() || searching}><Search size={16} />{searching ? '正在搜索…' : '搜索资料'}</button>
      </div></form>
      {!projectId && <p className="hint">请先选择一个项目，再搜索资料。</p>}
      {searching && <p role="status" className="search-feedback">正在查找相关内容…</p>}
      {searchError && <div role="alert" className="message error">{searchError}</div>}
      {result?.warning && <div role="status" className="message">{result.warning}</div>}
      {result && <><p role="status" className="search-feedback">“{result.query}” · 找到 {result.hits.length} 条相关内容</p>
        {result.hits.length === 0 ? <div className="empty-small">没有找到相关内容。请换个关键词，或确认资料已处理完成。</div> :
          <div className="search-results">{result.hits.map(hit => <article className="search-result" key={hit.chunkId}>
            <div className="source-heading"><div><h3>{hit.source.file_name}</h3><small>{sourceLocation(hit)}</small></div>
              <button className="secondary" aria-expanded={selectedSource?.chunkId === hit.chunkId} onClick={event => {
                sourceTrigger.current = event.currentTarget; setSelectedSource(hit);
              }}>查看来源</button></div><p className="source-excerpt">{hit.source.excerpt}</p>
          </article>)}</div>}
      </>}
      {selectedSource && projectId && <SourceDetail key={selectedSource.chunkId} hit={selectedSource} projectId={projectId}
        onClose={() => { setSelectedSource(null); sourceTrigger.current?.focus(); }} />}
    </section>}
  </section>;
}

function SourceDetail({ projectId, hit, onClose }: { projectId: number; hit: SearchHit; onClose: () => void }) {
  const [chunk, setChunk] = useState<DocumentChunk | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => {
    const controller = new AbortController();
    setChunk(null); setError('');
    api<DocumentChunk>(`/projects/${projectId}/documents/${hit.source.document_id}/chunks/${hit.chunkId}`, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setChunk(data); })
      .catch(e => { if (!controller.signal.aborted) setError(errorMessage(e, '读取来源失败')); });
    return () => controller.abort();
  }, [projectId, hit.source.document_id, hit.chunkId, attempt]);
  return <section className="source-detail" role="region" aria-labelledby="source-detail-title">
    <div className="source-heading"><h3 id="source-detail-title" tabIndex={-1} ref={heading}>来源详情</h3>
      <button className="source-close" aria-label="关闭来源详情" onClick={onClose}><X size={18} /></button></div>
    <strong>{hit.source.file_name}</strong><p className="source-location">{sourceLocation(hit)}</p>
    {error ? <><div role="alert" className="message error">{error}</div><button className="secondary" onClick={() => setAttempt(value => value + 1)}>重试读取来源</button></> :
      chunk ? <div className="source-content">{chunk.content}</div> : <p role="status">正在读取原文…</p>}
  </section>;
}
