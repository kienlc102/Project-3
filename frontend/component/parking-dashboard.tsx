"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Car, Icon } from "./icons";

type Slot = { id: string; x: number; y: number; width: number; height: number };
type Camera = { camera_id: string; reference_width: number; reference_height: number; slots: Slot[] };
type Status = { ready: boolean; run: string; models: string[]; threshold: number; execution_targets: string[]; camera_configured: boolean; roi_count: number };
type Result = { slot_id: string; status: string; label: number | null; car_score?: number; latency_ms?: number; error?: string };
type Frame = { camera_id: string; frame_id: string; execution_target: string; complete: boolean; results: Result[]; counts: { occupied: number; vacant: number; unknown: number } };
type Entry = { id: string; time: string; source: string; frame: Frame };
type View = "overview" | "slots" | "devices" | "history" | "settings";
const nav: { id: View; name: string; icon: string }[] = [{ id: "overview", name: "Tổng quan", icon: "grid" }, { id: "slots", name: "Quản lý ô đỗ", icon: "car" }, { id: "devices", name: "Camera & thiết bị", icon: "camera" }, { id: "history", name: "Lịch sử kiểm tra", icon: "clock" }, { id: "settings", name: "Cài đặt", icon: "settings" }];
const demoSlots: Slot[] = Array.from({ length: 24 }, (_, i) => ({ id: `${i < 12 ? "A" : "B"}-${String(i % 12 + 1).padStart(2, "0")}`, x: i % 12 * 100, y: i < 12 ? 0 : 200, width: 90, height: 180 }));
const demoCamera: Camera = { camera_id: "camera_demo", reference_width: 1200, reference_height: 400, slots: demoSlots };
const demoFrame: Frame = { camera_id: "camera_demo", frame_id: "demo", execution_target: "esp32", complete: false, counts: { occupied: 16, vacant: 7, unknown: 1 }, results: demoSlots.map((s, i) => ({ slot_id: s.id, status: i === 20 ? "unknown" : "ok", label: i === 20 ? null : [2, 5, 8, 10, 14, 17, 22].includes(i) ? 0 : 1, car_score: i === 20 ? undefined : [2, 5, 8, 10, 14, 17, 22].includes(i) ? .08 : .96, latency_ms: i === 20 ? undefined : 3.2 })) };
const demoStatus: Status = { ready: true, run: "run_gpu01", models: ["int8"], threshold: .75, execution_targets: ["esp32"], camera_configured: true, roi_count: 24 };
const displayTime = (v: string) => new Date(v).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/gateway/${path}`, { ...options, cache: "no-store", signal: AbortSignal.timeout(90000) });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : `Không thể kết nối hệ thống (${response.status}). Kiểm tra backend và BACKEND_URL.`);
  return body as T;
}

export default function ParkingDashboard() {
  const [view, setView] = useState<View>("overview");
  const [demo, setDemo] = useState(true);
  const [status, setStatus] = useState<Status | null>(null);
  const [camera, setCamera] = useState<Camera | null>(null);
  const [frame, setFrame] = useState<Frame | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [updated, setUpdated] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<Result | null>(null);
  const [target, setTarget] = useState("esp32");
  const [lotName, setLotName] = useState("Bãi đỗ xe Trung Tâm");
  const [auto, setAuto] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const requestBusy = useRef(false);
  const generation = useRef(0);
  const currentStatus = demo ? demoStatus : status;
  const currentCamera = demo ? demoCamera : camera;
  const currentFrame = demo ? demoFrame : frame;
  const slots = currentCamera?.slots || [];
  const counts = currentFrame?.counts || { occupied: 0, vacant: 0, unknown: slots.length };
  const occupancy = slots.length ? Math.round(counts.occupied / slots.length * 100) : 0;
  const results: Result[] = slots.map(s => currentFrame?.results.find(r => r.slot_id === s.id) || { slot_id: s.id, label: null, status: "unknown" });
  const visible = results.filter(r => r.slot_id.toLowerCase().includes(query.toLowerCase()) && (filter === "all" || (filter === "occupied" ? r.label === 1 : filter === "vacant" ? r.label === 0 : r.label === null)));

  useEffect(() => { const saved = localStorage.getItem("parkly-lot-name"); if (saved) setLotName(saved); }, []);
  const refresh = useCallback(async () => {
    const version = generation.current;
    setBusy(true); setError("");
    try {
      const [s, r] = await Promise.all([api<Status>("status"), api<{ camera: Camera | null }>("rois")]);
      if (version !== generation.current) return;
      setStatus(s); setCamera(r.camera);
      setTarget(s.execution_targets.includes("esp32") ? "esp32" : "backend");
    } catch (e) { if (version === generation.current) { setError((e as Error).message); setStatus(null); setFrame(null); } }
    finally { if (version === generation.current) setBusy(false); }
  }, []);
  useEffect(() => { if (!demo) void refresh(); }, [demo, refresh]);

  const scan = useCallback(async (file?: File) => {
    if (demo) { setNotice("Đang xem dữ liệu minh họa. Chuyển sang hệ thống thật để kiểm tra camera."); return; }
    if (requestBusy.current) return;
    if (file && (file.size === 0 || file.size > 10 * 1024 * 1024)) { setError("Chọn ảnh có dung lượng từ 1 byte đến 10 MB."); return; }
    const version = generation.current;
    requestBusy.current = true; setBusy(true); setError(""); setFrame(null); setSelected(null);
    try {
      const data = new FormData(); if (file) data.append("file", file);
      const result = await api<Frame>(`${file ? "predict-frame" : "predict-camera"}?target=${target}`, { method: "POST", ...(file ? { body: data } : {}) });
      if (version !== generation.current) return;
      const now = new Date().toISOString(); setFrame(result); setUpdated(now);
      setEntries(prev => [{ id: result.frame_id, time: now, source: file ? "Ảnh tải lên" : "Camera snapshot", frame: result }, ...prev].slice(0, 100));
    } catch (e) { if (version === generation.current) setError((e as Error).message); }
    finally { requestBusy.current = false; if (version === generation.current) setBusy(false); }
  }, [demo, target]);
  useEffect(() => {
    if (!auto || demo || !status) return;
    const timer = setInterval(() => { if (document.visibilityState === "visible") void scan(); }, 30000);
    return () => clearInterval(timer);
  }, [auto, demo, status, scan]);

  function switchMode() {
    generation.current++; setDemo(!demo); setFrame(null); setEntries([]); setSelected(null); setError(""); setUpdated(null); setBusy(false); setAuto(false); setNotice(""); setStatus(null); setCamera(null);
  }
  function upload() { if (demo) setNotice("Chuyển sang hệ thống thật để tải ảnh và kiểm tra ROI."); else fileInput.current?.click(); }
  function exportCsv() {
    const csv = "\uFEFF" + ["slot_id,trang_thai,car_score,latency_ms", ...results.map(r => `${JSON.stringify(r.slot_id)},${r.label === 1 ? "occupied" : r.label === 0 ? "vacant" : "unknown"},${r.car_score ?? ""},${r.latency_ms ?? ""}`)].join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = `parkly-${demo ? "demo" : "snapshot"}.csv`; a.click(); URL.revokeObjectURL(url);
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Parkly trang chủ"><span className="brand-symbol">P<i/></span>parkly<span className="brand-dot">.</span></a>
      <span className="workspace-label">KHÔNG GIAN QUẢN LÝ</span>
      <button className="lot-switch" onClick={() => setView("settings")}><span className="lot-mark"><Icon name="car"/></span><span><strong>{lotName}</strong><small>Không gian chủ bãi</small></span><Icon name="chevron" size={14}/></button>
      <div className="nav-label">VẬN HÀNH</div>
      <nav aria-label="Điều hướng chính">{nav.map(n => <button key={n.id} className={`nav-item ${view === n.id ? "active" : ""}`} title={n.name} onClick={() => { setView(n.id); setQuery(""); }} aria-current={view === n.id ? "page" : undefined}><Icon name={n.icon}/><span>{n.name}</span>{n.id === "slots" && <b className="nav-count">{slots.length || "—"}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><Icon name="signal"/><strong>Mỗi ô đỗ, một góc nhìn.</strong><p>Theo dõi bãi xe trong một không gian duy nhất.</p><button onClick={() => setView("devices")}>Kiểm tra hệ thống <Icon name="arrow" size={15}/></button></div><div className="profile"><span className="avatar">QL</span><span><strong>Chủ bãi đỗ xe</strong><small>Quản lý hệ thống</small></span><Icon name="settings" size={17}/></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb">Không gian quản lý <Icon name="chevron" size={12}/><strong>{nav.find(n => n.id === view)?.name}</strong></div><div className="topbar-right"><span className={`connection ${demo ? "demo" : status ? "online" : "offline"}`}><i/>{demo ? "Dữ liệu minh họa" : status ? "Đã kết nối gateway" : "Chưa kết nối"}</span><button className="icon-button" aria-label="Xem cảnh báo hệ thống" onClick={() => { setView("devices"); setNotice(counts.unknown ? `Có ${counts.unknown} ô chưa xác định. Kiểm tra kết nối và kết quả suy luận.` : "Không có cảnh báo trong kết quả hiện tại."); }}><Icon name="bell"/><i className="notification-dot"/></button><span className="avatar small">QL</span></div></header>
    <main>
      <div className="page-heading"><div><div className="eyebrow">PARKLY / TRUNG TÂM ĐIỀU HÀNH</div><h1>{view === "overview" ? "Một góc nhìn. Toàn bộ bãi xe." : nav.find(n => n.id === view)?.name}</h1><p>{view === "overview" ? "Nắm bắt tình trạng bãi đỗ và chủ động trong từng quyết định." : `Quản lý và theo dõi ${lotName.toLowerCase()}.`}</p></div><button className="button secondary" onClick={switchMode}><i className={`dot ${demo ? "amber" : ""}`}/>{demo ? "Kết nối hệ thống thật" : "Xem bản minh họa"}<Icon name="arrow" size={16}/></button></div>
      {demo && <div className="demo-banner"><Icon name="info" size={16}/><span>Bạn đang khám phá giao diện với <strong>dữ liệu minh họa</strong>. Chuyển sang hệ thống thật để xem bãi xe của bạn.</span><b>DEMO</b></div>}
      {error && <div role="alert" className="alert error"><Icon name="info"/><span>{error}</span><button className="icon-button" onClick={() => setError("")} aria-label="Đóng lỗi"><Icon name="close" size={16}/></button></div>}
      {notice && <div role="status" className="alert"><Icon name="info"/><span>{notice}</span><button className="icon-button" onClick={() => setNotice("")} aria-label="Đóng thông báo"><Icon name="close" size={16}/></button></div>}
      {(view === "overview" || view === "slots") && <>
        <div className="metrics">{[{ label: "Tổng số ô đỗ", value: slots.length, note: "Trong cấu hình bãi xe", icon: "grid", color: "neutral" }, { label: "Ô đang có xe", value: counts.occupied, note: `${occupancy}% tổng sức chứa`, icon: "car", color: "green" }, { label: "Ô còn trống", value: counts.vacant, note: "Sẵn sàng đón xe", icon: "exit", color: "blue" }, { label: "Chưa xác định", value: counts.unknown, note: "Cần kiểm tra trạng thái", icon: "signal", color: "amber" }].map((m, i) => <article className={`metric ${m.color}`} key={m.label}><div className="metric-label">{m.label}<span className="metric-icon"><Icon name={m.icon}/></span></div><div className="metric-value">{!demo && !currentCamera ? "—" : String(m.value).padStart(2, "0")}<small>ô</small>{i === 1 && <span className="mini-bars">{[12, 21, 17, 26, 22, 30, 26, 34].map((h, k) => <i key={k} style={{ height: h }}/>)}</span>}</div><p><i className="dot"/>{m.note}</p></article>)}</div>
        <div className="overview-grid"><section className="panel"><div className="panel-heading"><div><h2>Sơ đồ bãi đỗ <span className="badge">{slots.length} ô</span></h2><p>{lotName} <span className="separator">/</span> {demo ? "Khu A & Khu B" : currentCamera?.camera_id || "Chưa cấu hình camera"}</p></div><button className={`icon-button ${busy ? "spinning" : ""}`} aria-label="Làm mới trạng thái hệ thống" disabled={busy} onClick={() => demo ? setNotice("Bản minh họa dùng dữ liệu cố định. Kết nối hệ thống thật để cập nhật.") : void refresh()}><Icon name="refresh" size={18}/></button></div>
          <div className="map-toolbar"><div className="legend"><span><i/>Có xe</span><span><i className="vacant"/>Trống</span><span><i className="unknown"/>Chưa xác định</span></div><span>Chọn ô để xem chi tiết</span></div>
          <div className="parking-map"><div className="north">N ↑</div><div className="landscape"><i/><i/><i/><span>LỐI ĐI BỘ</span><i/><i/><i/></div>{slots.length ? <><div className="parking-row">{results.slice(0, Math.ceil(results.length / 2)).map((r, i) => <ParkingSlot key={r.slot_id} result={r} index={i} onClick={() => setSelected(r)}/>)}</div><div className="driving-lane"><span>↑ VÀO</span><i/><b>→</b><span>LỐI DI CHUYỂN</span><b>→</b><i/><span>RA ↓</span></div><div className="parking-row lower">{results.slice(Math.ceil(results.length / 2)).map((r, i) => <ParkingSlot key={r.slot_id} result={r} index={i + 12} onClick={() => setSelected(r)}/>)}</div></> : <div className="empty-state"><Icon name="car" size={36}/><h3>Chưa có sơ đồ ô đỗ</h3><p>Kết nối backend và cấu hình ROI để hiển thị các ô đỗ.</p><button className="button secondary" onClick={() => setView("devices")}>Xem trạng thái hệ thống</button></div>}<div className="map-bottom"><span><i className="dot"/> {demo ? "Sơ đồ minh họa" : "Bố cục tổng hợp từ danh sách ROI"}</span><span>Không theo tỷ lệ thực tế</span></div></div>
          <div className="panel-footer"><span><Icon name="clock" size={13}/>{demo ? "Bản xem trước · dữ liệu cố định" : updated ? `Cập nhật lúc ${displayTime(updated)}` : "Đang chờ dữ liệu"}</span><button className="text-button" onClick={() => setView(view === "overview" ? "slots" : "history")}>{view === "overview" ? "Xem danh sách ô đỗ" : "Xem lịch sử kiểm tra"}<Icon name="arrow" size={15}/></button></div></section>
        <aside className="right-column"><section className="panel capacity"><div className="panel-heading"><h2>Mức sử dụng</h2><Icon name="car" size={18}/></div><div className="capacity-ring" style={{ background: `conic-gradient(#28664f ${occupancy}%, #edf0e9 0)` }}><div><strong>{occupancy}<small>%</small></strong><span>Đang có xe</span></div></div><p className="capacity-note"><i className="dot"/> {demo || currentFrame ? counts.vacant ? "Bãi xe vẫn còn chỗ trống" : "Kiểm tra kết quả từng ô" : "Chưa có kết quả kiểm tra"}</p><div className="capacity-split"><span><i className="dot"/>Có xe<strong>{counts.occupied}</strong></span><span><i className="dot blue"/>Còn trống<strong>{counts.vacant}</strong></span></div></section><section className="quick-card"><Icon name="camera" size={24}/><h2>Kiểm tra bãi xe</h2><p>Lấy ảnh mới từ camera để cập nhật trạng thái các ô đỗ.</p><button className="button primary" disabled={busy || (!demo && !status)} onClick={() => void scan()}><Icon name={busy ? "refresh" : "camera"} size={17}/>{busy ? "Đang xử lý…" : "Kiểm tra từ camera"}<Icon name="arrow" size={16}/></button><button className="upload-link" disabled={busy} onClick={upload}><Icon name="upload" size={14}/>Hoặc tải ảnh bãi xe lên</button></section></aside></div>
      </>}
      {view === "overview" && <div className="bottom-grid"><section className="panel"><div className="panel-heading"><div><h2>Hoạt động kiểm tra</h2><p>{demo ? "Minh họa số lượt kiểm tra trong ngày" : "Các lần kiểm tra trong phiên làm việc này"}</p></div><button className="text-button" onClick={() => setView("history")}>Xem tất cả<Icon name="arrow" size={15}/></button></div><ActivityChart entries={entries} demo={demo}/></section><section className="panel"><div className="panel-heading"><h2>Trạng thái hệ thống</h2><span className="badge">{demo ? "Minh họa" : "Gateway"}</span></div>{[{ icon: "camera", title: "Camera bãi đỗ", description: currentCamera?.camera_id || "Chưa có cấu hình", okay: !!currentCamera }, { icon: "signal", title: "Node suy luận ESP32", description: "Xác nhận kết nối qua suy luận", okay: !!currentStatus?.execution_targets.includes("esp32") }, { icon: "grid", title: "Mô hình nhận diện", description: currentStatus?.run || "Chưa kết nối", okay: !!currentStatus?.ready }].map(s => <div className="system-row" key={s.title}><span className="system-icon"><Icon name={s.icon}/></span><span><strong>{s.title}</strong><small>{s.description}</small></span><i className={`status-light ${s.okay ? "okay" : ""}`}/></div>)}<button className="text-button system-link" onClick={() => setView("devices")}>Quản lý thiết bị<Icon name="arrow" size={15}/></button></section></div>}
      {view === "slots" && <section className="panel table-panel"><div className="panel-heading"><h2>Danh sách ô đỗ</h2><button className="button secondary" onClick={exportCsv} disabled={!slots.length}><Icon name="download" size={16}/>Xuất CSV</button></div><div className="table-controls"><label className="search"><Icon name="search" size={17}/><input aria-label="Tìm ô đỗ" placeholder="Tìm theo mã ô đỗ…" value={query} onChange={e => setQuery(e.target.value)}/></label><select aria-label="Lọc trạng thái ô đỗ" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Tất cả trạng thái</option><option value="occupied">Có xe</option><option value="vacant">Còn trống</option><option value="unknown">Chưa xác định</option></select></div><div className="table-scroll"><table><thead><tr><th>MÃ Ô ĐỖ</th><th>TRẠNG THÁI</th><th>ĐIỂM NHẬN DIỆN XE</th><th>THỜI GIAN SUY LUẬN</th><th/></tr></thead><tbody>{visible.map(r => <tr key={r.slot_id}><td><strong>{r.slot_id}</strong></td><td><StatusBadge result={r}/></td><td>{r.car_score !== undefined ? `${(r.car_score * 100).toFixed(1)}%` : "—"}</td><td>{r.latency_ms !== undefined ? `${r.latency_ms} ms` : "—"}</td><td><button className="text-button" onClick={() => setSelected(r)}>Chi tiết<Icon name="chevron" size={13}/></button></td></tr>)}</tbody></table>{!visible.length && <div className="empty-state">Không có ô đỗ phù hợp.</div>}</div></section>}
      {view === "devices" && <section className="panel"><div className="panel-heading"><div><h2>Kết nối & nguồn dữ liệu</h2><p>Trạng thái cấu hình không thay thế kiểm tra kết nối thiết bị.</p></div><button className="button secondary" disabled={busy} onClick={() => demo ? setNotice("Chuyển sang hệ thống thật để đọc trạng thái gateway.") : void refresh()}><Icon name="refresh" size={16}/>Làm mới</button></div><div className="device-grid">{[{ icon: "grid", name: "Gateway suy luận", state: currentStatus?.ready ? "Sẵn sàng" : "Chưa kết nối", detail: `Model: ${currentStatus?.run || "—"}`, sub: `Định dạng: ${currentStatus?.models.join(", ") || "—"}` }, { icon: "camera", name: "Camera cố định", state: currentCamera ? "Đã cấu hình ROI" : "Chưa cấu hình", detail: currentCamera?.camera_id || "Cấu hình camera trên backend", sub: `${slots.length} vùng nhận diện · HTTP snapshot` }, { icon: "signal", name: "Node ESP32", state: currentStatus?.execution_targets.includes("esp32") ? "Đã cấu hình" : "Chưa cấu hình", detail: "Kết nối được xác nhận khi suy luận thành công", sub: "Grayscale 64 × 64 · INT8" }].map(d => <article className="device" key={d.name}><span className="device-icon"><Icon name={d.icon} size={28}/></span><h3>{d.name}</h3><span className="badge">{d.state}</span><p>{d.detail}</p><small>{d.sub}</small></article>)}</div><div className="device-actions"><label>Nơi thực thi<select value={target} onChange={e => { setTarget(e.target.value); setFrame(null); }} disabled={demo || !status || busy}>{(currentStatus?.execution_targets || ["esp32"]).map(t => <option key={t} value={t}>{t === "esp32" ? "ESP32 · INT8" : "Backend · tham chiếu"}</option>)}</select></label><button className="button primary" onClick={() => void scan()} disabled={busy || (!demo && !status)}><Icon name="camera" size={17}/>Kiểm tra camera</button><button className="button secondary" disabled={busy} onClick={upload}><Icon name="upload" size={17}/>Tải ảnh kiểm tra</button></div><div className="info-note"><Icon name="info"/><p>Kết quả hiện tại là nhận diện CNN từ ảnh. Dữ liệu cảm biến khoảng cách, biển số, doanh thu và kết quả kết hợp cảm biến chưa được backend cung cấp.</p></div></section>}
      {view === "history" && <section className="panel"><div className="panel-heading"><div><h2>Nhật ký kiểm tra trong phiên</h2><p>Lịch sử được giữ trong bộ nhớ đến khi tải lại trang hoặc đổi chế độ.</p></div><span className="badge">{entries.length} lần kiểm tra</span></div>{!entries.length ? <div className="empty-state"><Icon name="clock" size={38}/><h3>Chưa có lượt kiểm tra</h3><p>{demo ? "Chuyển sang hệ thống thật và kiểm tra camera để bắt đầu ghi nhận." : "Kiểm tra camera hoặc tải ảnh để lưu kết quả trong phiên này."}</p><button className="button secondary" onClick={() => setView("devices")}>Đến camera & thiết bị<Icon name="arrow" size={16}/></button></div> : <div className="table-scroll"><table><thead><tr><th>THỜI ĐIỂM</th><th>NGUỒN</th><th>CÓ XE / TRỐNG / CHƯA RÕ</th><th>KẾT QUẢ</th></tr></thead><tbody>{entries.map(e => <tr key={e.id}><td>{displayTime(e.time)}</td><td>{e.source}</td><td>{e.frame.counts.occupied} / {e.frame.counts.vacant} / {e.frame.counts.unknown}</td><td><span className={`state-badge ${e.frame.complete ? "vacant" : "unknown"}`}>{e.frame.complete ? "Hoàn tất" : "Có ô chưa xác định"}</span></td></tr>)}</tbody></table></div>}</section>}
      {view === "settings" && <section className="panel settings-panel"><div className="panel-heading"><div><h2>Tùy chỉnh không gian</h2><p>Cài đặt hiển thị cho trình duyệt này.</p></div><Icon name="settings"/></div><form onSubmit={e => { e.preventDefault(); const name = lotName.trim(); if (!name) return; setLotName(name); localStorage.setItem("parkly-lot-name", name); setNotice("Đã lưu tên hiển thị trên trình duyệt này."); }}><label>Tên bãi đỗ xe<input value={lotName} maxLength={70} required onChange={e => setLotName(e.target.value)}/></label><div className="setting-toggle"><span><strong>Tự kiểm tra camera mỗi 30 giây</strong><small>Chỉ hoạt động trong chế độ hệ thống thật, khi trang đang hiển thị.</small></span><input type="checkbox" aria-label="Tự kiểm tra camera" checked={auto} disabled={demo || !status} onChange={e => setAuto(e.target.checked)}/></div><button className="button primary" type="submit"><Icon name="check" size={17}/>Lưu thay đổi</button></form><div className="info-note"><Icon name="info"/><p>Cấu hình ROI, địa chỉ camera và ESP32 hiện được quản lý trên backend. Giao diện chưa có API chỉnh sửa cấu hình hoặc xác thực tài khoản.</p></div></section>}
      <footer className="footer"><span><strong>parkly.</strong> Không gian đỗ xe, vận hành thông minh.</span><span>{demo ? "CHẾ ĐỘ MINH HỌA" : "KẾT QUẢ CNN · CHƯA KẾT HỢP CẢM BIẾN"} <i>·</i> v1.0</span></footer>
    </main></div>
    <input ref={fileInput} className="hidden-input" type="file" accept="image/jpeg,image/png,image/webp,image/bmp" onChange={e => { const file = e.target.files?.[0]; if (file) void scan(file); e.target.value = ""; }}/>
    {selected && <SlotDialog result={selected} demo={demo} target={currentFrame?.execution_target} threshold={currentStatus?.threshold} onClose={() => setSelected(null)}/>}
  </div>;
}

