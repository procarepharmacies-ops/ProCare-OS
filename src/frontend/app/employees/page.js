"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import Shell from "../components/Shell";
import { t } from "../i18n";
import { api } from "../api";

export default function EmployeesPage() {
  const { lang, branch, branches, user } = useUI();
  const L = (k) => t(lang, k);
  const [employees, setEmployees] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [created, setCreated] = useState(null);

  const isCeo = user?.role === "ceo";

  const load = async () => {
    try {
      setLoading(true);
      const [empRes, sumRes] = await Promise.all([
        api.get("/employees/list", { branch_id: branch || undefined }),
        api.get("/employees/summary", { branch_id: branch || undefined }),
      ]);
      setEmployees(empRes.employees || []);
      setSummary(sumRes);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch]);

  if (loading) return <Shell titleKey="nav_employees"><div className="page">{L("loading")}</div></Shell>;

  return (
    <Shell titleKey="nav_employees">
      <div className="page">
        <div className="kpi-row">
          <div className="kpi-box">
            <div className="kpi-value">{summary?.total_employees || "0"}</div>
            <div className="kpi-label">{L("total_employees")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.active_employees || "0"}</div>
            <div className="kpi-label">{L("active_employees")}</div>
          </div>
        </div>

        {isCeo && (
          <div style={{ marginBottom: 16 }}>
            <button className="btn primary" onClick={() => setShowForm((s) => !s)}>
              {showForm ? L("cancel") : L("add_employee")}
            </button>
          </div>
        )}

        {isCeo && showForm && (
          <AddEmployeeForm
            L={L}
            branches={branches}
            onCreated={(result) => {
              setCreated(result);
              setShowForm(false);
              load();
            }}
          />
        )}

        {created && (
          <div className="card" style={{ marginBottom: 16, borderColor: "var(--primary)" }}>
            <h3 className="section-title">{L("generated_credentials")}</h3>
            {created.has_login ? (
              <>
                <p className="login-error" style={{ color: "var(--warning)" }}>{L("credentials_warning")}</p>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 15 }}>
                  <div><strong>{L("username")}:</strong> <span className="num">{created.username}</span></div>
                  <div><strong>{L("password")}:</strong> <span className="num">{created.password}</span></div>
                </div>
              </>
            ) : (
              <p className="muted">{L("no_login")}</p>
            )}
            <button className="btn" style={{ marginTop: 12 }} onClick={() => setCreated(null)}>
              {L("go_back")}
            </button>
          </div>
        )}

        {selectedEmployee && (
          <div className="card" style={{ marginBottom: 16 }}>
            <button
              className="btn"
              onClick={() => setSelectedEmployee(null)}
              style={{ marginBottom: 12 }}
            >
              {L("go_back")}
            </button>
            <h3>{lang === "ar" ? selectedEmployee.name_ar : selectedEmployee.name_en || selectedEmployee.name_ar}</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <strong>{L("username")}:</strong> {selectedEmployee.username}
              </div>
              <div>
                <strong>{L("system_role")}:</strong> {selectedEmployee.role ? L(`role_${selectedEmployee.role}`) : "-"}
              </div>
              <div>
                <strong>{L("job")}:</strong> {selectedEmployee.job_name || "-"}
              </div>
              <div>
                <strong>{L("basic_salary")}:</strong> {parseFloat(selectedEmployee.basic_salary).toLocaleString("en-US")}
              </div>
              <div>
                <strong>{L("active")}:</strong> {selectedEmployee.is_active ? "✓" : "✗"}
              </div>
            </div>

            <h4 style={{ marginTop: 16 }}>{L("permissions")}</h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {Object.entries(selectedEmployee.permissions || {}).map(([key, val]) => (
                <div key={key}>
                  <input type="checkbox" checked={val} disabled /> {L(key)}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="table-wrapper">
          <table className="tbl">
            <thead>
              <tr>
                <th>{L("employee")}</th>
                <th>{L("username")}</th>
                <th>{L("system_role")}</th>
                <th>{L("job")}</th>
                <th>{L("basic_salary")}</th>
                <th>{L("active")}</th>
              </tr>
            </thead>
            <tbody>
              {employees.length === 0 ? (
                <tr>
                  <td colSpan="6" className="empty">{L("none")}</td>
                </tr>
              ) : (
                employees.map((e) => (
                  <tr
                    key={e.employee_id}
                    onClick={() => setSelectedEmployee(e)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{lang === "ar" ? e.name_ar : e.name_en || e.name_ar}</td>
                    <td>{e.username}</td>
                    <td>{e.role ? L(`role_${e.role}`) : "-"}</td>
                    <td>{e.job_name || "-"}</td>
                    <td>{parseFloat(e.basic_salary).toLocaleString("en-US")}</td>
                    <td>{e.is_active ? "✓" : "✗"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}

function AddEmployeeForm({ L, branches, onCreated }) {
  const [nameAr, setNameAr] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [role, setRole] = useState("assistant");
  const [branchId, setBranchId] = useState("");
  const [hasLogin, setHasLogin] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!nameAr || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.post("/employees", {
        name_ar: nameAr,
        name_en: nameEn || null,
        role: hasLogin ? role : null,
        branch_id: branchId ? Number(branchId) : null,
        has_login: hasLogin,
      });
      onCreated(result);
    } catch (err) {
      setError(err.message || "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card" style={{ marginBottom: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <label className="login-field">
        <span>{L("name_arabic")}</span>
        <input className="input" value={nameAr} onChange={(e) => setNameAr(e.target.value)} required />
      </label>
      <label className="login-field">
        <span>{L("name_english")}</span>
        <input className="input" value={nameEn} onChange={(e) => setNameEn(e.target.value)} />
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
        <input type="checkbox" checked={hasLogin} onChange={(e) => setHasLogin(e.target.checked)} />
        {L("no_login")}
      </label>
      {hasLogin && (
        <label className="login-field">
          <span>{L("system_role")}</span>
          <select className="select" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="assistant">{L("role_assistant")}</option>
            <option value="manager">{L("role_manager")}</option>
            <option value="ceo">{L("role_ceo")}</option>
          </select>
        </label>
      )}
      <label className="login-field">
        <span>{L("branch")}</span>
        <select className="select" value={branchId} onChange={(e) => setBranchId(e.target.value)}>
          <option value="">{L("all_branches")}</option>
          {branches.map((b) => (
            <option key={b.branch_id} value={b.branch_id}>
              {b.name_ar}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="login-error">{error}</p>}
      <button className="btn primary" type="submit" disabled={busy || !nameAr}>
        {busy ? L("creating") : L("save")}
      </button>
    </form>
  );
}
