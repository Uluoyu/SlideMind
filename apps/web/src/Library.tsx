import { useEffect, useRef, useState } from 'react';
import { FileText, Image, Layers3, Upload } from 'lucide-react';
import { api, type StoredFile } from './api';

type Kind = 'documents' | 'assets' | 'templates';
const kinds: { key: Kind; label: string; accept: string }[] = [
  { key: 'documents', label: '项目资料', accept: '.pdf,.docx,.pptx,.xlsx,.txt,.md' },
  { key: 'assets', label: '图片素材', accept: '.png,.jpg,.jpeg,.webp' },
  { key: 'templates', label: '公司模板', accept: '.pptx' },
];

export default function Library({ projectId }: { projectId: number | null }) {
  const [kind, setKind] = useState<Kind>('documents');
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [level, setLevel] = useState('INTERNAL');
  const input = useRef<HTMLInputElement>(null);
  const path = kind === 'templates' ? '/templates' : projectId ? `/projects/${projectId}/${kind}` : null;
  const current = kinds.find(item => item.key === kind)!;

  useEffect(() => {
    let active = true;
    setFiles([]); setError(''); setNotice('');
    if (!path) return;
    setLoading(true);
    api<StoredFile[]>(path).then(data => { if (active) setFiles(data); })
      .catch(e => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path]);

  async function upload(file: File) {
    if (!path) return;
    setUploading(true); setError(''); setNotice('');
    const form = new FormData(); form.append('file', file); form.append('securityLevel', level);
    try {
      await api<StoredFile>(path, { method: 'POST', body: form });
      setFiles(await api<StoredFile[]>(path));
      setNotice('文件已保存。解析与索引将在后续版本接入。');
    } catch (e) { setError(e instanceof Error ? e.message : '上传失败'); }
    finally { setUploading(false); if (input.current) input.current.value = ''; }
  }

  return <section className="library">
    <div className="section-heading"><div><span className="eyebrow">YOUR KNOWLEDGE, ORGANIZED</span>
      <h1>每一份资料，都是表达的底气。</h1><p>按项目归档资料与素材，独立管理公司的视觉模板。</p></div></div>
    <div className="tabs" aria-label="资料类别">{kinds.map(item =>
      <button key={item.key} disabled={uploading} className={kind === item.key ? 'active' : ''}
        onClick={() => setKind(item.key)}>{item.key === 'documents' ? <FileText size={16} /> :
          item.key === 'assets' ? <Image size={16} /> : <Layers3 size={16} />}{item.label}</button>)}</div>
    {error && <div role="alert" className="message error">{error}</div>}
    {notice && <div role="status" className="message success">{notice}</div>}
    <div className="upload-zone">
      <span className="icon-tile"><Upload size={24} /></span><h2>添加{current.label}</h2>
      <p>{path ? `支持 ${current.accept.replaceAll('.', '').toUpperCase().replaceAll(',', ' / ')}` : '请先创建或选择一个项目'}</p>
      <div className="upload-actions"><label>安全等级<select value={level} onChange={e => setLevel(e.target.value)} disabled={uploading}>
        <option value="PUBLIC">公开</option><option value="INTERNAL">内部</option>
        <option value="CONFIDENTIAL">机密</option><option value="TOP_SECRET">绝密</option>
      </select></label><button className="primary" disabled={!path || uploading} onClick={() => input.current?.click()}>
        <Upload size={16} />{uploading ? '正在上传…' : '选择文件'}</button></div>
      <input ref={input} type="file" accept={current.accept} hidden onChange={e => {
        const file = e.target.files?.[0]; if (file) void upload(file);
      }} />
      <small>文件按项目保存；公司模板属于共享模板库。</small>
    </div>
    <div className="section-heading compact"><h2>{current.label}</h2><span className="muted">{files.length} 个文件</span></div>
    {loading ? <p role="status">正在读取文件…</p> : files.length === 0 ?
      <div className="empty-small">这里还没有文件。上传第一份资料，开始积累项目知识。</div> :
      <div className="file-list">{files.map(file => <div className="file-row" key={file.id}>
        <span className="file-type">{file.fileType.toUpperCase()}</span><div className="file-name"><strong>{file.fileName}</strong>
          <small>{(file.sizeBytes / 1024).toFixed(1)} KB · {new Date(file.createdAt).toLocaleDateString('zh-CN')}</small></div>
        <span className="muted">{file.securityLevel}</span><span className="badge">待解析</span>
      </div>)}</div>}
  </section>;
}
