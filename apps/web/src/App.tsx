import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { ArrowRight, BookOpen, ChevronRight, Folder, Layers3, LayoutDashboard, Plus, Sparkles } from 'lucide-react';
import { api, post, statusText, type Outline, type Presentation, type Project, type TemplateFile } from './api';
import Library from './Library';
import OutlineEditor from './OutlineEditor';
import PageEditor from './PageEditor';

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [presentations, setPresentations] = useState<Presentation[]>([]);
  const [presentationId, setPresentationId] = useState<number | null>(null);
  const [outline, setOutline] = useState<Outline | null>(null);
  const [view, setView] = useState<'workspace' | 'library'>('workspace');
  const [newProject, setNewProject] = useState(false);
  const [newDeck, setNewDeck] = useState(false);
  const [templates, setTemplates] = useState<TemplateFile[]>([]);
  const [requestBusy, setBusy] = useState(false);
  const [editorBusy, setEditorBusy] = useState(false);
  const [editorDirty, setEditorDirty] = useState(false);
  const busy = requestBusy || editorBusy || editorDirty;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const project = projects.find(p => p.id === projectId);
  const deck = presentations.find(p => p.id === presentationId);
  const linkedTemplate = templates.find(t => t.id === project?.templateId);
  // Only a parsed (READY) template actually applies at export; anything else falls back.
  const templateName = linkedTemplate?.status === 'READY' ? linkedTemplate.fileName : null;

  const updateStatus = useCallback((status: string) => {
    setPresentations(current => current.map(p => p.id === presentationId ? { ...p, status } : p));
    setOutline(current => current ? { ...current, status } : null);
  }, [presentationId]);

  useEffect(() => {
    let active = true;
    api<Project[]>('/projects').then(data => {
      if (active) { setProjects(data); setProjectId(data[0]?.id ?? null); }
    }).catch(e => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setPresentations([]); setPresentationId(null); setOutline(null); setNewDeck(false);
    if (projectId === null) return;
    setLoading(true);
    api<Presentation[]>(`/projects/${projectId}/presentations`).then(data => {
      if (active) { setPresentations(data); setPresentationId(data[0]?.id ?? null); }
    }).catch(e => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId]);

  useEffect(() => {
    let active = true;
    setOutline(null);
    if (!presentationId || !projectId) return;
    api<Presentation>(`/documents/${presentationId}?projectId=${projectId}`).then(async current => {
      if (current.status === 'DRAFT') return;
      const data = await api<Outline>(`/documents/${presentationId}/outline?projectId=${projectId}`);
      if (active) setOutline(data);
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [presentationId, projectId]);

  // Template choices back the project-section selector; a failed fetch just leaves it empty.
  useEffect(() => {
    if (view !== 'workspace' || projectId === null) return;
    let active = true;
    api<TemplateFile[]>('/templates').then(data => { if (active) setTemplates(data); }).catch(() => {});
    return () => { active = false; };
  }, [view, projectId]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setBusy(false); }
  }

  async function openProjectForm() {
    setNewProject(true); setView('workspace');
    await run(async () => setTemplates(await api<TemplateFile[]>('/templates')));
  }

  function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    void run(async () => {
      const created = await api<Project>('/projects', post({ name: fields.get('name'),
        description: fields.get('description'), templateId: fields.get('templateId') ? Number(fields.get('templateId')) : null }));
      setProjects(current => [created, ...current]); setProjectId(created.id); setNewProject(false);
    });
  }

  function createDeck(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    void run(async () => {
      const created = await api<Presentation>('/documents', post({ projectId,
        title: fields.get('title'), pageCount: Number(fields.get('pageCount')),
        audience: fields.get('audience'), style: fields.get('style'),
        requirements: String(fields.get('requirements')).split('\n').map(x => x.trim()).filter(Boolean) }));
      setPresentations(current => [created, ...current]); setPresentationId(created.id); setNewDeck(false);
    });
  }

  function applyTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project) return;
    const fields = new FormData(event.currentTarget);
    void run(async () => {
      const updated = await api<Project>(`/projects/${project.id}/template`,
        post({ templateId: fields.get('templateId') ? Number(fields.get('templateId')) : null }));
      setProjects(current => current.map(p => p.id === updated.id ? updated : p));
    });
  }

  // confirm: save the edited outline; feedback: model revision of the edited outline; neither: (re)generate.
  function updateOutline(confirm: boolean, feedback?: string) {
    if (!deck) return;
    const pages = outline?.pages.map(({ pageNo, title, purpose, sourceChunkIds }) => ({ pageNo, title, purpose, sourceChunkIds }));
    void run(async () => {
      const result = await api<Outline>(`/documents/${deck.id}/outline/${confirm ? 'confirm' : 'generate'}?projectId=${projectId}`,
        post(confirm ? { pages } : feedback ? { feedback, pages } : undefined));
      setOutline(result);
      // The task's page count changes only when an outline is confirmed (matches the server).
      setPresentations(current => current.map(p => p.id === deck.id ? { ...p, status: result.status, pageCount: confirm ? result.pages.length : p.pageCount } : p));
    });
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="SlideMind 首页" onClick={e => { if (busy) e.preventDefault(); }}><span className="brand-icon"><Layers3 size={24} /></span>SlideMind<span className="brand-dot">.</span></a>
      <span className="workspace-label">个人工作空间</span>
      <nav><button disabled={busy} className={view === 'workspace' ? 'nav-item active' : 'nav-item'} onClick={() => setView('workspace')}><LayoutDashboard size={18} />创作工作台</button>
        <button disabled={busy} className={view === 'library' ? 'nav-item active' : 'nav-item'} onClick={() => setView('library')}><BookOpen size={18} />资料与模板</button></nav>
      <div className="sidebar-heading"><span>我的项目</span><button aria-label="创建项目" disabled={busy} onClick={() => void openProjectForm()}><Plus size={17} /></button></div>
      <div className="project-list">{projects.length === 0 && <p className="sidebar-empty">把下一次汇报，<br />从一个项目开始。</p>}{projects.map(p =>
        <button disabled={busy} key={p.id} className={`project-link ${projectId === p.id ? 'selected' : ''}`} onClick={() => { setProjectId(p.id); setView('workspace'); setNewProject(false); }}><Folder size={16} /><span>{p.name}</span></button>)}</div>
      <div className="sidebar-bottom"><span className="avatar">我</span><div><strong>个人工作台</strong><small>Local workspace · v0.1</small></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><span>工作空间</span><ChevronRight size={14} /><strong>{view === 'library' ? '资料与模板' : project?.name ?? '开始创作'}</strong><span className="version-pill">基础框架</span></header>
      <main>
        {error && <div role="alert" className="message error">{error}<button aria-label="关闭错误提示" onClick={() => setError('')}>×</button></div>}
        {view === 'library' ? <Library key={projectId} projectId={projectId} /> : <>
          <section className="hero"><div><span className="eyebrow"><span className="tiny-dot" /> THINK CLEAR. PRESENT BETTER.</span>
            <h1>让想法，<br />成为有说服力的表达。</h1><p>从项目资料出发，梳理思路、规划页面。<br />和你的 PPT 智能体，一起完成下一次精彩汇报。</p>
            <button className="primary" disabled={busy || loading} onClick={() => project ? setNewDeck(true) : void openProjectForm()}><Plus size={17} />{project ? '开始新的 PPT' : '创建第一个项目'}<ArrowRight size={16} /></button></div>
            <div className="hero-art" aria-hidden="true"><div className="paper back" /><div className="paper front"><span className="paper-tag">A CLEARER PERSPECTIVE</span><div className="paper-title">Ideas.<br />Into impact.</div><div className="paper-rule" /><div className="paper-chart"><i /><i /><i /><i /><i /></div><span className="paper-footer">SLIDEMIND <span>01 / 08</span></span></div><span className="floating-mark"><Sparkles size={22} /></span></div>
          </section>
          {newProject && <form className="form-panel" onSubmit={createProject}><div className="section-heading compact"><h2>创建项目空间</h2><button type="button" className="text-button" disabled={busy} onClick={() => setNewProject(false)}>取消</button></div>
            <div className="form-grid"><label>项目名称<input name="name" placeholder="例如：华力 8A 人员轨迹项目" required maxLength={128} autoFocus /></label><label>公司模板<select name="templateId"><option value="">稍后配置</option>{templates.map(t => <option key={t.id} value={t.id}>{t.fileName}</option>)}</select></label></div>
            <label>项目说明<textarea name="description" rows={2} maxLength={4000} placeholder="项目背景、目标与使用场景" /></label><button className="primary" disabled={busy}>创建项目<ArrowRight size={16} /></button></form>}
          <section className="workflow-strip"><div><span>01</span><div><strong>整理资料</strong><small>建立你的项目知识库</small></div></div><ChevronRight size={17} /><div><span>02</span><div><strong>策划大纲</strong><small>让每一页都有明确目的</small></div></div><ChevronRight size={17} /><div><span>03</span><div><strong>设计与生成</strong><small>编辑页面，导出 PPTX</small></div></div></section>
          {project && <section><div className="section-heading"><div><span className="eyebrow">YOUR PRESENTATIONS</span><h2>{project.name}</h2><p>{project.description || '在这里管理项目的每一次表达。'}</p></div><button className="secondary" disabled={busy} onClick={() => setNewDeck(true)}><Plus size={16} />新建 PPT</button></div>
            <form className="template-bar" onSubmit={applyTemplate}><label htmlFor="project-template">公司模板
              <select id="project-template" name="templateId" key={project.id} defaultValue={project.templateId ?? ''}>
                <option value="">不使用模板（默认主题）</option>
                {templates.map(t => <option key={t.id} value={t.id}>
                  {t.fileName}{t.status === 'READY' ? '' : `（${t.status === 'FAILED' ? '解析失败' : '待解析'}）`}</option>)}
              </select></label>
              <button className="secondary" disabled={busy}>应用模板</button>
              <small className="muted">{templateName ? '导出 PPTX 时将应用该模板的主题颜色、字体与页面尺寸。' :
                project.templateId ? '关联的模板未解析成功，导出使用默认主题；可先在“资料与模板”中重试解析。' :
                  '未关联模板，导出使用默认主题。'}</small>
            </form>
            {newDeck && <form className="form-panel" onSubmit={createDeck}><div className="section-heading compact"><h2>这一次，你想表达什么？</h2><button className="text-button" type="button" disabled={busy} onClick={() => setNewDeck(false)}>取消</button></div>
              <label>汇报主题<input name="title" defaultValue={project.name} required maxLength={255} /></label>
              <div className="form-grid three"><label>页数<input name="pageCount" type="number" min={1} max={50} defaultValue={8} required /></label><label>汇报对象<input name="audience" placeholder="例如：公司领导" maxLength={128} /></label><label>风格<input name="style" defaultValue="专业、简洁" maxLength={255} /></label></div>
              <label>希望突出的重点<textarea name="requirements" rows={3} placeholder="每行一个重点，例如：&#10;人员轨迹分析&#10;AI 违规检测" maxLength={10000} /></label><button className="primary" disabled={busy}>创建 PPT 任务<ArrowRight size={16} /></button></form>}
            {loading ? <p role="status">正在加载项目…</p> : presentations.length === 0 ? <div className="empty-state"><span className="icon-tile"><Layers3 size={25} /></span><h3>留给下一个好想法的位置</h3><p>新建一个 PPT，先从主题与大纲开始。</p></div> :
              <div className="deck-grid">{presentations.map(p => <button key={p.id} disabled={busy} className={`deck-card ${p.id === presentationId ? 'selected' : ''}`} onClick={() => { setPresentationId(p.id); setNewDeck(false); }}><div className="deck-preview"><span>SLIDEMIND / PROJECT</span><strong>{p.title}</strong><i /></div><div className="deck-info"><strong>{p.title}</strong><span>{p.pageCount} 页 <span className="badge">{statusText[p.status] ?? p.status}</span></span></div></button>)}</div>}
            {deck && !newDeck && <div className="selected-deck"><div className="section-heading compact"><h2>{deck.title}</h2>{deck.status === 'DRAFT' && <button className="primary" disabled={busy} onClick={() => updateOutline(false)}><Sparkles size={16} />{requestBusy ? '正在生成大纲…' : '生成初始大纲'}</button>}</div>
              {outline ? outline.status === 'OUTLINE_GENERATED' ?
                <OutlineEditor outline={outline} busy={busy} onChange={setOutline} onConfirm={() => updateOutline(true)}
                  onRegenerate={() => updateOutline(false)} onRevise={feedback => updateOutline(false, feedback)} /> : <>
                  <details className="confirmed-outline"><summary>查看已确认大纲（{outline.pages.length} 页）</summary>
                    <OutlineEditor outline={outline} busy={busy} onChange={setOutline} onConfirm={() => updateOutline(true)} /></details>
                  <PageEditor key={deck.id} documentId={deck.id} projectId={project.id} templateName={templateName}
                    onStatus={updateStatus} onBusy={setEditorBusy} onDirty={setEditorDirty} />
                </> : <p className="hint">{deck.status === 'DRAFT' ? '先生成可编辑的大纲，再逐页确认汇报思路。配置模型服务后会结合项目资料规划，可能需要几十秒。' : '正在读取大纲…'}</p>}</div>}
          </section>}
          {!project && !newProject && !loading && <div className="empty-small">创建项目后，即可上传资料、管理模板和策划 PPT 大纲。</div>}
        </>}
        <footer className="page-footer"><span>SlideMind · 会思考的 PPT Agent</span><span>从内容出发，让表达发生。</span></footer>
      </main>
    </div>
  </div>;
}
