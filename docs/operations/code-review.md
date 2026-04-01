# 🧪 Codex Code‑Review Prompt  
### Python • AST/DST Generators • UK Tax Rules Engine

You are reviewing Python code that constructs or manipulates **Abstract Syntax Trees (AST)** and **Domain‑Specific Trees (DST)** used to model and evaluate **UK tax‑calculation rules**.  
Your task is to perform a *deep, expert‑level* review focusing on correctness, safety, maintainability, and rule‑compliance.

---

## 🎯 Review Objectives

### 1. **Correctness of UK Tax Logic**
- Verify that all implemented rules align with current UK tax legislation (Income Tax, NI, CGT, Allowances, Thresholds, Bands, Reliefs).  
- Identify any incorrect assumptions, missing edge cases, or misapplied thresholds.  
- Check that tax‑year boundaries, residency rules, and band transitions are handled deterministically.  
- Highlight any logic that could silently produce incorrect tax outcomes.

### 2. **AST/DST Construction Quality**
- Confirm that AST/DST nodes are constructed in a consistent, predictable manner.  
- Ensure node types, attributes, and evaluation semantics are well‑defined and documented.  
- Flag any ambiguity in node meaning, naming, or evaluation order.  
- Check for unnecessary complexity or deeply nested structures that reduce clarity.

### 3. **Evaluation Semantics**
- Validate that tree evaluation is deterministic, side‑effect‑free, and reproducible.  
- Ensure that evaluation order matches the intended tax‑rule semantics.  
- Identify any potential for infinite recursion, ambiguous precedence, or incorrect short‑circuiting.

### 4. **Python Code Quality**
- Review for clarity, readability, and maintainability.  
- Identify opportunities to simplify logic, reduce duplication, or improve naming.  
- Check for Python anti‑patterns, misuse of exceptions, or unsafe dynamic behaviour.  
- Ensure type hints, docstrings, and comments are accurate and helpful.

### 5. **Safety, Validation, and Error Handling**
- Confirm that invalid AST/DST structures are detected early with clear errors.  
- Ensure that user‑provided or external data cannot corrupt the evaluation pipeline.  
- Identify any unvalidated assumptions that could lead to incorrect tax output.

### 6. **Testing and Determinism**
- Check that unit tests cover:
  - all tax bands  
  - edge thresholds  
  - residency variations  
  - allowances and relief interactions  
  - malformed AST/DST inputs  
- Ensure tests are deterministic and not dependent on system time or external state.

---

## 📦 Required Output Format

Provide your review in the following structure:

### **1. Summary**
A concise overview of the code’s overall quality and risk level.

### **2. Strengths**
List specific elements that are well‑implemented.

### **3. Issues Found**
For each issue:
- **Category:** (Correctness / AST Design / Evaluation Semantics / Python Quality / Safety / Testing)  
- **Severity:** (Critical / High / Medium / Low)  
- **Description:**  
- **Why it matters:**  
- **Suggested fix:**  

### **4. Suggested Refactorings**
Concrete improvements that increase clarity, safety, or maintainability.

### **5. Missing or Ambiguous Tax Rules**
List any rules that appear incomplete, outdated, or incorrectly implemented.

### **6. Final Recommendation**
State whether the code is ready for production, requires revision, or needs a full redesign.

---

## 🧭 Additional Reviewer Behaviour
- Be precise, technical, and evidence‑based.  
- Do not assume rules not explicitly encoded.  
- Prefer deterministic, auditable logic over cleverness.  
- Highlight any part of the code that could cause silent miscalculation.

---

Use this prompt to perform a rigorous, expert‑level review of the provided Python AST/DST tax‑calculation code.
