"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { View, Camera, Status, Frame, Entry, Result } from "./types";
import { demoCamera, demoFrame, demoStatus } from "./data";
import { api } from "./api";
export function useParkingDashboard() {
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
  const counts = currentFrame?.counts || {
    occupied: 0,
    vacant: 0,
    unknown: slots.length,
  };
  const occupancy = slots.length
    ? Math.round((counts.occupied / slots.length) * 100)
    : 0;
  const results: Result[] = slots.map(
    (s) =>
      currentFrame?.results.find((r) => r.slot_id === s.id) || {
        slot_id: s.id,
        label: null,
        status: "unknown",
      },
  );
  const visible = results.filter(
    (r) =>
      r.slot_id.toLowerCase().includes(query.toLowerCase()) &&
      (filter === "all" ||
        (filter === "occupied"
          ? r.label === 1
          : filter === "vacant"
            ? r.label === 0
            : r.label === null)),
  );

  useEffect(() => {
    const saved = localStorage.getItem("parkly-lot-name");
    if (saved) setLotName(saved);
  }, []);
  const refresh = useCallback(async () => {
    const version = generation.current;
    setBusy(true);
    setError("");
    try {
      const [s, r] = await Promise.all([
        api<Status>("status"),
        api<{ camera: Camera | null }>("rois"),
      ]);
      if (version !== generation.current) return;
      setStatus(s);
      setCamera(r.camera);
      setTarget(s.execution_targets.includes("esp32") ? "esp32" : "backend");
    } catch (e) {
      if (version === generation.current) {
        setError((e as Error).message);
        setStatus(null);
        setFrame(null);
      }
    } finally {
      if (version === generation.current) setBusy(false);
    }
  }, []);
  useEffect(() => {
    if (!demo) void refresh();
  }, [demo, refresh]);

  const scan = useCallback(
    async (file?: File) => {
      if (demo) {
        setNotice(
          "Đang xem dữ liệu minh họa. Chuyển sang hệ thống thật để kiểm tra camera.",
        );
        return;
      }
      if (requestBusy.current) return;
      if (file && (file.size === 0 || file.size > 10 * 1024 * 1024)) {
        setError("Chọn ảnh có dung lượng từ 1 byte đến 10 MB.");
        return;
      }
      const version = generation.current;
      requestBusy.current = true;
      setBusy(true);
      setError("");
      setFrame(null);
      setSelected(null);
      try {
        const data = new FormData();
        if (file) data.append("file", file);
        const result = await api<Frame>(
          `${file ? "predict-frame" : "predict-camera"}?target=${target}`,
          { method: "POST", ...(file ? { body: data } : {}) },
        );
        if (version !== generation.current) return;
        const now = new Date().toISOString();
        setFrame(result);
        setUpdated(now);
        setEntries((prev) =>
          [
            {
              id: result.frame_id,
              time: now,
              source: file ? "Ảnh tải lên" : "Camera snapshot",
              frame: result,
            },
            ...prev,
          ].slice(0, 100),
        );
      } catch (e) {
        if (version === generation.current) setError((e as Error).message);
      } finally {
        requestBusy.current = false;
        if (version === generation.current) setBusy(false);
      }
    },
    [demo, target],
  );
  useEffect(() => {
    if (!auto || demo || !status) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void scan();
    }, 30000);
    return () => clearInterval(timer);
  }, [auto, demo, status, scan]);

  function switchMode() {
    generation.current++;
    setDemo(!demo);
    setFrame(null);
    setEntries([]);
    setSelected(null);
    setError("");
    setUpdated(null);
    setBusy(false);
    setAuto(false);
    setNotice("");
    setStatus(null);
    setCamera(null);
  }
  function upload() {
    if (demo)
      setNotice("Chuyển sang hệ thống thật để tải ảnh và kiểm tra ROI.");
    else fileInput.current?.click();
  }
  function exportCsv() {
    const csv =
      "\uFEFF" +
      [
        "slot_id,trang_thai,car_score,latency_ms",
        ...results.map(
          (r) =>
            `${JSON.stringify(r.slot_id)},${r.label === 1 ? "occupied" : r.label === 0 ? "vacant" : "unknown"},${r.car_score ?? ""},${r.latency_ms ?? ""}`,
        ),
      ].join("\r\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `parkly-${demo ? "demo" : "snapshot"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return {
    view,
    setView,
    demo,
    status,
    setFrame,
    entries,
    busy,
    error,
    setError,
    notice,
    setNotice,
    updated,
    query,
    setQuery,
    filter,
    setFilter,
    selected,
    setSelected,
    target,
    setTarget,
    lotName,
    setLotName,
    auto,
    setAuto,
    fileInput,
    currentStatus,
    currentCamera,
    currentFrame,
    slots,
    counts,
    occupancy,
    results,
    visible,
    refresh,
    scan,
    switchMode,
    upload,
    exportCsv,
  };
}
export type DashboardState = ReturnType<typeof useParkingDashboard>;
