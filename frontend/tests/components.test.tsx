import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RiskBadge } from "../src/components/risk-badge";
import { RiskGauge } from "../src/components/risk-gauge";
import { SeverityPill } from "../src/components/severity-pill";
import { FindingsTab } from "../src/components/findings-tab";
import type { FindingResponse } from "../src/lib/api";

describe("RiskBadge", () => {
  it("renders low band with correct label and score", () => {
    render(<RiskBadge band="low" score={0} showLabelText={true} />);
    expect(screen.getByText("LOW")).toBeInTheDocument();
    expect(screen.getByText("(0)")).toBeInTheDocument();
    expect(screen.getByText("No significant issues found")).toBeInTheDocument();
  });

  it("renders high band with review label", () => {
    render(<RiskBadge band="high" score={85} showLabelText={true} />);
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    expect(screen.getByText("(85)")).toBeInTheDocument();
    expect(screen.getByText("Needs careful review")).toBeInTheDocument();
  });

  it("renders warning asterisk when coverage warning exists", () => {
    render(<RiskBadge band="medium" score={45} hasWarning={true} />);
    expect(screen.getByText("*")).toBeInTheDocument();
  });
});

describe("RiskGauge", () => {
  it("renders gauge with score readout", () => {
    render(<RiskGauge score={68} />);
    expect(screen.getByTestId("risk-gauge")).toBeInTheDocument();
    expect(screen.getByText("68")).toBeInTheDocument();
    expect(screen.getByText("Score")).toBeInTheDocument();
  });
});

describe("SeverityPill", () => {
  it("renders critical severity with label and icon", () => {
    render(<SeverityPill severity="critical" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("renders medium severity with label and icon", () => {
    render(<SeverityPill severity="medium" />);
    expect(screen.getByText("Medium")).toBeInTheDocument();
  });
});

describe("FindingsTab", () => {
  const mockFindings: FindingResponse[] = [
    {
      id: "f1",
      document_id: "doc-1",
      module: "consistency",
      type: "figure_words_mismatch",
      category: "inconsistency",
      title: "Amount in words doesn't match the figure",
      severity: "high",
      page: 1,
      clause_ref: "4.2",
      evidence: "Rs. 50,000 vs Fifty Thousand",
      explanation: "Numerical figure differs from written sum.",
      what_it_means: "Numerical figure differs from written sum.",
      what_to_check: "Verify the intended contract sum.",
      uncertain: false,
      feedback: null,
      created_at: new Date().toISOString(),
    },
    {
      id: "f2",
      document_id: "doc-1",
      module: "forensics",
      type: "incremental_update",
      category: "tampering",
      title: "Post-creation revision or alteration",
      severity: "critical",
      page: 2,
      clause_ref: null,
      evidence: "PDF trailer has 2 revision bodies",
      explanation: "Document was saved incrementally.",
      what_it_means: "Document was saved incrementally.",
      what_to_check: "Inspect raw revision bodies.",
      uncertain: false,
      feedback: null,
      created_at: new Date().toISOString(),
    },
  ];

  it("renders finding cards with severity, titles, and evidence", () => {
    const onSelect = vi.fn();
    const onFeedback = vi.fn();

    render(
      <FindingsTab
        findings={mockFindings}
        selectedFindingId="f1"
        onSelectFinding={onSelect}
        onFeedbackChange={onFeedback}
      />
    );

    expect(screen.getByText("Amount in words doesn't match the figure")).toBeInTheDocument();
    expect(screen.getByText("Post-creation revision or alteration")).toBeInTheDocument();
    expect(screen.getByText("Rs. 50,000 vs Fifty Thousand")).toBeInTheDocument();
  });

  it("filters findings by category chip", () => {
    const onSelect = vi.fn();
    const onFeedback = vi.fn();

    render(
      <FindingsTab
        findings={mockFindings}
        selectedFindingId={null}
        onSelectFinding={onSelect}
        onFeedbackChange={onFeedback}
      />
    );

    // Click 'tampering' filter chip
    const tamperingButton = screen.getByRole("button", { name: "tampering" });
    fireEvent.click(tamperingButton);

    expect(screen.getByText("Post-creation revision or alteration")).toBeInTheDocument();
    expect(screen.queryByText("Amount in words doesn't match the figure")).not.toBeInTheDocument();
  });

  it("triggers feedback action when Confirm button is clicked", () => {
    const onSelect = vi.fn();
    const onFeedback = vi.fn();

    render(
      <FindingsTab
        findings={mockFindings}
        selectedFindingId={null}
        onSelectFinding={onSelect}
        onFeedbackChange={onFeedback}
      />
    );

    const confirmButtons = screen.getAllByRole("button", { name: /confirm issue/i });
    fireEvent.click(confirmButtons[0]);

    expect(onFeedback).toHaveBeenCalled();
  });
});
