
Here’s your post-MVP roadmap for the Gradebook CLI project, based on our earlier planning discussions. I’ve grouped it into thematic categories for clarity:

---

### **Data Model Enhancements**

* **Submission timestamps**: Record when each submission was entered (for late flagging or audit).
* **Soft deletion**: Allow reversible deletion for students, assignments, etc.
* **Submission notes**: Support optional teacher-entered comments per submission.
* **Tagging system**: For categorizing assignments by skill, unit, or standards.
* **Student metadata**: Fields like preferred name, pronouns, student ID, parent contact info.

---

### **Report Improvements**

* **Detailed grade reports**: Per student, include category breakdowns, assignment comments.
* **Export to CSV/JSON**: For all views—submissions, students, grades.
* **Progress over time**: Timeline-based or snapshot-style reports.
* **Incomplete/missing work reports**: Grouped by student or assignment.

---

### **Batch Operations and Automation**

* **CSV import**: Load students, assignments, or submissions in bulk.
* **Bulk update tools**: For mass assignment editing or reweighting categories.
* **Late/exempt detection rules**: Automate based on due dates and timestamps.

---

### **Architecture and Extensibility**

* **Plugin system or hooks**: Allow limited user extensions without modifying core.
* **CLI refactor**: Abstract menu structure to reduce boilerplate and increase flexibility.
* **Error logging**: Optional debug mode or structured error output.

---

### **Interface Expansion**

* **Web interface**: Read-only views or interactive dashboard (possibly Flask-based).
* **RESTful API**: To support future GUI, mobile, or integrations.
* **Neovim/terminal plugin**: Custom views for use during grading sessions.

---

### **Access and Permissions**

* **Multi-user support**: Roles for teachers, assistants, observers.
* **Password protection**: Encrypt or protect data file with optional password.

---

### **Pedagogical Features**

* **Student learning profiles**: Track mastery or goals by topic or standard.
* **Feedback templates**: Reusable comment banks for common feedback.

---

