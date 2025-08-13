# Gradebook CLI Refactor Checklist

- grep for 'return None' and change to 'return' for bail-outs
<!-- - change "..." to "->" -->

## ⬆️ Core Infrastructure

<!-- - [ ] Move `utils.py` to `core/utils.py` and update all import paths -->
<!-- - [ ] Add `core/response.py` with `Response` and `ErrorCode` classes -->
<!-- - [ ] Rename Response.message → Response.detail and add status_code -->
<!-- - [ ] Update all manipulator methods to return `Response` objects -->
<!-- - [ ] Ensure all raises from model methods are caught and wrapped by Gradebook methods -->

## 🧹 Standardization & Conventions

<!-- - [ ] Use type annotations (not Optional[]) consistently -->
<!-- - [ ] Use `from __future__ import annotations` across refactored files -->
<!-- - [ ] Adopt `ErrorCode` enums where appropriate for `response.error` -->
<!-- - [ ] Use string keys like `"record"`, `"student"`, `"assignment"` consistently in `response.data` -->
<!-- - [ ] Document `response.data` return shape explicitly in each method's docstring -->
<!-- - [ ] Adopt consistent backtick usage for code-like values in docstrings (see below) -->

## 🧪 CLI Updates

<!-- - [ ] Replace all calls to Gradebook mutator methods to expect `Response` objects -->
<!-- - [ ] Update CLI menus to branch on `response.success`, `response.detail`, and optionally print `.error` -->
<!-- - [ ] Migrate any direct model writes (e.g. `student.name = x`) to new `gradebook.update_*` methods -->
<!-- - [ ] Ensure any CLI-side lookups that may fail now check `response.success` and handle fallback behavior -->

## 📜 Docstring Conventions

<!-- - [ ] Add/update docstrings to all refactored Gradebook methods -->
<!-- - [ ] Ensure each docstring includes: -->
<!--   - Args section with types -->
<!--   - Returns section outlining `Response` contract -->
<!--   - Notes section if behavior needs clarification (e.g. empty return, key presence) -->

## 🧪 Testing & Smoke Checks

- [ ] Run full manual flow through each menu after migration
- [ ] Confirm that all CLI interfaces still display appropriate prompts and errors
- [ ] Look for any uncaught exceptions or missing response handling

## 💡 Optional (Post-MVP)

- [ ] Introduce centralized `response_utils.py` for standard error/message helpers
- [ ] Prep Response class for JSON serialization if targeting REST API
- [ ] Standarize Reponse Status Codes
    - 200 OK
    - 204 OK, no content
    - 400 bad request
    - 404 not found
    - 500 internal error



---

### ✅ Backtick Usage Summary

| Context                                | Use Backticks?  | Example                                       | Notes                                           |
| -------------------------------------- | --------------  | --------------------------------------------- | ----------------------------------------------- |
| **Type hints in `Args:` / `Returns:`** | ❌ No           | `assignment (Assignment): ...`                | Types are already in the signature format.      |
| **Inline prose (class/type names)**    | ✅ Yes          | “Returns a `Student` object.”                 | Use when referring to types in narrative text.  |
| **Function or method names**           | ✅ Yes          | “See also: `find_student_by_uuid()`.”         | Helps distinguish symbols from prose.           |
| **Field names / dict keys**            | ✅ Yes          | “Found in `response.data["record"]`.”         | Clarifies structure or syntax in narrative.     |
| **Boolean literals** (`True`, `False`) | ❌ No           | “Returns True if...”                          | Considered part of natural language here.       |
| **`None` as a return value**           | ❌ No           | “Returns None if...”                          | Not code context—no need to highlight.          |
| **HTTP status codes**                  | ❌ No           | “Returns 404 if not found.”                   | These are standard numeric values, not symbols. |
| **Literal values / examples in prose** | ✅ Optional     | “Call with `verbose=True` to enable logging.” | Use backticks if showing exact code usage.      |

---

