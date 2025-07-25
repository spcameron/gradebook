- [ ] CLI menu edit methods mix data changes and print statements
    - Extract update_* wrappers for clean state changes, return bool
    - Update edit_* methods (and similar manipulators) to print messaging based on bool values

- [ ] Refactor classes to access property getters rather than private attributes directly

# Data Manipulation Method Conventions (MVP Phase)

This document defines the behavior of Gradebook's data manipulation methods (e.g. `mark_student_absent`, `remove_category`, `add_class_date`, etc.) during the MVP development phase.

## Return Values

All public data manipulation methods in `Gradebook` follow this return contract:

| Return Value | Meaning                                | Interface Response                     |
|--------------|----------------------------------------|----------------------------------------|
| `True`       | A change was successfully made         | Display success confirmation message   |
| `False`      | No change occurred (e.g. redundant op) | Suppress message or show soft warning  |
| `raise`      | Invalid input or precondition failure  | Display error message with exception   |

Example:

```python
success = gradebook.mark_student_absent(student, class_date)

if success:
    print("Student marked absent.")
else:
    print("Student was already marked absent.")
```

## Exceptions

ValueError is raised in response to:
- Invalid references (e.g. student not in course, date not in schedule)
- Attempts to mutate non-editable records
- Other business logic violations

Do not catch these inside the Gradebook. The interface layer (CLI/GUI/API) is responsible for handling them.

# Future Plans

## Refactoring Plan: DataChangeResult Pattern

After MVP stabilization, we will replace the current `bool`-based return convention for data manipulation methods with a structured response object.

## Motivation

- Unify return behavior for interface layers (CLI, GUI, API)
- Improve transparency of no-ops and failures
- Decouple data mutation logic from presentation logic

## Proposed Class

```python
class DataChangeResult:
    def __init__(
        self,
        success: bool,
        message: str = "",
        error: Optional[Exception] = None,
        metadata: Optional[dict[str, Any]] = None
    ):
        self.success = success
        self.message = message
        self.error = error
        self.metadata = metadata or {}
```
## Migration Plan

1. Update all methods returning `bool` to return `DataChangeResult`
2. Replace `return True` -> `return DataChangeResults(success=True)`
3. Replace `return False` -> `return DataChangeResults(success=False, message="...")`
4. Refactor CLI layer to unpack and display `.message` or handle `.error`
5. Introduce helper utilities to bridge bool-to-response behavior temporarily, if needed

## Benefits

- Clear success/failure status
- Optional messages or error payloads
- Compatible with GUI/API response models
- Minimized tight coupling between data and interface logic

