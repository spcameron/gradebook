Project File Structure: Gradebook MVP

```
gradebook/
├── main.py                  # Entry point / temporary driver
├── models/                  # Core class definitions
│   ├── __init__.py
│   ├── course.py
│   ├── student.py
│   ├── gradebook.py
│   ├── category.py
│   ├── assignment.py
│   └── submission.py
├── storage/                 # Persistence logic
│   ├── __init__.py
│   ├── json_store.py        # Handles JSON read/write
│   └── schema.py            # Defines structure expectations (if needed)
├── utils/                   # Supporting tools
│   └── id_generator.py      # Unique ID or timestamp helpers
└── tests/                   # Dedicated testing with pytest or unittest
    ├── __init__.py
    ├── test_student.py
    ├── test_assignment.py
    ├── test_submission.py
    └── ...
```

Notes:
- Models are intentionally decoupled; `Submission` holds references via IDs to avoid tight coupling.
- `main.py` can serve as a scratchpad or lightweight CLI while developing.
- `tests/` should mirror the structure of `models/` to keep things organized.
- Persistence and resolution of inter-entity relationships are handled in the `storage/` layer, not embedded in models.
- Use `pytest` for lightweight test writing, unless a stronger structure (e.g. `unittest`) is desired.

This layout supports clean partitioning from the start while remaining easy to evolve as the project grows.

