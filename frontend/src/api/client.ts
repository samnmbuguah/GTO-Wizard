const BASE_URL = import.meta.env.PROD ? 'http://localhost:8000/api' : '/api';

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number>;
}

export const apiClient = {
  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { params, ...rest } = options;
    const token = localStorage.getItem('gto_token');
    
    let url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          searchParams.append(key, value.toString());
        }
      });
      const queryString = searchParams.toString();
      if (queryString) url += `?${queryString}`;
    }

    const headers = new Headers(rest.headers);
    if (token) {
      headers.set('Authorization', `Token ${token}`);
    }
    if (!(rest.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const response = await fetch(url, {
      ...rest,
      headers,
    });

    if (response.status === 401) {
      localStorage.removeItem('gto_token');
      localStorage.removeItem('gto_user');
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: 'An unexpected error occurred' };
      }
      throw errorData;
    }

    return response.json();
  },

  get<T>(endpoint: string, params?: Record<string, string | number>, options?: RequestOptions) {
    return this.request<T>(endpoint, { ...options, method: 'GET', params });
  },

  post<T>(endpoint: string, body: any, options?: RequestOptions) {
    return this.request<T>(endpoint, { 
      ...options, 
      method: 'POST', 
      body: JSON.stringify(body) 
    });
  },

  patch<T>(endpoint: string, body: any, options?: RequestOptions) {
    return this.request<T>(endpoint, { 
      ...options, 
      method: 'PATCH', 
      body: JSON.stringify(body) 
    });
  },

  delete<T>(endpoint: string, options?: RequestOptions) {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }
};
