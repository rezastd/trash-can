async function readError(response) {
  try {
    const data = await response.json();
    return data.detail || data.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function classifyPhoto(blob) {
  const form = new FormData();
  form.append("image", blob, "photo.jpg");
  const response = await fetch("/api/classify", { method: "POST", body: form });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function fetchBins() {
  const response = await fetch("/api/bins");
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).bins;
}

export async function saveBins(bins) {
  const response = await fetch("/api/bins", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bins }),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).bins;
}

export async function resetBins() {
  const response = await fetch("/api/bins/reset", { method: "POST" });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).bins;
}
