const BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8787';

async function handleResponse(response) {
  if (!response.ok) {
    const text = await response.text();
    const error = new Error(`Request failed with ${response.status}`);
    error.details = text;
    throw error;
  }
  return response.json();
}

export async function getHealth() {
  const response = await fetch(`${BASE_URL}/health`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' }
  });
  return handleResponse(response);
}

export async function ping(message) {
  const response = await fetch(`${BASE_URL}/api/ping`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ message })
  });
  return handleResponse(response);
}
