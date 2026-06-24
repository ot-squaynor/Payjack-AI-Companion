"use client";

import { useState } from "react";
import type { ChatResponse } from "@/lib/types";

type ResponseCardProps = {
  response: ChatResponse;
  showDebug?: boolean;
};

export function ResponseCard({ response, showDebug = false }: ResponseCardProps) {
  const [citationsOpen, setCitationsOpen] = useState(false);

  return (
    <div className="response-card">
      <div className="response-answer">
        <p>{response.answer}</p>
      </div>

      {response.refusal ? (
        <div className="response-section">
          <strong>Refusal</strong>
          <p>
            {response.refusal.category}: {response.refusal.message}
          </p>
        </div>
      ) : null}

      {showDebug && response.tool_traces.length > 0 ? (
        <div className="response-section">
          <strong>Tool Traces</strong>
          {response.tool_traces.map((trace) => (
            <div key={`${response.request_id}-${trace.name}`} className="trace-card">
              <p className="trace-title">{trace.name}</p>
              <pre>{JSON.stringify(trace.result, null, 2)}</pre>
            </div>
          ))}
        </div>
      ) : null}

      {response.citations.length > 0 ? (
        <div className="response-section">
          <button
            type="button"
            className="citations-toggle"
            onClick={() => setCitationsOpen((open) => !open)}
            aria-expanded={citationsOpen}
          >
            <span className="citations-toggle-icon" aria-hidden="true">
              {citationsOpen ? "▾" : "▸"}
            </span>
            {citationsOpen
              ? "Hide citations"
              : `Show ${response.citations.length} citation${response.citations.length !== 1 ? "s" : ""}`}
          </button>
          {citationsOpen && (
            <div>
              {response.citations.map((citation) => (
                <div key={`${citation.doc_id}-${citation.score}`} className="citation-card">
                  <p className="trace-title">{citation.title}</p>
                  <p>{citation.snippet}</p>
                  <span className="citation-score">
                    Relevance: {Math.round(citation.score * 100)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}

      {showDebug && Object.keys(response.debug).length > 0 ? (
        <div className="response-section">
          <strong>Debug</strong>
          <pre>{JSON.stringify(response.debug, null, 2)}</pre>
        </div>
      ) : null}
    </div>
  );
}
