export const isUrlSafe = (url: string): boolean => {
  try {
    const parsed = new URL(url);
    const hostname = parsed.hostname;
    
    // Block localhost and common internal IPs
    const blockedHostnames = ['localhost', '127.0.0.1', '0.0.0.0'];
    if (blockedHostnames.includes(hostname)) return false;
    
    // Simple check for internal IPs (10.x.x.x, 192.168.x.x, 172.16.x.x)
    if (/^10\./.test(hostname)) return false;
    if (/^192\.168\./.test(hostname)) return false;
    if (/^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(hostname)) return false;

    return true;
  } catch {
    return false; // Invalid URL
  }
};

export interface ApiResponse {
  status: number;
  statusText: string;
  headers: Record<string, string>;
  data: any;
  time: number;
  error?: string;
}

export const executeRequest = async (
  method: string,
  url: string,
  headersStr: string,
  bodyStr: string
): Promise<ApiResponse> => {
  const startTime = performance.now();
  
  if (!isUrlSafe(url)) {
    return {
      status: 0,
      statusText: 'Blocked',
      headers: {},
      data: null,
      time: 0,
      error: 'Request to localhost or internal IP is blocked for security.',
    };
  }

  let headers = {};
  if (headersStr.trim()) {
    try {
      headers = JSON.parse(headersStr);
    } catch {
      return {
        status: 0,
        statusText: 'Error',
        headers: {},
        data: null,
        time: 0,
        error: 'Invalid JSON format in headers',
      };
    }
  }

  let body = undefined;
  if (['POST', 'PUT', 'PATCH'].includes(method) && bodyStr.trim()) {
    try {
      body = bodyStr;
      JSON.parse(bodyStr); // Just to validate it's proper JSON if they try, though raw text is okay too
    } catch {
      // If it's not JSON, we'll just send it as raw text
    }
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

  try {
    const response = await fetch(url, {
      method,
      headers,
      body,
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);

    const endTime = performance.now();
    const time = Math.round(endTime - startTime);

    const responseHeaders: Record<string, string> = {};
    response.headers.forEach((value, key) => {
      responseHeaders[key] = value;
    });

    let data;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    return {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
      data,
      time,
    };
  } catch (error: any) {
    clearTimeout(timeoutId);
    const endTime = performance.now();
    return {
      status: 0,
      statusText: 'Error',
      headers: {},
      data: null,
      time: Math.round(endTime - startTime),
      error: error.name === 'AbortError' ? 'Request timed out' : error.message || 'Failed to fetch (CORS or Network Error)',
    };
  }
};
