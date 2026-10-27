"use client";
import { Icon } from "./icons";
import { useParkingDashboard } from "./parking-dashboard/use-parking-dashboard";
import { SlotDialog } from "./parking-dashboard/slot-dialog";
import { Sidebar } from "./parking-dashboard/sidebar";
import { DashboardHeader } from "./parking-dashboard/dashboard-header";
import { PageHeading } from "./parking-dashboard/page-heading";
import { Metrics } from "./parking-dashboard/metrics";
import { ParkingMap } from "./parking-dashboard/parking-map";
import { CapacityCard } from "./parking-dashboard/capacity-card";
import { QuickActions } from "./parking-dashboard/quick-actions";
import { ActivityPanel } from "./parking-dashboard/activity-panel";
import { SystemSummary } from "./parking-dashboard/system-summary";
import { SlotsTable } from "./parking-dashboard/slots-table";
import { DevicesPanel } from "./parking-dashboard/devices-panel";
import { HistoryPanel } from "./parking-dashboard/history-panel";
import { SettingsPanel } from "./parking-dashboard/settings-panel";
import { DashboardFooter } from "./parking-dashboard/dashboard-footer";
export default function ParkingDashboard() {
  const {
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
  } = useParkingDashboard();
  return (
    <div className="app-shell">
      <Sidebar
        view={view}
        setView={setView}
        setQuery={setQuery}
        lotName={lotName}
        slots={slots}
      />
      <div className="main-shell">
        <DashboardHeader
          view={view}
          setView={setView}
          demo={demo}
          status={status}
          setNotice={setNotice}
          counts={counts}
        />
        <main>
          <PageHeading
            view={view}
            demo={demo}
            lotName={lotName}
            switchMode={switchMode}
          />
          {demo && (
            <div className="demo-banner">
              <Icon name="info" size={16} />
              <span>
                Bạn đang khám phá giao diện với{" "}
                <strong>dữ liệu minh họa</strong>. Chuyển sang hệ thống thật để
                xem bãi xe của bạn.
              </span>
              <b>DEMO</b>
            </div>
          )}
          {error && (
            <div role="alert" className="alert error">
              <Icon name="info" />
              <span>{error}</span>
              <button
                className="icon-button"
                onClick={() => setError("")}
                aria-label="Đóng lỗi"
              >
                <Icon name="close" size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="alert">
              <Icon name="info" />
              <span>{notice}</span>
              <button
                className="icon-button"
                onClick={() => setNotice("")}
                aria-label="Đóng thông báo"
              >
                <Icon name="close" size={16} />
              </button>
            </div>
          )}
          {(view === "overview" || view === "slots") && (
            <>
              <Metrics
                demo={demo}
                currentCamera={currentCamera}
                slots={slots}
                counts={counts}
                occupancy={occupancy}
              />
              <div className="overview-grid">
                <ParkingMap
                  view={view}
                  setView={setView}
                  demo={demo}
                  busy={busy}
                  setNotice={setNotice}
                  updated={updated}
                  setSelected={setSelected}
                  lotName={lotName}
                  currentCamera={currentCamera}
                  slots={slots}
                  results={results}
                  refresh={refresh}
                />
                <aside className="right-column">
                  <CapacityCard
                    demo={demo}
                    currentFrame={currentFrame}
                    counts={counts}
                    occupancy={occupancy}
                  />
                  <QuickActions
                    demo={demo}
                    status={status}
                    busy={busy}
                    scan={scan}
                    upload={upload}
                  />
                </aside>
              </div>
            </>
          )}
          {view === "overview" && (
            <div className="bottom-grid">
              <ActivityPanel setView={setView} demo={demo} entries={entries} />
              <SystemSummary
                setView={setView}
                demo={demo}
                currentStatus={currentStatus}
                currentCamera={currentCamera}
              />
            </div>
          )}
          {view === "slots" && (
            <SlotsTable
              query={query}
              setQuery={setQuery}
              filter={filter}
              setFilter={setFilter}
              setSelected={setSelected}
              slots={slots}
              visible={visible}
              exportCsv={exportCsv}
            />
          )}
          {view === "devices" && (
            <DevicesPanel
              demo={demo}
              status={status}
              setFrame={setFrame}
              busy={busy}
              setNotice={setNotice}
              target={target}
              setTarget={setTarget}
              currentStatus={currentStatus}
              currentCamera={currentCamera}
              slots={slots}
              refresh={refresh}
              scan={scan}
              upload={upload}
            />
          )}
          {view === "history" && (
            <HistoryPanel setView={setView} demo={demo} entries={entries} />
          )}
          {view === "settings" && (
            <SettingsPanel
              demo={demo}
              status={status}
              setNotice={setNotice}
              lotName={lotName}
              setLotName={setLotName}
              auto={auto}
              setAuto={setAuto}
            />
          )}
          <DashboardFooter demo={demo} />
        </main>
      </div>
      <input
        ref={fileInput}
        className="hidden-input"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/bmp"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void scan(file);
          e.target.value = "";
        }}
      />
      {selected && (
        <SlotDialog
          result={selected}
          demo={demo}
          target={currentFrame?.execution_target}
          threshold={currentStatus?.threshold}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