function StatusBadge({ result }: { result: Result }) {
  return <span className={`state-badge ${result.label === 1 ? "occupied" : result.label === 0 ? "vacant" : "unknown"}`}><i/>{result.label === 1 ? "Có xe" : result.label === 0 ? "Còn trống" : "Chưa xác định"}</span>;
}
function ParkingSlot({ result, index, onClick }: { result: Result; index: number; onClick: () => void }) {
  return <button className={`parking-slot ${result.label === 1 ? "occupied" : result.label === 0 ? "vacant" : "unknown"}`} onClick={onClick} aria-label={`Ô ${result.slot_id}: ${result.label === 1 ? "có xe" : result.label === 0 ? "trống" : "chưa xác định"}`}><span className="slot-visual">{result.label === 1 ? <Car color={["#587266", "#91a09a", "#667b88", "#b3b0a5"][index % 4]}/> : <span className={result.label === 0 ? "vacant-symbol" : "unknown-symbol"}>{result.label === 0 ? "P" : "?"}</span>}</span><span className="slot-id">{result.slot_id}</span></button>;
}
function ActivityChart({ demo, entries }: { demo: boolean; entries: Entry[] }) {
  const bars = demo ? [3, 5, 4, 8, 12, 16, 13, 18, 22, 17, 14, 19, 15, 12, 16, 21, 18, 14, 10, 8, 6, 4, 3, 2] : Array.from({ length: 24 }, (_, h) => entries.filter(e => Number(new Date(e.time).toLocaleString("en-US", { hour: "2-digit", hourCycle: "h23", timeZone: "Asia/Ho_Chi_Minh" })) === h).length);
  const max = Math.max(...bars, 1);
  return <div className="chart-wrap"><div className="chart-scale"><span>{max}</span><span>{Math.round(max / 2)}</span><span>0</span></div><div className="chart"><div className="chart-bars" role="img" aria-label={demo ? "Lượt kiểm tra minh họa theo giờ" : "Số lượt kiểm tra theo giờ trong phiên"}>{bars.map((v, i) => <div key={i} className={`chart-bar ${i === 8 ? "highlight" : ""}`} style={{ height: `${v / max * 100}%`, minHeight: v ? 4 : 0 }} title={`${i}:00 — ${v} lượt kiểm tra`}/>)}</div><div className="chart-hours">{["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "23:00"].map(h => <span key={h}>{h}</span>)}</div></div></div>;
}
function SlotDialog({ result, demo, target, threshold, onClose }: { result: Result; demo: boolean; target?: string; threshold?: number; onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null; close.current?.focus();
    const handler = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); if (event.key === "Tab") { event.preventDefault(); close.current?.focus(); } };
    document.addEventListener("keydown", handler);
    return () => { document.removeEventListener("keydown", handler); previous?.focus(); };
  }, [onClose]);
  return <div className="modal-backdrop" onClick={onClose}><section role="dialog" aria-modal="true" aria-labelledby="slot-dialog-title" className="detail-modal" onClick={e => e.stopPropagation()}><div className="panel-heading"><h2 id="slot-dialog-title">Ô đỗ {result.slot_id}</h2><button ref={close} className="icon-button" aria-label="Đóng chi tiết" onClick={onClose}><Icon name="close"/></button></div><div className="detail-content"><StatusBadge result={result}/><div className="detail-car"><Car color={result.label === 1 ? "#4a6d60" : "#a6b6b0"}/></div><dl>{[["Nguồn dữ liệu", demo ? "Minh họa" : target || "Chưa kiểm tra"], ["Điểm nhận diện xe", result.car_score !== undefined ? `${(result.car_score * 100).toFixed(1)}%` : "—"], ["Thời gian suy luận", result.latency_ms !== undefined ? `${result.latency_ms} ms` : "—"], ["Ngưỡng phân loại", threshold ?? "—"]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>{result.error && <p className="detail-error">{result.error}</p>}<p className="muted">Kết quả từ ảnh phản ánh thời điểm kiểm tra, không phải trạng thái được xác nhận liên tục.</p></div></section></div>;
}
