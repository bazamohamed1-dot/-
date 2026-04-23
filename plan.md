1. **Model Updates (`students/models.py`)**:
   - Update `CanteenAttendance`: Make `student` a `ForeignKey` with `null=True, blank=True`. Add `employee` as a `ForeignKey(Employee, null=True, blank=True)`. Ensure `unique_together` allows for either student or employee to be recorded once per day.
   - Update `Employee`: Add `canteen_meals_remaining` (`IntegerField(default=0)`). Add a property `is_supervisor` or similar if needed for statistics mapping, though `rank` might suffice. Ensure Employee has a unique `employee_code` or generate a UUID/Barcode property if one doesn't exist to generate the barcode.
2. **Migrations**:
   - Run `makemigrations` and `migrate`.
3. **Canteen Views (`students/views.py`)**:
   - Update `scan_card` and `manual_attendance`:
     - If the scanned code/ID matches a student, record student attendance.
     - If it matches an employee, record employee attendance and decrement `canteen_meals_remaining` if > 0. If 0, return an error message "لا يوجد رصيد وجبات متبقي" (No meals remaining). Limit to one meal per day per employee.
     - Return the `canteen_meals_remaining` in the success response.
   - Update `canteen_daily_summary` (GET): Calculate student, teacher, worker, admin counts directly from `CanteenAttendance` table for the given date.
   - Update `get_present_list`: Include `level` (المستوى) for students (via `academic_year` or extracting from `class_name`). Return employee details if the attendee is an employee.
4. **Canteen Frontend (`students/templates/students/canteen.html`)**:
   - Update the "Present List" table HTML to include a "المستوى" (Level) column.
   - In JS `updatePresentList()`, populate the level column. Show employees clearly if they appear in the list.
   - In `scan_card` JS handler, display the remaining meals for employees in a toast or alert.
   - Make all fields in the "Stats Modal" readonly except "Guests" (الضيوف) and "Notes/Meal Desc". Remove the inputs for manual tweaking from the UI, or make them `readonly` and rely on auto-calculated values.
5. **HR Frontend (`students/templates/students/hr.html` and views)**:
   - Add a modal or inline UI to set `canteen_meals_remaining` for an employee.
   - Add a button to generate and print a barcode for the employee (using a JS barcode library or backend generation).
6. **Excel Export (`students/views.py`)**:
   - Update `export_canteen_stats`: Instead of downloading a brand-new generated file, maintain a "Cumulative" Excel file on the server. Whenever export is called, open the existing server-side file (if it exists), append the new rows/updates, save it, and then serve that file for download.
7. **Testing**: Run tests and verify manually via frontend.
8. **Submit**.
