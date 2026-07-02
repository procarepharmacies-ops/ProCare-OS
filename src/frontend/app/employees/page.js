"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import Shell from "../components/Shell";
import { t } from "../i18n";
import { api } from "../api";

export default function EmployeesPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [employees, setEmployees] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
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
    loadData();
  }, [branch]);

  if (loading) return <Shell titleKey="nav_employees"><div className="page">{L("loading")}</div></Shell>;

  return (
    <Shell titleKey="nav_employees">
      <div className="page">
        {/* KPIs */}
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

        {/* Detail View */}
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
                <strong>{L("job")}:</strong> {selectedEmployee.job_name || "-"}
              </div>
              <div>
                <strong>{L("basic_salary")}:</strong> {parseFloat(selectedEmployee.basic_salary).toLocaleString()}
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

        {/* Employees Table */}
        <div className="table-wrapper">
          <table className="tbl">
            <thead>
              <tr>
                <th>{L("employee")}</th>
                <th>{L("username")}</th>
                <th>{L("job")}</th>
                <th>{L("basic_salary")}</th>
                <th>{L("active")}</th>
              </tr>
            </thead>
            <tbody>
              {employees.length === 0 ? (
                <tr>
                  <td colSpan="5" className="empty">{L("none")}</td>
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
                    <td>{e.job_name || "-"}</td>
                    <td>{parseFloat(e.basic_salary).toLocaleString()}</td>
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
