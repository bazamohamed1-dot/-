import xlrd

def inspect_xls():
    try:
        wb = xlrd.open_workbook('Eleve.xls')
        sheet = wb.sheet_by_index(0)

        print("Columns:", sheet.row_values(0))
        print("First row:", sheet.row_values(1))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_xls()
