let csrf = '';

export async function session() {
  const response = await fetch('/engineering/session', { credentials: 'same-origin', cache: 'no-store' });
  if (!response.ok) throw new Error('The local workbench is unavailable. Start the Python service.');
  csrf = (await response.json()).csrf;
}

export async function api<T>(path: string, body?: unknown, signal?: AbortSignal, renewed = false): Promise<T> {
  const response = await fetch(path, { method: body === undefined ? 'GET' : 'POST', signal, credentials: 'same-origin', cache: 'no-store',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json', 'X-Workbench-CSRF': csrf },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const result = await response.json();
  if (!renewed && (response.status === 401 || (response.status === 403 && result.detail === 'Local session and CSRF token required'))) {
    await session();
    return api<T>(path, body, signal, true);
  }
  if (!response.ok) {
    const detail = result.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join('; ') : 'Request failed');
  }
  return result;
}
