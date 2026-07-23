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
  const [payroll, setPayroll] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [created, setCreated] = useState(null);

  // Load the payroll panel whenever an employee is opened.
  useEffect(() => {
    if (!selectedEmployee) {
      setPayroll(null);
      return;
    }
    let alive = true;
    api.employeePayroll(selectedEmployee.employee_id)
      .then((r) => alive && setPayroll(r))
      .catch(() => alive && setPayroll(null));
    return () => { alive = false; };
  }, [selectedEmployee]);

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

            {/* Payroll panel: base / commission / deductions / advances / net */}
            <h4 style={{ marginTop: 16 }}>{L("pay_title")}</h4>
            {payroll && payroll.summary ? (
              <>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                  {[
                    ["pay_base", payroll.summary.basic_salary],
                    ["pay_commission", payroll.summary.commission],
                    ["pay_deductions", payroll.summary.deductions],
                    ["pay_advances", payroll.summary.advances],
                  ].map(([k, v]) => (
                    <div key={k} className="kpi-box" style={{ minWidth: 120 }}>
                      <div className="kpi-value" style={{ fontSize: 18 }}>{Number(v || 0).toLocaleString("en-US")}</div>
                      <div className="kpi-label">{L(k)}</div>
                    </div>
                  ))}
                  <div className="kpi-box" style={{ minWidth: 120 }}>
                    <div className="kpi-value" style={{ fontSize: 18, color: "var(--ok)" }}>
                      {Number(payroll.summary.net || 0).toLocaleString("en-US")}
                    </div>
                    <div className="kpi-label">{L("pay_net")} · {payroll.summary.period || ""}</div>
                  </div>
                </div>
                {payroll.records.length > 1 && (
                  <div className="table-wrapper" style={{ marginTop: 12 }}>
                    <table className="tbl">
                      <thead>
                        <tr>
                          <th>{L("pay_period")}</th>
                          <th className="num">{L("pay_base")}</th>
                          <th className="num">{L("pay_commission")}</th>
                          <th className="num">{L("pay_deductions")}</th>
                          <th className="num">{L("pay_advances")}</th>
                          <th className="num">{L("pay_net")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {payroll.records.map((p) => (
                          <tr key={p.payroll_id}>
                            <td>{p.period || "—"}</td>
                            <td className="num">{Number(p.basic_salary).toLocaleString("en-US")}</td>
                            <td className="num">{Number(p.commission + p.over_commission).toLocaleString("en-US")}</td>
                            <td className="num">{Number(p.deduction + p.absence_money).toLocaleString("en-US")}</td>
                            <td className="num">{Number(p.cash_advance).toLocaleString("en-US")}</td>
                            <td className="num" style={{ fontWeight: 600 }}>{Number(p.net).toLocaleString("en-US")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <p className="muted">
                {L("pay_none")}
                {payroll ? ` · ${L("pay_on_file")}: ${Number(payroll.base_salary_on_file || 0).toLocaleString("en-US")}` : ""}
              </p>
            )}

            {/* Salary advances (سلف) detail ledger — Employee_cash_advance */}
            {payroll && payroll.advances && payroll.advances.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>
                  {L("pay_advances_ledger")}
                  <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>
                    {" "}· {L("pay_advances_total")}: {Number(payroll.advances_total || 0).toLocaleString("en-US")}
                  </span>
                </h4>
                <div className="table-wrapper">
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>{L("date")}</th>
                        <th>{L("pay_advance_type")}</th>
                        <th className="num">{L("pay_advances")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payroll.advances.map((a) => (
                        <tr key={a.advance_id}>
                          <td>{a.created_at ? new Date(a.created_at).toLocaleDateString("en-GB") : "—"}</td>
                          <td>{a.advance_type || "—"}</td>
                          <td className="num" style={{ fontWeight: 600 }}>{Number(a.amount).toLocaleString("en-US")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
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

        {selectedEmployee && (
          <DevPlanPanel
            L={L}
            lang={lang}
            employee={selectedEmployee}
            onClose={() => setSelectedEmployee(null)}
          />
        )}
      </div>
    </Shell>
  );
}

// PMP / development plan: goals per employee with category, target date, status.
function DevPlanPanel({ L, lang, employee, onClose }) {
  const [goals, setGoals] = useState(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("performance");
  const [targetDate, setTargetDate] = useState("");

  const load = () =>
    api.employeeGoals(employee.employee_id).then((r) => setGoals(r.goals)).catch(() => setGoals([]));
  useEffect(() => {
    setGoals(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employee.employee_id]);

  async function addGoal() {
    try {
      await api.createGoal(employee.employee_id, {
        title,
        category,
        target_date: targetDate || null,
      });
      setTitle("");
      setTargetDate("");
      load();
    } catch {
      /* keep form state */
    }
  }

  async function setStatus(goalId, status) {
    try {
      await api.setGoalStatus(goalId, status);
      load();
    } catch {
      /* ignore */
    }
  }

  const badge = { active: "", achieved: "ok", dropped: "danger" };

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 className="section-title" style={{ margin: 0 }}>
          {L("dev_plan")} — {lang === "ar" ? employee.name_ar : employee.name_en || employee.name_ar}
        </h3>
        <button className="btn icon" onClick={onClose}>✕</button>
      </div>

      <div style={{ display: "flex", gap: 8, margin: "12px 0", flexWrap: "wrap" }}>
        <input className="input" placeholder={L("goal_title")} value={title}
               onChange={(e) => setTitle(e.target.value)} style={{ flex: 1, minWidth: 200 }} />
        <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="performance">{L("cat_performance")}</option>
          <option value="training">{L("cat_training")}</option>
          <option value="behavior">{L("cat_behavior")}</option>
        </select>
        <input className="input" type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
        <button className="btn primary" disabled={title.trim().length < 2} onClick={addGoal}>
          {L("add_goal")}
        </button>
      </div>

      {!goals && <p className="muted">{L("loading")}</p>}
      {goals && goals.length === 0 && <p className="muted">{L("no_goals")}</p>}
      {goals && goals.length > 0 && (
        <table className="tbl">
          <thead>
            <tr>
              <th>{L("goal_title")}</th>
              <th>{L("goal_category")}</th>
              <th>{L("target_date")}</th>
              <th>{L("status")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {goals.map((g) => (
              <tr key={g.goal_id}>
                <td>{g.title}</td>
                <td className="muted">{L(`cat_${g.category}`)}</td>
                <td className="muted">{g.target_date || "—"}</td>
                <td>
                  <span className={`badge ${badge[g.status] || ""}`}>{L(`goal_${g.status}`)}</span>
                </td>
                <td>
                  {g.status === "active" && (
                    <span style={{ display: "flex", gap: 6 }}>
                      <button className="btn" onClick={() => setStatus(g.goal_id, "achieved")}>
                        {L("mark_achieved")}
                      </button>
                      <button className="btn icon" title={L("goal_dropped")}
                              onClick={() => setStatus(g.goal_id, "dropped")}>✕</button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
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
