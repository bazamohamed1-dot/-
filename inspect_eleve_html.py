from bs4 import BeautifulSoup

def inspect_html():
    with open('Eleve.xls', 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    rows = soup.find_all('tr')

    if len(rows) > 0:
        # Assuming first row is header if not wrapped in <thead>
        # But looking at output, it seems to be just data rows?
        # Let's print first 2 rows
        for i in range(min(5, len(rows))):
             cols = [c.get_text(strip=True) for c in rows[i].find_all('td')]
             print(f"Row {i}: {cols}")

if __name__ == "__main__":
    inspect_html()
