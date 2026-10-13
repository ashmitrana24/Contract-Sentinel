import { describe, it, expect } from "vitest";

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB

function validateUploadFile(file: { name: string; type: string; size: number }): {
  valid: boolean;
  error?: string;
} {
  const isPdf =
    file.name.toLowerCase().endsWith(".pdf") || file.type === "application/pdf";
  if (!isPdf) {
    return { valid: false, error: "Only PDF documents are supported (.pdf)." };
  }

  if (file.size > MAX_FILE_SIZE) {
    return {
      valid: false,
      error: `File exceeds maximum size limit of 25 MB (${(file.size / (1024 * 1024)).toFixed(1)} MB).`,
    };
  }

  return { valid: true };
}

describe("Upload validation logic", () => {
  it("accepts valid PDF within 25 MB limit", () => {
    const res = validateUploadFile({
      name: "contract.pdf",
      type: "application/pdf",
      size: 5 * 1024 * 1024,
    });
    expect(res.valid).toBe(true);
    expect(res.error).toBeUndefined();
  });

  it("rejects non-PDF documents", () => {
    const res = validateUploadFile({
      name: "contract.docx",
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      size: 2 * 1024 * 1024,
    });
    expect(res.valid).toBe(false);
    expect(res.error).toContain("Only PDF documents are supported");
  });

  it("rejects PDF exceeding 25 MB", () => {
    const res = validateUploadFile({
      name: "heavy_scanned_contract.pdf",
      type: "application/pdf",
      size: 26 * 1024 * 1024,
    });
    expect(res.valid).toBe(false);
    expect(res.error).toContain("exceeds maximum size limit");
  });
});
