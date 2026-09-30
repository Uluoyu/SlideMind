export interface Project {
  id: number; name: string; description: string; templateId: number | null;
  createdAt: string; updatedAt: string;
}
export interface StoredFile {
  id: number; fileName: string; fileType: string; sizeBytes: number;
  securityLevel: string; status: string; createdAt: string;
}
export type DocumentStatus = 'UPLOADED' | 'QUEUED' | 'PARSING' | 'INDEXING' | 'READY' | 'FAILED';
export interface ProjectDocument extends StoredFile {
  status: DocumentStatus; processingError: string | null; chunkCount: number; processedAt: string | null;
}
export interface SearchHit {
  chunkId: number; score: number; source: SourceReference; location: string | null;
}
export interface SearchResult {
  query: string; hits: SearchHit[]; mode: 'hybrid' | 'hybrid-rerank'; warning: string | null;
}
export interface DocumentChunk {
  id: number; chunkIndex: number; pageNo: number | null; content: string; metadata: Record<string, unknown>;
}
export interface Presentation {
  id: number; projectId: number; title: string; pageCount: number;
  audience: string; style: string; requirements: string[]; status: string;
}
export interface OutlinePage { pageNo: number; title: string; purpose: string }
export interface Outline { pages: OutlinePage[]; status: string; planner: string }

export interface SourceReference {
  document_id: number; file_name: string; page_no: number | null; excerpt: string;
}
export interface TextBlock {
  type: 'text'; title: string; text: string; sources: SourceReference[];
}
export interface PageSpec {
  schema_version: '1.0'; page_no: number; layout: 'title' | 'two_column' | 'summary';
  title: string; subtitle: string; content: TextBlock[];
}
export interface PageRecord {
  pageNo: number; version: number; status: string; pageJson: PageSpec | null;
}
export interface Pages { status: string; pages: PageRecord[]; generator: string }

export async function apiResponse(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`/api/ppt${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail :
      Array.isArray(detail) ? detail.map(item => `${item.loc.join('.')}: ${item.msg}`).join('；') :
      `请求失败（${response.status}），请检查后端服务与数据库迁移。`);
  }
  return response;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await apiResponse(path, init)).json() as Promise<T>;
}

export function post(body?: unknown): RequestInit {
  return { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) };
}

export const statusText: Record<string, string> = {
  DRAFT: '待策划', OUTLINE_GENERATED: '大纲待确认', OUTLINE_CONFIRMED: '大纲已确认',
  UPLOADED: '待解析', COMPLETED: '已完成', FAILED: '失败',
  DESIGN_GENERATED: '页面待导出', RENDERING: '正在导出',
};
