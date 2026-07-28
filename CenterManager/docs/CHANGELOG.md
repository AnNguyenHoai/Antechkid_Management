# CHANGELOG – Sprint 0.5

## Added
- `ui/students/navigation_panel.py`: Search box + student list (Code + Name only).
- `ui/students/student_workspace.py`: Main workspace with Header, Basic Info, Learning, Notes sections.
- Main window now uses two-column layout (Navigation | Workspace) with splitter.

## Changed
- `ui/main_window.py`: Replaced StudentListPage with NavigationPanel and StudentWorkspace.
- `ui/students/student_form_dialog.py`: Added edit mode – accepts `student_id` to load existing student data.
- `ui/students/__init__.py`: Exported new components.

## Removed / Deprecated
- `StudentProfileDialog` is no longer used for viewing – replaced by Workspace.
- `StudentListPage` is no longer used – replaced by NavigationPanel.

## Database
- No schema changes.

## Known Issues
- Export PDF button is disabled (not implemented yet).
- Parent, Assessment, Products, Timeline, Attachments sections are empty placeholders (not in scope).
- No dark mode or themes.

# CHANGELOG – Sprint 0.5 (sửa lỗi)

## Fixed
- Lỗi `parent().refresh_navigation` trong StudentWorkspace – thay bằng Signal `student_updated`.
- Kết nối signal để refresh navigation sau khi edit thành công.
- Thêm nút "+ Add Student" trên toolbar để tạo học sinh mới.

## Added
- Nút Add Student trên toolbar.
- Signal `student_updated` trong StudentWorkspace.

## Changed
- `MainWindow` kết nối với signal để refresh navigation.

# CHANGELOG – Sprint 0.5

## Changed
- Tối ưu layout StudentWorkspace: thu nhỏ header, avatar, padding, spacing để giảm khoảng trống.
- Điều chỉnh kích thước font và margin các section.

## Fixed
- Lỗi gọi parent().refresh_navigation – thay bằng signal student_updated.
- Đồng bộ refresh navigation sau edit/add.

## Added
- Nút "+ Add Student" trên toolbar.

# CHANGELOG – Sprint 1.0

## Added
- Full 8 sections in Workspace: Basic, Parents, Learning, Assessment, Products, Attachments, Timeline, Notes.
- Empty state for each section (except Basic/Learning/Notes which have data).
- Notes displayed as Card.
- QListWidget for student list replacing QTableWidget.
- Icon and message for empty Workspace.
- Tooltip for disabled Export PDF button.

## Changed
- Student List now shows only Code and Name without headers/grid.
- Basic Information layout changed to vertical (Label above Value) instead of form.
- Header height reduced to 70px, toolbar to 40px.
- Spacing standardized: section margin 24, padding 16, label-value gap 8.
- Scroll to top when switching students.
- Navigation panel uses custom QListWidget items with hover/selection styles.

## Removed
- Table header in student list.
- Horizontal form layout for Basic Information.

## Fixed
- Parent call in workspace – replaced with signal.
- Empty state spacing reduced.

## Known Issues
- Export PDF disabled.
- Parent, Assessment, Products, Attachments, Timeline sections have no CRUD yet (empty only).

# CHANGELOG – Sprint 1.1

## Added
- Parent management (full CRUD): model, repository, service, UI.
- Migration to add `occupation` column to parents table.
- ParentCard widget and ParentDialog.
- Parent Section in Workspace with dynamic cards and Add/Edit/Delete buttons.
- Cascade delete relationship from Student to Parent (hard delete).

## Changed
- Updated Student model: added cascade to parents relationship.
- Updated MainWindow to accept ParentService.
- Updated Workspace to use ParentService.

## Fixed
- Minor layout issues.

## Known Issues
- Parent deletion confirmation works.
- Primary contact flag is stored but not yet used for ordering.

# CHANGELOG – Sprint 1.2

## Added
- Timeline Engine: full CRUD of timeline events.
- TimelineEvent model with metadata_json, created_by.
- TimelineRepository and TimelineService.
- Integration with StudentService: logs StudentCreated, StudentUpdated events.
- Integration with ParentService: logs ParentAdded, ParentUpdated, ParentDeleted events.
- TimelineWidget and TimelineCard UI components.
- Timeline Section in Student Workspace (read-only, newest first).
- Empty state for timeline.
- Migration to create timeline_events table and indexes.

## Changed
- StudentService and ParentService now accept TimelineService as dependency.
- MainWindow and Workspace now accept TimelineService.

## Known Issues
- None.

# CHANGELOG – Sprint 1.4

## Added
- Student Summary Layer (cards below header).
- SummaryService and SummaryDTO to aggregate data from multiple services.
- SummaryWidget and SummaryCard UI components.
- Display: Current Level, Latest Assessment, Primary Contact, Last Activity, Learning Status, Age, Assessment Count, Timeline Count, Parent Count.
- Auto-refresh summary after changes (parent, assessment, timeline).
- Empty state handling for missing data.

## Changed
- StudentWorkspace: added SummaryWidget above Basic Information.
- MainWindow and app.py: injected SummaryService.

## Fixed
- Timeline refresh after assessment/parent changes.

# CHANGELOG – Sprint 1.4

## Added
- Student Summary Layer (SummaryWidget) displaying 9 key metrics.
- StudentSummaryService and StudentSummaryDTO.
- Summary cards: Current Level, Latest Assessment, Primary Contact, Last Activity, Status, Age, Assessment Count, Timeline Count, Parent Count.
- Integration with existing services (Student, Parent, Assessment, Timeline).
- Empty state handling for missing data.

## Changed
- StudentWorkspace now includes Summary section above Basic Information.
- Updated MainWindow and app.py to inject SummaryService.

## Fixed
- QSizePolicy.Minimum attribute error in SummaryCard.
- Timeline refresh after parent/assessment changes.

## Known Issues
- None.