"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import { t } from "../i18n";
import { apiFetch } from "../api";
import Icon from "../components/icons";

export default function KnowledgePage() {
  const { lang, online } = useUI();
  const L = (k) => t(lang, k);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [topics, setTopics] = useState({});
  const [searching, setSearching] = useState(false);
  const [activeNode, setActiveNode] = useState(null);

  useEffect(() => {
    fetchTopics();
  }, []);

  const fetchTopics = async () => {
    try {
      const data = await apiFetch("/api/knowledge/topics");
      setTopics(data.topics || {});
    } catch (e) {
      console.error(e);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    try {
      const data = await apiFetch(`/api/knowledge/search?q=${encodeURIComponent(query)}`);
      setResults(data.results || []);
    } catch (e) {
      console.error(e);
    }
    setSearching(false);
  };

  const loadNode = async (id) => {
    try {
      const data = await apiFetch(`/api/knowledge/nodes/${id}`);
      setActiveNode(data);
    } catch (e) {
      console.error(e);
    }
  };

  const refreshIndex = async () => {
    try {
      await apiFetch("/api/knowledge/refresh", { method: "POST" });
      fetchTopics();
      alert("Knowledge graph re-indexed successfully.");
    } catch (e) {
      alert("Failed to refresh index.");
    }
  };

  if (!online) return <div className="card pad tc">{L("offline")}</div>;

  return (
    <div className="pad-lg">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0 }}>{L("nav_knowledge")}</h2>
        <button className="btn icon" onClick={refreshIndex} title="Refresh Index">
          <Icon name="refresh" />
        </button>
      </div>

      <div className="grid">
        <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
          <div className="card pad">
            <form onSubmit={handleSearch} style={{ display: "flex", gap: 10 }}>
              <input 
                type="text" 
                className="input" 
                placeholder="Search business documents, schemas, rules..." 
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{ flex: 1 }}
              />
              <button className="btn primary" type="submit" disabled={searching || !query.trim()}>
                {searching ? "..." : "Search"}
              </button>
            </form>
          </div>

          {results.length > 0 && (
            <div className="card pad">
              <h3>Search Results</h3>
              <div style={{ marginTop: 15, display: "flex", flexDirection: "column", gap: 15 }}>
                {results.map((r) => (
                  <div key={r.id} style={{ cursor: "pointer", borderBottom: "1px solid var(--color-border)", paddingBottom: 15 }} onClick={() => loadNode(r.id)}>
                    <h4 style={{ margin: "0 0 5px 0", color: "var(--color-primary)" }}>{r.title}</h4>
                    <div className="kpi-sub" style={{ marginBottom: 5 }}>{r.path} • {r.topic}</div>
                    <div style={{ fontSize: 13 }}>{r.snippet}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!results.length && (
            <div className="card pad">
              <h3>Knowledge Map</h3>
              <div style={{ marginTop: 15 }}>
                {Object.entries(topics).map(([topic, nodes]) => (
                  <div key={topic} style={{ marginBottom: 20 }}>
                    <h4 style={{ textTransform: "capitalize", borderBottom: "1px solid var(--color-border)", paddingBottom: 5 }}>{topic.replace("_", " ")}</h4>
                    <ul style={{ listStyle: "none", padding: 0, margin: "10px 0 0 0" }}>
                      {nodes.map(n => (
                        <li key={n.id} style={{ padding: "5px 0", cursor: "pointer", color: "var(--color-primary)" }} onClick={() => loadNode(n.id)}>
                          📄 {n.title}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div>
          {activeNode ? (
            <div className="card pad" style={{ position: "sticky", top: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <h3 style={{ margin: "0 0 5px 0" }}>{activeNode.title}</h3>
                <button className="btn icon" onClick={() => setActiveNode(null)}><Icon name="close" /></button>
              </div>
              <div className="kpi-sub" style={{ marginBottom: 15 }}>{activeNode.path} • {activeNode.topic}</div>
              <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 14, overflowY: "auto", maxHeight: "calc(100vh - 200px)" }}>
                {activeNode.content}
              </pre>
            </div>
          ) : (
            <div className="card pad tc" style={{ color: "var(--color-text-sub)" }}>
              Select a document to view its full content.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
