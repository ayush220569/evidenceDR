import React, { useState } from "react";
import { apiClient } from "../lib/api";
import { LayerTag } from "./UIBits";
import { UploadSimple, Trash, Eye, FileArchive, X, Warning } from "@phosphor-icons/react";

const LAYER_KEYS = ["browser", "web_tier", "portal", "server", "datastore", "client_pro", "os_system", "unknown"];

export default function FileUploader({ caseId, files, layers, onChange }) {
  const [uploading, setUploading] = useState(false);
  const [drag, setDrag] = useState(false);
  const [preview, setPreview] = useState(null);
  const [preflight, setPreflight] = useState(null); // { settings, files: [...] } awaiting user confirm
  const [pendingUpload, setPendingUpload] = useState(null); // FileList held while user reviews

  const runPreflight = async (fileList) => {
    if (!fileList?.length) return;
    const items = Array.from(fileList).map(f => ({ name: f.name, size: f.size }));
    try {
      const res = await apiClient.uploadPreflight(items);
      const anyWarnings = res.files.some(f => f.warnings?.length > 0);
      if (anyWarnings) {
        setPreflight(res);
        setPendingUpload(fileList);
        return;
      }
    } catch (e) {
      // pre-flight is advisory only — failure shouldn't block upload
    }
    handleFiles(fileList);
  };

  const handleFiles = async (fileList) => {
    if (!fileList?.length) return;
    setPreflight(null);
    setPendingUpload(null);
    setUploading(true);
    try {
      const res = await apiClient.uploadFiles(caseId, Array.from(fileList));
      onChange?.(res.case);
    } catch (e) {
      alert(`Upload failed: ${e.response?.data?.detail || e.message}`);
    } finally { setUploading(false); }
  };

  const onDrop = (e) => {
    e.preventDefault(); setDrag(false);
    runPreflight(e.dataTransfer.files);
  };

  const setLayer = async (fileId, layer) => {
    await apiClient.setFileLayer(caseId, fileId, layer);
    const c = await apiClient.getCase(caseId);
    onChange?.(c);
  };

  const remove = async (fileId) => {
    await apiClient.deleteFile(caseId, fileId);
    const c = await apiClient.getCase(caseId);
    onChange?.(c);
  };

  const extract = async (fileId) => {
    await apiClient.extractZip(caseId, fileId);
    const c = await apiClient.getCase(caseId);
    onChange?.(c);
  };

  const view = async (file) => {
    const data = await apiClient.previewFile(caseId, file.id);
    setPreview({ ...file, text: data.text });
  };

  return (
    <div data-testid="file-uploader">
      <div
        onDragOver={e => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-md p-6 text-center transition-colors ${drag ? "border-[#00E5FF] bg-[#00E5FF]/5" : "border-white/15 bg-[#0A0A0C]"}`}
        data-testid="dropzone"
      >
        <UploadSimple size={36} weight="duotone" className="mx-auto mb-3 text-[#00E5FF]" />
        <div className="font-heading font-bold uppercase tracking-wider text-sm mb-1">Drop files or click to upload</div>
        <div className="text-xs text-[#71717A] mb-3 font-mono">.log .txt .json .xml .csv .har .zip .dmp .evtx images / pdf</div>
        <label className="btn-primary cursor-pointer inline-flex" data-testid="upload-input-label">
          {uploading ? "Uploading…" : "Choose files"}
          <input type="file" multiple className="hidden" onChange={e => runPreflight(e.target.files)} data-testid="file-input" />
        </label>
      </div>

      {preflight && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6" onClick={() => { setPreflight(null); setPendingUpload(null); }}>
          <div className="ep-card max-w-2xl w-full max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()} data-testid="preflight-modal">
            <div className="flex items-center gap-3 p-4 border-b border-white/10">
              <Warning size={22} weight="duotone" className="text-[#F59E0B]" />
              <div className="flex-1">
                <div className="font-heading font-bold uppercase text-sm">Upload pre-flight</div>
                <div className="text-[11px] text-[#71717A] font-mono">{preflight.files.length} file(s) — review before indexing</div>
              </div>
              <button onClick={() => { setPreflight(null); setPendingUpload(null); }} className="text-[#A1A1AA] hover:text-white" data-testid="close-preflight"><X size={20} /></button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {preflight.files.map((f, i) => (
                <div key={i} className="border border-white/10 rounded p-3 bg-[#0A0A0C]" data-testid={`preflight-file-${i}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="font-mono text-sm truncate flex-1">{f.name}</div>
                    <div className="text-[11px] font-mono text-[#71717A] ml-2">{(f.size / 1_000_000).toFixed(2)} MB</div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[11px] font-mono mb-2">
                    <div><span className="text-[#71717A]">chunks: </span><span className="text-[#00E5FF]">{f.estimated_chunks ?? "—"}</span></div>
                    <div><span className="text-[#71717A]">coverage: </span><span className={f.estimated_coverage < 0.5 ? "text-[#F59E0B]" : "text-[#10B981]"}>{(f.estimated_coverage * 100).toFixed(0)}%</span></div>
                    <div><span className="text-[#71717A]">handler: </span><span>{f.is_binary_handler ? "binary parser" : "text/log"}</span></div>
                  </div>
                  {f.warnings?.length > 0 && (
                    <div className="space-y-1">
                      {f.warnings.map((w, j) => (
                        <div key={j} className="flex items-start gap-2 text-[11px] text-[#F59E0B]" data-testid={`preflight-warning-${i}-${j}`}>
                          <Warning size={12} className="mt-0.5 flex-shrink-0" />
                          <span>{w}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              <div className="border border-white/5 rounded p-2 text-[11px] font-mono text-[#71717A]">
                Current caps · max_chunks={preflight.settings.max_chunks_per_file.toLocaleString()} ·
                index_bytes={(preflight.settings.max_index_bytes_per_file / 1_000_000).toFixed(0)}MB ·
                mode={preflight.settings.index_read_mode}
                <div className="text-[10px] mt-1">Adjust in Settings → Retrieval.</div>
              </div>
            </div>

            <div className="p-4 border-t border-white/10 flex gap-2 justify-end">
              <button onClick={() => { setPreflight(null); setPendingUpload(null); }} className="btn-secondary" data-testid="preflight-cancel">Cancel</button>
              <button onClick={() => handleFiles(pendingUpload)} className="btn-primary" data-testid="preflight-proceed">Upload anyway</button>
            </div>
          </div>
        </div>
      )}

      {files?.length > 0 && (
        <div className="mt-4 border border-white/10 rounded-md overflow-hidden">
          {files.map(f => (
            <div key={f.id} className="flex items-center gap-3 px-4 py-3 border-b border-white/5 last:border-b-0 hover:bg-white/5" data-testid={`file-row-${f.id}`}>
              <div className="flex-1 min-w-0">
                <div className="font-mono text-sm truncate">{f.name}</div>
                <div className="text-[11px] text-[#71717A]">{(f.size / 1024).toFixed(1)} KB · {f.ext} {f.from_zip && `· from ${f.from_zip}`}</div>
              </div>
              <select value={f.layer} onChange={e => setLayer(f.id, e.target.value)} className="text-xs px-2 py-1.5 font-mono" data-testid={`file-layer-${f.id}`}>
                {LAYER_KEYS.map(k => <option key={k} value={k}>{layers?.[k]?.name || k}</option>)}
              </select>
              <LayerTag layer={f.layer} layers={layers} />
              <button onClick={() => view(f)} className="text-[#A1A1AA] hover:text-[#00E5FF] p-1" data-testid={`preview-${f.id}`}><Eye size={16} /></button>
              {f.ext === ".zip" && <button onClick={() => extract(f.id)} className="text-[#A1A1AA] hover:text-[#00E5FF] p-1" title="Extract zip" data-testid={`extract-${f.id}`}><FileArchive size={16} /></button>}
              <button onClick={() => remove(f.id)} className="text-[#A1A1AA] hover:text-[#EF4444] p-1" data-testid={`delete-file-${f.id}`}><Trash size={16} /></button>
            </div>
          ))}
        </div>
      )}

      {preview && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6" onClick={() => setPreview(null)}>
          <div className="ep-card max-w-3xl w-full max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-white/10">
              <div>
                <div className="font-heading font-bold uppercase text-sm">{preview.name}</div>
                <div className="text-[11px] text-[#71717A] font-mono">{(preview.size/1024).toFixed(1)} KB · layer: {preview.layer}</div>
              </div>
              <button onClick={() => setPreview(null)} className="text-[#A1A1AA] hover:text-white" data-testid="close-preview"><X size={20} /></button>
            </div>
            <div className="terminal-block flex-1 overflow-y-auto m-4" style={{ maxHeight: "60vh" }} data-testid="preview-content">
              {preview.text}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
