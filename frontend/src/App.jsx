import { useCallback, useEffect, useRef, useState } from "react";
import { classifyPhoto, fetchBins, resetBins, saveBins } from "./api.js";

function slugify(text) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100);
  return (
    <div className="conf-row">
      <div className="conf-track">
        <div className="conf-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="conf-num">{pct}%</span>
    </div>
  );
}

function ClassifyTab() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [cameraError, setCameraError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startCamera = useCallback(async () => {
    setCameraError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("This browser has no camera API. Use photo upload below.");
      return;
    }
    try {
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err) {
      setCameraError(
        err?.name === "NotAllowedError"
          ? "Camera permission denied. Allow it in the browser, or use photo upload."
          : `Camera unavailable (${err?.name || "error"}). Use photo upload below.`
      );
    }
  }, [stopCamera]);

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, [startCamera, stopCamera]);

  async function classify(blob) {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await classifyPhoto(blob));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function capture() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob((blob) => blob && classify(blob), "image/jpeg", 0.9);
  }

  function onFile(event) {
    const file = event.target.files?.[0];
    if (file) classify(file);
    event.target.value = "";
  }

  return (
    <section>
      <div className="camera-box">
        {cameraError ? (
          <p className="muted">{cameraError}</p>
        ) : (
          <video ref={videoRef} playsInline muted className="camera" />
        )}
        <canvas ref={canvasRef} hidden />
      </div>
      <div className="row">
        {!cameraError && (
          <button onClick={capture} disabled={busy} className="primary">
            {busy ? "Classifying…" : "Classify this item"}
          </button>
        )}
        <label className="file-btn">
          Upload photo
          <input type="file" accept="image/*" capture="environment" onChange={onFile} hidden />
        </label>
      </div>
      {cameraError && (
        <p className="muted small">
          Tip: camera needs HTTPS. If you opened this over plain HTTP on your
          phone, reload via the https address from the run guide.
        </p>
      )}
      {error && <p className="error">{error}</p>}
      {result && (
        <article className="result">
          <p className="kicker">Put it in</p>
          <h2>{result.bin_name}</h2>
          <ConfidenceBar value={result.confidence} />
          {result.runner_up && (
            <p className="runner">
              Runner-up: {result.runner_up.name} (
              {Math.round(result.runner_up.p * 100)}%)
            </p>
          )}
          <details>
            <summary>What the camera saw</summary>
            <dl>
              {Object.entries(result.description).map(([k, v]) => (
                <div key={k} className="desc-row">
                  <dt>{k}</dt>
                  <dd>{v || "—"}</dd>
                </div>
              ))}
            </dl>
          </details>
        </article>
      )}
    </section>
  );
}

function BinsTab() {
  const [bins, setBins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    fetchBins()
      .then(setBins)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  function update(i, patch) {
    setBins((prev) => prev.map((b, j) => (j === i ? { ...b, ...patch } : b)));
    setNotice("");
  }

  function addBin() {
    const id = slugify(`bin-${bins.length + 1}`);
    setBins((prev) => [...prev, { id, name: "", rules: "" }]);
  }

  function removeBin(i) {
    setBins((prev) => prev.filter((_, j) => j !== i));
  }

  async function save() {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const saved = await saveBins(bins);
      setBins(saved);
      setNotice("Saved. New classifications use these bins.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      setBins(await resetBins());
      setNotice("Restored the default bin set.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="muted">Loading bins…</p>;

  return (
    <section>
      <p className="muted">
        These bins become the choices the classifier picks from. Match them to
        your real cans: the name shows on the result screen, the rules tell the
        judge what goes in.
      </p>
      {bins.map((bin, i) => (
        <article key={`${bin.id}-${i}`} className="bin-card">
          <div className="row spread">
            <code className="bin-id">{bin.id || "(no id yet)"}</code>
            <button
              className="danger-link"
              onClick={() => removeBin(i)}
              disabled={saving || bins.length <= 1}
            >
              Remove
            </button>
          </div>
          <label>
            ID
            <input
              value={bin.id}
              onChange={(e) => update(i, { id: slugify(e.target.value) })}
              placeholder="e.g. recycle"
              autoCapitalize="none"
            />
          </label>
          <label>
            Name
            <input
              value={bin.name}
              onChange={(e) => update(i, { name: e.target.value })}
              placeholder="e.g. Recycle"
            />
          </label>
          <label>
            Rules
            <textarea
              value={bin.rules}
              onChange={(e) => update(i, { rules: e.target.value })}
              placeholder="What belongs in this bin?"
              rows={3}
            />
          </label>
        </article>
      ))}
      <div className="row">
        <button onClick={save} disabled={saving} className="primary">
          {saving ? "Saving…" : "Save bins"}
        </button>
        <button onClick={addBin} disabled={saving}>
          Add bin
        </button>
        <button onClick={reset} disabled={saving}>
          Reset to defaults
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {notice && <p className="notice">{notice}</p>}
    </section>
  );
}

export default function App() {
  const [tab, setTab] = useState("classify");
  return (
    <div className="page">
      <header>
        <h1>Which Bin?</h1>
        <nav>
          <button
            className={tab === "classify" ? "active" : ""}
            onClick={() => setTab("classify")}
          >
            Classify
          </button>
          <button
            className={tab === "bins" ? "active" : ""}
            onClick={() => setTab("bins")}
          >
            Bins
          </button>
        </nav>
      </header>
      <main>{tab === "classify" ? <ClassifyTab /> : <BinsTab />}</main>
    </div>
  );
}
